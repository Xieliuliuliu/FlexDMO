"""Responsive Matplotlib charts for the desktop workspace."""
import time
import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib.transforms import Bbox
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout

from utils.metrics import calculate_IGD


def shade_constraints(ax, descriptors):
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    for constraint in descriptors or []:
        style = {"color": "#aab2bf", "alpha": 0.27, "zorder": 0}
        if constraint.get("kind") == "circle":
            ax.add_patch(Circle(constraint["center"], constraint["radius"], **style))
            continue
        axis = constraint.get("axis")
        if axis not in (0, 1):
            continue
        low, high = (xmin, xmax) if axis == 0 else (ymin, ymax)
        if constraint.get("kind") == "interval":
            low, high = max(low, constraint["lower"]), min(high, constraint["upper"])
        else:
            operator = constraint.get("operator")
            if operator in (">", ">="):
                high = min(high, constraint["threshold"])
            elif operator in ("<", "<="):
                low = max(low, constraint["threshold"])
            else:
                continue
        if low < high:
            (ax.axvspan if axis == 0 else ax.axhspan)(low, high, **style)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


class PreviewToolbar(NavigationToolbar2QT):
    def home(self, *args):
        # Return to the current frame's automatic bounds, not a stale frame's
        # saved bounds in Matplotlib's navigation stack.
        self.parent().reset_view()


class ResponsiveCanvas(FigureCanvasQTAgg):
    """Scale the previous image during resize; rasterize once after settling."""

    def __init__(self, figure):
        self._preview = None
        self.last_draw_seconds = 0.0
        super().__init__(figure)
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(120)
        self.resize_timer.timeout.connect(self._finish_resize)

    def resizeEvent(self, event):
        if hasattr(self, "resize_timer"):
            if not self.resize_timer.isActive() and hasattr(self, "renderer"):
                buffer = self.renderer.buffer_rgba()
                self._preview = QImage(buffer, int(self.renderer.width), int(self.renderer.height),
                                       QImage.Format.Format_RGBA8888).copy()
            self.resize_timer.start()
        super().resizeEvent(event)

    def draw_idle(self):
        if hasattr(self, "resize_timer") and self.resize_timer.isActive():
            return
        super().draw_idle()

    def _draw_idle(self):
        if hasattr(self, "resize_timer") and self.resize_timer.isActive():
            return
        super()._draw_idle()

    def _finish_resize(self):
        self._preview = None
        if self._draw_pending:
            QTimer.singleShot(0, self._draw_idle)
        else:
            super().draw_idle()

    def paintEvent(self, event):
        if self._preview is not None and self.resize_timer.isActive():
            painter = QPainter(self)
            try:
                painter.drawImage(self.rect(), self._preview)
            finally:
                painter.end()
            return
        super().paintEvent(event)

    def draw(self):
        # Explicit draw/export remains synchronous and uses the exact current
        # figure size, even while a resize redraw would otherwise be deferred.
        if hasattr(self, "resize_timer"):
            self.resize_timer.stop()
        self._preview = None
        started = time.perf_counter()
        super().draw()
        self.last_draw_seconds = time.perf_counter() - started


