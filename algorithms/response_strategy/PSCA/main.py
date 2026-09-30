"""Joint subspace and correlation alignment for dynamic optimization.

This module reproduces the response method proposed in:
G. Li, Y. Liu, and X. Deng, "A prediction method for dynamic
multiobjective optimization based on joint subspace and correlation
alignment," Complex & Intelligent Systems, vol. 10, pp. 4421-4444,
2024. https://doi.org/10.1007/s40747-024-01369-4

The paper calls the method PSCA (the article contains a few PCSA
typographical variants). FlexDMO applies its existing
constraint-domination selection whenever the original method requests
nondominated sorting and crowding selection.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import crowd_selection, quick_non_dominate_sort


def orthogonal_basis(values):
    """Return the complete PCA basis used by equations (8) and (12)."""
    matrix = np.atleast_2d(np.asarray(values, dtype=float))
    dimension = matrix.shape[1]
    if len(matrix) < 2 or np.allclose(matrix, matrix[0]):
        return np.eye(dimension)
    centered = matrix - np.mean(matrix, axis=0)
    _, _, right_vectors = np.linalg.svd(
        centered,
        full_matrices=True,
    )
    return right_vectors.T


def symmetric_matrix_power(matrix, exponent, regularization=1e-6):
    """Compute a stable symmetric matrix power for CORAL."""
    values = np.asarray(matrix, dtype=float)
    values = 0.5 * (values + values.T)
    eigenvalues, eigenvectors = np.linalg.eigh(values)
    eigenvalues = np.maximum(eigenvalues, float(regularization))
    return (eigenvectors * (eigenvalues**exponent)) @ eigenvectors.T


def correlation_alignment(
    source,
    target,
    regularization=1e-6,
):
    """Equation (17): Q_source^-0.5 Q_target^0.5."""
    source = np.atleast_2d(np.asarray(source, dtype=float))
    target = np.atleast_2d(np.asarray(target, dtype=float))
    dimension = source.shape[1]
    if target.shape[1] != dimension:
        raise ValueError("Source and target dimensions must match.")
    if len(source) < 2 or len(target) < 2:
        return np.eye(dimension)
    source_covariance = np.atleast_2d(
        np.cov(source, rowvar=False),
    )
    target_covariance = np.atleast_2d(
        np.cov(target, rowvar=False),
    )
    if source_covariance.shape != (dimension, dimension):
        return np.eye(dimension)
    return (
        symmetric_matrix_power(
            source_covariance,
            -0.5,
            regularization,
        )
        @ symmetric_matrix_power(
            target_covariance,
            0.5,
            regularization,
        )
    )


def _resample_rows(values, size):
    values = np.atleast_2d(np.asarray(values, dtype=float))
    if not len(values):
        raise ValueError("Cannot resample an empty solution set.")
    positions = np.linspace(0, len(values) - 1, int(size))
    return values[np.rint(positions).astype(int)].copy()


class PSCA(ResponseStrategy):
    """Predict translation, rotation, and distortion of the Pareto set."""

    def __init__(
        self,
        cluster_num=3,
        covariance_regularization=1e-6,
    ):
        super().__init__()
        self.cluster_num = int(cluster_num)
        self.covariance_regularization = float(
            covariance_regularization,
        )
        if self.cluster_num <= 0:
            raise ValueError("cluster_num must be positive.")
        if self.covariance_regularization <= 0:
            raise ValueError(
                "covariance_regularization must be positive."
            )
        self._history = []
        self._response_count = 0

    @staticmethod
    def _pareto_decisions(population, target_size):
        archived = population.copy()
        quick_non_dominate_sort(archived)
        decisions = np.asarray(
            [
                individual.X
                for individual in archived.individuals
                if individual.rank == 1
            ],
            dtype=float,
        )
        if not len(decisions):
            decisions = archived.get_decision_matrix()
        order = np.lexsort(tuple(
            decisions[:, column]
            for column in reversed(range(decisions.shape[1]))
        ))
        return _resample_rows(decisions[order], target_size)

    def _fallback(self, current, problem, rng):
        random_decisions = rng.uniform(
            problem.xl,
            problem.xu,
            size=(problem.solution_num, problem.decision_num),
        )
        candidates = Population(
            X=np.vstack((current, random_decisions)),
            xl=problem.xl,
            xu=problem.xu,
        )
        candidates.update_objective_constrain(problem)
        return crowd_selection(candidates, problem.solution_num)

    def _subspace_prediction(self, previous, current, rng):
        cluster_count = min(
            self.cluster_num,
            len(previous),
            len(current),
        )
        if cluster_count <= 1:
            previous_labels = np.zeros(len(previous), dtype=int)
            current_labels = np.zeros(len(current), dtype=int)
        else:
            seed = int(rng.integers(0, np.iinfo(np.int32).max))
            previous_labels = KMeans(
                n_clusters=cluster_count,
                n_init=10,
                random_state=seed,
            ).fit_predict(previous)
            current_labels = KMeans(
                n_clusters=cluster_count,
                n_init=10,
                random_state=seed + 1,
            ).fit_predict(current)

        previous_centers = np.vstack([
            np.mean(previous[previous_labels == label], axis=0)
            for label in range(cluster_count)
        ])
        generated = []
        for label in range(cluster_count):
            current_cluster = current[current_labels == label]
            current_center = np.mean(current_cluster, axis=0)
            distances = np.linalg.norm(
                previous_centers - current_center,
                axis=1,
            )
            paired_label = int(np.argmin(distances))
            previous_cluster = previous[
                previous_labels == paired_label
            ]
            previous_center = previous_centers[paired_label]

            previous_basis = orthogonal_basis(previous_cluster)
            current_basis = orthogonal_basis(current_cluster)
            rotation = previous_basis.T @ current_basis
            translation = current_center - previous_center
            generated.append(
                (current_cluster - current_center)
                @ rotation
                + current_center
                + translation
            )
        return np.vstack(generated)

    def response(self, population, problem, algorithm):
        seed = int(getattr(algorithm, "seed", 0))
        rng = np.random.default_rng(seed + self._response_count)
        self._response_count += 1

        current = self._pareto_decisions(
            population,
            problem.solution_num,
        )
        self._history.append(current)
        self._history = self._history[-2:]
        if len(self._history) < 2:
            result = self._fallback(current, problem, rng)
            quick_non_dominate_sort(result)
            return result

        previous, current = self._history
        quasi_first = np.clip(
            self._subspace_prediction(previous, current, rng),
            problem.xl,
            problem.xu,
        )
        first_population = Population(
            X=quasi_first,
            xl=problem.xl,
            xu=problem.xu,
        )
        first_population.update_objective_constrain(problem)
        elite_size = max(2, problem.solution_num // 2)
        elite = crowd_selection(first_population, elite_size)
        elite_decisions = elite.get_decision_matrix()

        alignment = correlation_alignment(
            current - np.mean(current, axis=0),
            elite_decisions - np.mean(elite_decisions, axis=0),
            self.covariance_regularization,
        )
        quasi_second = (
            (current - np.mean(current, axis=0)) @ alignment
            + np.mean(elite_decisions, axis=0)
        )
        quasi_second = np.clip(
            quasi_second,
            problem.xl,
            problem.xu,
        )

        candidates = Population(
            X=np.vstack((quasi_first, quasi_second)),
            xl=problem.xl,
            xu=problem.xu,
        )
        candidates.update_objective_constrain(problem)
        result = crowd_selection(candidates, problem.solution_num)
        quick_non_dominate_sort(result)
        return result
