from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from .components import FOLDERS, PLUGIN_ROOT, import_code
from .core import defaults, parameter_label, parse_parameters, records
from .controller import RunController
from .widgets import ChoiceBox as QComboBox
from .parameter_ui import parameter_field


class ParameterDialog(QDialog):
    def __init__(self, record, values=None, parent=None, locked=()):
        super().__init__(parent)
        self.setWindowTitle("组件参数 · " + record["name"])
        self.record = record
        self.template = {k: v for k, v in defaults(record).items() if k not in locked}
        self.fields = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for key, value in self.template.items():
            field = parameter_field(record, key, (values or {}).get(key, value))
            self.fields[key] = field
            form.addRow(parameter_label(record, key), field)
        layout.addLayout(form)
        if not self.fields:
            layout.addWidget(QLabel("此组件没有额外参数。"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            self.values = parse_parameters({key: field.text() for key, field in self.fields.items()}, self.template, self.record)
        except ValueError as error:
            QMessageBox.warning(self, "参数无效", str(error))
            return
        super().accept()


class ComponentDialog(QDialog):
    def __init__(self, refresh_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("算法代码 · 单个 Python 文件即可")
        self.setMinimumWidth(580)
        self.refresh_callback = refresh_callback
        self.created = None
        self.trial = RunController(self)
        self.trial.frame_received.connect(self._trial_frame)
        self.trial.error_received.connect(self._trial_error)
        self.trial.finished.connect(self._trial_finished)
        self.trial_timeout = QTimer(self)
        self.trial_timeout.setSingleShot(True)
        self.trial_timeout.timeout.connect(self._trial_timeout)
        self.trial_frames = 0
        self.trial_failed = False
        layout = QVBoxLayout(self)
        hint = QLabel("直接编写 .py 文件，放进算法目录或点击导入；不需要 JSON 或注册代码。\n"
                      "动态策略：response(population, problem, ...)\n"
                      "搜索算法：step(population, problem, ...)\n"
                      "返回 Population 或与原种群同形状的二维决策矩阵。默认参数自动生成设置。\n"
                      "刷新只解析代码；试跑会在独立进程执行代码，仅使用可信来源。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.kind = QComboBox()
        self.kind.addItem("动态响应策略", "dynamic")
        self.kind.addItem("搜索算法", "search")
        self.code_choice = QComboBox()
        self.kind.currentIndexChanged.connect(self._update_choices)
        for label, field in (("组件类型", self.kind), ("已发现代码", self.code_choice)):
            form.addRow(label, field)
        layout.addLayout(form)
        self.import_button = QPushButton("导入写好的 Python 文件")
        self.import_button.clicked.connect(self.import_file)
        layout.addWidget(self.import_button)
        refresh = QPushButton("已添加文件？刷新现有组件")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        self.folder_button = QPushButton("打开算法代码目录")
        self.folder_button.clicked.connect(self.open_folder)
        layout.addWidget(self.folder_button)
        guide = QPushButton("查看代码接入说明与短示例")
        guide.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(__file__).with_name("CODE_API.md")))))
        layout.addWidget(guide)
        self.check_button = QPushButton("检查并快速试跑（不保存数据）")
        self.check_button.clicked.connect(self.check_code)
        layout.addWidget(self.check_button)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMaximumBlockCount(500)
        self.report.setPlaceholderText("语法/接口检查与试跑结果显示在这里；失败包含文件和实际行号。")
        layout.addWidget(self.report)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self._update_choices()

    def _update_choices(self):
        if not hasattr(self, "code_choice"):
            return
        previous = self.code_choice.currentData()
        self.code_choice.clear()
        errors = []
        found = records(errors)
        for record in found[self.kind.currentData()]:
            if record.get("format") == "python-file":
                self.code_choice.addItem(record["name"], record)
                if previous and record["folder_name"] == previous["folder_name"]:
                    self.code_choice.setCurrentIndex(self.code_choice.count() - 1)
        if hasattr(self, "check_button"):
            self.check_button.setEnabled(self.code_choice.count() > 0 and not self.trial.active)
        if errors and hasattr(self, "report"):
            self.report.setPlainText("部分代码未加载：\n" + "\n".join(errors))

    def import_file(self):
        source, _ = QFileDialog.getOpenFileName(self, "导入算法（仅复制，不执行）", "", "Python (*.py)")
        if not source:
            return
        try:
            self.created = import_code(source, self.kind.currentData())
            self.path_label.setText(f"已导入：{self.created}\n可直接编辑代码；修改参数或接口后点击刷新。")
            self.refresh()
            for i in range(self.code_choice.count()):
                if self.code_choice.itemData(i)["source_file"] == str(self.created.resolve()):
                    self.code_choice.setCurrentIndex(i)
        except Exception as error:
            self.report.setPlainText(str(error))

    def open_folder(self):
        folder = PLUGIN_ROOT / FOLDERS[self.kind.currentData()]
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def check_code(self):
        if self.trial.active:
            return
        record = self.code_choice.currentData()
        if not record:
            return
        try:
            registry = records()
            selected = {kind: next(r for r in registry[kind] if r["name"] == name) for kind, name in
                        (("dynamic", "NoResponse"), ("search", "NSGAII"), ("problem", "CDP1"))}
            selected[self.kind.currentData()] = record
            profile = defaults(record)
            if any(spec.get("required") for spec in record.get("parameter_specs", {}).values()):
                dialog = ParameterDialog(record, parent=self)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                profile = dialog.values
            profile = parse_parameters(profile, defaults(record), record)
            params = {k: defaults(r) for k, r in selected.items()}
            params[self.kind.currentData()] = profile
            params["problem"].update(decision_num=3, solution_num=6, tau=1, n=10, total_evaluate_time=2)
            self.trial_frames, self.trial_failed = 0, False
            self.report.setPlainText("正在独立子进程中试跑 CDP1（6 个体、2 环境）；不写运行文件。")
            self.trial.start({"records": selected, "params": params})
            self._trial_controls(False)
            self.trial_timeout.start(20000)
        except Exception as error:
            self.report.setPlainText(str(error))

    def _trial_controls(self, enabled):
        for widget in (self.kind, self.code_choice, self.import_button, self.folder_button):
            widget.setEnabled(enabled)
        self.check_button.setEnabled(enabled and self.code_choice.count() > 0)

    def _trial_frame(self, frame):
        self.trial_frames += 1

    def _trial_error(self, error):
        self.trial_failed = True
        self.report.appendPlainText(error)

    def _trial_finished(self, status):
        self.trial_timeout.stop()
        self._trial_controls(True)
        if status == "completed" and self.trial_frames and not self.trial_failed:
            self.report.appendPlainText(f"试跑通过：收到 {self.trial_frames} 个回放快照；可用于测试运行和批量实验。\n"
                                        "这只验证基本接口与运行链路，不等于证明算法正确或论文复现成功。")
        elif not self.trial_failed:
            self.report.appendPlainText("试跑未产生完整快照；完整 optimize 类需要调用 collect_information。")

    def _trial_timeout(self):
        self.trial_failed = True
        self.report.appendPlainText("快速检查超过 20 秒，正在终止；较慢算法请在测试运行中调整预算验证。")
        self.trial.stop()

    def done(self, result):
        self.trial_timeout.stop()
        self.trial.shutdown()
        super().done(result)

    def refresh(self):
        if self.trial.active:
            self.report.appendPlainText("请先等待试跑结束再刷新代码。")
            return
        try:
            self.refresh_callback()
            self._update_choices()
            errors = []
            records(errors)
            if errors:
                self.report.setPlainText("部分组件未加载：\n" + "\n".join(errors))
            elif not self.created:
                self.path_label.setText("组件已刷新。无须重启；新的运行子进程会重新加载算法代码。")
        except Exception as error:
            QMessageBox.warning(self, "无法刷新", str(error))
