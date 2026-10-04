"""VARE-specific numerical, response-interface, and optimizer workflows."""

import importlib
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from algorithms.response_strategy.VARE.main import (
    VARE,
    _student_t_right_tail,
    adaptive_polynomial_mutation,
    adaptive_prediction_probability,
    associate_reference,
    environment_mutation_index,
    fit_vector_autoregression,
    pca_var_predict,
    reference_directions,
    repair_bounds,
    significant_decision_change,
)
from components.Population import Population
from problems.benchmark.CDP1.main import CDP1
from problems.benchmark.CDP6.main import CDP6
from utils.information_parser import get_all_dynamic_strategy, get_dynamic_response_config


class MovingProblem:
    def __init__(self, count=8, dimensions=4, objectives=2):
        self.solution_num = count
        self.decision_num = dimensions
        self.objective_num = objectives
        self.xl = np.zeros(dimensions)
        self.xu = np.ones(dimensions)
        self.t = 0
        self.evaluated = 0
        self.calls = []

    def evaluate(self, decisions):
        x = np.asarray(decisions, dtype=float)
        self.evaluated += len(x)
        self.calls.append((self.t, len(x)))
        centers = np.linspace(0.1, 0.9, self.objective_num) + 0.03 * self.t
        f = np.column_stack([np.sum((x - center) ** 2, axis=1) for center in centers])
        g = (0.2 + 0.05 * self.t - np.sum(x, axis=1))[:, None]
        return f, g


def initial_population(problem, count=None):
    size = problem.solution_num if count is None else count
    x = np.random.default_rng(18).uniform(problem.xl, problem.xu, (size, problem.decision_num))
    population = Population(X=x, xl=problem.xl, xu=problem.xu)
    population.update_objective_constrain(problem)
    return population


class SeededAlgorithm:
    seed = 53


