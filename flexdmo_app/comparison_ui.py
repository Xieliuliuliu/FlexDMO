"""Read-only comparison of completed batch runs; no implicit export."""
import math
import queue
import threading

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QVBoxLayout

from .comparison import comparison_runs
from .widgets import ChoiceBox


class ComparisonDialog(QDialog):
    def __init__(self, tasks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量结果对比")
        self.resize(1050, 780)
        self.runs = []
        self.cancel = threading.Event()
        self.inbox = queue.Queue()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.group = ChoiceBox()
        self.mode = ChoiceBox()
        self.mode.addItems(["环境末帧 IGD", "环境末帧可行率", "同环境 PF", "重复运行 MIGD"])
        self.environment, self.seed = ChoiceBox(), ChoiceBox()
        for title, field in (("问题与预算", self.group), ("比较内容", self.mode),
                             ("PF 环境", self.environment), ("PF 随机种子", self.seed)):
            form.addRow(title, field)
        layout.addLayout(form)
        self.figure = Figure(figsize=(8, 4.5), layout="constrained", facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        self.note = QLabel("正在读取已完成结果…")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.group.currentIndexChanged.connect(self.change_group)
        for field in (self.mode, self.environment, self.seed):
            field.currentIndexChanged.connect(self.draw)
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        inbox, cancel = self.inbox, self.cancel
        def worker():
            inbox.put(comparison_runs(tasks, cancel.is_set))
        threading.Thread(target=worker, name="Qt-Comparison-IO", daemon=True).start()

    def poll(self):
        try:
            self.runs, self.errors = self.inbox.get_nowait()
        except queue.Empty:
            return
        self.timer.stop()
        groups = list(dict.fromkeys(r["group"] for r in self.runs))
        self.group.blockSignals(True)
        for index, key in enumerate(groups):
            run = next(r for r in self.runs if r["group"] == key)
            task = run["task"]
            p = task["request"]["params"]["problem"]
            label = f"{task['request']['records']['problem']['name']} · tau={p.get('tau')} / n={p.get('n')} · " + \
                    f"{p.get('decision_num')} 变量 / {p.get('solution_num')} 个体 / {p.get('total_evaluate_time')} 环境 · 配置 {index + 1}"
            self.group.addItem(label, key)
            self.group.setItemData(index, str(p), role=3)  # Qt.ToolTipRole
        self.group.blockSignals(False)
        self.change_group()

    def selected_runs(self):
        return [r for r in self.runs if r["group"] == self.group.currentData()]

    def change_group(self, *args):
        runs = self.selected_runs()
        for field, values in ((self.environment, sorted({t for r in runs for t in r["ends"]})),
                              (self.seed, sorted({r["task"]["seed"] for r in runs}))):
            previous = field.currentData()
            field.blockSignals(True)
            field.clear()
            for value in values:
                field.addItem(str(value), value)
            if previous in values:
                field.setCurrentIndex(values.index(previous))
            field.blockSignals(False)
        self.draw()

    def draw(self, *args):
        if self.cancel.is_set():
            return
        runs, mode = self.selected_runs(), self.mode.currentIndex()
        self.environment.setEnabled(mode == 2)
        self.seed.setEnabled(mode == 2)
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.grid(alpha=0.2)
        variants = list(dict.fromkeys(r["variant"] for r in runs))
        names = {key: next(r["label"] for r in runs if r["variant"] == key) for key in variants}
        # Distinct parameter/code variants remain visibly distinct even when
        # their component names are identical.
        if len(set(names.values())) < len(names):
            names = {key: name + f" [配置 {i + 1}]" for i, (key, name) in enumerate(names.items())}
        colors = {key: f"C{i % 10}" for i, key in enumerate(variants)}
        missing, nonfinite = [], 0
        seen = set()
        if mode in (0, 1):
            for r in runs:
                x = [p[0] for p in r["points"]]
                y = [p[1 if mode == 0 else 2] for p in r["points"]]
                nonfinite += sum(not math.isfinite(v) for v in y)
                y = [v if math.isfinite(v) else np.nan for v in y]
                ax.plot(x, y, marker="o", markersize=3, alpha=0.7, color=colors[r["variant"]],
                        label=names[r["variant"]] if r["variant"] not in seen else "_nolegend_")
                seen.add(r["variant"])
            ax.set(xlabel="Environment", ylabel="IGD" if mode == 0 else "Feasible ratio")
            if mode == 1:
                ax.set_ylim(-0.02, 1.02)
        elif mode == 2:
            t, seed = self.environment.currentData(), self.seed.currentData()
            reference = None
            for r in runs:
                if r["task"]["seed"] != seed:
                    continue
                frame = r["ends"].get(t)
                if frame is None:
                    missing.append(names[r["variant"]])
                    continue
                f = np.asarray(frame["population"].get_feasible_objective_matrix())
                if f.size:
                    ax.scatter(f[:, 0], f[:, 1], s=15, alpha=0.7, color=colors[r["variant"]], label=names[r["variant"]])
                else:
                    missing.append(names[r["variant"]] + "（无可行解）")
                reference = np.asarray(frame["POF"])
            available = {r["variant"] for r in runs if r["task"]["seed"] == seed}
            missing.extend(names[v] + "（无此 seed）" for v in variants if v not in available)
            if reference is not None:
                ax.scatter(reference[:, 0], reference[:, 1], color="#f3b044", s=4, label="True PF")
            ax.set(xlabel="f1", ylabel="f2", title=f"Environment {t} / seed {seed} (f1-f2 projection)")
        else:
            for i, variant in enumerate(variants):
                values = [r["task"].get("result", {}).get("metrics", {}).get("MIGD") for r in runs if r["variant"] == variant]
                nonfinite += sum(v is not None and not math.isfinite(v) for v in values)
                finite = [v for v in values if v is not None and math.isfinite(v)]
                if finite:
                    offsets = np.linspace(-0.13, 0.13, len(finite)) if len(finite) > 1 else [0]
                    ax.scatter(i + np.asarray(offsets), finite, color=colors[variant], s=30)
                ax.annotate(f"n={len(values)}, inf={sum(v is not None and not math.isfinite(v) for v in values)}",
                            (i, 1), xycoords=("data", "axes fraction"), ha="center", va="bottom", fontsize=8)
            ax.set_xticks(range(len(variants)), [names[v] for v in variants], rotation=15, ha="right", fontsize=9)
            ax.set_ylabel("MIGD")
        if mode != 3 and ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=8)
        self.toolbar.update()
        self.canvas.draw_idle()
        self.note.setText(f"已完成结果 {len(runs)} 个；失败、取消和未完成任务不参与对比。"
                          + ("每条线是一次独立运行，不是重复实验均值。" if mode in (0, 1) else
                             "只绘制所选环境与 seed；三目标仅投影到 f1–f2。" if mode == 2 else "每个点是一次独立运行的 MIGD。")
                          + (f" 无穷大/非有限值 {nonfinite} 个，图中留空，不按零处理。" if nonfinite else "")
                          + (" 缺少快照或可行解：" + "、".join(missing) if missing else "")
                          + (f" 读取失败 {len(getattr(self, 'errors', []))} 个，详情见提示。" if getattr(self, "errors", []) else ""))
        self.note.setToolTip("\n".join(getattr(self, "errors", [])))

    def done(self, result):
        self.cancel.set()
        self.timer.stop()
        super().done(result)

    def closeEvent(self, event):
        self.cancel.set()
        self.timer.stop()
        super().closeEvent(event)
