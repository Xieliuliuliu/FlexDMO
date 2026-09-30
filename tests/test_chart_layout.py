import unittest

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.layout_engine import ConstrainedLayoutEngine

from plots.test_module.draw_population import fit_chart_layout


class EmbeddedChartLayoutTests(unittest.TestCase):
    def test_chart_layout_preserves_responsive_layout_engine(self):
        figure = Figure(figsize=(6, 3), dpi=100, layout='constrained')
        ax = figure.add_subplot(111)
        fit_chart_layout(figure)
        self.assertIsInstance(figure.get_layout_engine(), ConstrainedLayoutEngine)
        self.assertEqual(ax.get_xticklabels()[0].get_fontsize(), 9)

    def test_ticks_stay_inside_resized_chart(self):
        for width, height in ((800, 450), (480, 260), (600, 180)):
            with self.subTest(size=(width, height)):
                figure = Figure(figsize=(width / 100, height / 100), dpi=100, layout='constrained')
                canvas = FigureCanvasAgg(figure)
                ax = figure.add_subplot(111)
                ax.set_title('Dynamic PF (t=1, evaluations=7000)', fontsize=10)
                ax.set_xlabel('f1', fontsize=9)
                ax.set_ylabel('f2', fontsize=9)
                fit_chart_layout(figure)
                canvas.draw()
                for label in ax.get_xticklabels() + ax.get_yticklabels():
                    bbox = label.get_window_extent(canvas.get_renderer())
                    self.assertGreaterEqual(bbox.x0, 0)
                    self.assertGreaterEqual(bbox.y0, 0)
                    self.assertLessEqual(bbox.x1, width)
                    self.assertLessEqual(bbox.y1, height)


if __name__ == '__main__':
    unittest.main()
