"""Exercise the new prediction components through actual optimizers/replay."""

import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np

from flexdmo_app.core import defaults, load_frames, records, registered_class, save_frames
from tests.test_change_detection import ConstraintOnlyProblem


STRATEGIES = ("FCP", "VARE", "ADPS")
SEARCHES = ("NSGAII", "MOEA/D", "SPEA2", "RMMEDA")
PROBLEMS = ("CDP1", "CDP2", "CDP3", "CDP4", "CDP5", "CDP6", "DF1")


class FrameRecorder:
    def __init__(self):
        self.frames = []

    def send(self, frame):
        self.frames.append(copy.deepcopy(frame))


class TEVCPredictionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = records()

    def component(self, kind, name, **overrides):
        record = next(r for r in self.catalog[kind] if r["name"] == name)
        parameters = dict(defaults(record), **overrides)
        return registered_class(record)(**parameters)

    def run_case(self, strategy, search="NSGAII", problem="CDP6", seed=17, recorder=None):
        if isinstance(problem, str):
            problem = self.component("problem", problem, decision_num=4, solution_num=8,
                                     n=10, tau=3, total_evaluate_time=6)
            problem.initial_convergence = 2 * problem.solution_num
        search_parameters = {"seed": seed}
        if search == "MOEA/D":
            search_parameters["neighbor_size"] = 3
        elif search == "RMMEDA":
            search_parameters["K"] = 2
        if recorder is not None:
            search_parameters["pip"] = recorder
        optimizer = self.component("search", search, **search_parameters)
        response = self.component("dynamic", strategy)
        optimizer.optimize(problem, response)
        return optimizer, problem

    def assert_valid_history(self, optimizer, problem):
        self.assertTrue(problem.is_ended())
        self.assertEqual(list(optimizer.history["runtime"]), list(range(problem.total_change_time)))
        for environment, frames in optimizer.history["runtime"].items():
            self.assertTrue(frames)
            for population in frames.values():
                self.assertEqual(population.n, problem.solution_num)
                decisions = population.get_decision_matrix()
                self.assertTrue(np.isfinite(decisions).all())
                self.assertTrue(np.all(decisions >= problem.xl))
                self.assertTrue(np.all(decisions <= problem.xu))
                # Fixed-time reevaluation must not move the environment or budget.
                expected_f, expected_g = problem.evaluate(decisions, need_count=False, t=environment)
                np.testing.assert_allclose(population.get_objective_matrix(), expected_f)
                if expected_g is not None:
                    np.testing.assert_allclose(population.get_constrain_matrix(), expected_g)
                    expected_cv = np.maximum(expected_g, 0.0).sum(axis=1)
                    np.testing.assert_allclose(population.get_constraint_violation_vector(), expected_cv)
                    self.assertEqual([i.feasible for i in population], list(expected_cv <= 1e-12))

    def test_all_search_and_problem_combinations_reach_prediction_environments(self):
        # 3 response strategies x 4 optimizers x 7 problems = 84 combinations.
        for strategy in STRATEGIES:
            for search in SEARCHES:
                for problem in PROBLEMS:
                    with self.subTest(strategy=strategy, search=search, problem=problem):
                        optimizer, instance = self.run_case(strategy, search, problem)
                        self.assert_valid_history(optimizer, instance)

    def test_constraint_only_changes_reach_every_environment(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                optimizer, problem = self.run_case(strategy, problem=ConstraintOnlyProblem())
                self.assert_valid_history(optimizer, problem)

    def test_equal_seed_reproduces_entire_history(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                first, _ = self.run_case(strategy)
                second, _ = self.run_case(strategy)
                self.assertEqual(list(first.history["runtime"]), list(second.history["runtime"]))
                for t, frames in first.history["runtime"].items():
                    self.assertEqual(list(frames), list(second.history["runtime"][t]))
                    for evaluation, population in frames.items():
                        other = second.history["runtime"][t][evaluation]
                        np.testing.assert_array_equal(population.get_decision_matrix(), other.get_decision_matrix())

    def test_native_live_frames_and_saved_replay_keep_constraint_information(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                recorder = FrameRecorder()
                optimizer, problem = self.run_case(strategy, recorder=recorder)
                self.assert_valid_history(optimizer, problem)
                self.assertEqual({frame["t"] for frame in recorder.frames}, set(range(6)))
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "explicit-save.json"
                    save_frames(path, recorder.frames)
                    replay = load_frames(path)
                self.assertEqual(len(replay), len(recorder.frames))
                for original, restored in zip(recorder.frames, replay):
                    self.assertEqual(restored["settings"]["response_strategy_class"], strategy)
                    self.assertEqual(restored["t"], original["t"])
                    self.assertEqual(restored["evaluate_times"], original["evaluate_times"])
                    for accessor in ("get_decision_matrix", "get_objective_matrix", "get_constrain_matrix"):
                        np.testing.assert_allclose(getattr(restored["population"], accessor)(),
                                                   getattr(original["population"], accessor)())


if __name__ == "__main__":
    unittest.main()
