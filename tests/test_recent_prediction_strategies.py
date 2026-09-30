import unittest

import numpy as np

from algorithms.response_strategy.LRDMOEA.main import (
    LRDMOEA,
    extract_key_points,
    fit_ridge_transition,
    predict_key_points,
)
from algorithms.response_strategy.PSCA.main import (
    PSCA,
    correlation_alignment,
    orthogonal_basis,
)
from components.Population import Population


class _Algorithm:
    seed = 31


class _MovingConstrainedProblem:
    def __init__(self):
        self.solution_num = 24
        self.decision_num = 4
        self.objective_num = 2
        self.xl = np.zeros(4)
        self.xu = np.ones(4)
        self.t = 0

    def evaluate(self, decisions):
        decisions = np.asarray(decisions, dtype=float)
        shift = 0.04 * self.t
        first = np.sum((decisions - shift) ** 2, axis=1)
        second = np.sum(
            (decisions - (0.8 - shift)) ** 2,
            axis=1,
        )
        constraint = (
            0.25 - np.sum(decisions[:, :2], axis=1)
        )[:, None]
        return np.column_stack((first, second)), constraint


def _initial_population(problem):
    population = Population(
        xl=problem.xl,
        xu=problem.xu,
        n_init=problem.solution_num,
    )
    population.update_objective_constrain(problem)
    return population


class PSCAHelperTests(unittest.TestCase):
    def test_pca_basis_is_orthogonal(self):
        values = np.random.default_rng(2).normal(size=(20, 5))
        basis = orthogonal_basis(values)
        np.testing.assert_allclose(
            basis.T @ basis,
            np.eye(5),
            atol=1e-10,
        )

    def test_correlation_alignment_maps_covariance_scale(self):
        rng = np.random.default_rng(4)
        source = rng.normal(size=(1000, 2))
        target = source @ np.diag([2.0, 0.5])
        alignment = correlation_alignment(source, target)
        mapped = source @ alignment
        np.testing.assert_allclose(
            np.cov(mapped, rowvar=False),
            np.cov(target, rowvar=False),
            atol=0.05,
        )


class LinearPredictionHelperTests(unittest.TestCase):
    def test_ridge_transition_and_prediction_preserve_shape(self):
        base = np.arange(12, dtype=float).reshape(3, 2, 2)
        history = [base[index] for index in range(3)]
        coefficients = fit_ridge_transition(history)
        self.assertEqual(coefficients.shape, (5, 4))
        predicted = predict_key_points(history)
        self.assertEqual(predicted.shape, (2, 2))
        self.assertTrue(np.all(np.isfinite(predicted)))

    def test_extracts_requested_percentiles_plus_center(self):
        problem = _MovingConstrainedProblem()
        population = _initial_population(problem)
        points = extract_key_points(population, key_points=12)
        self.assertEqual(points.shape, (12, problem.decision_num))


class RecentPredictionWorkflowTests(unittest.TestCase):
    def assert_valid(self, population, problem):
        self.assertEqual(population.n, problem.solution_num)
        decisions = population.get_decision_matrix()
        self.assertTrue(np.all(np.isfinite(decisions)))
        self.assertTrue(np.all(decisions >= problem.xl))
        self.assertTrue(np.all(decisions <= problem.xu))
        self.assertTrue(
            np.all(np.isfinite(population.get_objective_matrix()))
        )
        self.assertTrue(
            np.all(np.isfinite(population.get_constrain_matrix()))
        )
        self.assertTrue(
            all(individual.rank is not None for individual in population)
        )

    def test_psca_runs_subspace_and_correlation_response(self):
        np.random.seed(7)
        problem = _MovingConstrainedProblem()
        population = _initial_population(problem)
        strategy = PSCA(cluster_num=3)
        for time_step in range(1, 4):
            problem.t = time_step
            population = strategy.response(
                population,
                problem,
                _Algorithm(),
            )
            self.assert_valid(population, problem)

    def test_lr_dmoea_learns_multiple_environment_transitions(self):
        np.random.seed(9)
        problem = _MovingConstrainedProblem()
        population = _initial_population(problem)
        strategy = LRDMOEA(
            predicted_fraction=0.5,
            mutation_fraction=0.2,
        )
        for time_step in range(1, 5):
            problem.t = time_step
            population = strategy.response(
                population,
                problem,
                _Algorithm(),
            )
            self.assert_valid(population, problem)

    def test_invalid_recent_strategy_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            PSCA(cluster_num=0)
        with self.assertRaises(ValueError):
            LRDMOEA(predicted_fraction=0.9, mutation_fraction=0.2)


if __name__ == "__main__":
    unittest.main()
