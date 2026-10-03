"""Start the FlexDMO desktop application."""
from pathlib import Path
import multiprocessing
import os
import sys

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    from PySide6.QtWidgets import QApplication
    from flexdmo_app.window import FlexDMOWindow
    app = QApplication(sys.argv)
    app.setApplicationName("FlexDMO")
    app.setStyle("Fusion")
    window = FlexDMOWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
