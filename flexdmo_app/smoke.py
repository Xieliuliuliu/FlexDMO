"""Real Qt + spawned-process integration checks; outputs stay in ignored results."""
import sys
import time
from unittest.mock import patch


def main():
    import main_qt  # Bootstrap existing scientific packages before Qt imports.
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from flexdmo_app.window import FlexDMOWindow
    from flexdmo_app.core import ROOT, defaults, load_frames, records, save_frames
    from flexdmo_app.controller import RunController
    import numpy as np

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FlexDMOWindow()
    window.show()
    statuses, errors = [], []
    window.controller.status_changed.connect(statuses.append)
    window.controller.error_received.connect(errors.append)

    def wait(predicate, timeout=45):
        until = time.monotonic() + timeout
        while not predicate():
            app.processEvents()
            if time.monotonic() > until:
                raise TimeoutError("Qt smoke timeout")
            time.sleep(0.01)
        app.processEvents()

    output = ROOT / "results"
    output.mkdir(parents=True, exist_ok=True)
    try:
        paused = []
        def pause_once(frame):
            if not paused:
                paused.append(True)
                window.controller.pause()
                assert window.controller.state.value == "pause"
                QTimer.singleShot(700, window.controller.resume)
        window.controller.frame_received.connect(pause_once)
        window.start_run()
        wait(lambda: not window.controller.active)
        window.controller.frame_received.disconnect(pause_once)
        assert "paused" in statuses and statuses[-1] == "completed", statuses
        assert not errors, errors
        assert {f["t"] for f in window.frames} == set(range(5))
        save_frames(output / "smoke_roundtrip.json", window.frames)
        restored = load_frames(output / "smoke_roundtrip.json")
        assert len(restored) == len(window.frames)
        np.testing.assert_array_equal(restored[-1]["population"].get_objective_matrix(), window.frames[-1]["population"].get_objective_matrix())
        # By default repeated real runs do not persist data or show a dialog.
        archive = output / "rerun_smoke"
        archive.mkdir(parents=True, exist_ok=True)
        before = set(archive.glob("*.json"))
        with patch.object(window, "archive_folder", return_value=archive), \
                patch("flexdmo_app.window.QMessageBox.warning", side_effect=AssertionError("Unexpected restart dialog")):
            for _ in range(2):
                window.start_run()
                wait(lambda: not window.io_busy and not window.controller.active)
                assert statuses[-1] == "completed", statuses
                assert window.frames and window.dirty
        archived = set(archive.glob("*.json")) - before
        assert not archived
        window.auto_save.setChecked(True)
        with patch.object(window, "archive_folder", return_value=archive):
            window.start_run()
            wait(lambda: not window.io_busy and not window.controller.active)
        archived = set(archive.glob("*.json")) - before
        assert len(archived) == 2 and not window.dirty
        assert all(load_frames(path) for path in archived)
        window.auto_save.setChecked(False)
        print("PASS repeated runs: default no files/no dialog; opt-in saves complete replayable results", flush=True)
        window.install_frames(restored)
        for mode in range(window.mode_combo.count()):
            window.mode_combo.setCurrentIndex(mode)
            window.render_latest()
            app.processEvents()
        window.mode_combo.setCurrentIndex(0)
        for width, height in ((1360, 860), (900, 680), (700, 560)):
            window.resize(width, height)
            app.processEvents()
            window.render_latest()
            window.chart.canvas.draw()
            app.processEvents()
            assert window.centralWidget().width() >= 350, window.centralWidget().width()
            assert window.play_button.isEnabled()
            assert window.grab().save(str(output / f"qt-{width}.png"))
        window.slider.setValue(0)
        window.toggle_replay()
        wait(lambda: window.index >= 2, timeout=5)
        window.stop_replay()
        assert window.index >= 2
        assert not window.replay_timer.isActive()
        print(f"PASS Qt window: complete/pause/resume/save/load/{len(restored)} snapshots/multi and single charts/3 sizes/replay", flush=True)

        registry = records()
        worker = RunController()
        received, worker_errors, terminal = [], [], []
        worker.frame_received.connect(received.append)
        worker.error_received.connect(worker_errors.append)
        worker.finished.connect(terminal.append)
        for name in ("MOEA/D", "NSGAII", "RMMEDA", "SPEA2"):
            received.clear()
            selected = {"dynamic": next(r for r in registry["dynamic"] if r["name"] == "NoResponse"),
                        "search": next(r for r in registry["search"] if r["name"] == name),
                        "problem": next(r for r in registry["problem"] if r["name"] == "CDP1")}
            params = {kind: defaults(record) for kind, record in selected.items()}
            params["problem"].update(decision_num=3, solution_num=10, tau=1, total_evaluate_time=3)
            if "neighbor_size" in params["search"]:
                params["search"]["neighbor_size"] = 5
            request = {"records": selected, "params": params}
            worker.start(request)
            wait(lambda: not worker.active)
            assert terminal[-1] == "completed", (name, terminal, worker_errors)
            assert {f["t"] for f in received} == {0, 1, 2}, (name, len(received))
            print(f"PASS spawned algorithm: {name}, {len(received)} frames", flush=True)

        for strategy in registry["dynamic"]:
            received.clear()
            selected = {"dynamic": strategy,
                        "search": next(r for r in registry["search"] if r["name"] == "NSGAII"),
                        "problem": next(r for r in registry["problem"] if r["name"] == "CDP1")}
            params = {kind: defaults(record) for kind, record in selected.items()}
            params["problem"].update(decision_num=3, solution_num=10, tau=1, total_evaluate_time=3)
            request = {"records": selected, "params": params}
            worker.start(request)
            wait(lambda: not worker.active)
            assert terminal[-1] == "completed", (strategy["name"], terminal, worker_errors)
            assert {f["t"] for f in received} == {0, 1, 2}
            print(f"PASS spawned strategy: {strategy['name']}", flush=True)

        for problem_name in ("CDP2", "CDP3", "CDP4", "CDP5", "CDP6"):
            received.clear()
            selected["dynamic"] = next(r for r in registry["dynamic"] if r["name"] == "NoResponse")
            selected["problem"] = next(r for r in registry["problem"] if r["name"] == problem_name)
            params = {kind: defaults(record) for kind, record in selected.items()}
            params["problem"].update(decision_num=3, solution_num=10, tau=1, total_evaluate_time=3)
            request = {"records": selected, "params": params}
            worker.start(request)
            wait(lambda: not worker.active)
            assert terminal[-1] == "completed", (problem_name, terminal, worker_errors)
            save_frames(output / f"smoke_{problem_name}.json", received)
            window.install_frames(load_frames(output / f"smoke_{problem_name}.json"))
            window.render_latest()
            window.chart.canvas.draw()
            assert {f["t"] for f in received} == {0, 1, 2}
            print(f"PASS constrained replay/chart: {problem_name}", flush=True)

        # Force a constructor error in the CHILD; EOF and controls must recover.
        params["search"]["unknown_preview_parameter"] = 1
        worker.start(request)
        wait(lambda: not worker.active)
        assert terminal[-1] == "failed" and worker_errors
        del params["search"]["unknown_preview_parameter"]
        worker_errors.clear()
        params["problem"]["total_evaluate_time"] = 10000
        received.clear()
        worker.start(request)
        wait(lambda: bool(received))
        worker.pause()
        worker.stop()
        wait(lambda: not worker.active, timeout=10)
        assert terminal[-1] == "stopped"
        assert received
        save_frames(output / "smoke_partial.json", received)
        assert load_frames(output / "smoke_partial.json")
        print("PASS error recovery and paused termination with partial replay", flush=True)
        worker.shutdown()
        window.dirty = False
        window.close()
        print("ALL QT SMOKE CHECKS PASSED", flush=True)
        return 0
    finally:
        window.controller.shutdown()
        window.dirty = False
        window.close()


if __name__ == "__main__":
    raise SystemExit(main())
