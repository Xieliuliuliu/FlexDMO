"""The new components use the same test/batch controls and require no ML runtime."""

import os
import subprocess
import sys
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flexdmo_app.core import ROOT, defaults, parameter_label, registered_class, validate_request
from flexdmo_app.batch_runner import BatchRunner
from flexdmo_app.experiments import build_plan
from flexdmo_app.window import FlexDMOWindow


class TEVCComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_test_and_batch_views_discover_new_components_with_chinese_parameters(self):
        window = FlexDMOWindow()
        try:
            selector = window.selectors["dynamic"]
            batch_selector = window.batch.lists["dynamic"]
            for name, year in (("FCP", 2025), ("VARE", 2026), ("ADPS", 2026)):
                with self.subTest(name=name):
                    index = next(i for i in range(selector.count()) if selector.itemData(i)["name"] == name)
                    selector.setCurrentIndex(index)
                    self.app.processEvents()
                    request = window.request()
                    record = request["records"]["dynamic"]
                    self.assertEqual(record["year"], year)
                    self.assertEqual(request["params"]["dynamic"], defaults(record))
                    registered_class(record)(**request["params"]["dynamic"])
                    self.assertGreater(validate_request(request), 0)
                    for key in defaults(record):
                        self.assertNotEqual(parameter_label(record, key), key)
                    item = next(batch_selector.item(i) for i in range(batch_selector.count())
                                if batch_selector.itemData(i)["name"] == name)
                    item.setCheckState(Qt.CheckState.Checked)
                    self.assertIn(name, {r["name"] for r in window.batch.selection()["dynamic"]})
                    if name == "VARE":
                        window.parameter_fields["dynamic"]["regularization"].setText("0")
                        zero_request = window.request()
                        self.assertEqual(zero_request["params"]["dynamic"]["regularization"], 0)
                        self.assertGreater(validate_request(zero_request), 0)
                        window.batch.use_test_configuration()
                        self.assertEqual(window.batch.profiles[("dynamic", record["folder_name"])]["regularization"], 0)
            window.batch.use_test_configuration()
            self.assertIn("ADPS", {r["name"] for r in window.batch.selection()["dynamic"]})
        finally:
            window.dirty = False
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_new_components_run_when_torch_and_sklearn_imports_are_blocked(self):
        code = '''
import importlib.abc
import sys
class BlockML(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"torch", "sklearn"}:
            raise ModuleNotFoundError("ML runtime must not be required: " + fullname)
sys.meta_path.insert(0, BlockML())
from flexdmo_app.core import records, registered_class, defaults
from algorithms.search_algorithm.NSGA2.main import NSGA2
from problems.benchmark.CDP6.main import CDP6
for name in ("FCP", "VARE", "ADPS"):
    record = next(r for r in records()["dynamic"] if r["name"] == name)
    problem = CDP6(4, 10, 3, 8, 6)
    problem.initial_convergence = 16
    optimizer = NSGA2(seed=9)
    optimizer.optimize(problem, registered_class(record)(**defaults(record)))
    assert problem.is_ended()
    assert list(optimizer.history["runtime"]) == list(range(6))
assert not any(n.split(".")[0] in {"torch", "sklearn"} for n in sys.modules)
print("NUMPY_COMPONENTS_OK")
'''
        env = dict(os.environ, MPLBACKEND="Agg", QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NUMPY_COMPONENTS_OK", result.stdout)

    def test_spawned_batch_runs_replay_in_memory_without_saving(self):
        window = FlexDMOWindow()
        runner = BatchRunner()
        try:
            registry = window.registry
            selection = {
                "dynamic": [r for r in registry["dynamic"] if r["name"] in ("FCP", "VARE", "ADPS")],
                "search": [next(r for r in registry["search"] if r["name"] == "NSGAII")],
                "problem": [next(r for r in registry["problem"] if r["name"] == "CDP6")],
            }
            shared = {"decision_num": 4, "solution_num": 8, "total_evaluate_time": 6,
                      "tau": "3", "n": "10", "repeats": 1, "seed": 19}
            tasks = build_plan(selection, shared)
            self.assertEqual(len(tasks), 3)
            runner.start(tasks, parallel=2, save_results=False)
            deadline = time.monotonic() + 60
            while runner.active and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.assertFalse(runner.active, "Prediction batch did not finish")
            self.assertIsNone(runner.directory)
            self.assertIsNone(runner.report_path)
            for task in runner.tasks:
                with self.subTest(strategy=task["request"]["records"]["dynamic"]["name"]):
                    self.assertEqual(task["status"], "completed", task.get("error"))
                    self.assertNotIn("output_path", task["request"])
                    frames = task["result"]["frames"]
                    self.assertEqual({frame["t"] for frame in frames}, set(range(6)))
                    window.dirty = False
                    window.open_batch_result(frames)
                    # Render real prediction frames in all three coordinated charts.
                    for index in (0, len(frames) // 2, len(frames) - 1):
                        window.select_frame(index)
                        window.render_latest()
                        self.app.processEvents()
                        self.assertEqual(window.index, index)
                        self.assertEqual(window.frame_label.text().split("  ·")[0],
                                         f"环境 {frames[index]['t']}")
        finally:
            for controller in list(runner.controllers.values()):
                controller.shutdown()
            runner.export_timer.stop()
            window.dirty = False
            window.close()
            window.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
