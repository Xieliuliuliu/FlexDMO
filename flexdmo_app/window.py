"""A standalone, dockable research workspace for the Qt migration trial."""
from datetime import datetime
from pathlib import Path
import queue
import threading
import time
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDockWidget, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSlider, QStackedWidget, QTabWidget, QToolBar,
    QVBoxLayout, QWidget,
)

from .charts import ChartWidget
from .dashboard import ChartDashboard
from .controller import RunController
from .history import HistoryPanel
from .parameter_ui import parameter_field
from .widgets import ChoiceBox as QComboBox
from .core import ROOT, defaults, load_frames, parameter_label, parse_parameters, records, save_frames

STATUS = {"idle": "待运行", "running": "运行中", "paused": "暂停中",
          "stopping": "正在终止", "stopped": "已终止 · 可回放", "completed": "已完成 · 可回放",
          "failed": "运行失败 · 已保留快照", "replay": "历史回放"}


def button(text, callback, object_name=""):
    widget = QPushButton(text)
    widget.setObjectName(object_name)
    widget.clicked.connect(callback)
    return widget


class FlexDMOWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlexDMO")
        self.resize(1360, 860)
        self.setMinimumSize(700, 520)
        self.registry = records()
        self.frames = []
        self.index = -1
        self.dirty = False
        self.pending_draw = False
        self.total_evaluations = 0
        self.started_at = None
        self.io_inbox = queue.Queue()
        self.io_busy = False
        self.io_success = None
        self.last_result_path = None
        self.environment_counts = {}
        self.environment_frame_indices = {}
        self.parameter_cache = {}
        self.result_label_prefix = "结果："
        self.history_auto_hidden = False
        self.controller = RunController(self)
        self.controller.frame_received.connect(self.receive_frame)
        self.controller.status_changed.connect(self.update_controls)
        self.controller.error_received.connect(self.log)
        self.controller.finished.connect(self.run_finished)
        self._theme()
        self._build_toolbar()
        self._build_settings()
        self._build_center()
        self._build_history()
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        view_menu = self.menuBar().addMenu("视图")
        view_menu.addAction(self.settings_dock.toggleViewAction())
        view_menu.addAction(self.history_dock.toggleViewAction())
        self.diagnostics_action = view_menu.addAction("显示诊断信息")
        self.diagnostics_action.setCheckable(True)
        self.diagnostics_action.toggled.connect(self.show_diagnostics)
        saved_results = view_menu.addAction("打开自动保存目录")
        saved_results.triggered.connect(self.open_archive_folder)
        reset_layout = view_menu.addAction("恢复工作区布局")
        reset_layout.triggered.connect(self.restore_layout)
        self.render_timer = QTimer(self)
        self.render_timer.setInterval(100)
        self.render_timer.timeout.connect(self.render_latest)
        self.render_timer.start()
        self.replay_timer = QTimer(self)
        self.replay_timer.timeout.connect(self.advance_replay)
        self.io_timer = QTimer(self)
        self.io_timer.setInterval(50)
        self.io_timer.timeout.connect(self._finish_io)
        self.io_timer.start()
        self.rebuild_parameters()
        self.fast_preset()
        self.update_controls("idle")
        from .batch_ui import BatchWidget
        self.batch = BatchWidget(self)
        self.batch.replay_requested.connect(self.open_batch_result)
        self.workspace_stack.addWidget(self.batch)
        self._test_dock_visibility = (True, True)
        self.resizeDocks([self.settings_dock, self.history_dock], [290, 220], Qt.Orientation.Horizontal)

    def _theme(self):
        palette = QPalette()
        for role, color in ((QPalette.ColorRole.Window, "#f2f5f9"),
                            (QPalette.ColorRole.WindowText, "#24334b"),
                            (QPalette.ColorRole.Base, "#ffffff"),
                            (QPalette.ColorRole.AlternateBase, "#f6f8fb"),
                            (QPalette.ColorRole.Text, "#24334b"),
                            (QPalette.ColorRole.Button, "#ffffff"),
                            (QPalette.ColorRole.ButtonText, "#24334b"),
                            (QPalette.ColorRole.Highlight, "#129bad"),
                            (QPalette.ColorRole.HighlightedText, "#ffffff")):
            palette.setColor(role, QColor(color))
        # Set the application palette too: native macOS dark appearance can
        # otherwise supply white text to newly created child controls/popups.
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#728097"))
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                     QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#9ba8bb"))
        QApplication.instance().setPalette(palette)
        self.setPalette(palette)
        self.setStyleSheet("""
            QMainWindow { background: #f2f5f9; }
            QToolBar { background: white; border-bottom: 1px solid #dce3ed; padding: 8px; spacing: 8px; }
            QDockWidget::title { background: #e8edf4; padding: 9px; font-weight: 600; }
            QGroupBox { border: 1px solid #dce3ed; border-radius: 7px; margin-top: 14px; padding: 12px 8px 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #304767; }
            QPushButton { color: #24334b; padding: 7px 12px; border: 1px solid #d4deea; border-radius: 5px; background: white; }
            QPushButton:hover { background: #edf6f8; border-color: #129bad; }
            QPushButton:disabled { color: #9ba8bb; background: #eff2f6; }
            QPushButton#primary { background: #129bad; color: white; border-color: #129bad; }
            QPushButton#danger { color: #bd4857; }
            QLineEdit, QComboBox { color: #24334b; padding: 5px; border: 1px solid #cfd9e6; border-radius: 4px; background: white; }
            QComboBox QAbstractItemView {
                color: #24334b; background: white; border: 1px solid #cfd9e6;
                selection-background-color: #129bad; selection-color: white;
                outline: 0;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #129bad; color: white;
            }
            QLineEdit:focus { border-color: #129bad; }
            QProgressBar { border: 0; background: #e7edf4; border-radius: 3px; max-height: 8px; }
            QProgressBar::chunk { background: #129bad; border-radius: 3px; }
            QTreeWidget { border: 1px solid #dce3ed; background: white; }
            QLabel#muted { color: #728097; }
            QLabel#brand { color: #11998e; font-size: 20px; font-weight: 700; }
        """)

    def _build_toolbar(self):
        toolbar = QToolBar("工作区", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        brand = QLabel("FlexDMO")
        brand.setObjectName("brand")
        toolbar.addWidget(brand)
        toolbar.addSeparator()
        self.module_actions = []
        self.module_group = QActionGroup(self)
        for index, title in enumerate(("测试运行", "批量实验")):
            action = QAction(title, self)
            action.setCheckable(True)
            action.setChecked(index == 0)
            action.triggered.connect(lambda checked, i=index: self.switch_workspace(i))
            self.module_group.addAction(action)
            self.module_actions.append(action)
            toolbar.addAction(action)
        toolbar.addSeparator()
        self.open_action = QAction("打开结果", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_result)
        toolbar.addAction(self.open_action)
        self.save_action = QAction("保存结果", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_result)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        self.settings_action = toolbar.addAction("实验设置")
        self.settings_action.triggered.connect(lambda: self.settings_dock.setVisible(not self.settings_dock.isVisible()))
        self.history_action = toolbar.addAction("运行历史")
        self.history_action.triggered.connect(lambda: self.history_dock.setVisible(not self.history_dock.isVisible()))
        components_action = toolbar.addAction("组件管理")
        components_action.triggered.connect(self.manage_components)

    def switch_workspace(self, index):
        if not hasattr(self, "batch"):
            return
        if index == self.workspace_stack.currentIndex():
            return
        if index == 1:
            self._test_dock_visibility = (self.settings_dock.isVisible(), self.history_dock.isVisible())
            self.settings_dock.hide()
            self.history_dock.hide()
        else:
            self.settings_dock.setVisible(self._test_dock_visibility[0])
            self.history_dock.setVisible(self._test_dock_visibility[1] and self.width() >= 1150)
        self.workspace_stack.setCurrentIndex(index)
        self.module_actions[index].setChecked(True)
        self.settings_action.setEnabled(index == 0)
        self.history_action.setEnabled(index == 0)
        self.statusBar().showMessage("批量实验：勾选组件 → 选择预设或参数扫描 → 开始实验" if index == 1 else "测试运行：设置参数、查看多图或打开历史结果")

    def open_batch_result(self, path):
        if self.controller.active or self.io_busy:
            QMessageBox.information(self, "测试任务仍在运行", "请先结束当前测试任务再回放批量结果；批量实验可继续运行。")
        elif self.allow_discard():
            self.switch_workspace(0)
            if isinstance(path, list):
                self.install_frames(path)
                self.dirty = True
                self.statusBar().showMessage("本次实验的内存回放；关闭后不保留，可手动保存结果。", 10000)
            else:
                self._start_io("load", path)

    def manage_components(self):
        if self.controller.active or self.batch.runner.active:
            QMessageBox.information(self, "任务仍在运行", "请在任务结束后新增或刷新组件。")
            return
        from .component_ui import ComponentDialog
        ComponentDialog(self.refresh_registry, self).exec()

    def refresh_registry(self):
        if self.controller.active or self.batch.runner.active:
            raise ValueError("任务运行期间不能刷新组件")
        self._remember_parameters()
        errors = []
        registry = records(errors)
        for kind, selector in self.selectors.items():
            previous = self.selected[kind]["folder_name"]
            selector.blockSignals(True)
            selector.clear()
            for record in registry[kind]:
                suffix = (f" · {record['year']}" if record.get("year") else "") if kind != "problem" else f" · {'有约束' if record['constraints'] else '无约束'}"
                selector.addItem(record["name"] + suffix, record)
            selected = next((i for i, record in enumerate(registry[kind]) if record["folder_name"] == previous), 0)
            selector.setCurrentIndex(selected)
            selector.blockSignals(False)
        self.registry = registry
        self._build_parameter_form()
        self.batch.refresh_registry()
        self.statusBar().showMessage("组件已刷新，参数输入已保留。" if not errors else
                                     f"组件已刷新；{len(errors)} 个代码问题可在组件管理查看。", 6000)
        for error in errors:
            self.log(error)

    def _build_settings(self):
        self.settings_dock = QDockWidget("实验设置", self)
        self.settings_dock.setObjectName("flexdmo-settings")
        self.settings_dock.setMinimumWidth(240)
        self.settings_tabs = QTabWidget()
        choices = QWidget()
        layout = QVBoxLayout(choices)
        layout.setSpacing(14)
        self.selectors = {}
        self.selected = {}
        for kind, title, preferred in (("dynamic", "动态响应策略", "D-NSGA-II-B"),
                                       ("search", "搜索算法", "NSGAII"),
                                       ("problem", "测试问题", "CDP1")):
            group = QGroupBox(title)
            content = QVBoxLayout(group)
            selector = QComboBox()
            selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            selector.setMinimumContentsLength(12)
            for record in self.registry[kind]:
                suffix = ((f" · {record['year']}" if record.get("year") else "") if kind != "problem" else
                          f" · {'有约束' if record['constraints'] else '无约束'}")
                selector.addItem(record["name"] + suffix, record)
            chosen = next((i for i, r in enumerate(self.registry[kind]) if r["name"] == preferred), 0)
            selector.setCurrentIndex(chosen)
            self.selectors[kind] = selector
            content.addWidget(selector)
            layout.addWidget(group)
        hint = QLabel("参数在下次运行时生效。")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)
        replay_options = QGroupBox("回放记录")
        options = QVBoxLayout(replay_options)
        self.history_policy = QComboBox()
        self.history_policy.addItem("完整快照 · 可逐帧回放", "full")
        self.history_policy.addItem("环境末帧 · 减少回放占用", "environment")
        self.history_policy.setToolTip("环境末帧只保留各环境最新快照，仍实时绘图。\n不裁剪预测策略读取的算法内部历史，不写临时文件。")
        options.addWidget(self.history_policy)
        layout.addWidget(replay_options)
        layout.addStretch()
        self.settings_tabs.addTab(choices, "算法与问题")
        self.parameter_scroll = QScrollArea()
        self.parameter_scroll.setWidgetResizable(True)
        self.parameter_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.settings_tabs.addTab(self.parameter_scroll, "参数")
        self.settings_dock.setWidget(self.settings_tabs)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.settings_dock)
        for selector in self.selectors.values():
            selector.currentIndexChanged.connect(self.rebuild_parameters)

    def rebuild_parameters(self):
        self._remember_parameters()
        self._build_parameter_form()

    def _remember_parameters(self):
        # Cache drafts by component, including invalid text so merely switching
        # tabs/algorithms never silently replaces the user's input.
        for kind, fields in getattr(self, "parameter_fields", {}).items():
            record = self.selected[kind]
            self.parameter_cache[(kind, record["folder_name"])] = {
                key: field.text() for key, field in fields.items()
            }

    def reset_parameters(self):
        self._remember_parameters()
        for kind, selector in self.selectors.items():
            self.parameter_cache.pop((kind, selector.currentData()["folder_name"]), None)
        self._build_parameter_form()
        self.statusBar().showMessage("当前组合已恢复原算法默认参数。", 6000)

    def _build_parameter_form(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        self.parameter_fields = {}
        self.templates = {}
        for kind in ("dynamic", "search", "problem"):
            record = self.selectors[kind].currentData()
            self.selected[kind] = record
            template = defaults(record)
            self.templates[kind] = template
            draft = self.parameter_cache.get((kind, record["folder_name"]), {})
            fields = self.parameter_fields[kind] = {}
            group = QGroupBox(record["name"])
            form = QFormLayout(group)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            for key, value in template.items():
                field = parameter_field(record, key, draft.get(key, value))
                field.setObjectName(f"parameter-{kind}-{key}")
                fields[key] = field
                form.addRow(parameter_label(record, key) + "：", field)
            if not template:
                form.addRow(QLabel("此策略无需额外参数"))
            layout.addWidget(group)
        layout.addWidget(button("快速试跑预设", self.fast_preset))
        layout.addWidget(button("恢复原算法默认参数", self.reset_parameters))
        layout.addStretch()
        self.parameter_scroll.setWidget(container)
        if hasattr(self, "selection_label"):
            self.update_selection_label()

    def selected_summary(self):
        return "  /  ".join(self.selected[k]["name"] for k in ("dynamic", "search", "problem"))

    def update_selection_label(self):
        if not self.frames:
            self.selection_label.setText("待运行：" + self.selected_summary())
            return
        settings = self.frames[0]["settings"]
        def display_name(kind, class_name):
            stored = settings.get({"dynamic": "response_strategy_name", "search": "search_algorithm_name", "problem": "problem_name"}[kind])
            if stored:
                return stored
            return next((r["name"] for r in self.registry[kind] if
                         r.get("class_name", Path(r["folder_name"]).name) == class_name), class_name)
        self.selection_label.setText(self.result_label_prefix + "  /  ".join(
            display_name(kind, settings.get(key, "")) for kind, key in
            (("dynamic", "response_strategy_class"), ("search", "search_algorithm_class"),
             ("problem", "problem_class"))))

    def fast_preset(self):
        fields = self.parameter_fields["problem"]
        for key, value in {"decision_num": 6, "solution_num": 20, "tau": 3, "total_evaluate_time": 5}.items():
            if key in fields:
                fields[key].setText(str(value))
        self.statusBar().showMessage("已应用快速试跑预设：20 个体 / 5 环境 / 间隔 3 代；可在参数页调整。", 12000)

    def _build_center(self):
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(12, 12, 12, 8)
        header = QHBoxLayout()
        self.selection_label = QLabel()
        self.selection_label.setWordWrap(True)
        header.addWidget(self.selection_label, 1)
        self.mode_combo = QComboBox()
        for title, mode in (("多图：PF / PS / IGD", "ALL"), ("多图：含约束违反量", "ALL4"),
                            ("目标空间 PF", "PF"), ("决策空间 PS", "PS"),
                            ("IGD 曲线", "IGD"), ("约束违反量", "CV")):
            self.mode_combo.addItem(title, mode)
        self.mode_combo.currentIndexChanged.connect(self.request_draw)
        header.addWidget(self.mode_combo)
        self.auto_save = QCheckBox("自动保存结果")
        self.auto_save.setToolTip("默认不保存；勾选后每次运行结束保存所选记录方式下的快照。")
        header.addWidget(self.auto_save)
        layout.addLayout(header)
        self.chart = ChartWidget()
        self.chart_dashboard = ChartDashboard(self.chart)
        layout.addWidget(self.chart_dashboard, 1)
        self.frame_label = QLabel("暂无快照")
        self.frame_label.setObjectName("muted")
        layout.addWidget(self.frame_label)
        controls = QHBoxLayout()
        self.start_button = button("开始运行", self.start_run, "primary")
        self.pause_button = button("暂停", self.controller.pause)
        self.stop_button = button("终止", self.controller.stop, "danger")
        for control in (self.start_button, self.pause_button, self.stop_button):
            controls.addWidget(control)
        self.status_label = QLabel("待运行")
        controls.addWidget(self.status_label, 1)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        replay_group = QGroupBox("回放时间轴")
        replay_layout = QVBoxLayout(replay_group)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self.select_frame)
        replay_layout.addWidget(self.slider)
        row = QHBoxLayout()
        self.replay_controls = []
        for title, callback in (("首帧", lambda: self.slider.setValue(0)),
                                ("上一帧", lambda: self.slider.setValue(self.index - 1)),
                                ("下一帧", lambda: self.slider.setValue(self.index + 1)),
                                ("末帧", lambda: self.slider.setValue(len(self.frames) - 1))):
            control = button(title, callback)
            self.replay_controls.append(control)
        self.play_button = button("播放", self.toggle_replay)
        for control in self.replay_controls[:2] + [self.play_button] + self.replay_controls[2:]:
            row.addWidget(control)
        self.speed_combo = QComboBox()
        for title, interval in (("1 帧/秒", 1000), ("4 帧/秒", 250), ("10 帧/秒", 100)):
            self.speed_combo.addItem(title, interval)
        self.speed_combo.setCurrentIndex(1)
        self.speed_combo.currentIndexChanged.connect(self.change_replay_speed)
        row.addWidget(self.speed_combo)
        replay_layout.addLayout(row)
        layout.addWidget(replay_group)
        self.test_center = center
        self.workspace_stack = QStackedWidget()
        self.workspace_stack.addWidget(center)
        self.setCentralWidget(self.workspace_stack)

    def _build_history(self):
        self.history_dock = QDockWidget("运行历史", self)
        self.history_dock.setObjectName("flexdmo-history")
        self.history_dock.setMinimumWidth(180)
        tabs = QTabWidget()
        self.history_tabs = tabs
        history = QWidget()
        layout = QVBoxLayout(history)
        self.history_panel = HistoryPanel()
        self.history_panel.frame_requested.connect(self.select_history_frame)
        layout.addWidget(self.history_panel, 1)
        hint = QLabel("点击环境查看末帧。\n时间轴按实际保留的快照回放。")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)
        tabs.addTab(history, "快照")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        tabs.addTab(self.log_view, "诊断信息")
        tabs.setTabVisible(1, False)
        self.history_dock.setWidget(tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)

    def log(self, message):
        self.log_view.appendPlainText(f"[{datetime.now():%H:%M:%S}] {message}")

    def show_diagnostics(self, visible):
        self.history_tabs.setTabVisible(1, visible)
        self.history_tabs.setCurrentIndex(1 if visible else 0)
        if visible and self.workspace_stack.currentIndex() == 0:
            self.history_dock.show()

    def archive_folder(self):
        return ROOT / "results" / "autosaved"

    def open_archive_folder(self):
        folder = self.archive_folder()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def request(self):
        params = {}
        for kind in self.templates:
            params[kind] = parse_parameters({key: field.text() for key, field in self.parameter_fields[kind].items()}, self.templates[kind], self.selected[kind])
        return {"records": dict(self.selected), "params": params, "history_policy": self.history_policy.currentData()}

    def allow_discard(self):
        if not self.dirty or not self.auto_save.isChecked():
            return True
        return QMessageBox.warning(self, "尚未保存结果", "当前快照尚未保存。是否放弃这些快照？",
                                   QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                   QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Discard

    def clear_history(self):
        self.stop_replay()
        self.frames = []
        self.result_label_prefix = "结果："
        self.index = -1
        self.dirty = False
        self.last_result_path = None
        self.environment_counts.clear()
        self.environment_frame_indices.clear()
        self.history_panel.clear()
        self.chart_dashboard.reset_cache()
        self.slider.setRange(0, 0)
        self.progress.setValue(0)
        self.frame_label.setText("暂无快照")
        self.frame_label.setToolTip("")
        self.update_selection_label()
        self.pending_draw = True

    def start_run(self):
        if self.controller.active:
            self.controller.resume()
            return
        if self.io_busy:
            return
        try:
            request = self.request()
            # Validate the lightweight problem before launching. Strategy and
            # search validation happens in the child (RNN can import PyTorch).
            from .core import registered_class
            problem = registered_class(request["records"]["problem"])(**request["params"]["problem"])
            budget = problem.initial_convergence + problem.change_each_evaluations * problem.total_change_time
            if self.auto_save.isChecked() and self.dirty and self.frames:
                # Preserve the previous run before replacing it, without an
                # unnecessary discard dialog or blocking the Qt event loop.
                path = self.archive_folder() / f"FlexDMO_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.json"
                self._start_io("save", path, lambda: self._launch_run(request, budget))
                return
            self._launch_run(request, budget)
        except Exception as error:
            self.log(str(error))
            QMessageBox.warning(self, "无法启动", str(error))

    def _launch_run(self, request, budget):
        self.clear_history()
        self.total_evaluations = budget
        self.controller.start(request)
        self.started_at = time.monotonic()
        self.log("开始任务：" + self.selection_label.text())
        self.statusBar().showMessage("运行中；结果仅保留在本次会话，默认不写磁盘。" if not self.auto_save.isChecked() else
                                     "运行中；结束后自动保存结果。", 6000)

    def receive_frame(self, frame):
        environment = int(frame["t"])
        light = frame.get("settings", {}).get("history_policy") == "environment"
        index = self.environment_frame_indices.get(environment) if light else None
        if index is None:
            index = len(self.frames)
            self.frames.append(frame)
        else:
            self.frames[index] = frame
        if len(self.frames) == 1:
            self.update_selection_label()
        self.dirty = True
        self.index = index
        self._history_item(frame, self.index)
        self.slider.blockSignals(True)
        self.slider.setMaximum(len(self.frames) - 1)
        self.slider.setValue(self.index)
        self.slider.blockSignals(False)
        if self.total_evaluations:
            self.progress.setValue(min(999, int(frame["evaluate_times"] / self.total_evaluations * 1000)))
        self.pending_draw = True

    def _history_item(self, frame, index):
        t = int(frame["t"])
        self.environment_frame_indices[t] = index
        self.environment_counts[t] = (1 if frame.get("settings", {}).get("history_policy") == "environment"
                                      else self.environment_counts.get(t, 0) + 1)
        self.history_panel.update_environment(t, frame["evaluate_times"], self.environment_counts[t], index)

    def select_history_frame(self, index, generation):
        if (generation != self.history_panel.generation or self.controller.active or self.io_busy
                or not 0 <= index < len(self.frames)):
            return
        self.stop_replay()
        self.slider.setValue(index)
        self.select_frame(index)  # Also refresh when the slider value did not change.

    def select_frame(self, index):
        if self.frames and 0 <= index < len(self.frames):
            self.index = index
            self.history_panel.set_current_environment(int(self.frames[index]["t"]))
            self.pending_draw = True

    def request_draw(self):
        self.pending_draw = True

    def render_latest(self):
        if not self.pending_draw:
            return
        if self.workspace_stack.currentIndex() == 1:
            return  # Keep the newest frame pending while the charts are hidden.
        self.pending_draw = False
        try:
            self.chart_dashboard.draw(self.frames, self.index, self.mode_combo.currentData())
            if self.index >= 0:
                frame = self.frames[self.index]
                self.history_panel.set_current_environment(int(frame["t"]))
                ratio = sum(ind.feasible for ind in frame["population"]) / len(frame["population"])
                self.frame_label.setText(f"环境 {frame['t']}  ·  评估 {frame['evaluate_times']:,}  ·  可行率 {ratio:.0%}")
                policy = "仅保留环境末帧；不裁剪算法内部历史。" if frame.get("settings", {}).get("history_policy") == "environment" else "完整回放记录。"
                self.frame_label.setToolTip(f"快照 {self.index + 1}/{len(self.frames)}；{policy}")
        except Exception as error:
            self.log(f"图表错误：{error}")
            self.statusBar().showMessage(f"图表无法显示：{error}")

    def update_controls(self, status=None):
        status = status or getattr(self, "view_status", self.controller.status)
        self.view_status = status
        active = self.controller.active
        self.status_label.setText(STATUS.get(status, status))
        self.start_button.setText("继续运行" if status == "paused" else
                                  "重新运行" if self.frames and not active else "开始运行")
        self.start_button.setEnabled(not self.io_busy and (not active or status == "paused"))
        self.pause_button.setEnabled(active and status == "running")
        self.stop_button.setEnabled(active and status != "stopping")
        self.auto_save.setEnabled(not active and not self.io_busy)
        self.settings_tabs.setEnabled(not active and not self.io_busy)
        self.open_action.setEnabled(not active and not self.io_busy)
        self.save_action.setEnabled(bool(self.frames) and not active and not self.io_busy)
        replay_allowed = bool(self.frames) and not active and not self.io_busy
        self.slider.setEnabled(replay_allowed)
        self.play_button.setEnabled(replay_allowed)
        self.speed_combo.setEnabled(replay_allowed)
        self.history_panel.setEnabled(replay_allowed)
        for control in self.replay_controls:
            control.setEnabled(replay_allowed)

    def run_finished(self, status):
        if status == "completed":
            self.progress.setValue(1000)
        elapsed = time.monotonic() - self.started_at if self.started_at else 0
        self.log(f"{STATUS[status]} · {len(self.frames)} 个快照 · {elapsed:.1f} 秒")
        self.statusBar().showMessage("运行失败，可在“视图 → 显示诊断信息”查看原因。" if status == "failed" else
                                     "本次运行已结束，可回放；默认不保存，需要保留请点击保存结果。", 10000)
        self.pending_draw = True
        self.update_controls(status)
        if self.auto_save.isChecked() and self.frames and self.dirty:
            path = self.archive_folder() / f"FlexDMO_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.json"
            self._start_io("save", path)

    def toggle_replay(self):
        if not self.frames or self.controller.active or self.io_busy:
            return
        if self.replay_timer.isActive():
            self.stop_replay()
        else:
            if self.index >= len(self.frames) - 1:
                self.slider.setValue(0)
            self.play_button.setText("暂停回放")
            self.replay_timer.start(self.speed_combo.currentData())

    def stop_replay(self):
        self.replay_timer.stop()
        self.play_button.setText("播放")

    def advance_replay(self):
        if self.index + 1 >= len(self.frames):
            self.stop_replay()
        else:
            self.slider.setValue(self.index + 1)

    def change_replay_speed(self):
        if self.replay_timer.isActive():
            self.replay_timer.setInterval(self.speed_combo.currentData())

    def _start_io(self, kind, path, on_success=None):
        self.stop_replay()
        self.io_busy = True
        self.io_success = on_success
        self.update_controls()
        self.statusBar().showMessage("正在读取结果…" if kind == "load" else "正在保存结果…")
        frames = list(self.frames)
        def worker():
            try:
                result = load_frames(path) if kind == "load" else save_frames(path, frames)
                self.io_inbox.put((kind, path, result, None))
            except Exception as error:
                self.io_inbox.put((kind, path, None, str(error)))
        threading.Thread(target=worker, name="Qt-Result-IO", daemon=True).start()

    def _finish_io(self):
        try:
            kind, path, result, error = self.io_inbox.get_nowait()
        except queue.Empty:
            return
        self.io_busy = False
        on_success, self.io_success = self.io_success, None
        if error:
            self.log(error)
            self.statusBar().showMessage("文件操作失败，原有快照仍保留。")
            QMessageBox.warning(self, "文件操作失败", error)
        elif kind == "load":
            self.install_frames(result)
            self.last_result_path = Path(path)
            self.switch_workspace(0)
            self.statusBar().showMessage(f"已加载 {len(result)} 个快照：{Path(path).name}")
            self.log(f"加载结果：{path}")
        else:
            self.dirty = False
            self.last_result_path = Path(path)
            self.statusBar().showMessage(f"已保存：{path}")
            self.log(f"保存结果：{path}")
        self.update_controls("replay" if kind == "load" and not error else None)
        if not error and on_success:
            try:
                on_success()
            except Exception as callback_error:
                self.log(str(callback_error))
                self.update_controls()
                QMessageBox.warning(self, "无法启动", str(callback_error))

    def install_frames(self, frames):
        if self.controller.active:
            raise RuntimeError("运行期间不能替换历史")
        self.clear_history()
        self.frames = frames
        for index, frame in enumerate(frames):
            self._history_item(frame, index)
        self.slider.setRange(0, len(frames) - 1)
        self.slider.setValue(len(frames) - 1)
        self.select_frame(len(frames) - 1)
        self.result_label_prefix = "回放："
        self.update_selection_label()
        self.update_controls("replay")

    def open_result(self):
        if self.controller.active or self.io_busy:
            return
        folder = self.archive_folder() if self.archive_folder().exists() else ROOT / "results"
        path, _ = QFileDialog.getOpenFileName(self, "打开 FlexDMO 结果", str(folder), "FlexDMO JSON (*.json)")
        if path and self.allow_discard():
            self._start_io("load", path)

    def save_result(self):
        if not self.frames or self.controller.active or self.io_busy:
            return
        folder = ROOT / "results"
        folder.mkdir(parents=True, exist_ok=True)
        suggested = folder / f"FlexDMO_Qt_{datetime.now():%Y%m%d_%H%M%S}.json"
        path, _ = QFileDialog.getSaveFileName(self, "保存运行快照", str(suggested), "FlexDMO JSON (*.json)")
        if path:
            self._start_io("save", path)

    def restore_layout(self):
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.settings_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
        self.settings_dock.setFloating(False)
        self.history_dock.setFloating(False)
        self.settings_dock.show()
        self.history_dock.show()
        self.resizeDocks([self.settings_dock, self.history_dock], [290, 220], Qt.Orientation.Horizontal)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "history_dock"):
            return
        if hasattr(self, "workspace_stack") and self.workspace_stack.currentIndex() == 1:
            return
        if self.width() < 1150 and self.history_dock.isVisible() and not self.history_dock.isFloating():
            self.history_dock.hide()
            self.history_auto_hidden = True
        elif self.width() >= 1150 and self.history_auto_hidden:
            self.history_dock.show()
            self.history_auto_hidden = False

    def closeEvent(self, event):
        if self.io_busy or self.batch.runner.exporting:
            QMessageBox.information(self, "正在处理文件", "请等文件操作完成后再关闭。")
            event.ignore()
            return
        if self.controller.active or self.batch.runner.active:
            reply = QMessageBox.question(self, "结束运行？", "关闭窗口将终止运行中的测试和批量任务；已保存的结果会保留。",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if not self.allow_discard():
            event.ignore()
            return
        self.stop_replay()
        self.controller.shutdown()
        self.batch.runner.shutdown()
        event.accept()
