"""Regression coverage for native paths and real spawn-based workers."""
import multiprocessing
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from utils.information_parser import (
    find_match_problem,
    find_match_response_strategy,
    find_match_search_algorithm,
)
from utils.result_io import load_test_module_information_results
from utils.run_executor import run_in_test_mode_process
from utils.run_executor_for_experiment import run_experiment_process
from views.common.GlobalVar import global_vars
from views.experiment_module.experiment_module_view import select_save_path
from views.test_module.test_module_handler import build_replay_timeline


PROBLEM_CONFIG = {
    "decision_num": 4, "n": 10, "tau": 1,
    "solution_num": 8, "total_evaluate_time": 3,
}


class PlatformSupportTests(unittest.TestCase):
    def setUp(self):
        self.original_experiment = dict(global_vars["experiment_module"])
        self.original_test = dict(global_vars["test_module"])

    def tearDown(self):
        for key, original in (("experiment_module", self.original_experiment),
                              ("test_module", self.original_test)):
            global_vars[key].clear()
            global_vars[key].update(original)

    def test_selected_save_path_keeps_native_separators(self):
        path_variable = Mock()
        path_variable.get.return_value = "/missing/results"
        global_vars["experiment_module"]["save_path"] = path_variable
        chosen = os.path.join(tempfile.gettempdir(), "FlexDMO 约束", "results")
        with patch("views.experiment_module.experiment_module_view.filedialog.askdirectory",
                   return_value=chosen):
            select_save_path()
        path_variable.set.assert_called_once_with(os.path.normpath(chosen))

    def test_cancelled_save_path_selection_preserves_value(self):
        path_variable = Mock()
        path_variable.get.return_value = tempfile.gettempdir()
        global_vars["experiment_module"]["save_path"] = path_variable
        with patch("views.experiment_module.experiment_module_view.filedialog.askdirectory",
                   return_value=""):
            select_save_path()
        path_variable.set.assert_not_called()

    def test_exit_menu_runs_only_after_user_invocation(self):
        from views.app_view import create_menu_bar

        root = Mock()
        with patch("views.app_view.tk.Menu") as menu:
            create_menu_bar(root)
        root.event_generate.assert_not_called()
        commands = menu.return_value.add_command.call_args_list
        exit_command = next(call.kwargs["command"] for call in commands
                            if call.kwargs.get("label") == "退出")
        exit_command()
        root.event_generate.assert_called_once_with("<<CloseApp>>")

    def collect_spawned_worker(self, target, args):
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=target, args=(*args, child))
        frames = []
        try:
            process.start()
            child.close()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if parent.poll(0.1):
                    try:
                        frames.append(parent.recv())
                    except EOFError:
                        break
                elif not process.is_alive():
                    break
            process.join(timeout=5)
            self.assertFalse(process.is_alive(), "spawn worker did not finish")
            self.assertEqual(process.exitcode, 0)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            parent.close()
            child.close()
        return frames

    def test_spawned_test_worker_emits_replayable_snapshots(self):
        frames = self.collect_spawned_worker(run_in_test_mode_process, (
            find_match_response_strategy("NoResponse"),
            find_match_search_algorithm("NSGAII"),
            find_match_problem("CDP6"), [],
            {"selected_dynamic": {}, "selected_search": {"seed": 5},
             "selected_problem": dict(PROBLEM_CONFIG)}, None,
        ))
        runtime = {}
        for frame in frames:
            runtime.setdefault(frame["t"], {})[frame["evaluate_times"]] = frame
            self.assertEqual(frame["population"].n, PROBLEM_CONFIG["solution_num"])
        self.assertEqual(sorted(runtime), [0, 1, 2])
        self.assertEqual(len(build_replay_timeline(runtime)), len(frames))

    def test_spawned_experiment_saves_loadable_native_path_results(self):
        with tempfile.TemporaryDirectory(prefix="FlexDMO-约束-") as directory:
            frames = self.collect_spawned_worker(run_experiment_process, (
                directory, "CDP6", "NoResponse", "NSGAII", 1, 10, 1,
                dict(PROBLEM_CONFIG), {}, {"seed": 5}, None,
            ))
            self.assertTrue(any("progress" in frame for frame in frames))
            result_files = [os.path.join(root, name)
                            for root, _, names in os.walk(directory)
                            for name in names if name.endswith(".json")]
            self.assertEqual(len(result_files), 1)
            result = load_test_module_information_results(result_files[0])
            self.assertIsNotNone(result)
            self.assertEqual(sorted(result["runtime_populations"]), [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
