"""Low-configuration batch workspace; component parameters are data-driven."""
from collections import Counter
from pathlib import Path
import os

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QProgressBar, QScrollArea, QSpinBox, QSplitter,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .batch_runner import BatchRunner
from .component_ui import ParameterDialog
from .component_choices import (component_year as algorithm_year, component_sort_key as algorithm_sort_key,
                                ordered_registry)
from .component_selector import ComponentSelector
from .core import ROOT, records
from .experiments import build_plan, grouped_statistics, task_row
from .widgets import ChoiceBox as QComboBox

TASK_STATUS = {"pending": "待运行", "running": "运行中", "paused": "暂停中", "stopping": "正在终止",
               "completed": "已完成", "canceled": "已取消", "failed": "失败", "exporting": "正在保存统计"}


def format_value(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        if value == float("inf"):
            return "∞"
        return f"{value:.6g}"
    return str(value)


class BatchWidget(QWidget):
    replay_requested = Signal(object)

    def __init__(self, test_window, parent=None):
        super().__init__(parent)
        self.test_window = test_window
        self.registry = ordered_registry(records())
        self.profiles = {}
        self.tasks = []
        self.items = {}
        self.runner = BatchRunner(self)
        self.runner.task_changed.connect(self.task_changed)
        self.runner.state_changed.connect(self.state_changed)
        self.runner.finished.connect(self.batch_finished)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        heading = QLabel("批量实验 · 选择多个组件，预览任务数量，再一键运行")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(245)
        config = QWidget()
        self.config_layout = QVBoxLayout(config)
        self.config_controls = config
        self.choice_tabs = QTabWidget()
        self.lists = {}
        self.filters = {}
        for kind, title in (("dynamic", "动态策略"), ("search", "搜索算法"), ("problem", "问题")):
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            choices = ComponentSelector(kind, multiple=True)
            self.filters[kind] = choices.filter_box
            self.lists[kind] = choices
            choices.itemChanged.connect(self.update_estimate)
            tab_layout.addWidget(choices)
            row = QHBoxLayout()
            for text, checked in (("全选可见", True), ("清空", False)):
                control = QPushButton(text)
                control.clicked.connect(lambda _, k=kind, c=checked: self.check_all(k, c))
                row.addWidget(control)
            advanced = QPushButton("当前组件参数…")
            advanced.clicked.connect(lambda _, k=kind: self.edit_profile(k))
            tab_layout.addLayout(row)
            tab_layout.addWidget(advanced)
            self.choice_tabs.addTab(tab, title)
        self.config_layout.addWidget(self.choice_tabs)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.preset = QComboBox()
        self.preset.addItems(["快速检查", "论文实验（可编辑）"])
        form.addRow("实验预设", self.preset)
        self.history_policy = QComboBox()
        self.history_policy.addItem("完整快照", "full")
        self.history_policy.addItem("环境末帧 · 减少回放占用", "environment")
        self.history_policy.setToolTip("仅减少回放副本和保存文件，不裁剪算法内部预测历史；每个环境保留末帧。")
        form.addRow("回放记录", self.history_policy)
        self.spin = {}
        for key, label, minimum, maximum in (("decision_num", "决策变量数", 2, 1000),
                ("solution_num", "种群规模", 4, 5000), ("total_evaluate_time", "环境总数", 1, 10000),
                ("repeats", "独立重复次数", 1, 500), ("seed", "起始随机种子", 0, 2147483647),
                ("parallel", "并行任务数", 1, min(8, os.cpu_count() or 1))):
            field = QSpinBox()
            field.setRange(minimum, maximum)
            field.valueChanged.connect(self.update_estimate)
            self.spin[key] = field
            form.addRow(label, field)
        self.tau = QLineEdit("3")
        self.n = QLineEdit("10")
        for label, field in (("变化间隔 tau", self.tau), ("变化强度 n", self.n)):
            field.setToolTip("可输入 5,10 或 5:15:5；范围含终点，步长必须为正")
            field.textChanged.connect(self.update_estimate)
            form.addRow(label, field)
        self.config_layout.addLayout(form)
        use_test = QPushButton("沿用当前测试配置")
        use_test.clicked.connect(self.use_test_configuration)
        self.config_layout.addWidget(use_test)
        configs = QHBoxLayout()
        for label, callback in (("保存实验配置", self.save_configuration), ("加载实验配置", self.load_configuration)):
            control = QPushButton(label)
            control.clicked.connect(callback)
            configs.addWidget(control)
        self.config_layout.addLayout(configs)
        self.estimate = QLabel()
        self.estimate.setWordWrap(True)
        self.config_layout.addWidget(self.estimate)
        hint = QLabel("同一次重复对所有算法使用相同 seed；\n失败和取消任务不混入完整实验的均值。\n"
                      "参数从算法代码或旧版配置自动读取。")
        hint.setWordWrap(True)
        self.config_layout.addWidget(hint)
        self.config_layout.addStretch()
        scroll.setWidget(config)
        splitter.addWidget(scroll)
        results = QWidget()
        result_layout = QVBoxLayout(results)
        self.result_tabs = QTabWidget()
        self.task_table = QTreeWidget()
        self.task_table.setHeaderLabels(["任务", "问题", "动态策略", "搜索算法", "tau / n", "重复 / seed", "状态", "进度", "MIGD", "耗时"])
        self.task_table.setRootIsDecorated(False)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for column, width in enumerate((45, 65, 120, 80, 70, 90, 80, 65, 85, 65)):
            self.task_table.setColumnWidth(column, width)
        self.task_table.itemDoubleClicked.connect(self.replay_item)
        self.result_tabs.addTab(self.task_table, "任务与进度")
        self.stats = QTreeWidget()
        self.stats.setRootIsDecorated(False)
        self.stats.setAlternatingRowColors(True)
        self.stats_keys = ["问题", "动态策略", "搜索算法", "tau", "n", "计划次数", "完成次数",
            "MIGD均值", "MIGD标准差", "MGD均值", "MGD标准差", "MHV均值", "MHV标准差", "feasibility均值", "feasibility标准差"]
        self.stats.setHeaderLabels([key.replace("feasibility", "可行率") for key in self.stats_keys])
        self.result_tabs.addTab(self.stats, "汇总统计")
        result_layout.addWidget(self.result_tabs, 1)
        self.status = QLabel("尚未生成任务")
        self.status.setWordWrap(True)
        result_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        result_layout.addWidget(self.progress)
        path_row = QHBoxLayout()
        self.save_results = QCheckBox("保存实验结果")
        self.save_results.setToolTip("默认不写磁盘；不勾选时结果只保留在本次会话，仍可双击回放。")
        result_layout.addWidget(self.save_results)
        self.output = QLineEdit(str(ROOT / "results" / "experiments"))
        self.choose_output_button = QPushButton("保存目录…")
        self.choose_output_button.clicked.connect(self.choose_output)
        path_row.addWidget(self.output, 1)
        path_row.addWidget(self.choose_output_button)
        result_layout.addLayout(path_row)
        controls = QHBoxLayout()
        self.buttons = {}
        secondary_controls = QHBoxLayout()
        for key, text, callback in (("generate", "更新任务", self.generate),
                                   ("start", "开始实验", self.start), ("pause", "暂停", self.toggle_pause),
                                   ("stop", "终止全部", self.runner.cancel), ("replay", "回放选中结果", self.replay_selected),
                                   ("compare", "比较结果", self.compare_results),
                                   ("export", "导出统计", self.export_statistics), ("folder", "打开结果目录", self.open_folder)):
            control = QPushButton(text)
            control.clicked.connect(callback)
            if key == "start":
                control.setObjectName("primary")
            self.buttons[key] = control
            (secondary_controls if key in ("replay", "compare", "export", "folder") else controls).addWidget(control)
        result_layout.addLayout(controls)
        result_layout.addLayout(secondary_controls)
        splitter.addWidget(results)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 950])
        self.preset.currentIndexChanged.connect(self.apply_preset)
        self.save_results.toggled.connect(lambda _: self.state_changed("pending"))
        self.refresh_registry()
        self.apply_preset()
        self.state_changed("pending")

    def refresh_registry(self):
        if self.runner.active:
            return
        self.registry = ordered_registry(records())
        for kind, choices in self.lists.items():
            previous = {choices.item(i).data(Qt.ItemDataRole.UserRole)["folder_name"] for i in range(choices.count())
                        if choices.item(i).checkState() == Qt.CheckState.Checked}
            first = choices.count() == 0
            current = choices.currentData()
            if first:
                current = self.test_window.selected[kind]
                previous = {current["folder_name"]}
            choices.set_records(self.registry[kind], current=current["folder_name"] if current else None,
                                checked=previous)
            if first:
                choices.scrollToTop()
        self.update_estimate()

    def check_all(self, kind, checked):
        choices = self.lists[kind]
        choices.blockSignals(True)
        for i in range(choices.count()):
            item = choices.item(i)
            if not checked or not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        choices.blockSignals(False)
        self.update_estimate()

    def selection(self):
        return {kind: [items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(items.count())
                       if items.item(i).checkState() == Qt.CheckState.Checked] for kind, items in self.lists.items()}

    def shared(self):
        return {**{key: widget.value() for key, widget in self.spin.items()}, "tau": self.tau.text(), "n": self.n.text(),
                "history_policy": self.history_policy.currentData()}

    def apply_preset(self):
        research = self.preset.currentIndex() == 1
        for key, value in {"decision_num": 10 if research else 6, "solution_num": 100 if research else 20,
                           "total_evaluate_time": 30 if research else 3, "repeats": 20 if research else 1,
                           "seed": 1, "parallel": 1}.items():
            self.spin[key].setValue(value)
        self.tau.setText("10,20" if research else "3")
        self.n.setText("5,10" if research else "10")
        self.update_estimate()

    def update_estimate(self, *args):
        if not hasattr(self, "estimate"):
            return
        try:
            from .experiments import parse_sweep
            from math import prod
            count = prod(len(items) for items in self.selection().values()) * len(parse_sweep(self.tau.text())) * len(parse_sweep(self.n.text())) * self.spin["repeats"].value()
            self.estimate.setText(f"预计 {count:,} 个任务；{self.spin['parallel'].value()} 个并行。\n更改配置后点击“生成 / 更新任务”。")
        except ValueError as error:
            self.estimate.setText(str(error))

    def edit_profile(self, kind):
        item = self.lists[kind].currentItem()
        if item is None:
            return
        record = item.data(Qt.ItemDataRole.UserRole)
        key = (kind, record["folder_name"])
        locked = ("decision_num", "solution_num", "total_evaluate_time", "n", "tau") if kind == "problem" else ("seed",) if kind == "search" else ()
        dialog = ParameterDialog(record, self.profiles.get(key), self, locked=locked)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.profiles[key] = dialog.values

    def use_test_configuration(self):
        try:
            request = self.test_window.request()
            for kind, choices in self.lists.items():
                record = request["records"][kind]
                self.profiles[(kind, record["folder_name"])] = request["params"][kind]
                for i in range(choices.count()):
                    choices.item(i).setCheckState(Qt.CheckState.Checked if choices.item(i).data(Qt.ItemDataRole.UserRole)["folder_name"] == record["folder_name"] else Qt.CheckState.Unchecked)
            for key in ("decision_num", "solution_num", "total_evaluate_time"):
                if key in request["params"]["problem"]:
                    self.spin[key].setValue(request["params"]["problem"][key])
            self.tau.setText(str(request["params"]["problem"]["tau"]))
            self.n.setText(str(request["params"]["problem"]["n"]))
            self.spin["seed"].setValue(request["params"]["search"].get("seed", 1))
            self.history_policy.setCurrentIndex(self.history_policy.findData(request.get("history_policy", "full")))
            self.update_estimate()
        except Exception as error:
            QMessageBox.warning(self, "测试配置无效", str(error))

    def generate(self):
        if self.runner.active:
            return False
        try:
            tasks = build_plan(self.selection(), self.shared(), self.profiles)
            if len(tasks) > 200 and QMessageBox.question(self, "较大的实验计划", f"生成 {len(tasks):,} 个任务，可能耗时较长。继续？") != QMessageBox.StandardButton.Yes:
                return False
            self.tasks = tasks
            self.task_table.clear()
            self.items = {}
            for task in tasks:
                self.items[task["id"]] = QTreeWidgetItem(self.task_table)
                self.task_changed(task)
            self.stats.clear()
            self.status.setText(f"已生成 {len(tasks)} 个任务，尚未开始。")
            self.state_changed("pending")
            return True
        except Exception as error:
            QMessageBox.warning(self, "无法生成任务", str(error))
            return False

    def start(self):
        if self.runner.active:
            return
        # Always regenerate from visible config so edits after preview cannot
        # silently launch the stale plan.
        if not self.generate():
            return
        try:
            self.runner.start(self.tasks, self.spin["parallel"].value(), self.output.text(),
                              save_results=self.save_results.isChecked())
            self.tasks = self.runner.tasks
        except Exception as error:
            QMessageBox.warning(self, "无法开始实验", str(error))

    def task_changed(self, task):
        item = self.items.get(task["id"])
        if item is None:
            return
        row = task_row(task)
        values = [row["任务"], row["问题"], row["动态策略"], row["搜索算法"],
                  f"{task['tau']} / {task['n']}", f"{task['repeat']} / {task['seed']}",
                  TASK_STATUS[task["status"]], f"{task['progress']:.0f}%", row["MIGD"], row["秒"]]
        for column, value in enumerate(values):
            item.setText(column, format_value(value))
        item.setData(0, Qt.ItemDataRole.UserRole, task["id"])
        item.setToolTip(6, task.get("error", "双击有快照的任务可回放；未保存结果仅存在当前会话。"))
        tasks = self.runner.tasks if self.runner.active else self.tasks
        if tasks:
            total = sum(100 if t["status"] in ("completed", "failed", "canceled") else t["progress"] for t in tasks)
            self.progress.setValue(int(total / len(tasks) * 10))

    def state_changed(self, state):
        active = self.runner.active
        self.config_controls.setEnabled(not active)
        self.save_results.setEnabled(not active)
        self.output.setEnabled(not active and self.save_results.isChecked())
        self.choose_output_button.setEnabled(not active and self.save_results.isChecked())
        self.buttons["generate"].setEnabled(not active)
        self.buttons["start"].setEnabled(not active)
        self.buttons["pause"].setEnabled(active and not self.runner.exporting and not self.runner.canceling)
        self.buttons["pause"].setText("继续实验" if self.runner.paused else "暂停")
        self.buttons["stop"].setEnabled(active and not self.runner.exporting and not self.runner.canceling)
        self.buttons["folder"].setEnabled(self.runner.directory is not None)
        self.buttons["export"].setEnabled(bool(self.tasks) and not active and any(t.get("result") for t in self.tasks))
        self.buttons["compare"].setEnabled(not active and any(t["status"] == "completed" for t in self.tasks))
        if active:
            self.status.setText(TASK_STATUS.get(state, state) +
                                (f" · {self.runner.directory.name}" if self.runner.directory else " · 不保存运行数据"))
            self.status.setToolTip(str(self.runner.directory) if self.runner.directory else "结果仅保留在内存")

    def toggle_pause(self):
        if self.runner.paused:
            self.runner.resume()
        else:
            self.runner.pause()

    def batch_finished(self, state):
        self.tasks = self.runner.tasks
        self.stats.clear()
        for row in grouped_statistics(self.tasks):
            QTreeWidgetItem(self.stats, [format_value(row.get(key)) for key in self.stats_keys])
        counts = Counter(t["status"] for t in self.tasks)
        self.status.setText(f"完成 {counts['completed']} / 失败 {counts['failed']} / 取消 {counts['canceled']}；"
                            + (f"统计保存失败：{self.runner.report_error}" if self.runner.report_error else
                               "CSV、Excel 和运行清单已保存；双击任务可回放。" if self.runner.report_path else
                               "未写入磁盘；双击可回放，关闭或新批次后不保留。"))
        self.status.setToolTip(str(self.runner.directory) if self.runner.directory else "结果仅保留在当前会话")
        self.progress.setValue(1000)
        self.state_changed(state)

    def replay_item(self, item, column=0):
        task = next((t for t in self.tasks if t["id"] == item.data(0, Qt.ItemDataRole.UserRole)), None)
        path = task.get("result", {}).get("path") if task else None
        frames = task.get("result", {}).get("frames") if task else None
        if frames:
            self.replay_requested.emit(frames)
        elif path and Path(path).is_file():
            self.replay_requested.emit(path)
        else:
            QMessageBox.information(self, "尚无结果", "该任务还没有可回放的快照。")

    def export_statistics(self):
        path = QFileDialog.getExistingDirectory(self, "导出统计到目录", self.output.text())
        if path and not self.runner.active:
            try:
                self.runner.export_statistics(path)
            except Exception as error:
                QMessageBox.warning(self, "无法导出统计", str(error))

    def compare_results(self):
        if self.runner.active:
            return
        from .comparison_ui import ComparisonDialog
        dialog = ComparisonDialog(list(self.tasks), self)
        dialog.exec()

    def replay_selected(self):
        items = self.task_table.selectedItems()
        if items:
            self.replay_item(items[0])

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "批量实验保存目录", self.output.text())
        if path and not self.runner.active:
            self.output.setText(path)

    def save_configuration(self):
        import json
        try:
            build_plan(self.selection(), self.shared(), self.profiles)
            profiles = []
            for (kind, folder), params in self.profiles.items():
                record = next((r for r in self.registry[kind] if r["folder_name"] == folder), None)
                if record:
                    profiles.append({"kind": kind, "name": record["name"], "params": params})
            data = {"version": 1, "selection": {k: [r["name"] for r in rows] for k, rows in self.selection().items()},
                    "shared": self.shared(), "profiles": profiles}
            folder = ROOT / "results"
            folder.mkdir(parents=True, exist_ok=True)
            path, _ = QFileDialog.getSaveFileName(self, "保存实验配置", str(folder / "experiment_config.json"), "JSON (*.json)")
            if path:
                Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self.status.setText("实验配置已保存：" + path)
        except Exception as error:
            QMessageBox.warning(self, "无法保存配置", str(error))

    def apply_configuration(self, data):
        if self.runner.active:
            raise ValueError("运行期间不能加载实验配置")
        if data.get("version") != 1:
            raise ValueError("不支持的实验配置版本")
        selected = {}
        for kind in self.lists:
            selected[kind] = []
            for name in data["selection"][kind]:
                record = next((r for r in self.registry[kind] if r["name"] == name), None)
                if record is None:
                    raise ValueError(f"未安装组件：{name}；请先通过组件管理添加")
                selected[kind].append(record)
        shared = data["shared"]
        for key, widget in self.spin.items():
            value = shared[key]
            if type(value) is not int or not widget.minimum() <= value <= widget.maximum():
                raise ValueError(f"{key} 超出支持范围")
        profiles = {}
        for profile in data.get("profiles", []):
            kind = profile["kind"]
            record = next((r for r in self.registry[kind] if r["name"] == profile["name"]), None)
            if record is None:
                raise ValueError(f"未安装组件：{profile['name']}")
            profiles[(kind, record["folder_name"])] = profile["params"]
        # Validate everything before changing any visible state.
        build_plan(selected, shared, profiles)
        self.profiles = profiles
        for kind, choices in self.lists.items():
            names = {r["name"] for r in selected[kind]}
            choices.blockSignals(True)
            for i in range(choices.count()):
                item = choices.item(i)
                item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole)["name"] in names else Qt.CheckState.Unchecked)
            choices.blockSignals(False)
        for key, widget in self.spin.items():
            widget.setValue(shared[key])
        self.tau.setText(shared["tau"])
        self.n.setText(shared["n"])
        self.history_policy.setCurrentIndex(self.history_policy.findData(shared.get("history_policy", "full")))
        self.update_estimate()

    def load_configuration(self):
        import json
        path, _ = QFileDialog.getOpenFileName(self, "加载实验配置", str(ROOT / "results"), "JSON (*.json)")
        if path:
            try:
                self.apply_configuration(json.loads(Path(path).read_text(encoding="utf-8")))
                self.status.setText("配置已加载；点击更新任务预览或开始实验。")
            except Exception as error:
                QMessageBox.warning(self, "无法加载配置", str(error))

    def open_folder(self):
        if self.runner.directory:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.runner.directory)))
