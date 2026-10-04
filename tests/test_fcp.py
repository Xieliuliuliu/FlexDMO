"""Source-mechanism fixtures and robustness tests for the FCP response only."""

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from algorithms.response_strategy.FCP.main import (
    FCP, center_spacing, generate_population, modify_objectives,
    penalty_clustering, predict_centers, repair_bounds,
)
from algorithms.search_algorithm.NSGA2.main import NSGA2
from components.Population import Population
from problems.benchmark.CDP1.main import CDP1
from utils.evolution_tools import fast_non_dominated_sort
from utils.information_parser import get_all_dynamic_strategy, get_dynamic_response_config


ROOT = Path(__file__).resolve().parents[1]
FCP_MODULE = "algorithms.response_strategy.FCP.main"


class _Problem:
    def __init__(self, size=13, mode="mixed"):
        self.solution_num = size
        self.decision_num = 3
        self.xl = np.array([-1.0, 0.5, -0.4])
        self.xu = np.array([1.0, 0.5, 1.0])
        self.t = 0
        self.evaluate_time = 0
        self.mode = mode
        self.calls = []

    def values(self, decisions):
        x = np.asarray(decisions)
        shift = 0.03 * self.t
        f = np.column_stack((np.sum((x - shift) ** 2, axis=1),
                             np.sum((x - 0.7 + shift) ** 2, axis=1))) + 5.0 * self.t
        if self.mode == "none":
            g = None
        elif self.mode == "infeasible":
            g = np.column_stack((np.ones(len(x)), 1.0 + np.abs(x[:, 0])))
        elif self.mode == "feasible":
            g = -np.ones((len(x), 2))
        else:
            g = np.column_stack((0.25 + shift - x[:, 0], x[:, 2] - 0.8))
        return f, g

    def evaluate(self, decisions):
        self.calls.append((np.asarray(decisions).copy(), self.t))
        self.evaluate_time += len(decisions)
        return self.values(decisions)

    def reset(self):
        self.t = 0
        self.evaluate_time = 0
        self.calls.clear()


def _population(problem, size=None, seed=31):
    size = problem.solution_num if size is None else size
    x = np.random.default_rng(seed).uniform(problem.xl, problem.xu, (size, 3))
    pop = Population(X=x, xl=problem.xl, xu=problem.xu)
    pop.update_objective_constrain(problem)
    return pop


class _Permutation:
    def __init__(self, order):
        self.order = np.array(order)

    def permutation(self, count):
        assert count == len(self.order)
        return self.order.copy()


