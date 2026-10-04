import inspect
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import numpy as np

from algorithms.response_strategy.ADPS import ADPS
from algorithms.response_strategy.ADPS.main import (
    _prefer, derivative_displacement, online_centers, prediction_noise,
)
from algorithms.search_algorithm.Algorithm import Algorithm
from algorithms.search_algorithm.MOEAD.main import MOEAD
from algorithms.search_algorithm.NSGA2.main import NSGA2
from algorithms.search_algorithm.RMMEDA.main import RMMEDA
from algorithms.search_algorithm.SPEA2.main import SPEA2
from components.Population import Population
from problems.Problem import Problem
from problems.benchmark.CDP1.main import CDP1
from problems.benchmark.DF1.main import DF1
from utils.evolution_tools import detection, quick_non_dominate_sort


class ProbeProblem(Problem):
    """Actual framework counting/time semantics, inspectable raw evaluations."""

    def __init__(self, size=10, dimensions=2, objectives=2, constrained=False,
                 constant=False):
        super().__init__(dimensions, objectives, int(constrained), 10, 1,
                         size, 8, "ADPS-test")
        self.constant = constant
        self.calls = []

    def evaluate(self, X, need_count=True, t=None):
        self.calls.append((len(np.atleast_2d(X)), need_count, t, self.t))
        return super().evaluate(X, need_count=need_count, t=t)

    def _evaluate_objectives(self, X, t):
        if self.constant:
            return np.ones((len(X), self.n_obj))
        first = X[:, 0] + 0.01 * t
        columns = [first, 1.0 - X[:, 0] + 0.01 * t]
        columns.extend(X[:, index % self.decision_num] ** 2
                       for index in range(2, self.n_obj))
        return np.column_stack(columns[:self.n_obj])

    def _evaluate_constraints(self, X, t):
        return (0.6 - X[:, 0])[:, None] if self.n_con else None


class Hook:
    seed = 17

    def __init__(self, stop_after=None):
        self.calls = 0
        self.stop_after = stop_after

    def control_process(self):
        self.calls += 1
        return self.stop_after is None or self.calls < self.stop_after


def initial_population(problem, count=None):
    count = problem.solution_num if count is None else count
    if not count:
        return Population(xl=problem.xl, xu=problem.xu)
    X = np.random.default_rng(4).uniform(problem.xl, problem.xu,
                                         (count, problem.decision_num))
    population = Population(X=X, xl=problem.xl, xu=problem.xu)
    population.update_objective_constrain(problem)
    return population


