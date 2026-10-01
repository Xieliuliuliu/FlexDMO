"""Small cross-platform widgets shared by the Qt workspaces."""
from PySide6.QtWidgets import QComboBox, QListView, QStyledItemDelegate


class ChoiceBox(QComboBox):
    """Use a list delegate, not a platform menu delegate, for styled choices.

    Qt's menu-style combo delegate can paint selected text white while the
    stylesheet paints its background white. A standard list delegate renders
    selection foreground and background together on macOS and other platforms.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setUniformItemSizes(True)
        self.setView(view)
        self.setItemDelegate(QStyledItemDelegate(view))
