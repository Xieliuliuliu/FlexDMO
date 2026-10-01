"""Code-defined parameters and new algorithm workflows through actual Qt."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import main_qt
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from flexdmo_app.component_ui import ComponentDialog
from flexdmo_app.components import PLUGIN_ROOT, discover_plugins
from flexdmo_app.core import load_frames, save_frames
from flexdmo_app.parameter_ui import ParameterChoice
from flexdmo_app.tests.test_code_plugins import SEARCH, RESPONSE
from flexdmo_app.window import FlexDMOWindow


class CodeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        if cls.app.platformName() == "cocoa":
            QAccessible.setActive(True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="_test_ui_", dir=PLUGIN_ROOT)
        self.root = Path(self.temp.name)
        for kind, source in (("search_algorithm", SEARCH), ("response_strategy", RESPONSE)):
            folder = self.root / kind
            folder.mkdir()
            (folder / "UserExample.py").write_text(source, encoding="utf-8")
        self.discovery = patch("flexdmo_app.components.discover_plugins", side_effect=lambda: discover_plugins(self.root))
        self.discovery.start()
        self.window = FlexDMOWindow()
        self.dialog = None
        if self.app.platformName() == "cocoa":
            self.window.show()
            self.app.processEvents()

    def tearDown(self):
        if self.dialog:
            self.dialog.reject()
        self.window.controller.shutdown()
        self.window.batch.runner.shutdown()
        self.window.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.discovery.stop()
        self.temp.cleanup()

    def choose(self, kind):
        combo = self.window.selectors[kind]
        index = next(i for i in range(combo.count()) if combo.itemData(i).get("format") == "python-file")
        combo.setCurrentIndex(index)

    def wait(self, predicate, timeout=20):
        end = time.monotonic() + timeout
        while not predicate():
            self.app.processEvents()
            if time.monotonic() > end:
                self.fail("Qt code workflow timed out")
            time.sleep(0.005)
        self.app.processEvents()

    def test_choice_fields_and_required_drafts_are_preserved(self):
        source = self.root / "search_algorithm" / "UserExample.py"
        source.write_text('''from typing import Literal
def step(population, problem, scale: float, enabled: bool = True, policy: Literal["a", "b"] = "a"):
    return population
''', encoding="utf-8")
        self.window.refresh_registry()
        self.choose("search")
        fields = self.window.parameter_fields["search"]
        self.assertIsInstance(fields["enabled"], ParameterChoice)
        self.assertIsInstance(fields["policy"], ParameterChoice)
        self.assertEqual(fields["scale"].text(), "")
        with self.assertRaises(ValueError):
            self.window.request()
        fields["scale"].setText("-0.5")
        fields["policy"].setText("b")
        self.window.selectors["search"].setCurrentIndex(0)
        self.choose("search")
        self.assertEqual(self.window.request()["params"]["search"]["scale"], -0.5)
        self.assertEqual(self.window.request()["params"]["search"]["policy"], "b")

    def test_code_refresh_keeps_user_values_and_adds_new_default_parameters(self):
        self.choose("search")
        self.window.parameter_fields["search"]["scale"].setText("0.1")
        path = self.root / "search_algorithm" / "UserExample.py"
        path.write_text(SEARCH.replace("scale: float = 0.02", "scale: float = 0.02, enabled: bool = True"), encoding="utf-8")
        self.window.refresh_registry()
        self.assertEqual(self.window.parameter_fields["search"]["scale"].text(), "0.1")
        self.assertTrue(self.window.request()["params"]["search"]["enabled"])
        self.assertTrue(any(self.window.batch.lists["search"].item(i).data(256).get("format") == "python-file"
                            for i in range(self.window.batch.lists["search"].count())))

    def test_component_dialog_trial_uses_defaults_without_an_extra_confirmation(self):
        self.dialog = ComponentDialog(self.window.refresh_registry, self.window)
        self.dialog.kind.setCurrentIndex(1)
        self.dialog.show()
        with patch("flexdmo_app.component_ui.ParameterDialog.exec", side_effect=AssertionError("unnecessary dialog")):
            self.dialog.check_code()
        self.wait(lambda: not self.dialog.trial.active)
        self.assertIn("试跑通过", self.dialog.report.toPlainText())
        self.assertFalse(list(self.root.rglob("*.json")))
        if getattr(self, "capture_directory", None):
            self.dialog.grab().save(str(self.capture_directory / "code_manager.png"))

    def test_bad_code_batch_task_does_not_block_a_healthy_algorithm(self):
        source = self.root / "search_algorithm" / "UserExample.py"
        source.write_text("def step(population, problem, scale=0.02):\n    raise ValueError('bad user code')\n", encoding="utf-8")
        self.window.refresh_registry()
        batch = self.window.batch
        choices = batch.lists["search"]
        for i in range(choices.count()):
            item = choices.item(i)
            if item.data(Qt.ItemDataRole.UserRole)["name"] in ("NSGAII", "UserExample"):
                item.setCheckState(Qt.CheckState.Checked)
        batch.start()
        self.wait(lambda: not batch.runner.active)
        self.assertEqual([t["status"] for t in batch.runner.tasks].count("completed"), 1)
        self.assertEqual([t["status"] for t in batch.runner.tasks].count("failed"), 1)
        failed = next(t for t in batch.runner.tasks if t["status"] == "failed")
        self.assertIn("bad user code", failed["error"])

    def test_hung_trial_is_terminated_and_leaves_no_active_controller(self):
        source = self.root / "search_algorithm" / "UserExample.py"
        source.write_text("def step(population, problem, scale=0.02):\n    while True: pass\n", encoding="utf-8")
        self.dialog = ComponentDialog(self.window.refresh_registry, self.window)
        self.dialog.kind.setCurrentIndex(1)
        self.dialog.check_code()
        self.dialog.trial_timeout.start(50)
        self.wait(lambda: not self.dialog.trial.active, timeout=6)
        self.assertTrue(self.dialog.trial_failed)
        self.assertIn("正在终止", self.dialog.report.toPlainText())

    def test_single_code_run_replay_manual_roundtrip_and_batch(self):
        self.choose("dynamic")
        self.choose("search")
        self.window.start_run()
        self.wait(lambda: not self.window.controller.active)
        self.assertEqual(self.window.controller.status, "completed")
        self.assertTrue(self.window.frames)
        settings = self.window.frames[0]["settings"]
        self.assertEqual(settings["response_strategy_params"]["rate"], 0.2)
        self.assertIn("sha256", settings["code_plugins"]["search"])
        control = self.window.history_panel.entries[0]["button"]
        QTest.mouseClick(control, Qt.MouseButton.LeftButton)
        self.window.render_latest()
        for chart in self.window.chart_dashboard.visible_modes():
            self.assertEqual(self.window.chart_dashboard.charts[chart]._last_request[1], self.window.index)
        path = self.root / "manual_roundtrip.json"
        save_frames(path, self.window.frames)
        self.assertEqual(len(load_frames(path)), len(self.window.frames))
        if self.app.platformName() == "cocoa":
            from flexdmo_app.tests.cocoa_probe import CocoaProbe
            probe = CocoaProbe()
            for _ in range(3):
                for entry in self.window.history_panel.entries.values():
                    QTest.mouseClick(entry["button"], Qt.MouseButton.LeftButton)
                    self.app.processEvents()
                    probe.check_history_widget(entry["button"])
            self.window.render_latest()
        if getattr(self, "capture_directory", None):
            self.window.grab().save(str(self.capture_directory / "code_run.png"))
        batch = self.window.batch
        batch.use_test_configuration()
        batch.start()
        self.wait(lambda: not batch.runner.active)
        self.assertTrue(all(t["status"] == "completed" for t in batch.runner.tasks))
        self.assertIn("frames", batch.runner.tasks[0]["result"])


if __name__ == "__main__":
    unittest.main()
