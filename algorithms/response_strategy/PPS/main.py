"""Population Prediction Strategy (PPS).

Faithful implementation of the center/manifold prediction procedure from:
A. Zhou, Y. Jin, and Q. Zhang, IEEE Transactions on Cybernetics, 2014.
"""

import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import crowd_selection, quick_non_dominate_sort


def fit_autoregression(center_history, order):
    """Fit one AR(order) model per decision dimension by least squares."""
    centers = np.atleast_2d(np.asarray(center_history, dtype=float))
    if centers.ndim != 2:
        raise ValueError("center_history must be a two-dimensional matrix.")
    if order <= 0:
        raise ValueError("order must be positive.")
    if len(centers) <= order:
        raise ValueError("AR fitting requires more observations than order.")

    design = np.array(
        [
            centers[index - order:index][::-1].reshape(-1)
            for index in range(order, len(centers))
        ],
        dtype=float,
    )
    dimension = centers.shape[1]
    design = design.reshape(len(design), order, dimension)
    targets = centers[order:]

    coefficients = np.empty((order, dimension), dtype=float)
    residual_variance = np.empty(dimension, dtype=float)
    for column in range(dimension):
        column_design = design[:, :, column]
        coefficients[:, column] = np.linalg.lstsq(
            column_design,
            targets[:, column],
            rcond=None,
        )[0]
        residuals = (
            targets[:, column]
            - column_design @ coefficients[:, column]
        )
        residual_variance[column] = float(np.mean(residuals**2))

    recent = centers[-order:][::-1]
    predicted_center = np.sum(coefficients * recent, axis=0)
    return predicted_center, residual_variance, coefficients


def manifold_distance(current_manifold, previous_manifold):
    """Return the directed average nearest-neighbour manifold distance."""
    current = np.atleast_2d(np.asarray(current_manifold, dtype=float))
    previous = np.atleast_2d(np.asarray(previous_manifold, dtype=float))
    if current.shape[1] != previous.shape[1]:
        raise ValueError("Manifolds must have the same decision dimension.")
    if not len(current) or not len(previous):
        return 0.0
    distances = np.linalg.norm(
        current[:, None, :] - previous[None, :, :],
        axis=2,
    )
    return float(np.mean(np.min(distances, axis=1)))


def repair_from_parent(predicted, parent, lower, upper):
    """Apply the midpoint boundary repair specified by the PPS paper."""
    predicted = np.asarray(predicted, dtype=float).copy()
    parent = np.asarray(parent, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    below = predicted < lower
    above = predicted > upper
    predicted[below] = 0.5 * (lower[below] + parent[below])
    predicted[above] = 0.5 * (upper[above] + parent[above])
    return predicted


class PPS(ResponseStrategy):
    """Predict a whole population using PS centers and manifolds."""

    def __init__(self, ar_order=3, history_length=23):
        super().__init__()
        self.ar_order = int(ar_order)
        self.history_length = int(history_length)
        if self.ar_order <= 0:
            raise ValueError("ar_order must be positive.")
        if self.history_length <= self.ar_order:
            raise ValueError(
                "history_length must be greater than ar_order."
            )
        self._centers = []
        self._manifolds = []
        self._populations = []

    def _normalize_population(self, population, problem):
        if population.n == problem.solution_num:
            return population
        if population.n > problem.solution_num:
            quick_non_dominate_sort(population)
            return crowd_selection(population, problem.solution_num)
        if population.n == 0:
            return Population(
                xl=problem.xl,
                xu=problem.xu,
                n_init=problem.solution_num,
            )
        indices = np.random.choice(
            population.n,
            size=problem.solution_num,
            replace=True,
        )
        return Population(
            individuals=[
                population.individuals[index].copy()
                for index in indices
            ],
            xl=problem.xl,
            xu=problem.xu,
        )

    def _remember(self, decisions):
        center = np.mean(decisions, axis=0)
        self._centers.append(center)
        self._manifolds.append(decisions - center)
        self._populations.append(decisions.copy())
        self._centers = self._centers[-self.history_length:]
        self._manifolds = self._manifolds[-2:]
        self._populations = self._populations[-2:]

    def _hybrid_initialization(self, problem, previous_decisions):
        random_count = problem.solution_num // 2
        reuse_count = problem.solution_num - random_count
        random_decisions = np.random.uniform(
            problem.xl,
            problem.xu,
            size=(random_count, problem.decision_num),
        )
        indices = np.random.choice(
            len(previous_decisions),
            size=reuse_count,
            replace=len(previous_decisions) < reuse_count,
        )
        return np.vstack((random_decisions, previous_decisions[indices]))

    def _predict(self, problem, previous_decisions):
        centers = np.asarray(self._centers, dtype=float)
        predicted_center, center_variance, _ = fit_autoregression(
            centers,
            self.ar_order,
        )
        distance = manifold_distance(
            self._manifolds[-1],
            self._manifolds[-2],
        )
        manifold_variance = distance**2 / problem.decision_num
        noise_scale = np.sqrt(
            np.maximum(center_variance + manifold_variance, 0.0)
        )
        noise = np.random.normal(
            0.0,
            noise_scale,
            size=previous_decisions.shape,
        )
        predicted = (
            predicted_center
            + self._manifolds[-1]
            + noise
        )
        return np.array(
            [
                repair_from_parent(
                    candidate,
                    parent,
                    problem.xl,
                    problem.xu,
                )
                for candidate, parent in zip(
                    predicted,
                    previous_decisions,
                )
            ],
            dtype=float,
        )

    def response(self, population, problem, algorithm):
        del algorithm
        population = self._normalize_population(population, problem)
        previous_decisions = population.get_decision_matrix().copy()
        self._remember(previous_decisions)

        if problem.t <= self.ar_order or len(self._centers) <= self.ar_order:
            decisions = self._hybrid_initialization(
                problem,
                previous_decisions,
            )
        else:
            decisions = self._predict(problem, previous_decisions)

        result = Population(
            X=decisions,
            xl=problem.xl,
            xu=problem.xu,
        )
        result.update_objective_constrain(problem)
        quick_non_dominate_sort(result)
        return result
