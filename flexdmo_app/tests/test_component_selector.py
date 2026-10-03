"""Shared control semantics independent of test/batch workspace wiring."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication

from flexdmo_app.component_selector import ComponentSelector


ROWS = [{"name": "old", "folder_name": "old", "year": 2007},
        {"name": "new", "folder_name": "new", "year": 2024},
        {"name": "unknown", "folder_name": "unknown"}]


class ComponentSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() == "cocoa":
            QAccessible.setActive(True)

    def setUp(self):
        self.selector = ComponentSelector("dynamic")

    def tearDown(self):
        self.selector.close()
        self.selector.deleteLater()
        self.app.processEvents()

    def test_single_filter_preserves_selection_and_keyboard_skips_hidden(self):
        selector = self.selector
        selector.set_records(ROWS, current="old")
        spy = QSignalSpy(selector.currentIndexChanged)
        selector.filter_box.setText("2024")
        self.assertEqual(selector.currentData()["name"], "old")
        self.assertIn("old", selector.summary.text())
        self.assertEqual(spy.count(), 0)
        selector.filter_box.clear()
        selector.setCurrentIndex(0)
        selector.filter_box.setText("年份未注明")
        selector.filter_box.clear()
        selector.item(1).setHidden(True)
        QTest.keyClick(selector.item(0).control, Qt.Key.Key_Down)
        self.assertEqual(selector.currentData()["name"], "unknown")
        self.assertEqual(sum(e.control.isChecked() for e in selector.entries), 1)

    def test_refresh_ignores_old_callbacks_and_retains_query(self):
        selector = self.selector
        selector.set_records(ROWS, current="old")
        stale = selector.item(0)
        generation = selector._generation
        selector.filter_box.setText("2024")
        selector.set_records(ROWS, current="old")
        selector._clicked(stale, generation)
        selector._changed(stale, generation)
        self.assertEqual(selector.currentData()["name"], "old")
        self.assertEqual(selector.filter_box.text(), "2024")
        self.assertEqual(sum(not e.isHidden() for e in selector.entries), 1)

    def test_multi_selection_is_independent_of_focus_and_filter(self):
        self.selector.deleteLater()
        selector = self.selector = ComponentSelector("dynamic", multiple=True)
        selector.set_records(ROWS, current="new", checked={"new", "old"})
        selector.filter_box.setText("2024")
        self.assertIn("筛选外 1 项", selector.summary.text())
        selector.filter_box.clear()
        selector.setCurrentIndex(2)
        self.assertEqual(selector.currentData()["name"], "unknown")
        self.assertEqual(sum(e.control.isChecked() for e in selector.entries), 2)
        QTest.keyClick(selector.item(2).control, Qt.Key.Key_Return)
        self.assertEqual(sum(e.control.isChecked() for e in selector.entries), 3)
        selector.set_records(ROWS, current="unknown", checked={"new", "old", "unknown"})
        self.assertEqual(selector.currentData()["name"], "unknown")
        self.assertEqual(sum(e.control.isChecked() for e in selector.entries), 3)

    def test_blank_filter_result_can_be_cleared_without_losing_choice(self):
        self.selector.set_records(ROWS, current="old")
        self.selector.filter_box.setText("no-such-algorithm")
        self.assertIn("没有匹配项", self.selector.summary.text())
        self.assertEqual(self.selector.currentData()["name"], "old")
        self.selector.filter_box.clear()
        self.assertEqual(sum(not e.isHidden() for e in self.selector.entries), 3)

    def test_native_accessibility_queries_survive_repeated_refreshes(self):
        if self.app.platformName() != "cocoa":
            self.skipTest("Requires the native macOS accessibility bridge")
        from flexdmo_app.tests.cocoa_probe import CocoaProbe
        probe = CocoaProbe()
        self.selector.show()
        for _ in range(30):
            self.selector.set_records(ROWS, current="old")
            self.app.processEvents()
            probe.check_history_widget(self.selector)
            for entry in self.selector.entries:
                probe.check_history_widget(entry.control)
        self.assertEqual(probe.calls, 120)


if __name__ == "__main__":
    unittest.main()