class FCPMechanismTests(unittest.TestCase):
    def test_modify_obj_uses_per_constraint_normalization_and_zero_y(self):
        f = np.array([[0.0, 10.0], [10.0, 0.0], [5.0, 5.0]])
        g = np.array([[-1.0, 0.0], [2.0, 4.0], [1.0, -1.0]])
        cv = np.array([0.0, 1.0, 0.25])[:, None]
        normalized = f / 10.0
        expected = np.hypot(normalized, cv) + 2.0 / 3.0 * cv
        np.testing.assert_allclose(modify_objectives(f, g), expected)
        # In particular, no rf * normalized-infeasible-objective term is added.
        self.assertAlmostEqual(modify_objectives(f, g)[1, 0], np.sqrt(2.0) + 2.0 / 3.0)

    def test_no_feasible_population_ignores_objectives(self):
        f = np.array([[100.0, 0.0], [0.0, 100.0], [50.0, 50.0]])
        g = np.array([[2.0, -1.0], [4.0, -2.0], [1.0, -3.0]])
        expected = np.repeat([[0.25], [0.5], [0.125]], 2, axis=1)
        np.testing.assert_allclose(modify_objectives(f, g), expected)

    def test_unconstrained_constant_objective_normalizes_to_one(self):
        f = np.array([[3.0, 0.0], [3.0, 2.0], [3.0, 4.0]])
        expected = np.array([[1.0, 0.0], [1.0, 0.5], [1.0, 1.0]])
        np.testing.assert_allclose(modify_objectives(f), expected)
        np.testing.assert_allclose(modify_objectives(f, np.empty((3, 0))), expected)
        self.assertEqual(modify_objectives(np.empty((0, 2))).shape, (0, 2))

    def test_finite_extreme_objectives_do_not_overflow_normalization(self):
        result = modify_objectives(np.array([[-1e308, 1e308], [1e308, -1e308]]))
        np.testing.assert_allclose(result, [[0.0, 1.0], [1.0, 0.0]])

    def test_clustering_is_in_penalty_not_decision_space(self):
        x = np.array([[-4.0, 1.0], [4.0, 1.0], [-3.0, -1.0], [3.0, -1.0]])
        f = np.array([[0.0, 10.0], [0.1, 9.9], [10.0, 0.0], [9.9, 0.1]])
        labels, centers = penalty_clustering(x, f, None, 2, np.random.default_rng(7))
        self.assertEqual(labels[0], labels[1])
        self.assertEqual(labels[2], labels[3])
        self.assertNotEqual(labels[0], labels[2])
        np.testing.assert_allclose(centers[np.argsort(centers[:, 1])], [[0.0, -1.0], [0.0, 1.0]])

    def test_no_feasible_clustering_is_controlled_by_constraint_penalty(self):
        x = np.arange(8.0).reshape(4, 2)
        f = np.array([[0.0, 1.0], [100.0, 0.0], [0.0, 1.0], [100.0, 0.0]])
        g = np.array([[4.0], [4.0], [1.0], [1.0]])
        labels, _ = penalty_clustering(x, f, g, 2, np.random.default_rng(2))
        self.assertEqual(labels[0], labels[1])
        self.assertEqual(labels[2], labels[3])
        self.assertNotEqual(labels[0], labels[2])

    def test_duplicate_penalties_and_small_population_cap_cluster_count(self):
        for size in (1, 2, 5):
            with self.subTest(size=size):
                x = np.arange(size * 2.0).reshape(size, 2)
                labels, centers = penalty_clustering(x, np.ones((size, 2)), None,
                                                     10, np.random.default_rng(5))
                np.testing.assert_array_equal(labels, np.zeros(size))
                np.testing.assert_allclose(centers, x.mean(axis=0, keepdims=True))

    def test_empty_lloyd_clusters_are_repaired_without_nan(self):
        # Force identical initialization although the feature rows are distinct.
        class DegenerateRNG:
            def integers(self, count):
                return 0

            def choice(self, count, p):
                return 0

        x = np.arange(12.0).reshape(6, 2)
        f = np.column_stack((np.arange(6.0), np.arange(6.0)[::-1]))
        labels, centers = penalty_clustering(x, f, None, 3, DegenerateRNG(), max_iter=2)
        self.assertEqual(len(np.unique(labels)), 3)
        self.assertTrue(np.all(np.isfinite(centers)))

    def test_prediction_uses_global_drift_not_temporal_cluster_matching(self):
        previous = np.array([[0.0, 1.0], [2.0, 3.0]])
        current = np.array([[2.0, 5.0], [4.0, 7.0]])
        centers = np.array([[2.0, 5.0], [4.0, 7.0]])
        predicted = predict_centers(current, previous, centers)
        np.testing.assert_allclose(predicted, [[4.0, 9.0], [6.0, 11.0]])
        np.testing.assert_allclose(predicted - centers, np.tile([2.0, 4.0], (2, 1)))

    def test_center_pairing_is_random_permutation_and_allows_self(self):
        centers = np.array([[0.0, 1.0], [2.0, 4.0], [5.0, 7.0]])
        widths, pairs = center_spacing(centers, _Permutation([2, 0, 1]))
        np.testing.assert_array_equal(pairs, [2, 0, 1])
        np.testing.assert_allclose(widths, [[5.0, 6.0], [2.0, 3.0], [3.0, 3.0]])
        widths, _ = center_spacing(centers, _Permutation([0, 1, 2]))
        np.testing.assert_array_equal(widths, np.zeros_like(centers))

    def test_generation_uses_spacing_uniform_boxes_and_balanced_odd_counts(self):
        centers = np.array([[0.3], [0.7]])
        widths = np.array([[0.1], [0.2]])
        result = generate_population(centers, widths, 5, [0.0], [1.0], np.random.default_rng(9))
        rng = np.random.default_rng(9)
        expected = np.vstack((0.3 + rng.uniform(-1.0, 1.0, (3, 1)) * 0.1,
                              0.7 + rng.uniform(-1.0, 1.0, (2, 1)) * 0.2))
        np.testing.assert_array_equal(result, expected)

    def test_reflection_handles_negative_fixed_and_nonfinite_decisions(self):
        values = [[-2.2, 9.0, 5.4], [-0.8, -8.0, 2.6],
                  [-5.2, np.nan, np.nan], [np.nan, np.inf, -np.inf]]
        result = repair_bounds(values, [-2.0, 1.0, 3.0], [-1.0, 1.0, 5.0])
        np.testing.assert_allclose(result, [[-1.8, 1.0, 4.6], [-1.2, 1.0, 3.4],
                                           [-1.2, 1.0, 4.0], [-1.5, 1.0, 3.0]])


