"""Linear-regression prediction response for dynamic optimization.

Reproduction of the population response in:
J. Ma, Y. Sang, Y. Xu, and B. Wang, "A Linear Regression
Prediction-Based Dynamic Multi-Objective Evolutionary Algorithm with
Correlations of Pareto Front Points," Algorithms, vol. 18, no. 6,
article 372, 2025. https://doi.org/10.3390/a18060372

The implementation follows the paper's twelve-point representation
(eleven percentiles plus the center), regularized multivariate linear
prediction, Gaussian sampling, D-NSGA-II-B mutation, and random
replacement. It remains optimizer-independent so it can be combined
with every static MOEA in FlexDMO.
"""

from __future__ import annotations

import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import quick_non_dominate_sort


def extract_key_points(population, key_points=12):
    """Extract eleven objective-ordered percentiles and the PS center."""
    if key_points < 2:
        raise ValueError("key_points must be at least 2.")
    archived = population.copy()
    quick_non_dominate_sort(archived)
    pareto = [
        individual
        for individual in archived.individuals
        if individual.rank == 1
    ]
    if not pareto:
        pareto = archived.individuals
    objectives = np.asarray(
        [individual.F for individual in pareto],
        dtype=float,
    )
    decisions = np.asarray(
        [individual.X for individual in pareto],
        dtype=float,
    )
    order = np.lexsort(tuple(
        objectives[:, column]
        for column in reversed(range(objectives.shape[1]))
    ))
    ordered = decisions[order]
    percentile_count = key_points - 1
    positions = np.linspace(0, len(ordered) - 1, percentile_count)
    percentiles = ordered[np.rint(positions).astype(int)]
    return np.vstack((percentiles, np.mean(decisions, axis=0)))


def fit_ridge_transition(history, regularization=1e-3):
    """Fit X(t) -> X(t+1) using all key points jointly."""
    snapshots = np.asarray(history, dtype=float)
    if snapshots.ndim != 3 or len(snapshots) < 2:
        raise ValueError("At least two key-point snapshots are required.")
    if regularization <= 0:
        raise ValueError("regularization must be positive.")
    inputs = snapshots[:-1].reshape(len(snapshots) - 1, -1)
    targets = snapshots[1:].reshape(len(snapshots) - 1, -1)
    design = np.column_stack((inputs, np.ones(len(inputs))))
    penalty = np.eye(design.shape[1]) * float(regularization)
    penalty[-1, -1] = 0.0
    coefficients = np.linalg.solve(
        design.T @ design + penalty,
        design.T @ targets,
    )
    return coefficients


def predict_key_points(history, regularization=1e-3):
    snapshots = np.asarray(history, dtype=float)
    if len(snapshots) == 1:
        return snapshots[-1].copy()
    if len(snapshots) == 2:
        return snapshots[-1] + snapshots[-1] - snapshots[-2]
    coefficients = fit_ridge_transition(
        snapshots,
        regularization,
    )
    current = snapshots[-1].reshape(-1)
    predicted = np.append(current, 1.0) @ coefficients
    return predicted.reshape(snapshots.shape[1:])


