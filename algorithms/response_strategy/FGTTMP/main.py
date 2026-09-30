"""FGTTMP dynamic response strategy.

Reproduction of the response framework proposed in:
Y. Wang, K. Li, G. Wang, D. Gong, and K. Li, "Solving Dynamic
Multiobjective Optimization Problems via Feedback-Guided Transfer and
Trend Manifold Prediction," IEEE Transactions on Systems, Man, and
Cybernetics: Systems, vol. 54, no. 12, pp. 7218-7231, 2024.

The paper leaves the scalar ``fitness`` in equations (6)-(7) dependent on
the embedded static optimizer. FlexDMO uses a scale-independent
rank-plus-normalized-objective fitness so the response can be paired with
any of its static MOEAs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.svm import SVC

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import crowd_selection, quick_non_dominate_sort


_EPSILON = 1e-12


@dataclass
class _Snapshot:
    decisions: np.ndarray
    objectives: np.ndarray
    violation: np.ndarray
    good: np.ndarray
    fitness: np.ndarray


def non_dominated_mask(objectives):
    """Return the minimization non-dominated mask for a finite matrix."""
    values = np.atleast_2d(np.asarray(objectives, dtype=float))
    if not len(values):
        return np.zeros(0, dtype=bool)
    finite = np.all(np.isfinite(values), axis=1)
    mask = finite.copy()
    for index in np.flatnonzero(finite):
        dominated = np.all(values[finite] <= values[index], axis=1) & np.any(
            values[finite] < values[index],
            axis=1,
        )
        if np.any(dominated):
            mask[index] = False
    return mask


def manifold_distance(first, second):
    """Equation (21): average nearest-neighbour manifold distance."""
    first = np.atleast_2d(np.asarray(first, dtype=float))
    second = np.atleast_2d(np.asarray(second, dtype=float))
    if not len(first) or not len(second):
        return 0.0
    distances = np.linalg.norm(
        first[:, None, :] - second[None, :, :],
        axis=2,
    )
    return float(np.mean(np.min(distances, axis=1)))


def feedback_coefficients(fitness_history):
    """Equations (6)-(7), normalized defensively for numerical safety."""
    fitness = np.asarray(fitness_history, dtype=float)
    if fitness.ndim != 2 or fitness.shape[0] < 2:
        raise ValueError("At least two historical fitness rows are required.")
    fitness = np.maximum(fitness, _EPSILON)
    totals = np.sum(fitness, axis=0)
    beta = fitness.shape[0] - 1
    weights = (totals[None, :] - fitness) / (
        beta * np.maximum(totals[None, :], _EPSILON)
    )
    column_sums = np.sum(weights, axis=0, keepdims=True)
    invalid = column_sums <= _EPSILON
    weights = np.divide(
        weights,
        np.where(invalid, 1.0, column_sums),
    )
    if np.any(invalid):
        weights[:, invalid[0]] = 1.0 / fitness.shape[0]
    return weights


def boundary_repair(values, lower, upper, rng):
    """Equation (8): randomly repair an invalid value toward the midpoint."""
    repaired = np.asarray(values, dtype=float).copy()
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    midpoint = 0.5 * (lower + upper)
    below = repaired < lower
    above = repaired > upper
    if np.any(below):
        repaired[below] = rng.uniform(
            np.broadcast_to(lower, repaired.shape)[below],
            np.broadcast_to(midpoint, repaired.shape)[below],
        )
    if np.any(above):
        repaired[above] = rng.uniform(
            np.broadcast_to(midpoint, repaired.shape)[above],
            np.broadcast_to(upper, repaired.shape)[above],
        )
    return np.clip(repaired, lower, upper)


def _cartesian_to_hyperspherical(vector):
    vector = np.asarray(vector, dtype=float)
    radius = float(np.linalg.norm(vector))
    if len(vector) <= 1 or radius <= _EPSILON:
        return np.zeros(max(len(vector) - 1, 0)), radius
    angles = np.empty(len(vector) - 1, dtype=float)
    for index in range(len(angles)):
        tail = np.linalg.norm(vector[index + 1 :])
        angles[index] = np.arctan2(tail, vector[index])
    return angles, radius


def _hyperspherical_to_cartesian(angles, radius):
    angles = np.asarray(angles, dtype=float)
    dimension = len(angles) + 1
    result = np.empty(dimension, dtype=float)
    sine_product = 1.0
    for index in range(dimension):
        if index == dimension - 1:
            result[index] = radius * sine_product
        else:
            result[index] = (
                radius * sine_product * np.cos(angles[index])
            )
            sine_product *= np.sin(angles[index])
    return result


class FGTTMP(ResponseStrategy):
    """Feedback-guided transfer plus trend manifold prediction."""

    def __init__(
        self,
        cluster_num=12,
        weak_learners=10,
        random_multiplier=20,
        history_length=50,
    ):
        super().__init__()
        self.cluster_num = max(1, int(cluster_num))
        self.weak_learners = max(1, int(weak_learners))
        self.random_multiplier = max(2, int(random_multiplier))
        self.history_length = max(3, int(history_length))
        self._history = []
        self._response_count = 0

    @staticmethod
    def _fitness(objectives, violation):
        objectives = np.asarray(objectives, dtype=float)
        violation = np.asarray(violation, dtype=float)
        span = np.ptp(objectives, axis=0)
        normalized = (
            objectives - np.min(objectives, axis=0)
        ) / np.where(span > _EPSILON, span, 1.0)
        good = non_dominated_mask(objectives)
        rank_penalty = (~good).astype(float)
        cv_scale = max(float(np.max(violation)), _EPSILON)
        return (
            1.0
            + np.mean(normalized, axis=1)
            + rank_penalty
            + violation / cv_scale
        )

    @staticmethod
    def _good_mask(objectives, violation):
        feasible = violation <= 1e-12
        if np.any(feasible):
            result = np.zeros(len(objectives), dtype=bool)
            feasible_indices = np.flatnonzero(feasible)
            result[feasible_indices] = non_dominated_mask(
                objectives[feasible],
            )
            return result
        threshold = np.quantile(violation, 0.25)
        return violation <= threshold

    def _archive(self, population, target_size):
        decisions = population.get_decision_matrix().astype(float, copy=True)
        objectives = population.get_objective_matrix().astype(float, copy=True)
        violation = population.get_constraint_violation_vector()
        order = np.lexsort(tuple(objectives[:, column] for column in reversed(
            range(objectives.shape[1])
        )))
        if len(order) != target_size:
            positions = np.linspace(0, len(order) - 1, target_size)
            order = order[np.rint(positions).astype(int)]
        decisions = decisions[order]
        objectives = objectives[order]
        violation = violation[order]
        snapshot = _Snapshot(
            decisions=decisions,
            objectives=objectives,
            violation=violation,
            good=self._good_mask(objectives, violation),
            fitness=self._fitness(objectives, violation),
        )
        self._history.append(snapshot)
        self._history = self._history[-self.history_length :]

    def _random_population(self, problem, rng):
        return rng.uniform(
            problem.xl,
            problem.xu,
            size=(problem.solution_num, problem.decision_num),
        )

    def _feedback_generation(self, problem, rng):
        decision_history = np.stack(
            [snapshot.decisions for snapshot in self._history],
        )
        objective_history = np.stack(
            [snapshot.objectives for snapshot in self._history],
        )
        fitness_history = np.stack(
            [snapshot.fitness for snapshot in self._history],
        )
        weights = feedback_coefficients(fitness_history)
        generated = np.sum(weights[:, :, None] * decision_history, axis=0)
        objective_proxy = np.sum(
            weights[:, :, None] * objective_history,
            axis=0,
        )
        generated = boundary_repair(
            generated,
            problem.xl,
            problem.xu,
            rng,
        )
        return generated, objective_proxy

    def _target_labels(self, generated, objective_proxy):
        count = len(generated)
        cluster_count = min(self.cluster_num, count)
        if cluster_count == 1:
            cluster_labels = np.ones(count, dtype=int)
        else:
            tree = linkage(generated, method="average", metric="euclidean")
            cluster_labels = fcluster(
                tree,
                t=cluster_count,
                criterion="maxclust",
            )
        unique = np.unique(cluster_labels)
        centers = np.vstack(
            [np.mean(objective_proxy[cluster_labels == label], axis=0)
             for label in unique]
        )
        useful_clusters = unique[non_dominated_mask(centers)]
        useful = np.isin(cluster_labels, useful_clusters)
        local_good = non_dominated_mask(objective_proxy)
        return useful & local_good

    def _transfer_filter(
        self,
        source,
        generated,
        generated_good,
        problem,
        rng,
    ):
        features = np.vstack((source.decisions, generated))
        labels = np.concatenate((source.good, generated_good)).astype(int)
        source_count = len(source.decisions)
        weights = np.concatenate(
            (
                np.full(source_count, 1.0 / source_count),
                np.full(len(generated), 1.0 / len(generated)),
            )
        )
        if len(np.unique(labels)) < 2:
            return generated

        source_beta = 0.5 * np.log(
            1.0 / (1.0 + np.sqrt(2.0 * np.log(self.weak_learners)))
        )
        classifiers = []
        classifier_weights = []
        target_slice = slice(source_count, None)
        for _ in range(self.weak_learners):
            model = SVC(kernel="rbf", gamma="scale")
            model.fit(features, labels, sample_weight=weights)
            prediction = model.predict(features)
            target_error = np.average(
                prediction[target_slice] != labels[target_slice],
                weights=weights[target_slice],
            )
            target_error = float(np.clip(target_error, 1e-6, 0.499999))
            target_beta = 0.5 * np.log(
                (1.0 - target_error) / target_error
            )
            source_wrong = (
                prediction[:source_count] != labels[:source_count]
            )
            target_wrong = (
                prediction[target_slice] != labels[target_slice]
            )
            weights[:source_count] *= np.exp(
                source_beta * source_wrong,
            )
            weights[target_slice] *= np.exp(
                target_beta * target_wrong,
            )
            weights /= max(float(np.sum(weights)), _EPSILON)
            classifiers.append(model)
            classifier_weights.append(target_beta)

        candidates = self._random_population(
            problem,
            rng,
        )
        extra = rng.uniform(
            problem.xl,
            problem.xu,
            size=(
                problem.solution_num * self.random_multiplier,
                problem.decision_num,
            ),
        )
        candidates = np.vstack((generated, candidates, extra))
        scores = np.zeros(len(candidates), dtype=float)
        for model, model_weight in zip(classifiers, classifier_weights):
            scores += model_weight * (
                2.0 * model.predict(candidates) - 1.0
            )
        selected = np.argsort(scores)[::-1][: problem.solution_num]
        return candidates[selected]

    def _fgt(self, problem, rng):
        generated, objective_proxy = self._feedback_generation(problem, rng)
        generated_good = self._target_labels(
            generated,
            objective_proxy,
        )
        return self._transfer_filter(
            self._history[-1],
            generated,
            generated_good,
            problem,
            rng,
        )

    def _tmp(self, problem, rng):
        previous, current = self._history[-2:]
        previous_ps = previous.decisions[previous.good]
        current_ps = current.decisions[current.good]
        if not len(previous_ps) or not len(current_ps):
            return current.decisions.copy()

        previous_center = np.mean(previous_ps, axis=0)
        current_center = np.mean(current_ps, axis=0)
        previous_manifold = previous_ps - previous_center
        current_manifold = current_ps - current_center
        sigma = manifold_distance(
            previous_manifold,
            current_manifold,
        ) / max(problem.solution_num, 1)
        predicted_manifold = current_manifold + rng.normal(
            0.0,
            sigma,
            size=current_manifold.shape,
        )

        direction = current_center - previous_center
        angles, radius = _cartesian_to_hyperspherical(direction)
        if radius > _EPSILON:
            scale = np.maximum(np.abs(angles), 1e-3)
            deflection = np.clip(
                rng.laplace(0.0, scale),
                -np.pi,
                np.pi,
            )
            direction = _hyperspherical_to_cartesian(
                angles + deflection,
                radius,
            )
        predicted_center = current_center + direction
        predicted = predicted_center + predicted_manifold
        return boundary_repair(
            predicted,
            problem.xl,
            problem.xu,
            rng,
        )

    def response(self, population, problem, algorithm):
        seed = int(getattr(algorithm, "seed", 0))
        rng = np.random.default_rng(seed + self._response_count)
        self._response_count += 1
        self._archive(population, problem.solution_num)

        if len(self._history) <= 2:
            decisions = self._random_population(problem, rng)
        else:
            decisions = np.vstack(
                (self._fgt(problem, rng), self._tmp(problem, rng))
            )

        result = Population(
            X=decisions,
            xl=problem.xl,
            xu=problem.xu,
        )
        result.update_objective_constrain(problem)
        quick_non_dominate_sort(result)
        if result.n > problem.solution_num:
            result = crowd_selection(result, problem.solution_num)
        return result
