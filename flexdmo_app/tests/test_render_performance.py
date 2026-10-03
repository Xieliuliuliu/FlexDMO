"""Rendering budgets and artist lifetimes, without machine-speed assertions."""
import time
import unittest
from unittest.mock import PropertyMock, patch

import numpy as np
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from flexdmo_app.charts import ChartWidget
from flexdmo_app.tests.test_interactions import frames
from flexdmo_app.window import FlexDMOWindow


class RenderPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.chart = ChartWidget()
        self.data = frames()

    def tearDown(self):
        self.chart.close()
        self.chart.deleteLater()
        self.app.processEvents()

    def test_each_mode_reuses_artists_without_accumulating_constraints(self):
        for mode in ("PF", "PS", "IGD", "CV"):
            self.chart.draw(self.data, 0, mode)
            original = {k: id(v) for k, v in self.chart._artists.items()}
            for i in range(20):
                self.chart.draw(self.data, i % 2, mode)
                self.assertEqual(original, {k: id(v) for k, v in self.chart._artists.items()})
                self.assertLessEqual(len(self.chart.axes.patches), 1)
            self.assertIsNone(self.chart.figure.get_layout_engine())

    def test_clear_request_hides_previous_data_and_next_frame_restores_it(self):
        self.chart.draw(self.data, 0, "PF")
        self.chart.draw([], -1, "PF")
        self.assertTrue(self.chart._artists["empty"].get_visible())
        self.assertFalse(self.chart._artists["feasible"].get_visible())
        self.assertTrue(all(not p.get_visible() for p in self.chart.axes.patches))
        self.chart.draw(self.data, 1, "PF")
        self.assertFalse(self.chart._artists["empty"].get_visible())
        self.assertTrue(self.chart._artists["feasible"].get_visible())

    def test_async_initial_paint_does_not_pin_live_igd_to_first_environment(self):
        self.chart.draw([], -1, "IGD")
        self.chart.show()
        QTest.qWait(180)
        history = [dict(self.data[0], t=i, evaluate_times=i + 1) for i in range(5)]
        for index in range(len(history)):
            self.chart.draw(history, index, "IGD")
            self.chart.canvas.draw()
            self.app.processEvents()
            self.assertIsNone(self.chart._manual_view)
            xmin, xmax = self.chart.axes.get_xlim()
            self.assertLess(xmin, 0)
            self.assertGreater(xmax, index)
        np.testing.assert_array_equal(self.chart._artists["line"].get_xdata(), range(5))

    def test_forward_igd_reads_only_new_frames_and_backward_has_no_future_leak(self):
        class TrackedFrames(list):
            def __getitem__(self, key):
                self.reads.append(key)
                return super().__getitem__(key)
        history = TrackedFrames(dict(self.data[0], t=i // 50, evaluate_times=i + 1) for i in range(103))
        history.reads = []
        self.chart.draw(history, 100, "IGD")
        history.reads.clear()
        self.chart.draw(history, 102, "IGD")
        self.assertTrue(all(i >= 100 for i in history.reads))
        self.chart.draw(history, 30, "IGD")
        np.testing.assert_array_equal(self.chart._artists["line"].get_xdata(), [0])

    def test_environment_only_replacement_refreshes_igd_at_same_cursor(self):
        history = [self.data[0]]
        self.chart.draw(history, 0, "IGD")
        history[0] = dict(self.data[1], t=0, evaluate_times=100)
        self.chart.draw(history, 0, "IGD")
        self.assertIs(self.chart._latest_environments[0], history[0])
        self.assertEqual(self.chart._artists["line"].get_ydata()[0], self.chart.igd(history[0]))

    def test_resize_storm_defers_rasterization_and_keeps_zoom(self):
        self.chart.show()
        self.chart.draw(self.data, 0, "PF")
        QTest.qWait(200)
        self.chart.axes.set_xlim(0.6, 0.7)
        canvas = self.chart.canvas
        with patch.object(canvas, "draw", wraps=canvas.draw) as draw:
            for i in range(10):
                canvas.resize(380 + i * 2, 260 + i)
                self.app.processEvents()
                QTest.qWait(5)
            self.assertEqual(draw.call_count, 0)
            QTest.qWait(180)
            self.assertEqual(draw.call_count, 1)
            np.testing.assert_allclose(self.chart.axes.get_xlim(), (0.6, 0.7))

    def test_drag_defers_only_live_drawing_not_received_frames(self):
        window = FlexDMOWindow()
        try:
            window.install_frames(list(self.data))
            count = len(window.frames)
            with patch.object(type(window.controller), "active", new_callable=PropertyMock, return_value=True), \
                    patch.object(window.chart_dashboard, "draw") as draw:
                window._interaction_until = time.monotonic() + 10
                for i in range(8):
                    window.receive_frame(dict(self.data[1], evaluate_times=100 + i))
                    window.render_latest()
                self.assertEqual(len(window.frames), count + 8)
                self.assertTrue(window.pending_draw)
                draw.assert_not_called()
                window._interaction_until = 0
                window.render_latest()
                draw.assert_called_once()
                self.assertEqual(draw.call_args.args[1], len(window.frames) - 1)
        finally:
            window.dirty = False
            window.close()
            window.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
