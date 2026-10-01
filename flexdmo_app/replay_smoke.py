"""Real optimization and native history replay stress, without result files."""
import argparse
import time


def main():
    import main_qt
    from pathlib import Path
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from flexdmo_app.core import ROOT
    from flexdmo_app.window import FlexDMOWindow
    from flexdmo_app.tests.cocoa_probe import CocoaProbe

    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", help="Optional QA screenshot outside the result directory")
    options = parser.parse_args()
    app = QApplication([])
    app.setStyle("Fusion")
    QAccessible.setActive(True)
    window = FlexDMOWindow()
    window.show()
    window.raise_()
    probe = CocoaProbe()
    output = ROOT / "results"
    def files():
        return {str(p.relative_to(output)): p.stat().st_size for p in output.rglob("*") if p.is_file()} if output.exists() else {}
    before = files()
    errors = []
    window.controller.error_received.connect(errors.append)
    def wait(predicate, seconds=45):
        deadline = time.monotonic() + seconds
        while not predicate():
            app.processEvents()
            if time.monotonic() >= deadline:
                raise TimeoutError("Native replay stress timed out")
            time.sleep(0.01)
        app.processEvents()
    try:
        assert not window.auto_save.isChecked()
        for run in range(3):
            previous = window.history_panel.generation
            window.start_run()
            wait(lambda: not window.controller.active)
            assert window.controller.status == "completed" and not errors, errors
            panel = window.history_panel
            assert len(panel.entries) == 5
            window.select_history_frame(0, previous)
            assert window.index == len(window.frames) - 1
            for cycle in range(4):
                for environment in sorted(panel.entries, reverse=bool(cycle % 2)):
                    control = panel.entries[environment]["button"]
                    panel.ensureWidgetVisible(control)
                    app.processEvents()
                    QTest.mouseClick(control, Qt.MouseButton.LeftButton)
                    window.render_latest()
                    app.processEvents()
                    assert window.index == panel.entries[environment]["index"]
                    assert panel.current_environment == environment and control.isChecked()
                    for mode in window.chart_dashboard.visible_modes():
                        assert window.chart_dashboard.charts[mode]._last_request[1] == window.index
                    for widget in (panel, panel.body, control):
                        probe.check_history_widget(widget)
                window.slider.setValue(0)
                window.render_latest()
                app.processEvents()
                assert panel.current_environment == window.frames[0]["t"]
            window.toggle_replay()
            assert window.replay_timer.isActive()
            panel.entries[1]["button"].click()
            assert not window.replay_timer.isActive()
            window.switch_workspace(1)
            window.switch_workspace(0)
            for width, height in ((900, 680), (1360, 860)):
                window.resize(width, height)
                app.processEvents()
            panel.entries[0]["button"].setFocus()
            QTest.keyClick(panel.entries[0]["button"], Qt.Key.Key_Down)
            QTest.keyClick(panel.entries[1]["button"], Qt.Key.Key_Return)
            assert panel.current_environment == 1
            assert files() == before
            print(f"PASS native run {run + 1}: history clicks, slider, play/pause, keyboard, rerun, no result files", flush=True)
        if options.capture:
            window.render_latest()
            app.processEvents()
            assert window.grab().save(str(Path(options.capture)))
        print(f"PASS {probe.calls} native Cocoa selected-children/title/label probes", flush=True)
        print("ALL NATIVE REPLAY CHECKS PASSED", flush=True)
        return 0
    finally:
        window.controller.shutdown()
        window.batch.runner.shutdown()
        window.dirty = False
        window.close()


if __name__ == "__main__":
    raise SystemExit(main())
