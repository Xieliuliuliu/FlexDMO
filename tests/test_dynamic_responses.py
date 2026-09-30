import unittest

import numpy as np

from algorithms.response_strategy.DNSGAIIA.main import DNSGAIIA
from algorithms.response_strategy.DNSGAIIB.main import DNSGAIIB
from algorithms.response_strategy.dynamic_nsga2 import polynomial_mutation
from algorithms.search_algorithm.NSGA2.main import NSGA2
from components.Population import Population
from problems.benchmark.CDP6.main import CDP6
from views.test_module.test_module_handler import build_replay_timeline


class RecordingPipe:
    def __init__(self):
        self.frames = []

    def send(self, information):
        self.frames.append(information)


class DynamicResponseTests(unittest.TestCase):
    def build_problem(self):
        return CDP6(
            decision_num=5,
            n=10,
            tau=2,
            solution_num=20,
            total_evaluate_time=3,
        )

    def build_population(self, problem):
        population = Population(
            xl=problem.xl,
            xu=problem.xu,
            n_init=problem.solution_num,
        )
        population.update_objective_constrain(problem)
        problem.t = 1
        return population

    def assert_valid_response(self, population, problem):
        self.assertEqual(population.n, problem.solution_num)
        decisions = population.get_decision_matrix()
        objectives = population.get_objective_matrix()
        constraints = population.get_constrain_matrix()
        self.assertEqual(decisions.shape, (problem.solution_num, 5))
        self.assertEqual(objectives.shape, (problem.solution_num, 2))
        self.assertEqual(
            constraints.shape,
            (problem.solution_num, problem.n_con),
        )
        self.assertTrue(np.all(np.isfinite(objectives)))
        self.assertTrue(np.all(np.isfinite(constraints)))
        self.assertTrue(np.all(decisions >= problem.xl))
        self.assertTrue(np.all(decisions <= problem.xu))
        self.assertTrue(
            all(individual.rank is not None for individual in population)
        )

    def test_random_immigrant_response_is_constraint_aware_and_bounded(self):
        np.random.seed(7)
        problem = self.build_problem()
        population = self.build_population(problem)

        result = DNSGAIIA(replacement_rate=0.25).response(
            population,
            problem,
            algorithm=None,
        )

        self.assert_valid_response(result, problem)

    def test_mutated_immigrant_response_changes_parent_decisions(self):
        np.random.seed(11)
        problem = self.build_problem()
        population = self.build_population(problem)
        before = population.get_decision_matrix().copy()

        result = DNSGAIIB(
            replacement_rate=0.3,
            mutation_probability=0.2,
            distribution_index=20,
        ).response(population, problem, algorithm=None)

        self.assert_valid_response(result, problem)
        after = result.get_decision_matrix()
        self.assertFalse(np.array_equal(before, after))

    def test_polynomial_mutation_forces_a_bounded_change_per_row(self):
        np.random.seed(17)
        decisions = np.full((6, 4), 0.5)
        mutated = polynomial_mutation(
            decisions,
            np.zeros(4),
            np.ones(4),
            probability=1e-12,
            distribution_index=20,
        )

        self.assertTrue(np.all(mutated >= 0))
        self.assertTrue(np.all(mutated <= 1))
        self.assertTrue(np.all(np.any(mutated != decisions, axis=1)))

    def test_invalid_parameters_fail_before_a_run_starts(self):
        with self.assertRaises(ValueError):
            DNSGAIIA(replacement_rate=0)
        with self.assertRaises(ValueError):
            DNSGAIIB(mutation_probability=1.1)
        with self.assertRaises(ValueError):
            DNSGAIIB(distribution_index=0)

    def test_test_mode_frames_are_compatible_with_live_view_and_replay(self):
        recorder = RecordingPipe()
        algorithm = NSGA2(
            seed=23,
            pip=recorder,
            mode="test",
        )
        problem = CDP6(
            decision_num=4,
            n=10,
            tau=1,
            solution_num=8,
            total_evaluate_time=2,
        )

        algorithm.optimize(problem, DNSGAIIB())

        self.assertGreater(len(recorder.frames), 2)
        runtime = {}
        for frame in recorder.frames:
            self.assertEqual(frame["population"].n, problem.solution_num)
            self.assertIn("objective_constraints", frame)
            runtime.setdefault(frame["t"], {})[
                frame["evaluate_times"]
            ] = frame

        timeline = build_replay_timeline(runtime)
        self.assertEqual(len(timeline), len(recorder.frames))
        self.assertEqual(
            [item[0] for item in timeline],
            sorted(item[0] for item in timeline),
        )
        self.assertEqual(
            timeline[-1][2]["settings"]["response_strategy_class"],
            "DNSGAIIB",
        )


if __name__ == "__main__":
    unittest.main()
