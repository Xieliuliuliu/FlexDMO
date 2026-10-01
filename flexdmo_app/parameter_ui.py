"""Code-driven fields with a common text API for draft preservation."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from .core import parameter_text
from .widgets import ChoiceBox


class ParameterChoice(ChoiceBox):
    def text(self):
        return self.currentData()

    def setText(self, text):
        text = str(text)
        index = self.findData(text)
        if index < 0:
            # Keep invalid drafts visible so switching components cannot
            # silently repair/change their meaning. Validation rejects them.
            self.addItem(text, text)
            index = self.count() - 1
        self.setCurrentIndex(index)


def parameter_field(record, key, value):
    spec = record.get("parameter_specs", {}).get(key, {})
    text = value if isinstance(value, str) else parameter_text(value, spec)
    choices = spec.get("choices")
    if spec.get("type") == "bool" or choices:
        field = ParameterChoice()
        if spec.get("required"):
            field.addItem("请选择（必填）", "")
        if spec.get("nullable"):
            field.addItem("未设置（None）", "None")
        for option in choices or [True, False]:
            field.addItem(str(option), parameter_text(option, spec))
        field.setText(text)
    else:
        field = QLineEdit(text)
        if spec.get("required"):
            field.setPlaceholderText(f"必填 · {spec['type']}")
        elif spec.get("type") in ("list", "dict", "tuple"):
            field.setPlaceholderText("JSON 格式，例如 [1, 2]")
        if spec.get("type") in ("int", "float"):
            field.setInputMethodHints(Qt.InputMethodHint.ImhFormattedNumbersOnly)
    default = record.get("defaults", {}).get(key)
    field.setToolTip(f"参数：{key}\n类型：{spec.get('type', '按默认值推断')}\n"
                     f"默认值：{parameter_text(default, spec) if 'defaults' in record else value}\n"
                     + ("取值范围请由算法代码检查。" if spec else ""))
    return field
