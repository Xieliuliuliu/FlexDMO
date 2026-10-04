"""Regression coverage for objective-independent constraint changes."""

import unittest
from types import SimpleNamespace

import numpy as np

from algorithms.response_strategy.NoResponse.main import NoResponse
from algorithms.search_algorithm.NSGA2.main import NSGA2
from algorithms.search_algorithm.MOEAD.main import MOEAD
from algorithms.search_algorithm.RMMEDA.main import RMMEDA
from algorithms.search_algorithm.SPEA2.main import SPEA2
from components.Population import Population
from problems.Problem import Problem
from utils.evolution_tools import detection


class ConstraintOnlyProblem(Problem):
    def __init__(self):
        super().__init__(2, 2, 2, 10, 1, 6, 3, "constraint-only")
        self.initial_convergence = 0

    def _evaluate_objectives(self, X, t):
        return np.column_stack((X[:, 0], 1.0 - X[:, 0]))

    def _evaluate_constraints(self, X, t):
        # 总违反量始终相同，但每条约束的变化都应能被检测。
        return np.tile([1.0 + t, 3.0 - t], (len(X), 1))

    def _calculate_pareto_front(self, t=None):
        return np.array([[0.0, 1.0], [1.0, 0.0]])

    def _calculate_pareto_set(self, t=None):
        return np.array([[0.0, 0.5], [1.0, 0.5]])


class ChangeDetectionTests(unittest.TestCase):
    def setUp(self):
        self.problem = ConstraintOnlyProblem()
        self.population = Population(X=np.full((6, 2), 0.5))
        self.population.update_objective_constrain(self.problem)

    def test_detects_constraint_change_even_with_same_objectives_and_total_violation(self):
        before = self.population.to_dict()
        evaluations = self.problem.evaluate_time
        self.problem.need_change = True
        self.assertEqual(detection(self.population, self.problem, 6), 1)
        self.assertEqual(self.problem.t, 1)
        self.assertEqual(self.problem.evaluate_time, evaluations)
        self.assertEqual(self.population.to_dict(), before)

    def test_unchanged_environment_is_not_a_change(self):
        self.assertEqual(detection(self.population, self.problem, 20), 0)

    def test_constraint_addition_removal_and_shape_change_are_detected(self):
        for old_constraints in (None, np.array([4.0])):
            with self.subTest(old=old_constraints):
                for individual in self.population:
                    individual.G = old_constraints
                self.assertEqual(detection(self.population, self.problem, 6), 1)
        for individual in self.population:
            individual.G = np.array([1.0, 3.0])
        self.problem._evaluate_constraints = lambda X, t: None
        self.assertEqual(detection(self.population, self.problem, 6), 1)

    def test_none_and_empty_unconstrained_values_are_equivalent(self):
        self.problem._evaluate_constraints = lambda X, t: None
        for individual in self.population:
            individual.G = np.empty(0)
        self.assertEqual(detection(self.population, self.problem, 6), 0)

    def test_small_constraint_changes_cannot_hide_feasibility_flip(self):
        self.problem._evaluate_constraints = lambda X, t: np.full((len(X), 1), 1.000001e-12)
        for individual in self.population:
            individual.G = np.array([0.999999e-12])
        self.assertEqual(detection(self.population, self.problem, 6), 1)

    def test_objective_changes_still_trigger_detection(self):
        self.problem._evaluate_objectives = lambda X, t: np.ones((len(X), 2))
        self.assertEqual(detection(self.population, self.problem, 6), 1)

    def test_invalid_detector_count_is_rejected(self):
        for count in (0, -1, 0.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                detection(self.population, self.problem, count)

    def test_empty_population_does_not_advance_pending_environment(self):
        self.problem.need_change = True
        self.assertEqual(detection(Population(), self.problem, 1), 0)
        self.assertEqual(self.problem.t, 0)

    def test_constraint_only_changes_produce_all_environment_histories(self):
        problem = ConstraintOnlyProblem()
        search = NSGA2(seed=4)
        search.optimize(problem, NoResponse())
        self.assertEqual(list(search.history["runtime"]), [0, 1, 2])
        for environment, frames in search.history["runtime"].items():
            for population in frames.values():
                expected = problem._evaluate_constraints(population.get_decision_matrix(), environment)
                np.testing.assert_allclose(population.get_constrain_matrix(), expected)

    def test_canceled_response_does_not_publish_stale_population_in_new_environment(self):
        class CancelResponse:
            def response(self, population, problem, algorithm):
                algorithm.state.value = "stop"
                return population.copy()

        for constructor in (NSGA2, MOEAD, RMMEDA, SPEA2):
            with self.subTest(search=constructor.__name__):
                problem = ConstraintOnlyProblem()
                kwargs = {"seed": 5, "state": SimpleNamespace(value="running")}
                if constructor is MOEAD:
                    kwargs["neighbor_size"] = 3
                elif constructor is RMMEDA:
                    kwargs["K"] = 2
                optimizer = constructor(**kwargs)
                optimizer.optimize(problem, CancelResponse())
                self.assertEqual(problem.t, 1)
                self.assertNotIn(1, optimizer.history["runtime"])
                self.assertEqual(optimizer.state.value, "stop")


if __name__ == "__main__":
    unittest.main()
