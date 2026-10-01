"""Synchronized multi-chart workspace with a scrollable narrow layout."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget
from .charts import ChartWidget


class ChartDashboard(QWidget):
    def __init__(self, primary, parent=None):
        super().__init__(parent)
        self.charts = {"PF": primary, **{mode: ChartWidget() for mode in ("PS", "IGD", "CV")}}
        self.mode = "ALL"
        self.request = ([], -1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll)
        for chart in self.charts.values():
            chart.toolbar.setIconSize(QSize(18, 18))
        self._columns = None
        self._arrange()

    def visible_modes(self):
        return ["PF", "PS", "IGD"] if self.mode == "ALL" else ["PF", "PS", "IGD", "CV"] if self.mode == "ALL4" else [self.mode]

    def _arrange(self):
        multiple = self.mode in ("ALL", "ALL4")
        columns = 2 if multiple and self.width() >= 760 else 1
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        visible = self.visible_modes()
        for chart in self.charts.values():
            chart.hide()
            chart.setMinimumHeight(240 if multiple else 180)
        for i, mode in enumerate(visible):
            chart = self.charts["PF"] if not multiple else self.charts[mode]
            chart.show()
            span = columns if len(visible) == 3 and i == 2 else 1
            self.grid.addWidget(chart, i // columns, i % columns, 1, span)
        self.body.setMinimumHeight(((len(visible) + columns - 1) // columns) * 250 if multiple else 0)

    def draw(self, frames, index, mode):
        if mode != self.mode:
            self.mode = mode
            self._arrange()
        self.request = (frames, index)
        for visible in self.visible_modes():
            chart = self.charts["PF"] if mode not in ("ALL", "ALL4") else self.charts[visible]
            chart.draw(frames, index, visible)

    def reset_cache(self):
        self.request = ([], -1)
        for chart in self.charts.values():
            chart.reset_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "grid"):
            columns = 2 if self.mode in ("ALL", "ALL4") and self.width() >= 760 else 1
            if columns != self._columns:
                self._arrange()
