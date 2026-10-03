"""Year ordering and filtering must preserve the selected batch algorithms."""
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flexdmo_app.batch_ui import algorithm_sort_key, algorithm_year
from flexdmo_app.component_selector import ComponentSelector
from flexdmo_app.window import FlexDMOWindow


class BatchYearTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_missing_year_baseline_and_equal_years(self):
        rows = [{"name": "old", "year": 2007}, {"name": "B", "year": "2024"},
                {"name": "A", "year": 2024}, {"name": "unknown"},
                {"name": "baseline", "year": 2025, "publication_type": "baseline"}]
        self.assertEqual([r["name"] for r in sorted(rows, key=algorithm_sort_key)], ["A", "B", "old", "baseline", "unknown"])
        self.assertIsNone(algorithm_year({"year": True}))

    def test_filters_refresh_configuration_and_workspace_switches(self):
        window = FlexDMOWindow()
        try:
            batch = window.batch
            for kind in ("dynamic", "search"):
                choices = batch.lists[kind]
                rows = [choices.item(i).data(Qt.ItemDataRole.UserRole) for i in range(choices.count())]
                self.assertEqual(rows, sorted(rows, key=algorithm_sort_key))
                selector = window.selectors[kind]
                self.assertIsInstance(selector, ComponentSelector)
                self.assertIs(type(selector), type(choices))
                self.assertFalse(selector.multiple)
                self.assertTrue(choices.multiple)
                self.assertEqual([selector.itemData(i)["folder_name"] for i in range(selector.count())],
                                 [r["folder_name"] for r in rows])
                self.assertEqual([selector.itemText(i) for i in range(selector.count())],
                                 [choices.item(i).text() for i in range(choices.count())])
            names = {k: {r["name"] for r in rows} for k, rows in batch.selection().items()}
            batch.filters["dynamic"].setText("2024")
            visible = [batch.lists["dynamic"].item(i) for i in range(batch.lists["dynamic"].count()) if not batch.lists["dynamic"].item(i).isHidden()]
            self.assertTrue(visible)
            self.assertTrue(all("2024" in item.text() for item in visible))
            batch.refresh_registry()
            self.assertEqual(names, {k: {r["name"] for r in rows} for k, rows in batch.selection().items()})
            self.assertTrue(any(batch.lists["dynamic"].item(i).isHidden() for i in range(batch.lists["dynamic"].count())))
            config = {"version": 1, "selection": {k: list(v) for k, v in names.items()}, "shared": batch.shared(), "profiles": []}
            batch.check_all("dynamic", False)
            batch.apply_configuration(config)
            for i in range(20):
                window.switch_workspace(i % 2)
                batch.choice_tabs.setCurrentIndex(i % 3)
                self.app.processEvents()
            self.assertEqual(names, {k: {r["name"] for r in rows} for k, rows in batch.selection().items()})
            window.switch_workspace(0)
            window.show()
            for width, height in ((1360, 860), (900, 680), (700, 560)):
                window.resize(width, height)
                self.app.processEvents()
                self.assertEqual(window.settings_tabs.widget(0).horizontalScrollBar().maximum(), 0)
        finally:
            window.dirty = False
            window.close()
            window.deleteLater()
            self.app.processEvents()