class ADPSMechanismTests(unittest.TestCase):
    def test_inverse_preference_covers_all_four_constraint_cases(self):
        cases = (
            # Feasible wins even with a much larger objective distance.
            (0., 100., 1., 0., True),
            # Infeasible cannot displace a feasible point even at the target.
            (1., 0., 0., 100., False),
            # Two infeasible points compare CV, not Euclidean distance.
            (1., 100., 2., 0., True),
            (2., 0., 1., 100., False),
            (1., 0., 1., 100., False),
            # Two feasible points compare Euclidean distance only.
            (0., 1., 0., 2., True),
            (0., 2., 0., 1., False),
            (0., 1., 0., 1., False),
            # Both tiny positive CVs are feasible under the shared tolerance.
            (1e-13, 1., 0., 2., True),
            (0., 2., 1e-13, 1., False),
        )
        for number_type in (float, np.float64):
            for candidate_cv, candidate_dist, current_cv, current_dist, expected in cases:
                with self.subTest(number_type=number_type, case=(candidate_cv, current_cv)):
                    actual = _prefer(*map(number_type, (candidate_cv, candidate_dist,
                                                       current_cv, current_dist)))
                    self.assertEqual(bool(actual), expected)

    def test_online_clustering_retains_extreme_slots_and_finite_means(self):
        F = np.array([[0., 1.], [.5, .5], [1., 0.]])
        centers, labels = online_centers(F, F)
        self.assertEqual(centers.shape, (3, 2))
        np.testing.assert_allclose(centers[1], [0, 1])
        np.testing.assert_allclose(centers[2], [1, 0])
        for label in np.unique(labels):
            np.testing.assert_allclose(centers[label], F[labels == label].mean(0))

    def test_online_labels_follow_translation_across_environments(self):
        X = np.array([[0., 2.], [1., 1.], [2., 0.]])
        centers, labels = online_centers(X, X)
        shifted, shifted_labels = online_centers(X + 4, X + 4, centers)
        np.testing.assert_allclose(shifted, centers + 4)
        np.testing.assert_array_equal(shifted_labels, labels)

    def test_duplicate_centers_and_singletons_are_not_singular(self):
        for count in (1, 2, 8):
            centers, labels = online_centers(np.ones((count, 4)),
                                             np.ones((count, 3)))
            self.assertEqual(centers.shape, (4, 4))
            np.testing.assert_allclose(centers, 1)
            self.assertTrue(np.all(np.isfinite(labels)))

    def test_second_derivative_changes_prediction_not_just_linear_velocity(self):
        history = np.array([0., 1., 3.])[:, None, None]
        shift, reversal = derivative_displacement(history)
        np.testing.assert_allclose(shift, [[3.]])  # velocity 2 + acceleration 1
        self.assertFalse(reversal.any())

    def test_sine_reversal_uses_declining_weighted_accelerations(self):
        # Accelerations 0, 1, 0: sine differences have negative inner product.
        history = np.array([0., 0., 0., 1., 2.])[:, None, None]
        shift, reversal = derivative_displacement(history)
        self.assertTrue(reversal[0])
        np.testing.assert_allclose(shift, [[1.3]])  # velocity 1 + 0.3 * 1

    def test_stable_acceleration_is_not_smoothed(self):
        history = np.array([0., 1., 3., 6., 10.])[:, None, None]
        shift, reversal = derivative_displacement(history)
        np.testing.assert_allclose(shift, [[5.]])
        self.assertFalse(reversal.any())

    def test_short_and_constant_derivative_histories_are_finite(self):
        for count in range(1, 6):
            shift, reversal = derivative_displacement(np.ones((count, 3, 4)))
            np.testing.assert_allclose(shift, 0)
            self.assertFalse(reversal.any())

    def test_equation10_noise_bound_and_zero_distance_guard(self):
        X, previous = np.array([[1., 0.], [2., 0.]]), np.zeros((2, 2))
        noise = prediction_noise(X, previous, np.random.default_rng(6))
        self.assertTrue(np.all(np.linalg.norm(noise, axis=1) < [0.5, 1.]))
        self.assertTrue(np.all(np.linalg.norm(noise, axis=1) > 0))
        np.testing.assert_allclose(prediction_noise(X, X, np.random.default_rng(6)), 0)

    def test_invalid_parameters_and_helper_inputs_fail_early(self):
        cases = [dict(weight_step=-1), dict(weight_step=np.nan),
                 dict(cluster_passes=0), dict(cluster_passes=1.5),
                 dict(inverse_iterations=0), dict(inverse_iterations=np.inf),
                 dict(inverse_step=0), dict(inverse_step=2),
                 dict(perturbation_scale=-1), dict(perturbation_scale=np.nan),
                 dict(evaluation_batch_size=0)]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ADPS(**kwargs)
        with self.assertRaises(ValueError):
            online_centers(np.empty((0, 2)), np.empty((0, 2)))
        with self.assertRaises(ValueError):
            derivative_displacement(np.ones((3, 2)))


