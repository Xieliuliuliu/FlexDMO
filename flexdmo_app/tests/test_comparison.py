import copy
import time
import unittest
from types import SimpleNamespace

import main_qt
import numpy as np
from PySide6.QtWidgets import QApplication

from flexdmo_app.comparison import comparison_runs
from flexdmo_app.comparison_ui import ComparisonDialog
from flexdmo_app.experiments import history_frames, build_plan
from flexdmo_app.tests import test_experiments
from flexdmo_app.tests.test_interactions import frames
from flexdmo_app.window import FlexDMOWindow


def tasks():
    fixture = test_experiments.ExperimentTests()
    fixture.setUp()
    result = build_plan(fixture.selection, fixture.shared)
    for t in result:
        t.update(status="completed", result={"frames": frames(), "metrics": {"MIGD": 0.25}})
    return result


class ComparisonTests(unittest.TestCase):
    def test_excludes_failed_canceled_and_partial(self):
        data = tasks()
        data[0]["result"]["partial"] = True
        data[1]["status"] = "failed"
        self.assertEqual(comparison_runs(data), ([], []))

    def test_groups_problem_budget_and_algorithm_parameters(self):
        data = tasks()
        runs, errors = comparison_runs(data)
        self.assertFalse(errors)
        self.assertEqual(runs[0]["group"], runs[1]["group"])
        self.assertEqual(runs[0]["variant"], runs[1]["variant"])
        data[1]["request"]["params"]["problem"]["solution_num"] += 1
        data[1]["request"]["params"]["search"]["proC"] = 0.25
        runs, _ = comparison_runs(data)
        self.assertNotEqual(runs[0]["group"], runs[1]["group"])
        self.assertNotEqual(runs[0]["variant"], runs[1]["variant"])

    def test_actual_loaded_source_versions_do_not_merge(self):
        data = tasks()
        for task, sha in zip(data, ("old", "new")):
            task["result"]["frames"][0]["settings"]["code_plugins"] = {"search": {"sha256": sha}}
        runs, _ = comparison_runs(data)
        self.assertNotEqual(runs[0]["variant"], runs[1]["variant"])

    def test_last_snapshot_and_no_feasible_infinity(self):
        data = tasks()
        later = copy.deepcopy(data[0]["result"]["frames"][0])
        later["evaluate_times"] += 1
        for i in later["population"]:
            i.feasible = False
        data[0]["result"]["frames"].append(later)
        runs, _ = comparison_runs(data)
        self.assertIs(runs[0]["ends"][0], later)
        self.assertEqual(runs[0]["points"][0][1:], (float("inf"), 0.0))

    def test_missing_file_is_reported_and_cancellation_stops_loading(self):
        data = tasks()
        data[0]["result"] = {"path": "/nonexistent/flexdmo-result.json"}
        runs, errors = comparison_runs(data)
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(comparison_runs(data, lambda: True), ([], []))

    def test_light_export_does_not_prune_internal_history(self):
        from problems.benchmark.CDP1.main import CDP1
        problem = CDP1(3, 10, 1, 4, 3)
        fs = frames()
        runtime = {f["t"]: {1: f["population"], 2: f["population"]} for f in fs}
        algorithm = SimpleNamespace(history={"runtime": runtime, "settings": fs[0]["settings"]})
        full = list(history_frames(algorithm, problem))
        light = list(history_frames(algorithm, problem, "environment"))
        self.assertEqual(len(full), 4)
        self.assertEqual(len(light), 2)
        self.assertEqual([len(v) for v in runtime.values()], [2, 2])
        for f, l in zip(full[1::2], light):
            np.testing.assert_array_equal(f["population"].get_decision_matrix(), l["population"].get_decision_matrix())
        with self.assertRaises(ValueError):
            list(history_frames(algorithm, problem, "bad"))

    def test_light_saved_roundtrip_and_manifest(self):
        import json
        from pathlib import Path
        import tempfile
        from flexdmo_app.core import load_frames, save_frames
        from flexdmo_app.experiments import export_reports
        data = tasks()
        data[0]["request"]["history_policy"] = "environment"
        for frame in data[0]["result"]["frames"]:
            frame["settings"]["history_policy"] = "environment"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "light.json"
            save_frames(path, data[0]["result"]["frames"])
            loaded = load_frames(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["settings"]["history_policy"], "environment")
            data[0]["result"].pop("frames")
            data[0]["result"]["path"] = str(path)
            runs, errors = comparison_runs(data)
            self.assertFalse(errors)
            self.assertEqual(len(runs), 2)
            export_reports(folder, data)
            manifest = json.loads((Path(folder) / "manifest.json").read_text())
            self.assertEqual(manifest[0]["history_policy"], "environment")
            raw = json.loads(path.read_text())
            raw["settings"]["history_policy"] = "bad"
            path.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):
                load_frames(path)


class ComparisonUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_modes_and_close_cancel_loader(self):
        dialog = ComparisonDialog(tasks())
        try:
            deadline = time.monotonic() + 5
            while dialog.timer.isActive():
                self.app.processEvents()
                if time.monotonic() > deadline:
                    self.fail("comparison load timeout")
                time.sleep(0.005)
            self.assertEqual(len(dialog.runs), 2)
            for i in range(4):
                dialog.mode.setCurrentIndex(i)
                dialog.draw()
                self.app.processEvents()
                self.assertEqual(len(dialog.figure.axes), 1)
                self.assertEqual(dialog.seed.isEnabled(), i == 2)
        finally:
            dialog.reject()
        self.assertTrue(dialog.cancel.is_set())

    def test_light_live_replaces_current_environment_without_changing_button(self):
        window = FlexDMOWindow()
        try:
            data = frames()
            for f in data:
                f["settings"]["history_policy"] = "environment"
            window.receive_frame(data[0])
            control = window.history_panel.entries[0]["button"]
            window.receive_frame(dict(data[0], evaluate_times=25))
            window.receive_frame(data[1])
            self.assertEqual(len(window.frames), 2)
            self.assertEqual(window.frames[0]["evaluate_times"], 25)
            self.assertIs(control, window.history_panel.entries[0]["button"])
            self.assertEqual(window.environment_counts, {0: 1, 1: 1})
            window.update_controls("completed")
            control.click()
            self.assertEqual(window.index, 0)
            self.assertEqual(window.slider.maximum(), 1)
        finally:
            window.dirty = False
            window.close()

    def test_old_plan_default_and_invalid_plan_is_atomic(self):
        window = FlexDMOWindow()
        try:
            batch = window.batch
            data = {"version": 1, "selection": {k: [r["name"] for r in rows] for k, rows in batch.selection().items()},
                    "shared": batch.shared()}
            data["shared"].pop("history_policy")
            batch.history_policy.setCurrentIndex(1)
            batch.apply_configuration(data)
            self.assertEqual(batch.history_policy.currentData(), "full")
            data["shared"]["history_policy"] = "invalid"
            before = batch.shared()
            with self.assertRaises(ValueError):
                batch.apply_configuration(data)
            self.assertEqual(batch.shared(), before)
        finally:
            window.dirty = False
            window.close()
