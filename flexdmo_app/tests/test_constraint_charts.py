"""Constraint visuals tested against the production Qt charts."""
import unittest

import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from PySide6.QtWidgets import QApplication

from flexdmo_app.charts import ChartWidget, shade_constraints
from flexdmo_app.tests.test_interactions import frames


class ConstraintChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.chart = ChartWidget()
        self.data = frames()

    def tearDown(self):
        self.chart.close()
        self.chart.deleteLater()
        self.app.processEvents()

    def test_pf_marks_infeasible_background_without_changing_bounds(self):
        self.chart.draw(self.data, 1, "PF")
        patches = self.chart._constraint_artists
        self.assertTrue(patches)
        for patch in patches:
            np.testing.assert_allclose(patch.get_facecolor(), to_rgba("#aab2bf", 0.27))
        self.assertTrue(np.isfinite(self.chart.axes.get_xlim()).all())
        self.assertTrue(np.isfinite(self.chart.axes.get_ylim()).all())

    def test_interval_circle_and_boundary_shading_preserve_axes(self):
        figure = Figure()
        axes = figure.subplots()
        axes.set_xlim(0, 2)
        axes.set_ylim(0, 3)
        shade_constraints(axes, [
            {"kind": "interval", "axis": 0, "lower": 0.3, "upper": 0.8},
            {"kind": "circle", "center": [1, 1], "radius": 0.2},
            {"axis": 1, "operator": ">=", "threshold": 0.5},
            {"axis": 0, "operator": ">=", "threshold": -1},
        ])
        self.assertEqual(len(axes.patches), 3)
        self.assertEqual(axes.get_xlim(), (0, 2))
        self.assertEqual(axes.get_ylim(), (0, 3))

    def test_replaying_pf_does_not_accumulate_background_patches(self):
        self.chart.draw(self.data, 0, "PF")
        count = len(self.chart.axes.patches)
        for index in (1, 0, 1, 0):
            self.chart.draw(self.data, index, "PF")
            self.assertEqual(len(self.chart.axes.patches), count)

    def test_ps_shows_every_individual_and_decision_dimension(self):
        self.chart.draw(self.data, 0, "PS")
        decisions = self.data[0]["population"].get_decision_matrix()
        segments = self.chart._artists["population"].get_segments()
        self.assertEqual(len(segments), len(decisions))
        for segment, decision in zip(segments, decisions):
            np.testing.assert_array_equal(segment[:, 0], np.arange(1, len(decision) + 1))
            np.testing.assert_array_equal(segment[:, 1], decision)

    def test_cv_bars_match_actual_constraint_violations(self):
        self.chart.draw(self.data, 1, "CV")
        bars = self.chart._artists["bars"]
        violations = self.data[1]["population"].get_constraint_violation_vector()
        self.assertEqual(len(bars.get_paths()), len(violations))
        for path, violation in zip(bars.get_paths(), violations):
            self.assertAlmostEqual(path.vertices[:, 1].max(), violation)
        np.testing.assert_allclose(bars.get_facecolor()[0], to_rgba("#db6972"))


if __name__ == "__main__":
    unittest.main()
