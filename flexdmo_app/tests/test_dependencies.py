"""The base desktop remains usable without optional algorithm libraries."""
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from flexdmo_app.core import ROOT, records, registered_class
from flexdmo_app.dependencies import check_dependencies, requirements_file


class DependencyTests(unittest.TestCase):
    def test_base_requirements_exclude_algorithm_libraries(self):
        for filename in ("requirements.txt", "requirements-macos.txt", "flexdmo_app/requirements.txt"):
            text = (ROOT / filename).read_text().lower()
            self.assertNotIn("torch", text)
            self.assertNotIn("scikit-learn", text)
        for name in ("DIP", "RNN", "FGTTMP", "PSCA"):
            self.assertTrue((ROOT / "algorithms/response_strategy" / name / "requirements.txt").is_file())

    def test_selected_algorithm_missing_library_has_correct_install_command(self):
        for name, module in (("DIP", "torch"), ("RNN", "torch"), ("FGTTMP", "sklearn"), ("PSCA", "sklearn")):
            record = next(r for r in records()["dynamic"] if r["name"] == name)
            with self.subTest(name=name), patch("flexdmo_app.dependencies.importlib.util.find_spec", return_value=None):
                with self.assertRaises(ModuleNotFoundError) as error:
                    registered_class(record)
                self.assertEqual(error.exception.name, module)
                self.assertIn(name, str(error.exception))
                self.assertIn(str(requirements_file(record)), str(error.exception))
                self.assertIn("-m pip install -r", str(error.exception))

    def test_existing_library_is_checked_without_importing(self):
        record = next(r for r in records()["dynamic"] if r["name"] == "DIP")
        with patch("flexdmo_app.dependencies.importlib.util.find_spec", return_value=object()) as find, \
                patch("importlib.import_module", side_effect=AssertionError("must not import")):
            check_dependencies(record)
            find.assert_called_once_with("torch")

    def test_missing_library_does_not_discard_previous_result(self):
        from PySide6.QtWidgets import QApplication
        from flexdmo_app.window import FlexDMOWindow
        app = QApplication.instance() or QApplication([])
        window = FlexDMOWindow()
        try:
            selector = window.selectors["dynamic"]
            selector.setCurrentIndex(next(i for i in range(selector.count()) if selector.itemData(i)["name"] == "DIP"))
            previous = [{"previous_result": True}]
            window.frames = previous
            window.dirty = True
            with patch("flexdmo_app.dependencies.importlib.util.find_spec", return_value=None), \
                    patch.object(window, "_launch_run") as launch, \
                    patch("flexdmo_app.window.QMessageBox.warning") as warning:
                window.start_run()
                launch.assert_not_called()
                self.assertIs(window.frames, previous)
                self.assertTrue(window.dirty)
                self.assertIn("pip install", warning.call_args.args[2])
        finally:
            window.dirty = False
            window.close()
            window.deleteLater()
            app.processEvents()

    def test_cold_desktop_and_default_run_never_import_optional_libraries(self):
        script = '''
import importlib.abc, sys
from types import SimpleNamespace
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("torch", "sklearn"):
            raise AssertionError("Unselected dependency imported: " + fullname)
sys.meta_path.insert(0, BlockOptional())
from PySide6.QtWidgets import QApplication
from flexdmo_app.window import FlexDMOWindow
from flexdmo_app.core import optimize_worker
app = QApplication([])
window = FlexDMOWindow()
for workspace in (1, 0, 1, 0):
    window.switch_workspace(workspace)
    app.processEvents()
selector = window.selectors["dynamic"]
for name in ("DIP", "RNN", "FGTTMP", "PSCA", "NoResponse"):
    selector.setCurrentIndex(next(i for i in range(selector.count()) if selector.itemData(i)["name"] == name))
    window.request()  # Selection and parameter parsing must remain lightweight.
window.refresh_registry()
request = window.request()
request["params"]["problem"].update(solution_num=4, decision_num=3, tau=1, total_evaluate_time=2)
class Pipe:
    def __init__(self): self.messages = []
    def send(self, value): self.messages.append(value)
    def close(self): pass
pipe = Pipe()
optimize_worker(request, SimpleNamespace(value="running"), pipe)
assert any("population" in message for message in pipe.messages)
assert "torch" not in sys.modules and "sklearn" not in sys.modules
window.close()
print("BASE_DESKTOP_AND_RUN_OK")
'''
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BASE_DESKTOP_AND_RUN_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
