"""Capture documentation from real Qt optimizations, without saved run data."""
import argparse
from pathlib import Path
import sys
import time


def main():
    import main_qt
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from flexdmo_app.window import FlexDMOWindow
    from flexdmo_app.comparison_ui import ComparisonDialog
    from flexdmo_app.component_ui import ComponentDialog
    from flexdmo_app.components import import_code
    from flexdmo_app.core import ROOT

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Existing directory for documentation screenshots")
    options = parser.parse_args()
    output = Path(options.output).resolve()
    if not output.is_dir():
        parser.error("output must be an existing directory")
    app = QApplication([])
    app.setStyle("Fusion")
    window = FlexDMOWindow()
    window.resize(1440, 940)
    window.show()
    def files():
        folder = ROOT / "results"
        return {str(p): p.stat().st_size for p in folder.rglob("*") if p.is_file()} if folder.exists() else {}
    before = files()
    imported = None
    code = None
    def wait(predicate, seconds=90):
        deadline = time.monotonic() + seconds
        while not predicate():
            app.processEvents()
            if time.monotonic() > deadline:
                raise TimeoutError("Documentation run timed out")
            time.sleep(0.01)
        app.processEvents()
    def capture(widget, name):
        # Allow actual resize/layout/draw timers to settle before QWidget.grab.
        end = time.monotonic() + 0.3
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)
        if widget is window:
            window.render_latest()
        app.processEvents()
        assert widget.grab().save(str(output / name))
        print("CAPTURE", name, flush=True)
    callback_errors = []
    previous_hook = sys.excepthook
    def callback_error(kind, error, traceback):
        callback_errors.append(f"{kind.__name__}: {error}")
        previous_hook(kind, error, traceback)
    sys.excepthook = callback_error
    try:
        window.start_run()
        wait(lambda: not window.controller.active)
        assert window.controller.status == "completed"
        full = {t: window.frames[index]["population"].get_decision_matrix().copy()
                for t, index in window.environment_frame_indices.items()}
        full_count = len(window.frames)
        window.history_policy.setCurrentIndex(1)
        window.start_run()
        wait(lambda: not window.controller.active)
        assert window.controller.status == "completed" and len(window.frames) == len(full)
        for t, index in window.environment_frame_indices.items():
            np.testing.assert_array_equal(full[t], window.frames[index]["population"].get_decision_matrix())
        print(f"PASS fixed-seed full/light identical environment ends: {full_count} -> {len(window.frames)} frames", flush=True)
        capture(window, "qt-test.png")
        window.settings_tabs.setCurrentIndex(1)
        capture(window, "qt-parameters.png")
        window.settings_tabs.setCurrentIndex(0)
        window.resize(850, 720)
        capture(window, "qt-narrow.png")
        window.resize(1440, 940)
        batch = window.batch
        batch.output.setText("results/experiments")
        window.switch_workspace(1)
        choices = batch.lists["dynamic"]
        for i in range(choices.count()):
            item = choices.item(i)
            item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole)["name"] in
                              ("NoResponse", "D-NSGA-II-B") else Qt.CheckState.Unchecked)
        batch.spin["repeats"].setValue(2)
        batch.history_policy.setCurrentIndex(1)
        batch.start()
        wait(lambda: not batch.runner.active)
        assert len(batch.tasks) == 4 and all(t["status"] == "completed" for t in batch.tasks)
        assert all(len(t["result"]["frames"]) == 3 for t in batch.tasks)
        capture(window, "qt-batch.png")
        dialog = ComparisonDialog(batch.tasks, window)
        dialog.show()
        wait(lambda: not dialog.timer.isActive())
        assert len(dialog.runs) == 4
        capture(dialog, "qt-comparison.png")
        dialog.mode.setCurrentIndex(2)
        capture(dialog, "qt-comparison-pf.png")
        dialog.reject()
        code = ComponentDialog(window.refresh_registry, window)
        imported = import_code(ROOT / "flexdmo_app" / "examples" / "MySearch.py", "search")
        code.kind.setCurrentIndex(1)
        code.refresh()
        selected = next(i for i in range(code.code_choice.count())
                        if code.code_choice.itemData(i)["source_file"] == str(imported.resolve()))
        code.code_choice.setCurrentIndex(selected)
        code.show()
        code.check_code()
        wait(lambda: not code.trial.active)
        assert code.trial.status == "completed" and not code.trial_failed
        capture(code, "qt-code.png")
        code.reject()
        assert files() == before, "Documentation generation wrote run data"
        assert not callback_errors, callback_errors
        print("PASS real single/batch comparison capture, lightweight batch, no saved runtime data", flush=True)
    finally:
        if code is not None:
            code.reject()
        # Only remove the demonstration copy that this script exclusively
        # created. The example source remains in the repo; existing code is
        # never overwritten by import_code.
        if imported is not None and imported.read_bytes() == (ROOT / "flexdmo_app" / "examples" / "MySearch.py").read_bytes():
            imported.unlink()
        window.controller.shutdown()
        window.batch.runner.shutdown()
        window.dirty = False
        window.close()
        sys.excepthook = previous_hook


if __name__ == "__main__":
    raise SystemExit(main())
