import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from flexdmo_app.core import (ROOT, defaults, load_frames, parse_parameters,
                             records, registered_class, RunState, save_frames)
from components.Population import Population


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.record = next(r for r in records()["problem"] if r["name"] == "CDP1")
        self.problem = registered_class(self.record)(decision_num=3, n=10, tau=1,
                                                     solution_num=4, total_evaluate_time=3)
        self.problem.t = 1
        pop = Population(X=[[0.2, 0.5, 0.5], [0.8, 0.5, 0.5]], xl=self.problem.xl, xu=self.problem.xu)
        pop.update_objective_constrain(self.problem)
        for i, individual in enumerate(pop):
            individual.rank = i
            individual.crowding_distance = float("inf") if i == 0 else 2.5
        self.frame = {"settings": {"problem_class": "CDP1", "search_algorithm_class": "NSGA2",
                       "response_strategy_class": "NoResponse", "problem_params": {
                           "decision_num": 3, "n": 10, "tau": 1, "solution_num": 4,
                           "total_change_time": 3}},
                      "population": pop, "t": 1, "evaluate_times": 30,
                      "POF": self.problem.get_pareto_front(), "POS": self.problem.get_pareto_set(),
                      "bound": [self.problem.xl, self.problem.xu],
                      "objective_constraints": self.problem.get_objective_constraints()}

    def test_registry_points_only_inside_repository(self):
        for kind, rows in records().items():
            self.assertTrue(rows, kind)
            for row in rows:
                self.assertTrue(Path(row["folder_name"]).is_relative_to(ROOT))
                self.assertIsInstance(defaults(row), dict)

    def test_parameter_parser(self):
        self.assertEqual(parse_parameters({"seed": "2", "proC": "0.8"}, {"seed": 1, "proC": 1.0}),
                         {"seed": 2, "proC": 0.8})

    def test_invalid_integer(self):
        with self.assertRaises(ValueError):
            parse_parameters({"solution_num": "3.5"}, {"solution_num": 100})

    def test_nonfinite_parameter(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_parameters({"proM": value}, {"proM": 1.0})

    def test_probability_and_seed_ranges(self):
        for key, raw, default in (("delta", "1.1", 0.9), ("seed", "-1", 1),
                                  ("seed", "4294967296", 1), ("tau", "0", 10)):
            with self.subTest(key=key, raw=raw), self.assertRaises(ValueError):
                parse_parameters({key: raw}, {key: default})

    def test_zero_probability_allowed(self):
        self.assertEqual(parse_parameters({"replacement_rate": "0"}, {"replacement_rate": 0.2}),
                         {"replacement_rate": 0.0})

    def test_plugin_probabilities_allow_zero_but_reject_out_of_range(self):
        for key in ("random_fraction", "predicted_fraction", "mutation_fraction", "dropout"):
            with self.subTest(key=key):
                self.assertEqual(parse_parameters({key: "0"}, {key: 0.2}), {key: 0.0})
                for raw in ("-0.1", "1.1"):
                    with self.assertRaises(ValueError):
                        parse_parameters({key: raw}, {key: 0.2})

    def test_custom_parameter_domain_is_not_inferred_from_default(self):
        self.assertEqual(parse_parameters({"offset": "-2", "custom_count": "0"},
                                         {"offset": 1.0, "custom_count": 3}),
                         {"offset": -2.0, "custom_count": 0})

    def test_roundtrip_keeps_objectives_constraints_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            save_frames(path, [self.frame])
            restored = load_frames(path)[0]
            np.testing.assert_array_equal(restored["population"].get_objective_matrix(), self.frame["population"].get_objective_matrix())
            np.testing.assert_array_equal(restored["population"].get_constrain_matrix(), self.frame["population"].get_constrain_matrix())
            np.testing.assert_array_equal(restored["POF"], self.frame["POF"])
            self.assertEqual([i.feasible for i in restored["population"]], [False, True])
            self.assertEqual(restored["population"][1].crowding_distance, 2.5)
            self.assertEqual(restored["population"][1].rank, 1)
            self.assertEqual(restored["t"], 1)

    def test_statistics_reader_accepts_desktop_result(self):
        from utils.result_io import load_result_from_files
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compatible.json"
            save_frames(path, [self.frame])
            restored = next(load_result_from_files([path]))
            self.assertIsNotNone(restored)
            frame = restored["runtime_populations"][1][30]
            np.testing.assert_array_equal(frame["population"].get_objective_matrix(), self.frame["population"].get_objective_matrix())

    def test_legacy_decision_only_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.json"
            save_frames(path, [self.frame])
            data = json.loads(path.read_text())
            data["information"]["1"]["30"] = {"decision": [[0.2, 0.5, 0.5], [0.8, 0.5, 0.5]]}
            path.write_text(json.dumps(data))
            restored = load_frames(path)[0]
            self.assertEqual([i.feasible for i in restored["population"]], [False, True])
            np.testing.assert_array_equal(restored["population"].get_objective_matrix(), self.frame["population"].get_objective_matrix())

    def test_unregistered_problem_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"settings": {"problem_class": "../../evil"}, "information": {}}))
            with self.assertRaises(ValueError):
                load_frames(path)

    def test_corrupt_matrix_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.json"
            save_frames(path, [self.frame])
            data = json.loads(path.read_text())
            data["information"]["1"]["30"]["objective"] = [[1, 2]]
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                load_frames(path)

    def test_empty_history_is_rejected(self):
        with self.assertRaises(ValueError):
            save_frames("unused.json", [])

    def test_atomic_save_keeps_old_file_on_serialization_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.json"
            path.write_text("old result")
            invalid = dict(self.frame, settings={"bad": object()})
            with self.assertRaises(TypeError):
                save_frames(path, [invalid])
            self.assertEqual(path.read_text(), "old result")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_shared_state_adapter(self):
        import multiprocessing
        state = RunState(multiprocessing.get_context("spawn").Value("i", 0))
        for status in ("running", "pause", "stop"):
            state.value = status
            self.assertEqual(state.value, status)


if __name__ == "__main__":
    unittest.main()
