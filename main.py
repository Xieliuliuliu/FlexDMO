"""Start the FlexDMO desktop application."""
from pathlib import Path
import multiprocessing
import os
import site
import sys

ROOT = Path(__file__).resolve().parent
# Compatibility for existing development installations. Normal installations
# put every dependency in one .venv and do not need this branch.
if Path(sys.prefix).resolve() == (ROOT / ".venv" / "qt-preview").resolve():
    for packages in (ROOT / ".venv" / "lib").glob("python*/site-packages"):
        site.addsitedir(str(packages))


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
