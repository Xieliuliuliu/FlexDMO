"""Real spawn-worker coverage using the same runtime as the desktop."""
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest

from flexdmo_app.core import (RunState, defaults, load_frames, optimize_worker,
                             records, save_frames)
from flexdmo_app.experiments import experiment_worker


class PlatformSupportTests(unittest.TestCase):
    def request(self):
        catalog = records()
        names = {"dynamic": "NoResponse", "search": "NSGAII", "problem": "CDP6"}
        selected = {kind: next(r for r in catalog[kind] if r["name"] == name)
                    for kind, name in names.items()}
        params = {kind: defaults(record) for kind, record in selected.items()}
        params["problem"].update(decision_num=4, n=10, tau=1,
                                 solution_num=8, total_evaluate_time=3)
        params["search"]["seed"] = 5
        return {"records": selected, "params": params}

    def collect_spawned_worker(self, target, request):
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        state = RunState(context.Value("i", 0))
        process = context.Process(target=target, args=(request, state, child))
        messages = []
        try:
            process.start()
            child.close()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                try:
                    if parent.poll(0.1):
                        messages.append(parent.recv())
                    elif not process.is_alive():
                        break
                except (EOFError, BrokenPipeError):
                    # Windows poll() reports a closed named pipe as a broken
                    # pipe, whereas POSIX exposes EOF through recv().
                    break
            process.join(timeout=5)
            self.assertFalse(process.is_alive(), "spawn worker did not finish")
            self.assertEqual(process.exitcode, 0, messages)
        finally:
            if process.pid is not None and process.is_alive():
                process.terminate()
                process.join(timeout=5)
            parent.close()
            child.close()
        return messages

    def test_spawned_test_worker_emits_replayable_snapshots(self):
        frames = self.collect_spawned_worker(optimize_worker, self.request())
        self.assertEqual(sorted({f["t"] for f in frames}), [0, 1, 2])
        self.assertTrue(all(f["population"].n == 8 for f in frames))
        with tempfile.TemporaryDirectory(prefix="FlexDMO-约束-") as directory:
            path = Path(directory) / "回放.json"
            save_frames(path, frames)
            self.assertEqual(len(load_frames(path)), len(frames))

    def test_spawned_experiment_saves_loadable_native_path_results(self):
        with tempfile.TemporaryDirectory(prefix="FlexDMO-约束-") as directory:
            path = Path(directory) / "批量结果.json"
            request = dict(self.request(), output_path=str(path))
            messages = self.collect_spawned_worker(experiment_worker, request)
            self.assertTrue(any(m.get("kind") == "progress" for m in messages))
            result = next(m for m in messages if m.get("kind") == "result")
            self.assertFalse(result["partial"])
            self.assertEqual(result["path"], str(path))
            self.assertEqual(sorted({f["t"] for f in load_frames(path)}), [0, 1, 2])

    def test_spawned_experiment_keeps_results_in_memory_by_default(self):
        messages = self.collect_spawned_worker(experiment_worker, self.request())
        result = next(m for m in messages if m.get("kind") == "result")
        self.assertFalse(result["partial"])
        self.assertNotIn("path", result)
        self.assertEqual(sorted({f["t"] for f in result["frames"]}), [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
