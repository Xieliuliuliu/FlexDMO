"""Replay history without item-view selection/accessibility cell caches."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class EnvironmentButton(QPushButton):
    navigate_requested = Signal(int)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End):
            self.navigate_requested.emit(event.key())
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)


class HistoryPanel(QScrollArea):
    # Include the history generation so queued events cannot select an old run.
    frame_requested = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setAccessibleName("回放环境历史")
        self.body = QWidget()
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(2, 2, 2, 2)
        self.rows.setSpacing(6)
        self.empty = QLabel("运行结束后，点击环境回放。")
        self.empty.setWordWrap(True)
        self.empty.setObjectName("muted")
        self.rows.addWidget(self.empty)
        self.rows.addStretch()
        self.setWidget(self.body)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.entries = {}
        self.generation = 0
        self.current_environment = None
        self.setStyleSheet("""
            QPushButton#history-environment {
                text-align: left; padding: 9px; background: white; color: #24334b;
                border: 1px solid #d4deea; border-radius: 5px;
            }
            QPushButton#history-environment:checked {
                background: #e3f4f5; color: #166373; border: 1px solid #129bad;
            }
            QPushButton#history-environment:focus { border: 2px solid #129bad; }
            QPushButton#history-environment:disabled { color: #9ba8bb; background: #eff2f6; }
        """)

    def update_environment(self, environment, evaluations, snapshots, index):
        environment = int(environment)
        if environment not in self.entries:
            control = EnvironmentButton(self.body)
            control.setObjectName("history-environment")
            control.setCheckable(True)
            control.setAutoDefault(False)
            control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            generation = self.generation
            control.clicked.connect(lambda _, t=environment, g=generation: self._activate(t, g))
            control.navigate_requested.connect(lambda key, t=environment, g=generation: self._navigate(t, key, g))
            self.entries[environment] = {"button": control, "index": index}
            self.group.addButton(control)
            position = sorted(self.entries).index(environment)
            self.rows.insertWidget(position, control)
        entry = self.entries[environment]
        entry["index"] = int(index)
        control = entry["button"]
        control.setText(f"环境 {environment}\n评估 {evaluations:,}")
        control.setAccessibleName(f"回放环境 {environment}")
        control.setAccessibleDescription(f"最近评估 {evaluations}，共 {snapshots} 个快照")
        control.setToolTip(f"点击查看本环境最近快照，共 {snapshots} 个；时间轴可逐帧回放。")
        self.empty.hide()

    def _activate(self, environment, generation):
        if not self.isEnabled() or generation != self.generation:
            return
        entry = self.entries.get(environment)
        if entry is not None:
            self.frame_requested.emit(entry["index"], generation)

    def _navigate(self, environment, key, generation):
        if not self.isEnabled() or generation != self.generation or environment not in self.entries:
            return
        ordered = sorted(self.entries)
        position = ordered.index(environment)
        if key == Qt.Key.Key_Home:
            position = 0
        elif key == Qt.Key.Key_End:
            position = len(ordered) - 1
        else:
            position = max(0, min(len(ordered) - 1, position + (1 if key == Qt.Key.Key_Down else -1)))
        control = self.entries[ordered[position]]["button"]
        control.setFocus(Qt.FocusReason.TabFocusReason)
        self.ensureWidgetVisible(control)

    def set_current_environment(self, environment):
        if environment in self.entries:
            self.entries[environment]["button"].setChecked(True)
            self.current_environment = environment

    def clear(self):
        self.generation += 1
        old, self.entries = self.entries, {}
        self.current_environment = None
        for entry in old.values():
            control = entry["button"]
            self.group.removeButton(control)
            control.setEnabled(False)
            control.hide()
            self.rows.removeWidget(control)
            # Defer destruction until after the current UI event. Never reuse
            # a button or its callback for a new run or replacement result.
            control.deleteLater()
        self.empty.show()
