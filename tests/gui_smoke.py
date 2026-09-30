"""Opt-in desktop smoke test: window, live worker, JSON replay and experiment.

Run with `.venv/bin/python tests/gui_smoke.py`; a real desktop is required.
"""
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_smoke():
    import main
    from views.common.GlobalVar import global_vars
    from views.test_module.test_module_handler import (
        load_selected_result, on_continue_button_click, on_scale_change,
        on_save_button_click, update_progress_control,
    )
    from utils.result_io import save_test_module_information_results
    from utils.run_executor import delete_state_in_test_mode
    from utils.run_executor_for_experiment import begin_running
    from views.components.task_progress import TaskProgress

    errors = []
    completed = []
    state_canvas = []
    original_mainloop = tk.Tk.mainloop
    config = {"decision_num": 4, "n": 10, "tau": 2,
              "solution_num": 20, "total_evaluate_time": 3}

    with tempfile.TemporaryDirectory(prefix="FlexDMO-GUI-约束-") as directory:
        def smoke_mainloop(root, *args, **kwargs):
            deadline = time.monotonic() + 60

            def finish(error=None):
                if error is not None:
                    errors.append(error)
                delete_state_in_test_mode()
                root.event_generate("<<CloseApp>>")

            def callback_error(exception, value, traceback):
                finish(value)

            root.report_callback_exception = callback_error

            def start():
                root.geometry('720x560')
                state = global_vars["test_module"]
                state["selected_dynamic"].set("D-NSGA-II-B")
                state["selected_search"].set("NSGAII")
                state["selected_problem"].set("CDP6")
                state["runtime_config"] = {
                    "selected_dynamic": {}, "selected_search": {"seed": 5},
                    "selected_problem": dict(config),
                }
                on_continue_button_click()
                root.after(100, check_test)

            def check_test():
                state = global_vars["test_module"]
                if time.monotonic() > deadline:
                    raise TimeoutError("GUI optimization/replay did not finish")
                if not state.get("replay_timeline"):
                    root.after(100, check_test)
                    return
                assert state["current_process"].exitcode == 0
                assert state['run_status'] == 'completed', state.get('status_text')
                assert state['workspace'].panels[2].winfo_viewable(), 'live chart tab was hidden'
                assert sorted(state["runtime_populations"]) == [0, 1, 2]
                assert state["canvas"].figure.axes, "no live chart was rendered"
                state_canvas.append(state['canvas'])
                saved = save_test_module_information_results(directory)
                with patch('views.test_module.test_module_handler.filedialog.askdirectory', return_value=directory), \
                     patch('views.test_module.test_module_handler.messagebox.showinfo'):
                    on_save_button_click()
                assert len(list(Path(directory).glob('*.json'))) == 2
                root.geometry('1300x760')
                assert load_selected_result(saved) is not None
                update_progress_control(state["scale"], state["current_label"],
                                        state["total_label"], render_selected=True)
                for index in (0, len(state["replay_timeline"]) - 1):
                    on_scale_change(str(index), state["current_label"], state["total_label"])
                    expected = state["replay_timeline"][index][0]
                    assert state["current_label"].cget("text") == f"当前评估次数： {expected}"
                delete_state_in_test_mode()
                state["selected_module"].set("Experiment Module")
                experiment = global_vars["experiment_module"]
                assert os.path.isabs(experiment["save_path"].get())
                experiment["save_path"].set(directory)
                card = TaskProgress(experiment["run_frame"], "CDP6", "NoResponse",
                                    "NSGAII", 1, 10, 1, 1,
                                    problem_config=config, search_config={"seed": 5})
                begin_running(card, on_complete=lambda task: completed.append(task))
                root.after(100, lambda: check_experiment(card))

            def check_experiment(card):
                if time.monotonic() > deadline:
                    raise TimeoutError("GUI experiment did not finish")
                if not completed:
                    root.after(100, lambda: check_experiment(card))
                    return
                assert card.status_var.get() == "completed", card.status_var.get()
                assert list(Path(directory).glob("NoResponse_NSGA2/CDP6/*.json"))
                global_vars["test_module"]["selected_module"].set("Test Module")
                assert global_vars['test_module']['selected_problem'].get() == 'CDP6'
                assert global_vars['test_module']['canvas'] is state_canvas[0]
                print("GUI_SMOKE_OK: live worker, manual save, replay, experiment, retained module state", flush=True)
                finish()

            root.after(500, start)
            original_mainloop(root, *args, **kwargs)

        with patch.object(tk.Tk, "mainloop", smoke_mainloop):
            main.main()
    if errors:
        raise RuntimeError(errors)
    if not completed:
        raise RuntimeError("GUI smoke test did not reach completion")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    multiprocessing.set_start_method("spawn")
    run_smoke()
