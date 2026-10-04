"""Enforce desktop boundaries without relying on installed Tk/ML packages."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DesktopBoundaryTests(unittest.TestCase):
    def test_production_does_not_import_removed_ui_packages(self):
        paths = [ROOT / "main.py", ROOT / "main_qt.py"]
        for folder in ("flexdmo_app", "utils", "algorithms", "components",
                       "problems", "results_output"):
            paths.extend(p for p in (ROOT / folder).rglob("*.py")
                         if not any(part in ("tests", "plugins", "__pycache__")
                                    for part in p.relative_to(ROOT / folder).parts))
        forbidden = {"tkinter", "ttkbootstrap", "views", "plots"}
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    self.assertNotIn(name.split(".")[0], forbidden, str(path))
                    self.assertNotIn("backend_tk", name, str(path))

    def test_old_entrypoint_and_ui_sources_are_removed(self):
        self.assertFalse((ROOT / "main_tk.py").exists())
        for folder in ("views", "plots"):
            self.assertEqual(list((ROOT / folder).rglob("*.py")), [])

    def test_base_requirements_do_not_pull_optional_algorithm_libraries(self):
        for name in ("requirements.txt", "requirements-macos.txt", "flexdmo_app/requirements.txt"):
            requirements = (ROOT / name).read_text().lower()
            for library in ("ttkbootstrap", "torch", "scikit-learn", "psutil"):
                self.assertNotIn(library, requirements, name)

    def test_macos_uses_the_same_dependency_set(self):
        requirements = (ROOT / "requirements-macos.txt").read_text().splitlines()
        entries = [line.strip() for line in requirements
                   if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(entries, ["-r requirements.txt"])

    def test_unsupported_python_fails_before_loading_desktop_libraries(self):
        self.child("""
import main
from unittest.mock import patch
with patch.object(main.sys, "version_info", (3, 11, 0)):
    try:
        main.main()
    except SystemExit as error:
        assert "Python 3.12" in str(error)
    else:
        raise AssertionError("Older Python must receive an actionable error")
print("BOUNDARY_OK")
""", {"PySide6", "torch", "sklearn"})

    def child(self, code, blocked):
        blocker = f"""
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {blocked!r}:
            raise ModuleNotFoundError("Blocked test dependency: " + fullname)
sys.meta_path.insert(0, Block())
"""
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MPLBACKEND="Agg")
        result = subprocess.run([sys.executable, "-c", textwrap.dedent(blocker) + textwrap.dedent(code)],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BOUNDARY_OK", result.stdout)

    def test_desktop_starts_with_tk_and_ml_imports_blocked(self):
        self.child("""
from PySide6.QtWidgets import QApplication, QLabel
from flexdmo_app.window import FlexDMOWindow
app = QApplication([])
app.setStyle("Fusion")
window = FlexDMOWindow()
window.show()
app.processEvents()
logos = [label for label in window.findChildren(QLabel)
         if label.accessibleName() == "FlexDMO 标志"]
assert len(logos) == 1 and not logos[0].pixmap().isNull()
assert window.request()["records"]["problem"]["name"] == "CDP1"
window.dirty = False
window.close()
app.processEvents()
assert not any(name.split(".")[0] in {"tkinter", "ttkbootstrap", "torch", "sklearn"}
               for name in sys.modules)
print("BOUNDARY_OK")
""", {"tkinter", "ttkbootstrap", "torch", "sklearn"})

    def test_report_reader_has_no_desktop_or_optional_ml_dependency(self):
        self.child("""
from utils.result_io import load_result_from_files
from results_output.MIGD_table.main import run
assert list(load_result_from_files([])) == []
print("BOUNDARY_OK")
""", {"PySide6", "tkinter", "ttkbootstrap", "torch", "sklearn"})


if __name__ == "__main__":
    unittest.main()
