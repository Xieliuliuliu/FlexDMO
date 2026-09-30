import unittest

import numpy as np

from algorithms.response_strategy.PPS.main import (
    PPS,
    fit_autoregression,
    manifold_distance,
    repair_from_parent,
)
from components.Population import Population
from problems.benchmark.CDP1.main import CDP1


class PopulationPredictionStrategyTests(unittest.TestCase):
    def build_problem(self):
        return CDP1(
            decision_num=4,
            n=10,
            tau=2,
            solution_num=12,
            total_evaluate_time=8,
        )

    def test_autoregression_recovers_a_known_sequence(self):
        centers = np.array(
            [
                [1.0, 3.0],
                [2.0, 6.0],
                [4.0, 12.0],
                [8.0, 24.0],
            ]
        )

        predicted, variance, coefficients = fit_autoregression(
            centers,
            order=1,
        )

        np.testing.assert_allclose(predicted, [16.0, 48.0])
        np.testing.assert_allclose(variance, [0.0, 0.0], atol=1e-24)
        np.testing.assert_allclose(coefficients, [[2.0, 2.0]])

    def test_manifold_distance_matches_paper_definition(self):
        current = np.array([[0.0, 0.0], [2.0, 0.0]])
        previous = np.array([[0.0, 0.0], [1.0, 0.0]])

        self.assertAlmostEqual(
            manifold_distance(current, previous),
            0.5,
        )

    def test_midpoint_boundary_repair_matches_paper(self):
        repaired = repair_from_parent(
            predicted=np.array([-0.2, 1.2, 0.5]),
            parent=np.array([0.4, 0.6, 0.5]),
            lower=np.zeros(3),
            upper=np.ones(3),
        )

        np.testing.assert_allclose(repaired, [0.2, 0.8, 0.5])

    def test_response_reaches_ar_prediction_stage_and_stays_valid(self):
        np.random.seed(29)
        problem = self.build_problem()
        strategy = PPS(ar_order=3, history_length=23)
        population = Population(
            xl=problem.xl,
            xu=problem.xu,
            n_init=problem.solution_num,
        )
        population.update_objective_constrain(problem)

        for time_step in range(1, 5):
            problem.t = time_step
            population = strategy.response(
                population,
                problem,
                algorithm=None,
            )
            decisions = population.get_decision_matrix()
            self.assertEqual(population.n, problem.solution_num)
            self.assertTrue(np.all(np.isfinite(decisions)))
            self.assertTrue(np.all(decisions >= problem.xl))
            self.assertTrue(np.all(decisions <= problem.xu))
            self.assertTrue(
                all(individual.rank is not None for individual in population)
            )

        self.assertEqual(len(strategy._centers), 4)
        self.assertEqual(len(strategy._manifolds), 2)

    def test_invalid_history_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            PPS(ar_order=0)
        with self.assertRaises(ValueError):
            PPS(ar_order=3, history_length=3)


if __name__ == "__main__":
    unittest.main()
