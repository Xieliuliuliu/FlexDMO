"""Qt-native Matplotlib canvas, with no Tk global state."""
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.patches import Circle
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


class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(7, 4.6), layout="constrained", facecolor="white")
        self.axes = self.figure.add_subplot(111)
        self._mode = None
        self._manual_view = None
        self._drawing = False
        self._last_request = ([], -1, "PF")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = PreviewToolbar(self.canvas, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        self.igd_cache = {}
        self.draw([], -1, "PF")

    def reset_cache(self):
        self.igd_cache.clear()
        self._manual_view = None
        self._last_request = ([], -1, self._mode or "PF")
        self.toolbar.update()

    def reset_view(self):
        self._manual_view = None
        self.toolbar.update()
        self.draw(*self._last_request)

    def _capture_view(self, axes):
        if not self._drawing:
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
            self._draw_frame(frames, index, mode)
        finally:
            self._drawing = False

    def _draw_frame(self, frames, index, mode):
        # Keep the axes identity so toolbar back/forward entries remain valid.
        ax = self.axes
        ax.clear()
        ax.callbacks.connect("xlim_changed", self._capture_view)
        ax.callbacks.connect("ylim_changed", self._capture_view)
        ax.tick_params(labelsize=9)
        ax.grid(alpha=0.17)
        if not frames or index < 0:
            ax.text(0.5, 0.5, "Start a run or open a saved result" if mode == "PF" else "Waiting for run snapshots",
                    transform=ax.transAxes, ha="center", va="center", color="#728097", fontsize=12)
            labels = {"PF": ("f1", "f2"), "PS": ("Decision variable", "Value"),
                      "IGD": ("Environment", "IGD"), "CV": ("Individual", "Constraint violation")}
            ax.set_title(mode, fontsize=11)
            ax.set_xlabel(labels[mode][0])
            ax.set_ylabel(labels[mode][1])
            self.canvas.draw_idle()
            return
        frame = frames[index]
        pop = frame["population"]
        if mode == "PF":
            values = pop.get_objective_matrix()
            true = np.asarray(frame["POF"])
            feasible = np.asarray([ind.feasible for ind in pop], dtype=bool)
            ax.scatter(true[:, 0], true[:, 1], s=5, c="#efa83e", label="True PF")
            if feasible.any():
                ax.scatter(values[feasible, 0], values[feasible, 1], s=17, c="#149bad", label="Feasible")
            if (~feasible).any():
                ax.scatter(values[~feasible, 0], values[~feasible, 1], s=18, c="#db6972", marker="x", label="Infeasible")
            self._apply_view()
            shade_constraints(ax, frame.get("objective_constraints"))
            ax.set_xlabel("f1")
            ax.set_ylabel("f2")
            if values.shape[1] > 2:
                ax.text(0.02, 0.02, "Projection: objectives 1 & 2", transform=ax.transAxes, fontsize=9)
        elif mode == "PS":
            values = pop.get_decision_matrix()
            true = np.asarray(frame["POS"])
            axes = np.arange(1, values.shape[1] + 1)
            ax.plot(axes, values.T, color="#149bad", alpha=0.17, linewidth=0.8)
            ax.plot(axes, np.median(true, axis=0), color="#efa83e", linewidth=2, label="Median true PS")
            ax.set_xlabel("Decision variable")
            ax.set_ylabel("Value")
        elif mode == "IGD":
            # Only the latest snapshot of each environment up to the cursor.
            last = {}
            for previous in frames[:index + 1]:
                last[int(previous["t"])] = previous
            steps = sorted(last)
            scores = [self.igd(last[t]) for t in steps]
            finite = np.isfinite(scores)
            ax.plot(np.asarray(steps)[finite], np.asarray(scores)[finite], "o-", color="#149bad", label="IGD (feasible)")
            if not finite.all():
                ax.text(0.03, 0.95, "Some environments have no feasible solutions (IGD = infinity)",
                        transform=ax.transAxes, va="top", fontsize=8)
            ax.set_xlabel("Environment")
            ax.set_ylabel("IGD")
        else:
            violations = pop.get_constraint_violation_vector()
            ax.bar(np.arange(len(violations)), violations, color="#db6972", width=0.8, label="Constraint violation")
            ax.set_xlabel("Individual")
            ax.set_ylabel("Total positive constraint violation")
        ax.set_title(mode, fontsize=11, pad=12)
        self._apply_view()
        ax.legend(loc="best", fontsize=8)
        # Resolve lazy autoscaling while the draw guard is still active, so
        # canvas painting cannot mistake automatic limits for a user zoom.
        ax.get_xlim()
        ax.get_ylim()
        self.canvas.draw_idle()