def polynomial_mutation(
    decisions,
    lower,
    upper,
    rng,
    distribution_index=20.0,
):
    """D-NSGA-II-B polynomial mutation with one forced change per row."""
    decisions = np.asarray(decisions, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    probability = 1.0 / max(decisions.shape[1], 1)
    mask = rng.random(decisions.shape) < probability
    forced = rng.integers(0, decisions.shape[1], size=len(decisions))
    mask[np.arange(len(decisions)), forced] = True
    random_values = rng.random(decisions.shape)
    delta = np.where(
        random_values < 0.5,
        (2.0 * random_values) ** (1.0 / (distribution_index + 1.0))
        - 1.0,
        1.0
        - (2.0 * (1.0 - random_values))
        ** (1.0 / (distribution_index + 1.0)),
    )
    mutated = decisions + delta * (upper - lower)
    return np.where(
        mask,
        np.clip(mutated, lower, upper),
        decisions,
    )


class LRDMOEA(ResponseStrategy):
    """Predict correlated key points and randomly replace the population."""

    def __init__(
        self,
        key_points=12,
        regularization=1e-3,
        predicted_fraction=0.5,
        mutation_fraction=0.2,
        noise_scale=0.05,
        history_length=20,
    ):
        super().__init__()
        self.key_points = int(key_points)
        self.regularization = float(regularization)
        self.predicted_fraction = float(predicted_fraction)
        self.mutation_fraction = float(mutation_fraction)
        self.noise_scale = float(noise_scale)
        self.history_length = int(history_length)
        if self.key_points < 2:
            raise ValueError("key_points must be at least 2.")
        if self.regularization <= 0:
            raise ValueError("regularization must be positive.")
        if not 0 < self.predicted_fraction <= 1:
            raise ValueError(
                "predicted_fraction must be in (0, 1]."
            )
        if not 0 <= self.mutation_fraction <= 1:
            raise ValueError(
                "mutation_fraction must be in [0, 1]."
            )
        if self.predicted_fraction + self.mutation_fraction > 1:
            raise ValueError(
                "predicted_fraction + mutation_fraction "
                "must not exceed 1."
            )
        if self.noise_scale < 0:
            raise ValueError("noise_scale must be non-negative.")
        if self.history_length < 2:
            raise ValueError("history_length must be at least 2.")
        self._history = []
        self._response_count = 0

    def _predicted_population(self, predicted, count, problem, rng):
        key_indices = np.arange(count) % len(predicted)
        scale = self.noise_scale * (
            np.asarray(problem.xu) - np.asarray(problem.xl)
        )
        decisions = (
            predicted[key_indices]
            + rng.normal(0.0, scale, size=(count, problem.decision_num))
        )
        return np.clip(decisions, problem.xl, problem.xu)

    def response(self, population, problem, algorithm):
        if population.n == 0:
            result = Population(
                xl=problem.xl,
                xu=problem.xu,
                n_init=problem.solution_num,
            )
            result.update_objective_constrain(problem)
            quick_non_dominate_sort(result)
            return result

        seed = int(getattr(algorithm, "seed", 0))
        rng = np.random.default_rng(seed + self._response_count)
        self._response_count += 1

        key_snapshot = extract_key_points(
            population,
            self.key_points,
        )
        self._history.append(key_snapshot)
        self._history = self._history[-self.history_length:]
        predicted = np.clip(
            predict_key_points(self._history, self.regularization),
            problem.xl,
            problem.xu,
        )

        target_size = problem.solution_num
        base = population.get_decision_matrix()
        base_indices = rng.choice(
            len(base),
            size=target_size,
            replace=len(base) < target_size,
        )
        decisions = base[base_indices].copy()

        predicted_count = max(
            1,
            int(round(target_size * self.predicted_fraction)),
        )
        mutation_count = int(
            round(target_size * self.mutation_fraction)
        )
        if predicted_count + mutation_count > target_size:
            mutation_count = target_size - predicted_count

        predicted_decisions = self._predicted_population(
            predicted,
            predicted_count,
            problem,
            rng,
        )
        parent_indices = rng.choice(
            len(base),
            size=mutation_count,
            replace=len(base) < mutation_count,
        )
        mutated_decisions = polynomial_mutation(
            base[parent_indices],
            problem.xl,
            problem.xu,
            rng,
        )
        replacements = np.vstack(
            (predicted_decisions, mutated_decisions),
        )
        replacement_slots = rng.choice(
            target_size,
            size=len(replacements),
            replace=False,
        )
        decisions[replacement_slots] = replacements

        result = Population(
            X=decisions,
            xl=problem.xl,
            xu=problem.xu,
        )
        result.update_objective_constrain(problem)
        quick_non_dominate_sort(result)
        return result