class ChartWidget(QWidget):
    def __init__(self, parent=None, initial_mode="PF"):
        super().__init__(parent)
        self.setObjectName("chart-card")
        self.figure = Figure(figsize=(7, 4.6), facecolor="white")
        # Stable margins avoid a full constrained-layout solve on every frame.
        self.figure.subplots_adjust(left=0.16, right=0.97, bottom=0.22, top=0.86)
        self.axes = self.figure.add_subplot(111)
        self._mode = None
        self._manual_view = None
        self._drawing = False
        self._last_request = ([], -1, "PF")
        self.canvas = ResponsiveCanvas(self.figure)
        self.toolbar = PreviewToolbar(self.canvas, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        self.igd_cache = {}
        self._history_frames = None
        self._history_index = -1
        self._latest_environments = {}
        self._artists = {}
        self._constraint_artists = []
        self.draw([], -1, initial_mode)

    def reset_cache(self):
        self.igd_cache.clear()
        self._history_frames = None
        self._history_index = -1
        self._latest_environments = {}
        self._manual_view = None
        self._last_request = ([], -1, self._mode or "PF")
        self._drawing = True
        try:
            self._setup_axes(self._mode or "PF")
        finally:
            self._drawing = False
        self.toolbar.update()

    def reset_view(self):
        self._manual_view = None
        self.toolbar.update()
        self.draw(*self._last_request)

    def _capture_view(self, axes):
        # Initial/asynchronous canvas paints can resolve lazy autoscaling after
        # draw() returns. Only explicit limits (including toolbar pan/zoom)
        # turn autoscaling off; do not pin a live chart to its first frame.
        if not self._drawing and not (axes.get_autoscalex_on() and axes.get_autoscaley_on()):
            self._manual_view = (axes.get_xlim(), axes.get_ylim())

    def _apply_view(self):
        if self._manual_view is not None:
            self.axes.set_xlim(self._manual_view[0])
            self.axes.set_ylim(self._manual_view[1])

    def igd(self, frame):
        key = (int(frame["t"]), int(frame["evaluate_times"]))
        if key not in self.igd_cache:
            self.igd_cache[key] = float(calculate_IGD(
                frame["population"].get_feasible_objective_matrix(), frame["POF"]))
        return self.igd_cache[key]

    def draw(self, frames, index, mode):
        self._last_request = (frames, index, mode)
        if mode != self._mode:
            self._mode = mode
            self._manual_view = None
            self.toolbar.update()
        self._drawing = True
        try:
            if not self._artists or self._artists.get("mode") != mode:
                self._setup_axes(mode)
            self._draw_frame(frames, index, mode)
        finally:
            self._drawing = False

    def _setup_axes(self, mode):
        # Clear only on a mode/run change. Ordinary frames reuse all artists.
        ax = self.axes
        ax.clear()
        self._constraint_artists = []
        ax.callbacks.connect("xlim_changed", self._capture_view)
        ax.callbacks.connect("ylim_changed", self._capture_view)
        ax.tick_params(labelsize=9)
        ax.grid(color="#dce3ed", alpha=0.5, linewidth=0.6)
        for spine in ax.spines.values():
            spine.set_color("#d3dce7")
        ax.tick_params(colors="#58687c")
        labels = {"PF": ("f1", "f2"), "PS": ("Decision variable", "Value"),
                  "IGD": ("Environment", "IGD"), "CV": ("Individual", "Constraint violation")}
        ax.set_title(mode, fontsize=11, pad=10, color="#24334b")
        ax.set_xlabel(labels[mode][0], fontsize=9)
        ax.set_ylabel(labels[mode][1], fontsize=9)
        artists = self._artists = {"mode": mode}
        artists["empty"] = ax.text(0.5, 0.5, "Start a run or open a saved result",
                                   transform=ax.transAxes, ha="center", va="center", color="#728097", fontsize=10)
        artists["note"] = ax.text(0.03, 0.95, "", transform=ax.transAxes, va="top", fontsize=8)
        if mode == "PF":
            artists["true"] = ax.scatter([], [], s=5, c="#efa83e", label="True PF")
            artists["feasible"] = ax.scatter([], [], s=17, c="#149bad", label="Feasible")
            artists["infeasible"] = ax.scatter([], [], s=18, c="#db6972", marker="x", label="Infeasible")
        elif mode == "PS":
            artists["population"] = LineCollection([], colors="#149bad", alpha=0.17, linewidths=0.8)
            ax.add_collection(artists["population"])
            artists["true"], = ax.plot([], [], color="#efa83e", linewidth=2, label="Median true PS")
        elif mode == "IGD":
            artists["line"], = ax.plot([], [], "o-", color="#149bad", markersize=4, label="IGD (feasible)")
        else:
            artists["bars"] = PolyCollection([], facecolors="#db6972", label="Constraint violation")
            ax.add_collection(artists["bars"])
        artists["legend"] = ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
        artists["legend"].set_visible(False)

    def _autoscale(self, *points):
        if self._manual_view is not None:
            self._apply_view()
            return
        ax = self.axes
        ax.dataLim = Bbox.null()
        for values in points:
            values = np.asarray(values, dtype=float).reshape(-1, 2)
            finite = values[np.isfinite(values).all(axis=1)]
            if len(finite):
                ax.update_datalim(finite)
        ax.set_autoscalex_on(True)
        ax.set_autoscaley_on(True)
        ax.autoscale_view()

    def _igd_history(self, frames, index):
        if frames is not self._history_frames or index < self._history_index:
            self._latest_environments = {}
            start = 0
        else:
            # Revisit the previous cursor: environment-only history can replace
            # its latest frame in-place rather than append a new list entry.
            start = max(0, self._history_index)
        for position in range(start, index + 1):
            frame = frames[position]
            self._latest_environments[int(frame["t"])] = frame
        self._history_frames = frames
        self._history_index = index
        steps = sorted(self._latest_environments)
        return np.asarray(steps), np.asarray([self.igd(self._latest_environments[t]) for t in steps])

    def _draw_frame(self, frames, index, mode):
        ax, artists = self.axes, self._artists
        if not frames or index < 0:
            for key, artist in artists.items():
                if key not in ("mode", "empty"):
                    artist.set_visible(False)
            artists["empty"].set_visible(True)
            artists["legend"].set_visible(False)
            for patch in self._constraint_artists:
                patch.set_visible(False)
            ax.get_xlim()
            ax.get_ylim()
            self.canvas.draw_idle()
            return
        for key, artist in artists.items():
            if key != "mode":
                artist.set_visible(key != "empty")
        artists["note"].set_text("")
        frame = frames[index]
        pop = frame["population"]
        if mode == "PF":
            values = pop.get_objective_matrix()
            true = np.asarray(frame["POF"])
            feasible = np.asarray([ind.feasible for ind in pop], dtype=bool)
            artists["true"].set_offsets(true[:, :2])
            artists["feasible"].set_offsets(values[feasible, :2])
            artists["infeasible"].set_offsets(values[~feasible, :2])
            self._autoscale(true[:, :2], values[:, :2])
            for patch in self._constraint_artists:
                patch.remove()
            before = len(ax.patches)
            shade_constraints(ax, frame.get("objective_constraints"))
            self._constraint_artists = list(ax.patches)[before:]
            if values.shape[1] > 2:
                artists["note"].set_text("Projection: objectives 1 & 2")
        elif mode == "PS":
            values = pop.get_decision_matrix()
            true = np.asarray(frame["POS"])
            axes = np.arange(1, values.shape[1] + 1)
            segments = np.stack((np.broadcast_to(axes, values.shape), values), axis=-1)
            median = np.median(true, axis=0)
            artists["population"].set_segments(segments)
            artists["true"].set_data(axes, median)
            self._autoscale(segments.reshape(-1, 2), np.column_stack((axes, median)))
        elif mode == "IGD":
            steps, scores = self._igd_history(frames, index)
            finite = np.isfinite(scores)
            artists["line"].set_data(steps[finite], scores[finite])
            self._autoscale(np.column_stack((steps[finite], scores[finite])))
            if not finite.all():
                artists["note"].set_text("No feasible solutions in some environments (IGD = infinity)")
        else:
            violations = pop.get_constraint_violation_vector()
            x = np.arange(len(violations))
            bars = np.stack((np.column_stack((x - 0.4, np.zeros(len(x)))),
                             np.column_stack((x - 0.4, violations)),
                             np.column_stack((x + 0.4, violations)),
                             np.column_stack((x + 0.4, np.zeros(len(x))))), axis=1)
            artists["bars"].set_verts(bars)
            self._autoscale(bars.reshape(-1, 2))
        # Resolve lazy autoscaling while the draw guard is still active, so
        # canvas painting cannot mistake automatic limits for a user zoom.
        ax.get_xlim()
        ax.get_ylim()
        self.canvas.draw_idle()