class FCPResponseTests(unittest.TestCase):
    def assert_valid(self, result, problem):
        x = result.get_decision_matrix()
        self.assertEqual(x.shape, (problem.solution_num, problem.decision_num))
        self.assertTrue(np.all(np.isfinite(x)))
        self.assertTrue(np.all(x >= problem.xl))
        self.assertTrue(np.all(x <= problem.xu))
        f, g = problem.values(x)
        np.testing.assert_array_equal(result.get_objective_matrix(), f)
        if g is not None:
            np.testing.assert_array_equal(result.get_constrain_matrix(), g)
            np.testing.assert_allclose(result.get_constraint_violation_vector(), np.maximum(g, 0.0).sum(axis=1))
        else:
            self.assertTrue(all(individual.G is None and individual.feasible for individual in result))
        for rank, indices in enumerate(fast_non_dominated_sort(f, result.get_constraint_violation_vector()), 1):
            self.assertTrue(all(result[i].rank == rank for i in indices))

    def test_response_progresses_from_bootstrap_to_source_prediction(self):
        problem = _Problem()
        population = _population(problem)
        strategy = FCP(evaluation_batch_size=4)
        old_x = population.get_decision_matrix().copy()
        old_f = population.get_objective_matrix().copy()
        old_g = population.get_constrain_matrix().copy()
        problem.t = 1
        problem.calls.clear()
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("cold history")):
            result = strategy.response(population, problem, SimpleNamespace(seed=19))
        self.assert_valid(result, problem)
        np.testing.assert_array_equal(strategy._history[-1], old_x)
        np.testing.assert_array_equal(population.get_decision_matrix(), old_x)
        np.testing.assert_array_equal(population.get_objective_matrix(), old_f)
        np.testing.assert_array_equal(population.get_constrain_matrix(), old_g)
        self.assertTrue(all(individual.rank is None for individual in population))
        self.assertTrue(all(time == 1 and len(x) <= 4 for x, time in problem.calls))
        for time in range(2, 5):
            problem.t = time
            before = result.get_decision_matrix().copy()
            problem.calls.clear()
            with patch(FCP_MODULE + ".penalty_clustering", wraps=penalty_clustering) as clustered:
                result = strategy.response(result, problem, SimpleNamespace(seed=19))
                clustered.assert_called_once()
            self.assert_valid(result, problem)
            np.testing.assert_array_equal(strategy._history[-1], before)
            self.assertEqual(len(strategy._history), 2)
            self.assertEqual(sum(len(x) for x, _ in problem.calls), problem.solution_num)
            self.assertTrue(all(t == time for _, t in problem.calls))

    def test_constraint_priority_beats_superior_infeasible_objectives(self):
        problem = _Problem(size=2)
        population = Population(X=[[0.8, 0.5, 0.0], [-0.8, 0.5, 0.0]],
                                F=[[100.0, 100.0], [0.0, 0.0]], xl=problem.xl, xu=problem.xu)
        for individual, g in zip(population, ([-1.0], [0.01])):
            individual.G = np.array(g)
            individual.constraint_violation = float(max(g[0], 0.0))
            individual.feasible = g[0] <= 0.0
        selected = FCP()._select(population, 1, lambda: None)
        self.assertTrue(selected[0].feasible)
        np.testing.assert_array_equal(selected[0].F, [100.0, 100.0])

    def test_no_feasible_selection_prioritizes_total_raw_violation(self):
        problem = _Problem(size=2, mode="infeasible")
        population = _population(problem)
        population[0].F = np.zeros(2)
        population[1].F = np.ones(2) * 1000.0
        population[0].constraint_violation = 2.0
        population[1].constraint_violation = 1.0
        selected = FCP()._select(population, 1, lambda: None)
        self.assertEqual(selected[0].constraint_violation, 1.0)

    def test_empty_small_odd_undersized_and_oversized_populations(self):
        for target in (1, 2, 3, 7, 13):
            for incoming in (0, 1, target, target + 3):
                for mode in ("mixed", "infeasible", "feasible", "none"):
                    with self.subTest(target=target, incoming=incoming, mode=mode):
                        problem = _Problem(target, mode)
                        population = _population(problem, incoming)
                        strategy = FCP(cluster_num=10)
                        for time in (1, 2):
                            problem.t = time
                            population = strategy.response(population, problem, algorithm=None)
                            self.assert_valid(population, problem)

    def test_repeated_centers_get_degenerate_only_diversity_safeguard(self):
        problem = _Problem(size=9, mode="feasible")
        population = Population(X=np.tile([0.0, 0.5, 0.3], (9, 1)), xl=problem.xl, xu=problem.xu)
        population.update_objective_constrain(problem)
        strategy = FCP(diversity_floor=0.02)
        problem.t = 1
        strategy.response(population, problem, SimpleNamespace(seed=4))
        problem.t = 2
        result = strategy.response(population, problem, SimpleNamespace(seed=4))
        self.assert_valid(result, problem)
        self.assertGreater(np.ptp(result.get_decision_matrix()[:, 0]), 0.0)
        np.testing.assert_array_equal(result.get_decision_matrix()[:, 1], np.full(9, 0.5))

    def test_repaired_or_unevaluated_input_uses_safe_bootstrap(self):
        for kind in ("unevaluated", "broken_decision"):
            with self.subTest(kind=kind):
                problem = _Problem()
                strategy = FCP()
                population = _population(problem)
                strategy.response(population, problem, None)
                if kind == "unevaluated":
                    population[0].F = None
                else:
                    population[0].X = np.array([np.nan, np.inf, -np.inf])
                problem.t = 1
                with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("invalid history")):
                    result = strategy.response(population, problem, None)
                self.assert_valid(result, problem)
                self.assertEqual(len(strategy._history), 1)

    def test_history_and_results_do_not_alias_caller_or_each_other(self):
        problem = _Problem(size=4, mode="feasible")
        population = _population(problem)
        strategy = FCP()
        original = population.get_decision_matrix().copy()
        result = strategy.response(population, problem, None)
        population[0].X[:] = 0.123
        np.testing.assert_array_equal(strategy._history[-1], original)
        if result.n > 1:
            second = result[1].X.copy()
            result[0].X[:] = 0.321
            np.testing.assert_array_equal(result[1].X, second)

    def test_new_problem_or_changed_bounds_reset_history(self):
        strategy = FCP()
        first = _Problem()
        strategy.response(_population(first), first, None)
        second = _Problem()
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("reset history")):
            strategy.response(_population(second), second, None)
        self.assertEqual(strategy._response_count, 1)
        second.xu[0] = 0.9
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("new bounds")):
            strategy.response(_population(second), second, None)
        self.assertEqual(len(strategy._history), 1)

    def test_same_problem_reset_discards_history_and_restarts_seed_sequence(self):
        problem = _Problem()
        strategy = FCP()
        population = _population(problem)
        for problem.t in (1, 2, 3):
            population = strategy.response(population, problem, SimpleNamespace(seed=41))
        self.assertEqual(len(strategy._history), 2)
        problem.reset()
        population = _population(problem)
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("reset")):
            result = strategy.response(population, problem, SimpleNamespace(seed=41))
        fresh = FCP().response(population, problem, SimpleNamespace(seed=41))
        np.testing.assert_array_equal(result.get_decision_matrix(), fresh.get_decision_matrix())
        self.assertEqual(strategy._response_count, 1)
        self.assertEqual(len(strategy._history), 1)
        self.assertEqual(strategy._last_t, 0)

    def test_evaluation_rollback_resets_even_when_time_does_not_decrease(self):
        problem = _Problem()
        population = _population(problem)
        strategy = FCP()
        problem.t = 2
        population = strategy.response(population, problem, None)
        problem.t = 3
        population = strategy.response(population, problem, None)
        problem.evaluate_time = 0
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("evaluation rollback")):
            strategy.response(population, problem, None)
        self.assertEqual(strategy._response_count, 1)
        self.assertEqual(len(strategy._history), 1)

    def test_time_rollback_alone_resets_history(self):
        problem = _Problem()
        population = _population(problem)
        strategy = FCP()
        for problem.t in (2, 3):
            population = strategy.response(population, problem, None)
        problem.t = 1
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("time rollback")):
            strategy.response(population, problem, None)
        self.assertEqual(strategy._response_count, 1)
        self.assertEqual(len(strategy._history), 1)

    def test_repeated_first_environment_replaces_slot_and_stays_in_bootstrap(self):
        problem = _Problem()
        strategy = FCP()
        population = _population(problem)
        problem.t = 1
        population = strategy.response(population, problem, None)
        before = population.get_decision_matrix().copy()
        with patch(FCP_MODULE + ".penalty_clustering", side_effect=AssertionError("same environment")):
            strategy.response(population, problem, None)
        self.assertEqual(len(strategy._history), 1)
        np.testing.assert_array_equal(strategy._history[-1], before)

    def test_repeated_later_environment_predicts_from_distinct_prior_slot(self):
        problem = _Problem()
        strategy = FCP()
        population = _population(problem)
        problem.t = 1
        population = strategy.response(population, problem, None)
        first_environment_snapshot = strategy._history[-1].copy()
        problem.t = 2
        population = strategy.response(population, problem, None)
        repeated_input = population.get_decision_matrix().copy()
        with patch(FCP_MODULE + ".predict_centers", wraps=predict_centers) as predictor:
            strategy.response(population, problem, None)
            predictor.assert_called_once()
            np.testing.assert_array_equal(predictor.call_args.args[1], first_environment_snapshot)
        self.assertEqual(len(strategy._history), 2)
        np.testing.assert_array_equal(strategy._history[0], first_environment_snapshot)
        np.testing.assert_array_equal(strategy._history[1], repeated_input)

    def test_algorithm_seed_is_deterministic_without_touching_global_numpy_rng(self):
        problem = _Problem()
        population = _population(problem)
        left, right = FCP(), FCP()
        a = b = population
        np.random.seed(271)
        global_state = np.random.get_state()
        for time in (1, 2, 3):
            problem.t = time
            a = left.response(a, problem, SimpleNamespace(seed=17))
            b = right.response(b, problem, SimpleNamespace(seed=17))
            np.testing.assert_array_equal(a.get_decision_matrix(), b.get_decision_matrix())
            np.testing.assert_array_equal(a.get_objective_matrix(), b.get_objective_matrix())
        after = np.random.get_state()
        self.assertEqual(global_state[0], after[0])
        np.testing.assert_array_equal(global_state[1], after[1])
        self.assertEqual(global_state[2:], after[2:])
        different = FCP().response(population, problem, SimpleNamespace(seed=18))
        same = FCP().response(population, problem, SimpleNamespace(seed=17))
        self.assertFalse(np.array_equal(different.get_decision_matrix(), same.get_decision_matrix()))

    def test_none_algorithm_and_none_seed_use_same_defined_default(self):
        problem = _Problem()
        population = _population(problem)
        a = FCP().response(population, problem, None)
        b = FCP().response(population, problem, SimpleNamespace(seed=None))
        np.testing.assert_array_equal(a.get_decision_matrix(), b.get_decision_matrix())

    def test_hook_can_cancel_before_evaluation_and_keeps_state(self):
        problem = _Problem()
        population = _population(problem)
        problem.calls.clear()
        strategy = FCP()
        result = strategy.response(population, problem, SimpleNamespace(seed=8, control_process=lambda: False))
        self.assertIs(result, population)
        self.assertEqual(problem.calls, [])
        self.assertEqual(strategy._history, [])
        self.assertEqual(strategy._response_count, 0)

    def test_hook_cancels_within_clustering_without_committing_or_reevaluating(self):
        problem = _Problem()
        population = _population(problem)
        strategy = FCP()
        population = strategy.response(population, problem, None)
        history = [x.copy() for x in strategy._history]
        count = strategy._response_count
        problem.t = 1
        problem.calls.clear()
        with patch(FCP_MODULE + ".penalty_clustering", wraps=penalty_clustering) as clustered:
            calls = iter([True, True, True, False])
            result = strategy.response(population, problem,
                                      SimpleNamespace(seed=8, control_process=lambda: next(calls)))
            clustered.assert_called_once()
        self.assertIs(result, population)
        self.assertEqual(problem.calls, [])
        self.assertEqual(strategy._response_count, count)
        for before, after in zip(history, strategy._history):
            np.testing.assert_array_equal(before, after)

    def test_hook_cancels_between_evaluation_batches_and_retry_is_deterministic(self):
        problem = _Problem()
        population = _population(problem)
        strategy = FCP(evaluation_batch_size=2)
        problem.calls.clear()

        def hook():
            return not problem.calls

        result = strategy.response(population, problem, SimpleNamespace(seed=5, control_process=hook))
        self.assertIs(result, population)
        self.assertEqual(len(problem.calls), 1)
        self.assertEqual(len(problem.calls[0][0]), 2)
        self.assertEqual(strategy._response_count, 0)
        resumed = strategy.response(population, problem, SimpleNamespace(seed=5))
        fresh = FCP(evaluation_batch_size=2).response(population, problem, SimpleNamespace(seed=5))
        np.testing.assert_array_equal(resumed.get_decision_matrix(), fresh.get_decision_matrix())

    def test_hook_exceptions_propagate(self):
        problem = _Problem()
        population = _population(problem)

        def hook():
            raise InterruptedError("caller cancelled")

        with self.assertRaisesRegex(InterruptedError, "caller cancelled"):
            FCP().response(population, problem, SimpleNamespace(control_process=hook))

    def test_invalid_and_nonfinite_parameters_fail_explicitly(self):
        cases = {"cluster_num": [0, -1, 1.5, True, np.nan, np.inf],
                 "max_iter": [0, 1.5, np.nan, np.inf],
                 "evaluation_batch_size": [0, -1, np.nan, np.inf],
                 "crossover_eta": [-1, np.nan, np.inf],
                 "mutation_eta": [-1, np.nan, np.inf],
                 "diversity_floor": [-0.1, 1.1, np.nan, np.inf]}
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    FCP(**{name: value})
        problem = _Problem()
        for seed in (-1, 1.5, np.nan, np.inf):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                FCP().response(_population(problem), problem, SimpleNamespace(seed=seed))

    def test_bad_bounds_shapes_and_evaluation_values_fail_explicitly(self):
        for lower, upper in (([np.nan], [1.0]), ([2.0], [1.0]), ([0.0], [np.inf])):
            with self.assertRaises(ValueError):
                repair_bounds([[0.0]], lower, upper)
        with self.assertRaises(ValueError):
            modify_objectives([[1.0, np.nan]])
        with self.assertRaises(ValueError):
            modify_objectives([[1.0]], [[np.inf]])
        with self.assertRaises(ValueError):
            penalty_clustering(np.empty((0, 2)), np.empty((0, 2)), None, 2, np.random.default_rng(1))
        problem = _Problem()
        population = _population(problem)
        with patch.object(problem, "evaluate", return_value=(np.full((13, 2), np.nan), None)):
            with self.assertRaisesRegex(ValueError, "population objectives"):
                FCP().response(population, problem, None)

    def test_real_nsga2_dynamic_workflow_reaches_multiple_responses(self):
        problem = CDP1(decision_num=4, n=10, tau=2, solution_num=12, total_evaluate_time=4)
        problem.initial_convergence = 0
        strategy = FCP(cluster_num=3, evaluation_batch_size=4)
        algorithm = NSGA2(seed=23)
        algorithm.optimize(problem, strategy)
        self.assertGreaterEqual(strategy._response_count, 2)
        self.assertGreaterEqual(len(algorithm.history["runtime"]), 3)
        for steps in algorithm.history["runtime"].values():
            for population in steps.values():
                self.assertEqual(population.n, problem.solution_num)
                self.assertTrue(np.all(np.isfinite(population.get_objective_matrix())))