class ADPSResponseTests(unittest.TestCase):
    def assert_valid(self, population, problem):
        self.assertEqual(population.n, problem.solution_num)
        X = population.get_decision_matrix()
        self.assertEqual(X.shape, (problem.solution_num, problem.decision_num))
        self.assertTrue(np.all(X >= problem.xl))
        self.assertTrue(np.all(X <= problem.xu))
        self.assertTrue(np.all(np.isfinite(population.get_objective_matrix())))
        for individual in population:
            self.assertIsNotNone(individual.rank)
            violation = 0 if individual.G is None else np.maximum(individual.G, 0).sum()
            self.assertAlmostEqual(individual.constraint_violation, violation)
            self.assertEqual(individual.feasible, violation <= 1e-12)

    def test_cold_start_retains_ninety_percent_and_counts_exactly(self):
        problem = ProbeProblem()
        population = initial_population(problem)
        before = population.to_dict()
        old_count = problem.evaluate_time
        problem.t = 1
        strategy = ADPS()
        result = strategy.response(population, problem, Hook())
        self.assert_valid(result, problem)
        parents = population.get_decision_matrix()
        reused = sum(any(np.array_equal(ind.X, row) for row in parents) for ind in result)
        self.assertEqual(reused, 9)
        self.assertEqual(problem.evaluate_time - old_count, 10)
        self.assertEqual(population.to_dict(), before)
        np.testing.assert_allclose(strategy._history[0][1], population.get_objective_matrix())

    def test_empty_undersized_and_oversized_inputs_keep_target_size(self):
        for count in (0, 1, 3, 18):
            with self.subTest(count=count):
                problem = ProbeProblem()
                result = ADPS().response(initial_population(problem, count), problem, None)
                self.assert_valid(result, problem)

    def test_dual_domain_stage_counts_all_trials_without_advancing_time(self):
        problem = ProbeProblem(constrained=True)
        population = initial_population(problem)
        strategy = ADPS(inverse_iterations=4, evaluation_batch_size=3)
        for time in range(1, 7):
            problem.t = time
            problem.need_change = True
            old_count, call_start = problem.evaluate_time, len(problem.calls)
            original = population.to_dict()
            result = strategy.response(population, problem, Hook())
            self.assert_valid(result, problem)
            self.assertEqual(population.to_dict(), original)
            self.assertEqual(problem.t, time)
            self.assertTrue(problem.need_change)
            calls = problem.calls[call_start:]
            self.assertTrue(all(need_count and t == time for _, need_count, _, t in calls))
            expected = problem.solution_num + strategy.last_inverse_evaluations
            self.assertEqual(problem.evaluate_time - old_count, expected)
            self.assertEqual(sum(call[0] for call in calls), expected)
            if time >= 3:
                d, o = strategy.last_allocation
                self.assertEqual(d + o, problem.solution_num)
                self.assertGreater(d, 0)
                self.assertGreater(o, 0)
                self.assertEqual(strategy.last_inverse_evaluations, 2 * o * 4)
            population = result
        self.assertEqual(len(strategy._history), 5)

    def test_default_mapping_cost_is_four_n_not_twenty_one_n(self):
        problem = ProbeProblem(size=8)
        problem.change_each_evaluations = 10 * problem.solution_num
        strategy = ADPS(perturbation_scale=0)
        population = initial_population(problem)
        for t in (1, 2, 3):
            problem.t = t
            before = problem.evaluate_time
            population = strategy.response(population, problem, Hook())
        self.assertEqual(strategy.inverse_iterations, 3)
        self.assertEqual(strategy.last_allocation, (4, 4))
        self.assertEqual(strategy.last_inverse_iterations, 3)
        self.assertEqual(problem.evaluate_time - before, 4 * problem.solution_num)
        self.assertFalse(strategy.last_budget_limited)

    def test_small_tau_caps_inverse_iterations_and_reserves_static_generation(self):
        problem = ProbeProblem(size=8)
        problem.change_each_evaluations = 3 * problem.solution_num
        problem.initial_convergence = 0
        population = initial_population(problem)
        strategy = ADPS(inverse_iterations=20, perturbation_scale=0)
        for t in (1, 2, 3):
            problem.t = t
            # Arrange actual detector-boundary state, with no hidden free call.
            problem.evaluate_time = t * problem.change_each_evaluations
            before = problem.evaluate_time
            population = strategy.response(population, problem, Hook())
        self.assertTrue(strategy.last_budget_limited)
        self.assertEqual(strategy.last_inverse_iterations, 1)
        self.assertEqual(problem.evaluate_time - before, 2 * problem.solution_num)
        self.assertEqual(problem.t, 3)
        self.assertLessEqual(problem.evaluate_time - before,
                             problem.change_each_evaluations - problem.solution_num)

    def test_insufficient_small_tau_budget_uses_counted_ninety_ten_fallback(self):
        for tau in (1, 2):
            with self.subTest(tau=tau):
                problem = ProbeProblem(size=10)
                problem.change_each_evaluations = tau * problem.solution_num
                problem.initial_convergence = 0
                population = initial_population(problem)
                strategy = ADPS(inverse_iterations=20)
                for t in range(1, 5):
                    problem.t = t
                    problem.evaluate_time = t * problem.change_each_evaluations
                    before = problem.evaluate_time
                    parents = population.get_decision_matrix().copy()
                    population = strategy.response(population, problem, Hook())
                    self.assertEqual(problem.evaluate_time - before, problem.solution_num)
                    self.assertLessEqual(problem.evaluate_time - before,
                                         problem.change_each_evaluations)
                    self.assertEqual(problem.t, t)
                self.assertEqual(len(strategy._history), 4)
                self.assertTrue(strategy.last_budget_limited)
                self.assertEqual(strategy.last_inverse_evaluations, 0)
                self.assertEqual(strategy.last_allocation, (10, 0))
                self.assertEqual(sum(any(np.array_equal(ind.X, row) for row in parents)
                                     for ind in population), 9)

    def test_budget_cap_accounts_for_overshoot_and_objective_quota(self):
        problem = ProbeProblem(size=8)
        problem.change_each_evaluations = 24
        problem.initial_convergence = 0
        problem.evaluate_time = 25  # One row past the detector boundary.
        self.assertEqual(ADPS._mapping_budget(problem), 7)
        strategy = ADPS(inverse_iterations=20, perturbation_scale=0)
        population = initial_population(problem)
        for t in (1, 2):
            problem.t = t
            problem.evaluate_time = 24 * t
            population = strategy.response(population, problem, Hook())
        strategy.decision_weight, strategy.objective_weight = .1, .9
        problem.t, problem.evaluate_time = 3, 73
        before = problem.evaluate_time
        population = strategy.response(population, problem, Hook())
        # Available seven map rows limit seven desired objective seeds to three.
        self.assertEqual(strategy.last_allocation, (5, 3))
        self.assertEqual(strategy.last_inverse_iterations, 1)
        self.assertEqual(problem.evaluate_time - before, 14)
        self.assertTrue(strategy.last_budget_limited)

    def test_inverse_mapping_improves_objective_distance_and_counts_trials(self):
        problem = ProbeProblem(dimensions=1)
        strategy = ADPS(inverse_iterations=8)
        pool = Population(X=np.array([[.2]]), xl=problem.xl, xu=problem.xu)
        pool.update_objective_constrain(problem)
        target = np.array([[.8, .2]])
        before = problem.evaluate_time
        problem.need_change = True
        result, used = strategy._inverse_map(target, pool, problem, Hook())
        self.assertLess(np.linalg.norm(result[0].F - target[0]), 1e-10)
        self.assertEqual(used, 16)
        self.assertEqual(problem.evaluate_time - before, used)
        self.assertEqual(problem.t, 0)
        self.assertTrue(problem.need_change)

    def test_nonlinear_inverse_mapping_really_optimizes_not_lookup_only(self):
        class Nonlinear(ProbeProblem):
            def _evaluate_objectives(self, X, t):
                return np.column_stack((X[:, 0] ** 2, 1 - X[:, 0] ** 2))
        problem = Nonlinear(dimensions=1)
        pool = initial_population(problem, 1)
        strategy = ADPS(inverse_iterations=20)
        target = np.array([[.64, .36]])
        result, _ = strategy._inverse_map(target, pool, problem, Hook())
        self.assertLess(np.linalg.norm(result[0].F - target[0]),
                        np.linalg.norm(pool[0].F - target[0]) / 100)

    def test_inverse_mapping_respects_raw_constraints_over_distance(self):
        for start in (.2, .8):
            with self.subTest(start=start):
                problem = ProbeProblem(dimensions=1, constrained=True)
                pool = Population(X=np.array([[start]]), xl=problem.xl, xu=problem.xu)
                pool.update_objective_constrain(problem)
                mapped, _ = ADPS(inverse_iterations=12)._inverse_map(
                    np.array([[.1, .9]]), pool, problem, Hook())
                self.assertTrue(mapped[0].feasible)
                self.assertGreaterEqual(mapped[0].X[0], .6 - 1e-12)
                self.assertIsNotNone(mapped[0].G)

    def test_domain_contributions_change_weights_after_static_search(self):
        problem = ProbeProblem()
        strategy = ADPS(weight_step=.02, perturbation_scale=0)
        population = initial_population(problem)
        for t in (1, 2, 3):
            problem.t = t
            population = strategy.response(population, problem, Hook())
        strategy._origins = (np.array([[0., 0.], [1., 1.]]), np.array([0, 1]))
        # Stand-in for optimizer-produced nondominated points; no metadata.
        population = Population(X=np.full((10, 2), .9), F=np.tile([.9, .1], (10, 1)),
                                xl=problem.xl, xu=problem.xu)
        problem.t = 4
        strategy.response(population, problem, Hook())
        self.assertEqual(strategy.last_domain_counts, (0., 10.))
        self.assertAlmostEqual(strategy.objective_weight, .52 / 1.02)
        self.assertAlmostEqual(strategy.decision_weight + strategy.objective_weight, 1.)

    def test_attribution_ties_and_constraints_are_not_biased_by_duplicates(self):
        problem = ProbeProblem(constrained=True)
        strategy = ADPS()
        strategy._origins = (np.array([[.5, .5], [.5, .5], [.5, .5]]),
                             np.array([0, 0, 1]))
        population = Population(X=np.array([[.2, .5], [.8, .5]]),
                                xl=problem.xl, xu=problem.xu)
        population.update_objective_constrain(problem)
        quick_non_dominate_sort(population)
        self.assertEqual(strategy._domain_counts(population, problem, Hook()), (.5, .5))

    def test_singleton_constant_and_fixed_bounds_survive_prediction(self):
        for size in (1, 2, 10):
            with self.subTest(size=size):
                problem = ProbeProblem(size=size, objectives=3, constant=True)
                problem.xl[1] = problem.xu[1] = .5
                population = initial_population(problem)
                strategy = ADPS(inverse_iterations=3)
                for t in range(1, 7):
                    problem.t = t
                    population = strategy.response(population, problem, Hook())
                    self.assert_valid(population, problem)
                    np.testing.assert_allclose(population.get_decision_matrix()[:, 1], .5)

    def test_multiobjective_prediction_and_negative_objectives_are_supported(self):
        class Negative(ProbeProblem):
            def _evaluate_objectives(self, X, t):
                return super()._evaluate_objectives(X, t) - 2.
        problem = Negative(objectives=3)
        strategy = ADPS(inverse_iterations=3)
        population = initial_population(problem)
        for t in range(1, 5):
            problem.t = t
            population = strategy.response(population, problem, Hook())
            self.assert_valid(population, problem)
        self.assertEqual(strategy._history[-1][3].shape, (4, 3))
        self.assertTrue(np.all(population.get_objective_matrix() < 0))

    def test_repeat_response_does_not_invent_history_and_reset_clears_it(self):
        problem = ProbeProblem()
        strategy = ADPS(inverse_iterations=2)
        population = initial_population(problem)
        for t in range(1, 5):
            problem.t = t
            population = strategy.response(population, problem, Hook())
        strategy.response(population, problem, Hook())
        self.assertEqual(len(strategy._history), 4)
        problem.reset()
        population = initial_population(problem)
        strategy.response(population, problem, Hook())
        self.assertEqual(len(strategy._history), 1)
        self.assertEqual(strategy.decision_weight, .5)
        self.assertIsNone(strategy._origins)
        other = ProbeProblem(dimensions=3, objectives=3)
        strategy.response(initial_population(other), other, Hook())
        self.assertEqual(len(strategy._history), 1)
        self.assertEqual(strategy._history[0][2].shape, (4, 3))

    def test_response_is_reproducible_for_equal_algorithm_seeds(self):
        outputs = []
        for _ in range(2):
            problem = ProbeProblem()
            strategy = ADPS(inverse_iterations=2)
            population = initial_population(problem)
            for t in range(1, 5):
                problem.t = t
                population = strategy.response(population, problem, Hook())
            outputs.append(population.get_decision_matrix())
        np.testing.assert_array_equal(*outputs)

    def test_stop_before_response_consumes_no_evaluations_or_state(self):
        problem = ProbeProblem()
        population = initial_population(problem)
        old_count = problem.evaluate_time
        strategy = ADPS()
        result = strategy.response(population, problem, Hook(stop_after=1))
        self.assertEqual(problem.evaluate_time, old_count)
        self.assertEqual(result.to_dict(), population.to_dict())
        self.assertEqual(strategy._history, [])

    def test_stop_during_inverse_trials_does_not_publish_partial_state(self):
        problem = ProbeProblem()
        population = initial_population(problem)
        strategy = ADPS(inverse_iterations=20, evaluation_batch_size=2)
        for t in (1, 2):
            problem.t = t
            population = strategy.response(population, problem, Hook())
        problem.t = 3
        before = problem.evaluate_time
        class StopAfterRows(Hook):
            def control_process(self):
                return problem.evaluate_time - before < problem.solution_num + 2
        result = strategy.response(population, problem, StopAfterRows())
        self.assertEqual(problem.evaluate_time - before, problem.solution_num + 2)
        self.assertEqual(len(strategy._history), 2)
        self.assertEqual(result.to_dict(), population.to_dict())
        self.assertIsNone(strategy._origins)
        self.assertEqual(problem.t, 3)

    def test_pause_uses_existing_control_hook_and_resumes(self):
        problem = ProbeProblem()
        population = initial_population(problem)
        state = type("State", (), {"value": "pause"})()
        algorithm = Algorithm(state=state, seed=3)
        entered = threading.Event()
        def resume(_):
            entered.set()
            state.value = "running"
        with patch("algorithms.search_algorithm.Algorithm.time.sleep", resume):
            result = ADPS().response(population, problem, algorithm)
        self.assertTrue(entered.is_set())
        self.assert_valid(result, problem)

    def test_false_evaluation_advances_environment_but_adps_never_uses_it(self):
        problem = ProbeProblem()
        population = initial_population(problem)
        problem.need_change = True
        before = problem.evaluate_time
        self.assertEqual(detection(population, problem, 1), 1)
        self.assertEqual(problem.t, 1)
        self.assertEqual(problem.evaluate_time, before)
        self.assertFalse(problem.calls[-1][1])
        call_start = len(problem.calls)
        ADPS().response(population, problem, Hook())
        self.assertTrue(all(call[1] for call in problem.calls[call_start:]))
        self.assertEqual(problem.t, 1)