class VARENumericalTests(unittest.TestCase):
    def test_joint_var_recovers_cross_component_dynamics_and_intercept(self):
        transition = np.array([[0.8, -0.6], [0.6, 0.8]])
        intercept = np.array([0.1, -0.03])
        series = [np.array([0.7, -0.2])]
        for _ in range(39):
            series.append(series[-1] @ transition + intercept)
        predicted, coefficients, covariance = fit_vector_autoregression(series, 1, 0)
        np.testing.assert_allclose(coefficients[0], intercept, atol=1e-12)
        np.testing.assert_allclose(coefficients[1:], transition, atol=1e-12)
        np.testing.assert_allclose(predicted, series[-1] @ transition + intercept, atol=1e-12)
        np.testing.assert_allclose(covariance, 0, atol=1e-24)
        # Each univariate AR(1) cannot represent this cross-coupled rotation.
        self.assertGreater(abs(coefficients[1, 1]), 0.5)
        self.assertGreater(abs(coefficients[2, 0]), 0.5)

    def test_var_uses_every_lag_in_correct_order(self):
        rng = np.random.default_rng(7)
        series = rng.normal(size=(40, 3))
        predicted, coefficients, covariance = fit_vector_autoregression(series, 3)
        self.assertEqual(coefficients.shape, (10, 3))
        np.testing.assert_allclose(predicted, np.append(1.0, series[-3:][::-1].reshape(-1)) @ coefficients)
        self.assertEqual(covariance.shape, (3, 3))
        self.assertGreaterEqual(np.linalg.eigvalsh(covariance).min(), -1e-12)

    def test_temporal_pca_reconstructs_a_coupled_low_rank_trajectory(self):
        angle = np.arange(60) * 0.4
        reduced = np.column_stack((np.cos(angle), np.sin(angle)))
        mapping = np.array([[1, 0, 1, 0, 0.5, 0], [0, 1, 0, 1, 0, 0.5]])
        series = reduced @ mapping + 3.0
        predicted, rank = pca_var_predict(series, 1, 0.8, 0)
        expected = np.array([np.cos(24.0), np.sin(24.0)]) @ mapping + 3.0
        self.assertEqual(rank, 2)
        np.testing.assert_allclose(predicted, expected, atol=1e-11)

    def test_constant_and_rank_deficient_histories_are_finite(self):
        for series, rank in ((np.full((24, 6), 0.3), 0),
                             (np.arange(24)[:, None] * np.ones((1, 6)), 1)):
            with self.subTest(rank=rank):
                predicted, components = pca_var_predict(series)
                self.assertEqual(components, rank)
                self.assertTrue(np.all(np.isfinite(predicted)))
        np.testing.assert_array_equal(pca_var_predict(np.full((24, 6), 0.3))[0], np.full(6, 0.3))

    def test_t_distribution_and_degenerate_change_tests(self):
        for statistic in (0.1, 1.0, 6.313751514675):
            self.assertAlmostEqual(_student_t_right_tail(statistic, 1),
                                   0.5 - math.atan(statistic) / math.pi, places=11)
        self.assertAlmostEqual(_student_t_right_tail(1.812461122811, 10), 0.05, places=10)
        self.assertFalse(significant_decision_change(np.zeros((10, 4))))
        self.assertFalse(significant_decision_change([0.1]))
        self.assertFalse(significant_decision_change([1.0, 0.0]))
        self.assertTrue(significant_decision_change([1.0, 1.0]))

    def test_eah_does_not_confuse_objective_translation_with_ps_motion(self):
        x = np.full((10, 4), 0.2)
        f = np.zeros((10, 2))
        eta, delta_f, delta_x, significant = environment_mutation_index(x, x, f, f + 100)
        self.assertEqual(eta, 20)
        self.assertGreater(delta_f, 0)
        self.assertEqual(delta_x, 0)
        self.assertFalse(significant)

    def test_eah_combines_decision_and_objective_change_and_clamps_eta(self):
        x = np.full((10, 4), 0.2)
        f = np.ones((10, 2))
        eta, df, dx, significant = environment_mutation_index(x, x + 0.1, f, f + 1)
        self.assertTrue(significant)
        self.assertAlmostEqual(eta, 20 * np.exp(-(df + dx)))
        self.assertEqual(environment_mutation_index(x, x + 10, f, f + 100)[0], 2)

    def test_adaptation_uses_success_rates_not_raw_survival_counts(self):
        attempts = [[True, False, True], [True, False, False], [True, False, True], [False, False, False]]
        successes = [[True, False, False], [False, False, False], [False, False, False], [True, False, False]]
        probability = adaptive_prediction_probability(attempts, successes)
        self.assertAlmostEqual(probability[0], 0.25, places=6)
        self.assertEqual(probability[1], 0.5)
        self.assertEqual(probability[2], 0.5)
        np.testing.assert_allclose(adaptive_prediction_probability([[True, False]], [[True, True]]), [0.9, 0.1])

    def test_reference_grid_has_exact_size_and_simplex_sum(self):
        for n, m in ((1, 2), (2, 3), (13, 3), (17, 4), (7, 1)):
            weights = reference_directions(n, m)
            self.assertEqual(weights.shape, (n, m))
            np.testing.assert_allclose(weights.sum(axis=1), 1)
            self.assertTrue(np.all(weights >= 0))

    def test_association_is_permutation_invariant_and_feasibility_first(self):
        f = np.array([[0.2, 1], [0.5, 0.5], [1, 0.2], [0, 0]])
        x = np.arange(8).reshape(4, 2)
        w = reference_directions(3, 2)
        cv = np.array([0., 0., 0., 1.])
        indices = associate_reference(f, w, cv, x)
        self.assertNotIn(3, indices)
        permutation = np.array([2, 3, 0, 1])
        reordered = associate_reference(f[permutation], w, cv[permutation], x[permutation])
        np.testing.assert_array_equal(x[indices], x[permutation][reordered])
        self.assertEqual(associate_reference(f, w, [2., 1., 3., 4.], x).tolist(), [1, 1, 1])
        self.assertTrue(np.all(np.isfinite(associate_reference(np.ones((2, 2)), w))))

    def test_source_reflection_handles_far_outliers_nonfinite_and_fixed_bounds(self):
        x = np.array([[-0.2, 1.2, 0.5], [-100, 100, 4], [np.nan, np.inf, -np.inf]])
        repaired = repair_bounds(x, np.array([0, 0, 0.5]), np.array([1, 1, 0.5]))
        np.testing.assert_allclose(repaired[0], [0.2, 0.8, 0.5])
        self.assertTrue(np.all(np.isfinite(repaired)))
        self.assertTrue(np.all(repaired >= [0, 0, 0.5]))
        self.assertTrue(np.all(repaired <= [1, 1, 0.5]))

    def test_polynomial_mutation_stays_bounded_with_fixed_variables(self):
        x = np.full((1000, 3), 0.5)
        lower, upper = np.array([0, 0.5, 0]), np.array([1, 0.5, 1])
        result = adaptive_polynomial_mutation(x, lower, upper, 2, np.random.default_rng(3))
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertTrue(np.all(result >= lower))
        self.assertTrue(np.all(result <= upper))
        np.testing.assert_array_equal(result[:, 1], x[:, 1])
        self.assertTrue(np.any(np.any(result != x, axis=1)))
        self.assertTrue(np.any(np.all(result == x, axis=1)))

    def test_invalid_parameters_and_histories_fail_explicitly(self):
        for arguments in ({"lag_order": 0}, {"lag_order": 1.5}, {"lag_order": True},
                          {"history_length": 19}, {"explained_variance": 0},
                          {"explained_variance": np.nan}, {"regularization": -1},
                          {"regularization": np.inf}, {"history_length": np.inf}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                VARE(**arguments)
        for history in (np.ones((3, 2)), np.ones((10, 0)), [[np.nan]]):
            with self.assertRaises(ValueError):
                pca_var_predict(history)


class VAREResponseTests(unittest.TestCase):
    def assert_valid(self, population, problem):
        self.assertEqual(population.n, problem.solution_num)
        x = population.get_decision_matrix()
        self.assertEqual(x.shape, (problem.solution_num, problem.decision_num))
        self.assertTrue(np.all(np.isfinite(x)))
        self.assertTrue(np.all(x >= problem.xl))
        self.assertTrue(np.all(x <= problem.xu))
        f, g = problem.evaluate(x)
        np.testing.assert_allclose(population.get_objective_matrix(), f)
        if g is not None:
            np.testing.assert_allclose(population.get_constrain_matrix(), g)
            for ind, constraints in zip(population, g):
                violation = np.maximum(constraints, 0).sum()
                self.assertAlmostEqual(ind.constraint_violation, violation)
                self.assertEqual(ind.feasible, violation <= 1e-12)
        else:
            self.assertTrue(all(ind.G is None and ind.feasible for ind in population))
        self.assertTrue(all(ind.rank is not None for ind in population))

    def test_response_reaches_eah_linear_and_real_pca_var_stages(self):
        problem = MovingProblem()
        population = initial_population(problem)
        strategy = VARE(lag_order=1, history_length=5)
        seen = set()
        for t in range(1, 8):
            problem.t = t
            if t > 1:
                strategy._probability[:] = 1.0
            before = population.to_dict()
            population_after = strategy.response(population, problem, SeededAlgorithm())
            self.assertEqual(population.to_dict(), before)
            seen.update(strategy.last_diagnostics["modes"])
            self.assert_valid(population_after, problem)
            population = population_after
        self.assertEqual(seen, {"eah", "linear", "pca_var"})
        self.assertEqual(len(strategy._history), 5)
        self.assertEqual(len(strategy._attempts), 1)

    def test_history_is_environment_based_not_probe_or_evaluation_based(self):
        problem = MovingProblem()
        population = initial_population(problem)
        strategy = VARE(lag_order=1, history_length=4)
        problem.t = 1
        result = strategy.response(population, problem, None)
        history = [h.copy() for h in strategy._history]
        attempts = [a.copy() for a in strategy._attempts]
        problem.evaluate(result.get_decision_matrix())
        again = strategy.response(result, problem, None)
        self.assertEqual(strategy.last_diagnostics["stage"], "same_environment")
        self.assertEqual(len(strategy._history), 1)
        np.testing.assert_array_equal(strategy._history, history)
        np.testing.assert_array_equal(strategy._attempts, attempts)
        self.assert_valid(again, problem)
        problem.t = 2
        strategy.response(again, problem, None)
        self.assertEqual(len(strategy._history), 2)

    def test_default_five_lag_model_activates_only_after_twenty_environment_archives(self):
        problem = MovingProblem()
        strategy = VARE()
        observed_var = False
        for t in range(1, 25):
            # Simulate final evolved populations; the history is not a series
            # of response evaluations or copies of one initialization.
            x = (np.linspace(0.15, 0.75, problem.solution_num)[:, None]
                 + np.array([0.0, 0.03, -0.02, 0.01])[None, :]
                 + 0.06 * np.sin(t / 2.0))
            problem.t = t - 1
            population = Population(X=x, xl=problem.xl, xu=problem.xu)
            population.update_objective_constrain(problem)
            problem.t = t
            if t >= 20:
                strategy._probability[:] = 1.0  # Exercise every full VAR, not RNG luck.
            with patch("algorithms.response_strategy.VARE.main.pca_var_predict",
                       wraps=pca_var_predict) as actual_var:
                result = strategy.response(population, problem, SeededAlgorithm())
            self.assert_valid(result, problem)
            if t < 20:
                self.assertEqual(actual_var.call_count, 0)
            else:
                self.assertEqual(actual_var.call_count, problem.solution_num)
                self.assertEqual(set(strategy.last_diagnostics["modes"]), {"pca_var"})
                self.assertTrue(all(k > 0 for k in strategy.last_diagnostics["pca_components"]))
                self.assertEqual(actual_var.call_args.args[1], 5)
                self.assertEqual(len(actual_var.call_args.args[0]), t)
                observed_var = True
            if t >= strategy.lag_order:
                np.testing.assert_allclose(strategy._probability,
                                           adaptive_prediction_probability(strategy._attempts, strategy._successes))
        self.assertTrue(observed_var)
        self.assertEqual(len(strategy._history), 24)
        self.assertEqual(len(strategy._attempts), 5)

    def test_response_counts_two_population_evaluations_without_advancing_time(self):
        problem = CDP6(4, 10, 1, 8, 5)
        population = initial_population(problem)
        problem.t = 1
        problem.initial_convergence = 0
        problem.need_change = True
        before = problem.evaluate_time
        strategy = VARE()
        result = strategy.response(population, problem, None)
        self.assertEqual(problem.t, 1)
        self.assertEqual(problem.evaluate_time - before, 2 * problem.solution_num)
        self.assertTrue(problem.need_change)
        self.assert_valid(result, problem)
        self.assertEqual(problem.t, 1)

    def test_empty_small_and_mismatched_population_sizes(self):
        for count, incoming, dimensions in ((1, 0, 1), (1, 1, 1), (2, 1, 4), (5, 9, 4)):
            with self.subTest(count=count, incoming=incoming):
                problem = MovingProblem(count=count, dimensions=dimensions)
                population = initial_population(problem, incoming)
                problem.t = 1
                result = VARE().response(population, problem, None)
                self.assert_valid(result, problem)

    def test_constant_objectives_decisions_and_all_fixed_bounds(self):
        problem = MovingProblem(count=2, dimensions=2)
        problem.xl[:] = problem.xu[:] = 0.3
        population = initial_population(problem)
        strategy = VARE(lag_order=1, history_length=4)
        for t in range(1, 7):
            problem.t = t
            if t > 1:
                strategy._probability[:] = 1
            population = strategy.response(population, problem, None)
            self.assert_valid(population, problem)
        self.assertEqual(strategy.last_diagnostics["pca_components"], [0, 0])
        self.assertEqual(strategy.last_diagnostics["eta"], 20)

    def test_seeded_response_is_reproducible_and_accepts_seed_none(self):
        trajectories = []
        for _ in range(2):
            problem = MovingProblem()
            population = initial_population(problem)
            strategy = VARE(lag_order=1, history_length=4)
            for t in range(1, 5):
                problem.t = t
                population = strategy.response(population, problem, SeededAlgorithm())
            trajectories.append(population.get_decision_matrix())
        np.testing.assert_array_equal(*trajectories)
        problem = MovingProblem()
        algorithm = SeededAlgorithm()
        algorithm.seed = None
        self.assert_valid(VARE().response(initial_population(problem), problem, algorithm), problem)

    def test_reusing_strategy_resets_on_new_problem_backward_time_and_bounds(self):
        strategy = VARE(lag_order=1, history_length=4)
        problem = MovingProblem()
        population = initial_population(problem)
        for t in (1, 2):
            problem.t = t
            population = strategy.response(population, problem, None)
        problem.t = 0
        population = strategy.response(population, problem, None)
        self.assertEqual(len(strategy._history), 1)
        problem.xu[:] = 0.8
        problem.t = 1
        population = strategy.response(population, problem, None)
        self.assertEqual(len(strategy._history), 1)
        other = MovingProblem(count=3, dimensions=5, objectives=3)
        result = strategy.response(initial_population(other), other, None)
        self.assertEqual(len(strategy._history), 1)
        self.assert_valid(result, other)

    def test_unevaluated_and_nonfinite_inputs_are_repaired_and_reevaluated(self):
        problem = MovingProblem()
        x = np.full((problem.solution_num, problem.decision_num), 0.5)
        x[0] = [np.nan, np.inf, -np.inf, 10.0]
        population = Population(X=x, xl=problem.xl, xu=problem.xu)
        strategy = VARE()
        result = strategy.response(population, problem, None)
        self.assertFalse(strategy.last_diagnostics["old_baseline_known"])
        self.assert_valid(result, problem)
        self.assertTrue(np.isnan(population[0].X[0]))
        self.assertIsNone(population[0].F)

    def test_var_numerical_failure_has_a_finite_linear_fallback(self):
        problem = MovingProblem()
        population = initial_population(problem)
        strategy = VARE(lag_order=1, history_length=4)
        for t in range(1, 5):
            problem.t = t
            if t > 1:
                strategy._probability[:] = 1
            with patch("algorithms.response_strategy.VARE.main.pca_var_predict",
                       side_effect=np.linalg.LinAlgError("test")):
                population = strategy.response(population, problem, None)
        self.assertEqual(set(strategy.last_diagnostics["modes"]), {"linear"})
        self.assert_valid(population, problem)

    def test_raw_constraints_and_feasibility_are_refreshed_on_constraint_only_change(self):
        class ConstraintProblem(MovingProblem):
            def evaluate(self, decisions):
                x = np.asarray(decisions)
                return np.ones((len(x), 2)), np.full((len(x), 2), 1.0 if self.t else -1.0)

        problem = ConstraintProblem()
        population = initial_population(problem)
        old = population.to_dict()
        problem.t = 1
        result = VARE().response(population, problem, None)
        self.assertTrue(all(not ind.feasible and ind.constraint_violation == 2 for ind in result))
        self.assert_valid(result, problem)
        self.assertEqual(population.to_dict(), old)

    def test_nonfinite_evaluations_and_invalid_geometry_are_rejected(self):
        problem = MovingProblem()
        population = initial_population(problem)
        problem.xl[0] = np.nan
        with self.assertRaises(ValueError):
            VARE().response(population, problem, None)
        problem.xl[0] = 0
        with patch.object(problem, "evaluate", return_value=(np.full((8, 2), np.nan), None)):
            with self.assertRaises(ValueError):
                VARE().response(population, problem, None)

    def test_info_config_defaults_labels_and_existing_discovery(self):
        record = next(record for record in get_all_dynamic_strategy() if record["name"] == "VARE")
        self.assertEqual(record["year"], 2026)
        config = get_dynamic_response_config("VARE")
        strategy = VARE(**config)
        for key, value in config.items():
            self.assertEqual(getattr(strategy, key), value)
        info = json.loads((Path(record["folder_name"]) / "info.json").read_text())
        self.assertEqual(set(config), set(info["parameter_labels"]))
        self.assertTrue(all(any("\u4e00" <= c <= "\u9fff" for c in label)
                            for label in info["parameter_labels"].values()))

    def test_stop_at_response_entry_consumes_no_evaluations_or_history(self):
        problem = MovingProblem()
        population = initial_population(problem)
        algorithm = SeededAlgorithm()
        algorithm.control_process = lambda: False
        before = problem.evaluated
        strategy = VARE()
        result = strategy.response(population, problem, algorithm)
        self.assertEqual(problem.evaluated, before)
        self.assertEqual(strategy._history, [])
        self.assertEqual(result.to_dict(), population.to_dict())
        self.assertIsNot(result, population)

    def test_stop_between_evaluation_batches_consumes_no_further_evaluations(self):
        problem = MovingProblem(count=130)
        population = initial_population(problem)
        algorithm = SeededAlgorithm()
        running = [True]
        algorithm.control_process = lambda: running[0]
        original_evaluate = problem.evaluate

        def stop_after_batch(x):
            f, g = original_evaluate(x)
            running[0] = False
            return f, g

        before = problem.evaluated
        strategy = VARE()
        with patch.object(problem, "evaluate", side_effect=stop_after_batch):
            result = strategy.response(population, problem, algorithm)
        self.assertEqual(problem.evaluated - before, 64)
        self.assertEqual(strategy._history, [])
        self.assertEqual(strategy._attempts, [])
        self.assertIsNone(strategy._last_time)
        self.assertEqual(result.to_dict(), population.to_dict())

    def test_stop_between_var_directions_rolls_back_state_and_does_not_evaluate_offspring(self):
        problem = MovingProblem()
        population = initial_population(problem)
        strategy = VARE(lag_order=1, history_length=4)
        algorithm = SeededAlgorithm()
        running = [True]
        algorithm.control_process = lambda: running[0]
        for t in range(1, 4):
            problem.t = t
            population = strategy.response(population, problem, algorithm)
        problem.t = 4
        strategy._probability[:] = 1
        history = [h.copy() for h in strategy._history]
        attempts = [a.copy() for a in strategy._attempts]
        diagnostics = dict(strategy.last_diagnostics)
        rng_state = dict(strategy._rng.bit_generator.state)
        before = problem.evaluated

        def stop_after_var(*args):
            result = pca_var_predict(*args)
            running[0] = False
            return result

        with patch("algorithms.response_strategy.VARE.main.pca_var_predict", side_effect=stop_after_var) as mocked:
            result = strategy.response(population, problem, algorithm)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(problem.evaluated - before, problem.solution_num)
        np.testing.assert_array_equal(strategy._history, history)
        np.testing.assert_array_equal(strategy._attempts, attempts)
        self.assertEqual(strategy._last_time, 3)
        self.assertEqual(strategy.last_diagnostics, diagnostics)
        self.assertEqual(strategy._rng.bit_generator.state, rng_state)
        self.assertEqual(result.to_dict(), population.to_dict())

    def test_all_current_static_optimizers_complete_dynamic_constrained_and_unconstrained_runs(self):
        class RecordingVARE(VARE):
            def __init__(self):
                super().__init__(lag_order=1, history_length=8)
                self.responses = []

            def response(self, population, problem, algorithm):
                result = super().response(population, problem, algorithm)
                self.responses.append((problem.t, result.copy(), dict(self.last_diagnostics)))
                return result

        for name in ("NSGA2", "MOEAD", "SPEA2", "RMMEDA"):
            for problem_class in (CDP1, CDP6):
                with self.subTest(optimizer=name, problem=problem_class.__name__):
                    optimizer_class = getattr(importlib.import_module(f"algorithms.search_algorithm.{name}.main"), name)
                    algorithm = optimizer_class(seed=19)
                    problem = problem_class(4, 10, 3, 12, 7)
                    problem.initial_convergence = 24
                    strategy = RecordingVARE()
                    algorithm.optimize(problem, strategy)
                    self.assertTrue(problem.is_ended())
                    self.assertEqual(list(algorithm.history["runtime"]), list(range(7)))
                    self.assertEqual([t for t, _, _ in strategy.responses], list(range(1, 7)))
                    self.assertEqual(len(strategy._history), 6)
                    for t, population, diagnostics in strategy.responses:
                        f, g = problem.evaluate(population.get_decision_matrix(), need_count=False, t=t)
                        np.testing.assert_allclose(population.get_objective_matrix(), f)
                        if g is not None:
                            np.testing.assert_allclose(population.get_constrain_matrix(), g)
                        self.assertEqual(population.n, 12)
                        self.assertTrue(all(ind.rank is not None for ind in population))
                        self.assertEqual(diagnostics["history_size"], t)
                        self.assertTrue(np.all(np.isfinite(diagnostics["prediction_probability"])))
                    self.assertEqual(algorithm.history["settings"]["response_strategy_class"], "RecordingVARE")


if __name__ == "__main__":
    unittest.main()
