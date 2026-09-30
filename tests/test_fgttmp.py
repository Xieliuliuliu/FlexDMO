import unittest

import numpy as np

from algorithms.response_strategy.FGTTMP.main import (
    FGTTMP,
    boundary_repair,
    feedback_coefficients,
    manifold_distance,
    non_dominated_mask,
)
from components.Population import Population


class _Algorithm:
    seed = 17


class _MovingProblem:
    def __init__(self):
        self.solution_num = 18
        self.decision_num = 3
        self.objective_num = 2
        self.xl = np.zeros(3)
        self.xu = np.ones(3)
        self.t = 0

    def evaluate(self, decisions):
        decisions = np.asarray(decisions)
        shift = 0.1 * self.t
        first = np.sum((decisions - shift) ** 2, axis=1)
        second = np.sum((decisions - (1.0 - shift)) ** 2, axis=1)
        constraint = (0.05 - np.sum(decisions, axis=1))[:, None]
        return np.column_stack((first, second)), constraint


class FGTTMPHelperTests(unittest.TestCase):
    def test_feedback_coefficients_sum_to_one(self):
        fitness = np.array(
            [[1.0, 2.0], [3.0, 1.0], [2.0, 4.0]],
        )
        coefficients = feedback_coefficients(fitness)
        np.testing.assert_allclose(np.sum(coefficients, axis=0), 1.0)
        self.assertTrue(np.all(coefficients >= 0.0))

    def test_non_dominated_mask(self):
        mask = non_dominated_mask(
            [[0.0, 2.0], [1.0, 1.0], [2.0, 2.0]],
        )
        np.testing.assert_array_equal(mask, [True, True, False])

    def test_manifold_distance_and_boundary_repair(self):
        distance = manifold_distance([[0.0], [2.0]], [[1.0]])
        self.assertAlmostEqual(distance, 1.0)
        repaired = boundary_repair(
            [[-1.0, 2.0]],
            [0.0, 0.0],
            [1.0, 1.0],
            np.random.default_rng(3),
        )
        self.assertTrue(np.all(repaired >= 0.0))
        self.assertTrue(np.all(repaired <= 1.0))


class FGTTMPWorkflowTests(unittest.TestCase):
    def test_third_response_runs_fgt_and_tmp_with_constraints(self):
        problem = _MovingProblem()
        strategy = FGTTMP(
            cluster_num=4,
            weak_learners=3,
            random_multiplier=3,
        )
        population = Population(
            xl=problem.xl,
            xu=problem.xu,
            n_init=problem.solution_num,
        )
        population.update_objective_constrain(problem)

        for time_step in range(3):
            problem.t = time_step + 1
            population = strategy.response(
                population,
                problem,
                _Algorithm(),
            )
            self.assertEqual(population.n, problem.solution_num)
            decisions = population.get_decision_matrix()
            self.assertTrue(np.all(np.isfinite(decisions)))
            self.assertTrue(np.all(decisions >= problem.xl))
            self.assertTrue(np.all(decisions <= problem.xu))
            self.assertTrue(
                np.all(np.isfinite(population.get_objective_matrix()))
            )


if __name__ == "__main__":
    unittest.main()
