import unittest

import numpy as np

from algorithms.response_strategy.NoResponse.main import NoResponse
from algorithms.search_algorithm.MOEAD.main import MOEAD
from algorithms.search_algorithm.NSGA2.main import NSGA2
from algorithms.search_algorithm.RMMEDA.main import RMMEDA
from algorithms.search_algorithm.SPEA2.main import SPEA2
from problems.benchmark.CDP1.main import CDP1
from problems.benchmark.CDP2.main import CDP2
from problems.benchmark.CDP3.main import CDP3
from problems.benchmark.CDP4.main import CDP4
from problems.benchmark.CDP5.main import CDP5
from problems.benchmark.CDP6.main import CDP6


CONSTRAINED_PROBLEMS = (CDP1, CDP2, CDP3, CDP4, CDP5, CDP6)


class ConstrainedDynamicSuiteTests(unittest.TestCase):
    def build_problem(self, problem_class):
        return problem_class(
            decision_num=5,
            n=10,
            tau=2,
            solution_num=10,
            total_evaluate_time=3,
        )

    def test_every_problem_has_finite_objectives_and_constraints(self):
        random = np.random.default_rng(42)
        decisions = random.random((200, 5))

        for problem_class in CONSTRAINED_PROBLEMS:
            with self.subTest(problem=problem_class.__name__):
                problem = self.build_problem(problem_class)
                objectives, constraints = problem.evaluate(
                    decisions,
                    need_count=False,
                    t=3,
                )

                self.assertEqual(objectives.shape, (200, 2))
                self.assertEqual(constraints.shape, (200, problem.n_con))
                self.assertTrue(np.all(np.isfinite(objectives)))
                self.assertTrue(np.all(np.isfinite(constraints)))
                feasible = np.all(constraints <= 1e-12, axis=1)
                self.assertTrue(np.any(feasible))
                self.assertTrue(np.any(~feasible))

    def test_true_front_and_set_are_feasible_and_aligned(self):
        for problem_class in CONSTRAINED_PROBLEMS:
            for time_step in (0, 3, 7):
                with self.subTest(
                    problem=problem_class.__name__,
                    time=time_step,
                ):
                    problem = self.build_problem(problem_class)
                    front = problem.get_pareto_front(time_step)
                    pareto_set = problem.get_pareto_set(time_step)
                    objectives, constraints = problem.evaluate(
                        pareto_set,
                        need_count=False,
                        t=time_step,
                    )

                    self.assertGreater(len(front), 10)
                    self.assertEqual(len(front), len(pareto_set))
                    np.testing.assert_allclose(objectives, front, atol=1e-12)
                    self.assertTrue(np.all(constraints <= 1e-12))

    def test_visual_constraint_description_changes_with_environment(self):
        for problem_class in CONSTRAINED_PROBLEMS:
            with self.subTest(problem=problem_class.__name__):
                problem = self.build_problem(problem_class)
                at_start = problem.get_objective_constraints(0)
                after_change = problem.get_objective_constraints(5)

                self.assertTrue(at_start)
                self.assertNotEqual(at_start, after_change)

    def test_search_algorithms_run_on_disconnected_and_combined_constraints(self):
        cases = (CDP4, CDP5, CDP6)
        algorithm_factories = (
            lambda: NSGA2(seed=7),
            lambda: SPEA2(seed=7),
            lambda: MOEAD(seed=7, neighbor_size=3),
            lambda: RMMEDA(seed=7, K=2),
        )

        for problem_class in cases:
            for build_algorithm in algorithm_factories:
                algorithm = build_algorithm()
                with self.subTest(
                    problem=problem_class.__name__,
                    algorithm=algorithm.__class__.__name__,
                ):
                    problem = problem_class(
                        decision_num=4,
                        n=10,
                        tau=1,
                        solution_num=6,
                        total_evaluate_time=2,
                    )
                    algorithm.optimize(problem, NoResponse())

                    self.assertTrue(algorithm.history["runtime"])
                    final_population = list(
                        list(algorithm.history["runtime"].values())[-1].values()
                    )[-1]
                    self.assertEqual(len(final_population), 6)


if __name__ == "__main__":
    unittest.main()
