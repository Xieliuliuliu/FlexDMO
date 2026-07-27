import os
import tempfile
import unittest

import numpy as np

from algorithms.response_strategy.NoResponse.main import NoResponse
from algorithms.search_algorithm.NSGA2.main import NSGA2
from algorithms.search_algorithm.RMMEDA.LocalPCA import LocalPCA
from components.Individual import Individual
from components.Population import Population
from problems.Problem import Problem
from problems.benchmark.DF1.main import DF1
from utils.metrics import calculate_IGD, calculate_MIGD
from utils.result_io import _get_next_filename


class ToyProblem(Problem):
    def __init__(self):
        super().__init__(
            decision_num=2,
            n_obj=2,
            n_con=0,
            n=1,
            tau=1,
            solution_num=2,
            total_evaluate_time=2,
            label="test",
        )

    def _evaluate_objectives(self, X, t):
        return np.column_stack((X[:, 0] + t, X[:, 1]))

    def _calculate_pareto_front(self, t=None):
        return np.array([[float(t), 0.0]])

    def _calculate_pareto_set(self, t=None):
        return np.array([[0.0, 0.0]])


class PopulationRegressionTests(unittest.TestCase):
    def test_rejects_mismatched_decision_and_objective_rows(self):
        with self.assertRaises(ValueError):
            Population(X=np.zeros((2, 2)), F=np.zeros((1, 2)))

    def test_rejects_partially_evaluated_objective_matrix(self):
        population = Population(individuals=[
            Individual(np.array([0.0]), np.array([1.0])),
            Individual(np.array([1.0])),
        ])
        with self.assertRaises(ValueError):
            population.get_objective_matrix()


class ProblemRegressionTests(unittest.TestCase):
    def test_accepts_single_decision_vector_without_miscounting(self):
        problem = ToyProblem()
        objectives, _ = problem.evaluate(np.array([0.25, 0.75]))
        self.assertEqual(objectives.shape, (1, 2))
        self.assertEqual(problem.evaluate_time, 1)

    def test_reset_clears_pending_transition_and_caches(self):
        problem = ToyProblem()
        problem.get_pareto_front()
        problem.get_pareto_set()
        problem.need_change = True
        problem.t = 1
        problem.evaluate_time = 10

        problem.reset()

        self.assertEqual(problem.t, 0)
        self.assertEqual(problem.evaluate_time, 0)
        self.assertFalse(problem.need_change)
        self.assertIsNone(problem._pf_cache)
        self.assertIsNone(problem._ps_cache)


class AlgorithmRegressionTests(unittest.TestCase):
    def test_nsga2_supports_odd_population_size(self):
        np.random.seed(4)
        problem = DF1(
            decision_num=5,
            n=10,
            tau=1,
            solution_num=5,
            total_evaluate_time=1,
        )
        algorithm = NSGA2()

        algorithm.optimize(problem, NoResponse())

        self.assertTrue(problem.is_ended())
        last_population = list(list(algorithm.history["runtime"].values())[-1].values())[-1]
        self.assertEqual(last_population.n, 5)

    def test_local_pca_keeps_real_values_and_exact_sample_allocation(self):
        rng = np.random.default_rng(3)
        population = rng.random((11, 5))

        models, allocation = LocalPCA(population, M=2, K=5)

        self.assertEqual(int(np.sum(allocation)), len(population))
        for model in models:
            self.assertTrue(np.isrealobj(model["PI"]))


class MetricsRegressionTests(unittest.TestCase):
    def test_igd_for_empty_population_is_infinite(self):
        value = calculate_IGD(np.empty((0, 2)), np.array([[0.0, 1.0]]))
        self.assertTrue(np.isinf(value))

    def test_migd_supports_json_style_keys_and_uses_latest_evaluation(self):
        early = Individual(np.array([0.0]), np.array([2.0, 2.0]))
        latest = Individual(np.array([0.0]), np.array([0.0, 0.0]))
        runtime = {
            "0": {
                "20": {"POF": [[0.0, 0.0]], "population": [latest]},
                "5": {"POF": [[0.0, 0.0]], "population": [early]},
            }
        }
        self.assertEqual(calculate_MIGD(runtime), 0.0)


class ResultIoRegressionTests(unittest.TestCase):
    def test_next_filename_does_not_overwrite_when_indices_have_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("result_1.json", "result_3.json"):
                open(os.path.join(directory, name), "w", encoding="utf-8").close()

            self.assertEqual(_get_next_filename(directory, "result"), "result_4.json")


if __name__ == "__main__":
    unittest.main()