class ADPSIntegrationTests(unittest.TestCase):
    def test_discovery_defaults_and_chinese_parameter_labels(self):
        from flexdmo_app.core import records, registered_class, parameter_label
        from utils.information_parser import get_dynamic_response_config
        record = next(item for item in records()["dynamic"] if item["name"] == "ADPS")
        self.assertEqual(record["year"], 2026)
        self.assertIs(registered_class(record), ADPS)
        config = get_dynamic_response_config("ADPS")
        parameters = inspect.signature(ADPS).parameters
        self.assertEqual(config, {key: spec.default for key, spec in parameters.items()})
        self.assertEqual(set(record["parameter_labels"]), set(config))
        for key in config:
            self.assertNotEqual(parameter_label(record, key), key)
        self.assertIsInstance(ADPS(**config), ADPS)

    def test_import_does_not_require_optional_global_dependencies(self):
        script = """
import builtins
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'scipy', 'sklearn', 'torch', 'tensorflow'}:
        raise AssertionError('Optional dependency imported: ' + name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
from algorithms.response_strategy.ADPS import ADPS
ADPS()
"""
        result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                text=True, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_four_static_optimizers_on_constrained_and_unconstrained_problems(self):
        for optimizer in (NSGA2, MOEAD, SPEA2, RMMEDA):
            for problem_class in (DF1, CDP1):
                with self.subTest(optimizer=optimizer.__name__, problem=problem_class.__name__):
                    problem = problem_class(decision_num=4, n=10, tau=10,
                                            solution_num=10, total_evaluate_time=6)
                    problem.initial_convergence = 0
                    strategy = ADPS(inverse_iterations=2, perturbation_scale=.1)
                    algorithm = optimizer(seed=5)
                    algorithm.optimize(problem, strategy)
                    self.assertTrue(problem.is_ended())
                    self.assertEqual(problem.t, 5)
                    self.assertEqual(set(algorithm.history["runtime"]), set(range(6)))
                    self.assertEqual(len(strategy._history), 5)
                    self.assertGreater(strategy.last_inverse_evaluations, 0)
                    self.assertEqual(strategy.last_inverse_iterations, 2)
                    self.assertFalse(strategy.last_budget_limited)
                    for snapshots in algorithm.history["runtime"].values():
                        for population in snapshots.values():
                            self.assertEqual(population.n, problem.solution_num)
                            self.assertTrue(np.all(np.isfinite(population.get_objective_matrix())))
                            if problem.n_con:
                                self.assertTrue(all(ind.G is not None for ind in population))


if __name__ == "__main__":
    unittest.main()