class FCPDiscoveryTests(unittest.TestCase):
    def test_metadata_config_and_existing_auto_discovery_without_registry_edits(self):
        info = json.loads((ROOT / "algorithms/response_strategy/FCP/info.json").read_text())
        config = get_dynamic_response_config("FCP")
        self.assertEqual(info["name"], "FCP")
        self.assertEqual(info["year"], 2025)
        self.assertEqual(info["doi"], "10.1109/TEVC.2025.3551399")
        self.assertEqual(set(info["parameter_labels"]), set(config))
        self.assertTrue(all(any("\u4e00" <= char <= "\u9fff" for char in text)
                            for text in info["parameter_labels"].values()))
        record = next(item for item in get_all_dynamic_strategy() if item["name"] == "FCP")
        from flexdmo_app.core import defaults, parameter_label, registered_class, records
        self.assertIs(registered_class(record), FCP)
        record = next(item for item in records()["dynamic"] if item["name"] == "FCP")
        self.assertEqual(defaults(record), config)
        self.assertEqual(parameter_label(record, "cluster_num"), "惩罚空间聚类数")
        strategy = FCP(**config)
        for name, value in config.items():
            self.assertEqual(getattr(strategy, name), value)

    def test_clean_process_import_and_response_do_not_require_sklearn_or_scipy(self):
        code = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'sklearn', 'scipy', 'torch'}:
        raise AssertionError('unexpected algorithm dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from algorithms.response_strategy.FCP.main import FCP
from components.Population import Population
from tests.test_fcp import _Problem, _population
p = _Problem()
s = FCP()
pop = _population(p)
for p.t in (1, 2, 3):
    pop = s.response(pop, p, None)
assert pop.n == p.solution_num
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
