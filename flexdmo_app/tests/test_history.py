"""History click, lifetime, keyboard and accessibility regressions."""
import unittest
from unittest.mock import patch

import main_qt
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible, QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from flexdmo_app.tests.test_interactions import frames
from flexdmo_app.window import FlexDMOWindow


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.window = FlexDMOWindow()
        self.data = frames()
        self.data.insert(1, dict(self.data[0], evaluate_times=25))
        self.window.install_frames(self.data)

    def tearDown(self):
        self.window.dirty = False
        self.window.controller.shutdown()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_history_does_not_expose_item_view_selection(self):
        panel = self.window.history_panel
        self.assertFalse(panel.findChildren(QAbstractItemView))
        for widget in [panel, panel.body] + [e["button"] for e in panel.entries.values()]:
            interface = QAccessible.queryAccessibleInterface(widget)
            self.assertIsNotNone(interface)
            self.assertTrue(interface.isValid())
            self.assertIsNone(interface.selectionInterface())
            self.assertNotIn(interface.role(), (QAccessible.Role.Tree, QAccessible.Role.Table, QAccessible.Role.List))

    def test_light_theme_stays_readable_with_dark_system_palette(self):
        original = self.app.palette()
        dark = QPalette(original)
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                     QPalette.ColorRole.ButtonText):
            dark.setColor(role, QColor("#ffffff"))
        dark.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        try:
            self.app.setPalette(dark)
            self.window._theme()
            self.window.show()
            self.app.processEvents()
            control = self.window.history_panel.entries[0]["button"]
            for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
                self.assertEqual(control.palette().color(group, QPalette.ColorRole.ButtonText).name(), "#24334b")
                self.assertEqual(self.app.palette().color(group, QPalette.ColorRole.WindowText).name(), "#24334b")
        finally:
            self.app.setPalette(original)

    def test_click_selects_latest_snapshot_and_synchronizes_charts(self):
        self.window.history_panel.entries[0]["button"].click()
        self.assertEqual(self.window.index, 1)
        self.assertEqual(self.window.slider.value(), 1)
        self.window.render_latest()
        self.assertEqual(self.window.history_panel.current_environment, 0)
        for mode in self.window.chart_dashboard.visible_modes():
            self.assertEqual(self.window.chart_dashboard.charts[mode]._last_request[1], 1)

    def test_button_identity_survives_updates_for_same_environment(self):
        panel = self.window.history_panel
        original = panel.entries[1]["button"]
        self.window.receive_frame(dict(self.data[-1], evaluate_times=40))
        self.assertIs(panel.entries[1]["button"], original)
        original.click()
        self.assertEqual(self.window.index, 3)
        self.assertIn("40", original.text())

    def test_slider_tracks_history_highlight_without_emitting_click(self):
        panel = self.window.history_panel
        events = []
        panel.frame_requested.connect(lambda *args: events.append(args))
        self.window.slider.setValue(0)
        self.assertTrue(panel.entries[0]["button"].isChecked())
        self.assertFalse(panel.entries[1]["button"].isChecked())
        self.assertFalse(events)

    def test_history_click_pauses_automatic_playback(self):
        self.window.toggle_replay()
        self.assertTrue(self.window.replay_timer.isActive())
        self.window.history_panel.entries[1]["button"].click()
        self.assertFalse(self.window.replay_timer.isActive())
        self.assertEqual(self.window.play_button.text(), "播放")

    def test_events_from_replaced_history_cannot_select_new_results(self):
        panel = self.window.history_panel
        previous = panel.generation
        old_button = panel.entries[0]["button"]
        self.window.install_frames(self.data)
        self.assertGreater(panel.generation, previous)
        current = self.window.index
        old_button.click()  # Hidden, disabled and waiting for deferred deletion.
        panel._activate(0, previous)
        panel.frame_requested.emit(0, previous)  # Simulate a queued old signal.
        self.assertEqual(self.window.index, current)

    def test_busy_result_io_cannot_be_interrupted_by_history(self):
        self.window.io_busy = True
        self.window.update_controls()
        current = self.window.index
        panel = self.window.history_panel
        panel.entries[0]["button"].click()
        panel.frame_requested.emit(0, panel.generation)
        self.assertEqual(self.window.index, current)
        self.window.io_busy = False

    def test_keyboard_navigation_and_enter_activate_environment(self):
        self.window.show()
        self.app.processEvents()
        panel = self.window.history_panel
        first, last = (panel.entries[t]["button"] for t in (0, 1))
        first.setFocus()
        QTest.keyClick(first, Qt.Key.Key_Down)
        self.assertIs(self.app.focusWidget(), last)
        QTest.keyClick(last, Qt.Key.Key_Return)
        self.assertEqual(self.window.index, 2)
        QTest.keyClick(last, Qt.Key.Key_Home)
        self.assertIs(self.app.focusWidget(), first)
        QTest.keyClick(first, Qt.Key.Key_Space)
        self.assertEqual(self.window.index, 1)

    def test_rapid_clicks_coalesce_to_one_latest_draw(self):
        self.window.render_timer.stop()
        panel = self.window.history_panel
        with patch.object(self.window.chart_dashboard, "draw") as draw:
            for _ in range(20):
                panel.entries[1]["button"].click()
                panel.entries[0]["button"].click()
            self.window.render_latest()
            self.window.render_latest()
            draw.assert_called_once()
            self.assertEqual(draw.call_args.args[1], 1)


if __name__ == "__main__":
    unittest.main()
