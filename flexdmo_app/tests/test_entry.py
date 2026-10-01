"""The public entry point starts the current desktop workflow."""
import unittest
from unittest.mock import MagicMock, patch

import main


class EntryTests(unittest.TestCase):
    def test_main_starts_default_desktop(self):
        app = MagicMock()
        app.exec.return_value = 0
        window = MagicMock()
        with patch("PySide6.QtWidgets.QApplication", return_value=app), \
                patch("flexdmo_app.window.FlexDMOWindow", return_value=window):
            self.assertEqual(main.main(), 0)
        app.setApplicationName.assert_called_once_with("FlexDMO")
        window.show.assert_called_once()
        app.exec.assert_called_once()
