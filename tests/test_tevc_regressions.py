"""Edge cases found in the independent review of the prediction components."""

import copy
import unittest
from unittest.mock import patch

import numpy as np

from algorithms.response_strategy.VARE.main import VARE, associate_reference
from algorithms.search_algorithm.MOEAD.main import MOEAD
from algorithms.search_algorithm.NSGA2.main import NSGA2
from algorithms.search_algorithm.RMMEDA.main import RMMEDA
from algorithms.search_algorithm.SPEA2.main import SPEA2
from flexdmo_app.core import defaults, parse_parameters, records, registered_class
from flexdmo_app.experiments import build_plan
from problems.benchmark.DF1.main import DF1
from tests.test_vare import MovingProblem, SeededAlgorithm, initial_population


class TEVCRegressionTests(unittest.TestCase):
    def test_reused_strategy_after_problem_reset_matches_a_fresh_run(self):
        for search_type in (NSGA2, MOEAD, RMMEDA, SPEA2):
            with self.subTest(search=search_type.__name__):
                problem = DF1(3, 10, 3, 6, 2)
                problem.initial_convergence = 12
                strategy = VARE()
                kwargs = {"seed": 17}
                if search_type is MOEAD:
                    kwargs["neighbor_size"] = 3
                elif search_type is RMMEDA:
                    kwargs["K"] = 2
                search_type(**kwargs).optimize(problem, strategy)
                problem.reset()
                second = search_type(**kwargs)
                second.optimize(problem, strategy)
                reused = list(second.history["runtime"][1].values())[-1]
                self.assertEqual(strategy.last_diagnostics["stage"], "response")
                self.assertEqual(len(strategy._history), 1)
                problem.reset()
                third = search_type(**kwargs)
                third.optimize(problem, VARE())
                fresh = list(third.history["runtime"][1].values())[-1]
                np.testing.assert_array_equal(reused.get_decision_matrix(), fresh.get_decision_matrix())

    def test_failed_response_restores_history_and_random_state_before_retry(self):
        problem = MovingProblem()
        original = initial_population(problem)
        strategy, reference = VARE(), VARE()
        problem.t = 1
        population = strategy.response(original, problem, SeededAlgorithm())
        reference.response(original, problem, SeededAlgorithm())
        history = [row.copy() for row in strategy._history]
        rng_state = copy.deepcopy(strategy._rng.bit_generator.state)
        probability = strategy._probability.copy()
        problem.t = 2
        evaluate = problem.evaluate
        calls = 0

        def fail_after_parent_evaluation(X):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("temporary objective failure")
            return evaluate(X)

        before = problem.evaluated
        with patch.object(problem, "evaluate", side_effect=fail_after_parent_evaluation):
            with self.assertRaisesRegex(RuntimeError, "temporary objective failure"):
                strategy.response(population, problem, SeededAlgorithm())
        self.assertGreater(problem.evaluated, before)  # Do not erase consumed work.
        self.assertEqual(len(strategy._history), 1)
        np.testing.assert_array_equal(strategy._history, history)
        np.testing.assert_array_equal(strategy._probability, probability)
        self.assertEqual(strategy._rng.bit_generator.state, rng_state)
        self.assertEqual(strategy._last_time, 1)
        resumed = strategy.response(population, problem, SeededAlgorithm())
        fresh = reference.response(population, problem, SeededAlgorithm())
        self.assertEqual(len(strategy._history), 2)
        np.testing.assert_array_equal(resumed.get_decision_matrix(), fresh.get_decision_matrix())

    def test_infeasible_association_selects_the_actual_minimum_violation(self):
        indices = associate_reference([[1.0, 1.0], [0.0, 0.0]],
                                      [[1.0, 0.0], [0.0, 1.0]], [2e-12, 2.5e-12])
        np.testing.assert_array_equal(indices, [0, 0])

    def test_small_real_violation_improvement_counts_as_survival(self):
        class TinyViolationProblem(MovingProblem):
            def evaluate(self, X):
                self.evaluated += len(X)
                self.calls.append((self.t, len(X)))
                cv = 1.5e-12 if len(self.calls) >= 3 else 2e-12
                return np.ones((len(X), 2)), np.full((len(X), 1), cv)

        problem = TinyViolationProblem()
        population = initial_population(problem)
        problem.t = 1
        strategy = VARE()
        result = strategy.response(population, problem, SeededAlgorithm())
        self.assertTrue(all(strategy.last_diagnostics["survived"]))
        np.testing.assert_array_equal(result.get_constraint_violation_vector(),
                                      np.full(problem.solution_num, 1.5e-12))
        self.assertTrue(all(not individual.feasible for individual in result))

    def test_zero_regularization_is_valid_in_batch_plans(self):
        registry = records()
        selected = {kind: [next(r for r in registry[kind] if r["name"] == name)]
                    for kind, name in (("dynamic", "VARE"), ("search", "NSGAII"), ("problem", "CDP6"))}
        record = selected["dynamic"][0]
        values = {key: str(value) for key, value in defaults(record).items()}
        values["regularization"] = "0"
        parameters = parse_parameters(values, defaults(record), record)
        self.assertEqual(parameters["regularization"], 0)
        registered_class(record)(**parameters)
        shared = {"decision_num": 3, "solution_num": 6, "total_evaluate_time": 3,
                  "tau": "3", "n": "10", "repeats": 1, "seed": 17}
        plan = build_plan(selected, shared, {("dynamic", record["folder_name"]): parameters})
        self.assertEqual(plan[0]["request"]["params"]["dynamic"]["regularization"], 0)
        parameters["regularization"] = -1
        with self.assertRaises(ValueError):
            registered_class(record)(**parameters)


if __name__ == "__main__":
    unittest.main()
