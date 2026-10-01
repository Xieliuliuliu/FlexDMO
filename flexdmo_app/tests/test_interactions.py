"""Regression tests for the three preview-only interaction defects."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import main_qt  # Reuse scientific packages when running in the isolated Qt venv.
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from components.Population import Population
from problems.benchmark.CDP1.main import CDP1
from flexdmo_app.core import defaults
from flexdmo_app.window import FlexDMOWindow


def frames():
    problem = CDP1(3, 10, 1, 4, 3)
    result = []
    for t in (0, 1):
        problem.t = t
        pop = Population(X=[[0.2, 0.4, 0.4], [0.7, 0.5, 0.5]],
                         xl=problem.xl, xu=problem.xu)
        pop.update_objective_constrain(problem)
        result.append({"settings": {"problem_class": "CDP1", "search_algorithm_class": "NSGA2",
                                   "response_strategy_class": "NoResponse",
                                   "problem_params": {"decision_num": 3, "n": 10, "tau": 1,
                                                      "solution_num": 4, "total_evaluate_time": 3}},
                       "population": pop, "t": t, "evaluate_times": 20 + t * 10,
                       "POF": problem.get_pareto_front(), "POS": problem.get_pareto_set(),
                       "bound": [problem.xl, problem.xu],
                       "objective_constraints": problem.get_objective_constraints()})
    return result


class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.window = FlexDMOWindow()
        self.data = frames()

    def tearDown(self):
        self.window.dirty = False
        self.window.controller.shutdown()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def choose(self, kind, name):
        selector = self.window.selectors[kind]
        index = next(i for i in range(selector.count()) if selector.itemData(i)["name"] == name)
        selector.setCurrentIndex(index)

    def wait_for_io(self):
        deadline = time.monotonic() + 5
        while self.window.io_busy:
            self.app.processEvents()
            self.window._finish_io()
            if time.monotonic() > deadline:
                self.fail("Result IO did not finish")
            time.sleep(0.005)

    def test_diagnostics_hidden_and_interface_has_no_preview_badge(self):
        self.assertEqual(self.window.windowTitle(), "FlexDMO")
        self.assertFalse(self.window.history_tabs.isTabVisible(1))
        self.window.diagnostics_action.setChecked(True)
        self.assertTrue(self.window.history_tabs.isTabVisible(1))
        self.window.diagnostics_action.setChecked(False)
        self.assertFalse(self.window.history_tabs.isTabVisible(1))
        self.window.install_frames(self.data)
        self.window.render_latest()
        self.assertNotIn("快照", self.window.frame_label.text())
        self.assertIn("快照", self.window.frame_label.toolTip())
        self.assertEqual(self.window.start_button.text(), "重新运行")
        for mode in self.window.chart_dashboard.visible_modes():
            self.assertEqual(self.window.chart_dashboard.charts[mode].axes.get_title(), mode)

    def test_selected_dropdown_rows_have_visible_text_and_background(self):
        from flexdmo_app.component_ui import ComponentDialog
        dialog = ComponentDialog(self.window.refresh_registry, self.window)
        self.window.show()
        boxes = list(self.window.selectors.values()) + [self.window.mode_combo,
                self.window.speed_combo, self.window.batch.preset, dialog.kind]
        try:
            for combo in boxes:
                with self.subTest(combo=combo.currentText()):
                    if combo is self.window.batch.preset:
                        self.window.switch_workspace(1)
                    elif combo is dialog.kind:
                        dialog.show()
                    else:
                        self.window.switch_workspace(0)
                    self.app.processEvents()
                    combo.showPopup()
                    self.app.processEvents()
                    view = combo.view()
                    index = view.model().index(combo.currentIndex(), 0)
                    self.assertTrue(index.data())
                    rect = view.visualRect(index)
                    self.assertFalse(rect.isEmpty())
                    image = view.viewport().grab(rect).toImage()
                    colors = [image.pixelColor(x, y).name() for y in range(image.height())
                              for x in range(image.width())]
                    self.assertGreater(colors.count("#129bad"), len(colors) // 4)
                    self.assertIn("#ffffff", colors)  # Selected text is actually painted.
                    combo.hidePopup()
        finally:
            for combo in boxes:
                combo.hidePopup()
            dialog.close()
            self.window.switch_workspace(0)

    def test_dropdown_keyboard_selection_uses_correct_algorithm(self):
        self.window.show()
        self.app.processEvents()
        combo = self.window.selectors["search"]
        self.assertEqual(combo.currentData()["name"], "NSGAII")
        combo.showPopup()
        self.app.processEvents()
        QTest.keyClick(combo.view(), Qt.Key.Key_Down)
        QTest.keyClick(combo.view(), Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(combo.currentData()["name"], "RMMEDA")
        self.assertEqual(self.window.selected["search"]["name"], "RMMEDA")
        self.assertEqual(self.window.parameter_fields["problem"]["solution_num"].text(), "20")

    def test_rerun_archives_dirty_result_before_launch_without_prompt(self):
        from flexdmo_app.core import load_frames
        self.window.auto_save.setChecked(True)
        self.window.install_frames(self.data)
        self.window.dirty = True
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(self.window, "archive_folder", return_value=Path(directory)), \
                patch.object(self.window, "_launch_run") as launch, \
                patch("flexdmo_app.window.QMessageBox.warning") as warning:
            self.window.start_run()
            self.assertTrue(self.window.io_busy)
            launch.assert_not_called()
            self.assertIs(self.window.frames, self.data)
            self.wait_for_io()
            warning.assert_not_called()
            launch.assert_called_once()
            paths = list(Path(directory).glob("*.json"))
            self.assertEqual(len(paths), 1)
            self.assertEqual(len(load_frames(paths[0])), len(self.data))
            self.assertFalse(self.window.dirty)

    def test_archive_failure_keeps_old_result_and_does_not_launch(self):
        self.window.auto_save.setChecked(True)
        self.window.install_frames(self.data)
        self.window.dirty = True
        with patch("flexdmo_app.window.save_frames", side_effect=OSError("disk full")), \
                patch.object(self.window, "_launch_run") as launch, \
                patch("flexdmo_app.window.QMessageBox.warning") as warning:
            self.window.start_run()
            self.wait_for_io()
            launch.assert_not_called()
            self.assertIs(self.window.frames, self.data)
            self.assertTrue(self.window.dirty)
            self.assertIsNone(self.window.io_success)
            warning.assert_called_once()

    def test_rerun_saved_result_does_not_prompt_or_write_again(self):
        self.window.install_frames(self.data)
        with patch.object(self.window, "_launch_run") as launch, \
                patch.object(self.window, "_start_io") as save, \
                patch("flexdmo_app.window.QMessageBox.warning") as warning:
            self.window.start_run()
            launch.assert_called_once()
            save.assert_not_called()
            warning.assert_not_called()

    def test_rerun_repeated_clicks_do_not_duplicate_save_or_launch(self):
        self.window.auto_save.setChecked(True)
        self.window.install_frames(self.data)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(self.window, "archive_folder", return_value=Path(directory)), \
                patch.object(self.window, "_launch_run") as launch:
            for _ in range(2):
                self.window.dirty = True
                self.window.start_run()
                self.window.start_run()
                self.wait_for_io()
            self.assertEqual(launch.call_count, 2)
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 2)

    def test_invalid_rerun_parameters_keep_previous_result(self):
        self.window.install_frames(self.data)
        self.window.dirty = True
        self.window.parameter_fields["problem"]["solution_num"].setText("0")
        with patch.object(self.window, "_start_io") as save, \
                patch.object(self.window, "_launch_run") as launch, \
                patch("flexdmo_app.window.QMessageBox.warning") as warning:
            self.window.start_run()
            save.assert_not_called()
            launch.assert_not_called()
            self.assertIs(self.window.frames, self.data)
            self.assertTrue(self.window.dirty)
            warning.assert_called_once()

    def test_default_rerun_does_not_save_or_prompt(self):
        self.assertFalse(self.window.auto_save.isChecked())
        self.assertFalse(self.window.batch.save_results.isChecked())
        self.window.install_frames(self.data)
        self.window.dirty = True
        with patch.object(self.window, "_launch_run") as launch, \
                patch.object(self.window, "_start_io") as save, \
                patch("flexdmo_app.window.QMessageBox.warning") as warning:
            self.window.start_run()
            launch.assert_called_once()
            save.assert_not_called()
            self.assertTrue(self.window.allow_discard())
            warning.assert_not_called()

    def test_default_run_finish_keeps_frames_only_in_memory(self):
        self.window.install_frames(self.data)
        self.window.dirty = True
        with patch.object(self.window, "_start_io") as save:
            self.window.run_finished("completed")
            save.assert_not_called()
            self.assertTrue(self.window.dirty)
            self.assertIs(self.window.frames, self.data)

    def test_opt_in_auto_save_on_completion(self):
        self.window.auto_save.setChecked(True)
        self.window.install_frames(self.data)
        self.window.dirty = True
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(self.window, "archive_folder", return_value=Path(directory)):
            self.window.run_finished("completed")
            self.wait_for_io()
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            self.assertFalse(self.window.dirty)

    def test_batch_memory_replay_is_available_without_disk_io(self):
        self.window.switch_workspace(1)
        with patch.object(self.window, "_start_io") as io:
            self.window.open_batch_result(self.data)
            io.assert_not_called()
            self.assertIs(self.window.frames, self.data)
            self.assertTrue(self.window.dirty)
            self.assertEqual(self.window.workspace_stack.currentIndex(), 0)

    def test_manual_result_save_still_works_when_auto_save_is_off(self):
        self.window.install_frames(self.data)
        self.window.dirty = True
        with tempfile.TemporaryDirectory() as directory, \
                patch("flexdmo_app.window.QFileDialog.getSaveFileName", return_value=(str(Path(directory) / "manual.json"), "")):
            self.window.save_result()
            self.wait_for_io()
            self.assertTrue((Path(directory) / "manual.json").is_file())
            self.assertFalse(self.window.dirty)

    def test_switch_algorithm_retains_problem_parameters(self):
        fields = self.window.parameter_fields["problem"]
        fields["solution_num"].setText("42")
        fields["total_evaluate_time"].setText("7")
        self.choose("search", "SPEA2")
        current = self.window.parameter_fields["problem"]
        self.assertEqual(current["solution_num"].text(), "42")
        self.assertEqual(current["total_evaluate_time"].text(), "7")
        self.assertEqual(current["tau"].text(), "3")

    def test_component_drafts_restore_when_switching_back(self):
        self.window.parameter_fields["search"]["seed"].setText("23")
        self.choose("search", "MOEA/D")
        self.window.parameter_fields["search"]["seed"].setText("47")
        self.choose("search", "NSGAII")
        self.assertEqual(self.window.parameter_fields["search"]["seed"].text(), "23")
        self.choose("search", "MOEA/D")
        self.assertEqual(self.window.parameter_fields["search"]["seed"].text(), "47")

    def test_switch_problem_retains_other_components_and_own_draft(self):
        self.window.parameter_fields["search"]["seed"].setText("13")
        self.window.parameter_fields["problem"]["solution_num"].setText("42")
        self.choose("problem", "CDP2")
        self.assertEqual(self.window.parameter_fields["search"]["seed"].text(), "13")
        self.choose("problem", "CDP1")
        self.assertEqual(self.window.parameter_fields["problem"]["solution_num"].text(), "42")

    def test_invalid_draft_is_not_silently_replaced(self):
        self.window.parameter_fields["search"]["seed"].setText("unfinished")
        self.choose("search", "SPEA2")
        self.choose("search", "NSGAII")
        self.assertEqual(self.window.parameter_fields["search"]["seed"].text(), "unfinished")

    def test_reset_and_fast_preset_are_explicit(self):
        self.window.parameter_fields["search"]["seed"].setText("23")
        self.window.reset_parameters()
        for kind, record in self.window.selected.items():
            self.assertEqual({k: f.text() for k, f in self.window.parameter_fields[kind].items()},
                             {k: str(v) for k, v in defaults(record).items()})
        self.window.fast_preset()
        self.choose("dynamic", "NoResponse")
        self.assertEqual(self.window.parameter_fields["problem"]["solution_num"].text(), "20")
        self.assertEqual(self.window.parameter_fields["problem"]["total_evaluate_time"].text(), "5")

    def test_loaded_result_label_survives_algorithm_switch_and_reset(self):
        self.window.install_frames(self.data)
        before = self.window.selection_label.text()
        self.choose("search", "SPEA2")
        self.assertEqual(self.window.selection_label.text(), before)
        self.window.reset_parameters()
        self.assertEqual(self.window.selection_label.text(), before)
        self.assertIn("NSGAII", before)
        self.assertNotIn("SPEA2", before)

    def test_live_result_label_uses_frame_settings_not_draft(self):
        self.choose("search", "SPEA2")
        self.window.receive_frame(self.data[0])
        self.assertIn("NSGAII", self.window.selection_label.text())
        self.assertIn("NoResponse", self.window.selection_label.text())
        self.window.dirty = False
        self.window.clear_history()
        self.assertIn("SPEA2", self.window.selection_label.text())
        self.assertTrue(self.window.selection_label.text().startswith("待运行："))

    def test_all_chart_modes_preserve_zoom_between_frames(self):
        chart = self.window.chart
        for mode in ("PF", "PS", "IGD", "CV"):
            with self.subTest(mode=mode):
                chart.reset_cache()
                chart.draw(self.data, 0, mode)
                chart.canvas.draw()
                self.assertIsNone(chart._manual_view)
                axes = chart.axes
                axes.set_xlim(0.6, 0.7)
                axes.set_ylim(0.2, 0.3)
                chart.draw(self.data, 1, mode)
                chart.canvas.draw()
                self.assertIs(chart.figure.axes[0], axes)
                np.testing.assert_allclose(axes.get_xlim(), (0.6, 0.7))
                np.testing.assert_allclose(axes.get_ylim(), (0.2, 0.3))

    def test_home_restores_current_frame_automatic_limits(self):
        chart = self.window.chart
        chart.draw(self.data, 1, "PF")
        expected = (chart.axes.get_xlim(), chart.axes.get_ylim())
        chart.axes.set_xlim(0.6, 0.7)
        chart.axes.set_ylim(0.2, 0.3)
        chart.draw(self.data, 1, "PF")
        chart.toolbar.home()
        chart.canvas.draw()
        self.assertIsNone(chart._manual_view)
        np.testing.assert_allclose(chart.axes.get_xlim(), expected[0])
        np.testing.assert_allclose(chart.axes.get_ylim(), expected[1])

    def test_back_forward_navigation_survives_refresh(self):
        chart = self.window.chart
        chart.draw(self.data, 0, "PF")
        original = chart.axes.get_xlim()
        chart.toolbar.push_current()
        chart.axes.set_xlim(0.6, 0.7)
        chart.toolbar.push_current()
        chart.draw(self.data, 1, "PF")
        chart.toolbar.back()
        np.testing.assert_allclose(chart.axes.get_xlim(), original)
        chart.toolbar.forward()
        np.testing.assert_allclose(chart.axes.get_xlim(), (0.6, 0.7))

    def test_new_mode_and_new_history_reset_zoom(self):
        chart = self.window.chart
        chart.draw(self.data, 0, "PF")
        chart.axes.set_xlim(0.6, 0.7)
        chart.draw(self.data, 1, "PS")
        chart.canvas.draw()
        self.assertIsNone(chart._manual_view)
        self.assertNotEqual(chart.axes.get_xlim(), (0.6, 0.7))
        chart.axes.set_xlim(0.6, 0.7)
        chart.reset_cache()
        chart.draw(self.data, 1, "PS")
        chart.canvas.draw()
        self.assertIsNone(chart._manual_view)
        self.assertNotEqual(chart.axes.get_xlim(), (0.6, 0.7))

    def test_dashboard_synchronizes_all_visible_charts_without_future_leak(self):
        self.window.install_frames(self.data)
        self.window.render_latest()
        dashboard = self.window.chart_dashboard
        self.assertEqual(dashboard.visible_modes(), ["PF", "PS", "IGD"])
        for mode in dashboard.visible_modes():
            self.assertEqual(dashboard.charts[mode]._last_request[1], 1)
        self.window.slider.setValue(0)
        self.window.render_latest()
        igd = dashboard.charts["IGD"].axes.lines[0]
        np.testing.assert_array_equal(igd.get_xdata(), [0])

    def test_workspace_switch_preserves_result_and_parameter_draft(self):
        self.window.install_frames(self.data)
        self.window.parameter_fields["problem"]["solution_num"].setText("42")
        self.window.switch_workspace(1)
        self.assertIs(self.window.frames, self.data)
        self.window.switch_workspace(0)
        self.assertEqual(self.window.parameter_fields["problem"]["solution_num"].text(), "42")
        self.assertIn("NoResponse", self.window.selection_label.text())

    def test_registry_refresh_preserves_drafts_and_replay_label(self):
        self.window.install_frames(self.data)
        before = self.window.selection_label.text()
        self.window.parameter_fields["search"]["seed"].setText("47")
        self.window.refresh_registry()
        self.assertEqual(self.window.parameter_fields["search"]["seed"].text(), "47")
        self.assertEqual(self.window.selection_label.text(), before)


if __name__ == "__main__":
    unittest.main()
