"""One component picker for single-run and batch workspaces.

Use ordinary buttons rather than item-view cells: macOS accessibility can
retain invalid cell wrappers while an item view is rebuilt or hidden.
"""
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QLabel, QLineEdit,
                              QRadioButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from .component_choices import choice_label, component_sort_key


class ComponentEntry:
    """A record and its real control, shared by both selection modes."""

    def __init__(self, record, control):
        self.record = record
        self.control = control

    def data(self, role=Qt.ItemDataRole.UserRole):
        return self.record if role == Qt.ItemDataRole.UserRole else None

    def text(self):
        return self.control.text()

    def checkState(self):
        return Qt.CheckState.Checked if self.control.isChecked() else Qt.CheckState.Unchecked

    def setCheckState(self, state):
        self.control.setChecked(state == Qt.CheckState.Checked)

    def isHidden(self):
        return self.control.isHidden()

    def setHidden(self, hidden):
        self.control.setHidden(hidden)


class ComponentSelector(QWidget):
    currentIndexChanged = Signal(int)
    itemChanged = Signal(object)

    def __init__(self, kind, *, multiple=False, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.multiple = multiple
        self.entries = []
        self._current = -1
        self._generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("输入名称或年份筛选" if kind != "problem" else "输入问题名称筛选")
        self.filter_box.setAccessibleName("筛选组件")
        self.filter_box.textChanged.connect(self.filter_items)
        layout.addWidget(self.filter_box)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setMinimumHeight(90)
        self.scroll.setMaximumHeight(150 if not multiple else 180)
        self.body = QWidget()
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(3, 3, 3, 3)
        self.rows.setSpacing(4)
        self.rows.addStretch()
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("muted")
        layout.addWidget(self.summary)
        self.group = QButtonGroup(self)
        self.group.setExclusive(not multiple)
        self.setStyleSheet("""
            QRadioButton, QCheckBox { color: #24334b; padding: 5px; border-radius: 4px; }
            QRadioButton:checked, QCheckBox:checked { background: #e3f4f5; color: #166373; }
            QRadioButton:focus, QCheckBox:focus { border: 1px solid #129bad; }
        """)

    def set_records(self, records, *, current=None, checked=()):
        blocked = self.blockSignals(True)
        try:
            self.clear()
            records = list(records)
            if self.kind in ("dynamic", "search"):
                records.sort(key=component_sort_key)
            for record in records:
                self.addItem(choice_label(self.kind, record), record)
            if self.multiple:
                for entry in self.entries:
                    entry.setCheckState(Qt.CheckState.Checked if entry.record["folder_name"] in checked
                                        else Qt.CheckState.Unchecked)
            index = next((i for i, entry in enumerate(self.entries)
                          if entry.record["folder_name"] == current), 0 if self.entries else -1)
            self.setCurrentIndex(index)
            self.filter_items(self.filter_box.text())
        finally:
            self.blockSignals(blocked)

    def addItem(self, label, record):
        control = (QCheckBox if self.multiple else QRadioButton)(label, self.body)
        # Long user-defined names must not widen the whole settings dock.
        # Their full name remains available to accessibility and in the tooltip.
        control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        control.setAccessibleName(label)
        control.setToolTip(label)
        entry = ComponentEntry(record, control)
        self.entries.append(entry)
        self.rows.insertWidget(len(self.entries) - 1, control)
        self.group.addButton(control)
        control.installEventFilter(self)
        generation = self._generation
        control.toggled.connect(lambda _, e=entry, g=generation: self._changed(e, g))
        control.clicked.connect(lambda _, e=entry, g=generation: self._clicked(e, g))
        control.setHidden(self.filter_box.text().casefold() not in label.casefold())

    def clear(self):
        self._generation += 1
        old, self.entries = self.entries, []
        self._current = -1
        for entry in old:
            control = entry.control
            self.group.removeButton(control)
            control.removeEventFilter(self)
            control.setEnabled(False)
            control.hide()
            self.rows.removeWidget(control)
            # Keep existing native event/accessibility references valid until
            # this UI event has finished; old callbacks also carry a generation.
            control.deleteLater()

    def _changed(self, entry, generation):
        if generation != self._generation:
            return
        if self.multiple:
            self.itemChanged.emit(entry)
        elif entry.control.isChecked():
            self._set_current(self.entries.index(entry))
        self._update_summary()

    def _clicked(self, entry, generation):
        if generation == self._generation:
            self._set_current(self.entries.index(entry))

    def _set_current(self, index):
        if self._current != index:
            self._current = index
            self.currentIndexChanged.emit(index)
        self._update_summary()

    def count(self):
        return len(self.entries)

    def item(self, index):
        return self.entries[index]

    def itemData(self, index):
        return self.entries[index].record

    def itemText(self, index):
        return self.entries[index].text()

    def currentIndex(self):
        return self._current

    def currentItem(self):
        return self.entries[self._current] if 0 <= self._current < self.count() else None

    def currentData(self):
        entry = self.currentItem()
        return entry.record if entry else None

    def setCurrentItem(self, entry):
        self.setCurrentIndex(self.entries.index(entry))

    def setCurrentIndex(self, index):
        if not 0 <= index < self.count():
            return
        if not self.multiple:
            self.entries[index].control.setChecked(True)
        self._set_current(index)

    def filter_items(self, text):
        for entry in self.entries:
            entry.setHidden(text.casefold() not in entry.text().casefold())
        self.scrollToTop()
        self._update_summary()

    def scrollToTop(self):
        self.scroll.verticalScrollBar().setValue(0)

    def _update_summary(self):
        visible = sum(not entry.isHidden() for entry in self.entries)
        if self.multiple:
            selected = [entry for entry in self.entries if entry.control.isChecked()]
            hidden = sum(entry.isHidden() for entry in selected)
            text = f"已选 {len(selected)} 项" + (f"（筛选外 {hidden} 项）" if hidden else "")
        else:
            entry = self.currentItem()
            text = "当前：" + entry.text() if entry else "尚未选择"
        if not visible:
            text = "没有匹配项 · " + text
        self.summary.setText(text)

    def eventFilter(self, control, event):
        entry = next((entry for entry in self.entries if entry.control is control), None)
        if entry is not None and event.type() == QEvent.Type.FocusIn:
            # Moving focus in multi-select does not toggle a choice, but does
            # select the component whose parameters the user can edit.
            if self.multiple:
                self._set_current(self.entries.index(entry))
        if entry is not None and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                control.click()
                return True
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End):
                visible = [entry for entry in self.entries if not entry.isHidden()]
                if entry not in visible:
                    return True
                index = visible.index(entry)
                index = (0 if key == Qt.Key.Key_Home else len(visible) - 1 if key == Qt.Key.Key_End
                         else max(0, min(len(visible) - 1, index + (1 if key == Qt.Key.Key_Down else -1))))
                target = visible[index]
                target.control.setFocus(Qt.FocusReason.TabFocusReason)
                self.scroll.ensureWidgetVisible(target.control)
                if not self.multiple:
                    self.setCurrentItem(target)
                return True
        return super().eventFilter(control, event)
