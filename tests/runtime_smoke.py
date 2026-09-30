"""Desktop-only checks for visible failures, pause/resume and partial replay."""
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_smoke():
    import main
    from utils.run_executor import run_in_test_mode
    from views.common.GlobalVar import global_vars
    from views.test_module.test_module_handler import (
        load_selected_result, on_continue_button_click, on_pause_button_click,
        on_save_button_click, on_stop_button_click,
    )

    errors, completed = [], []
    original_mainloop = tk.Tk.mainloop
    with tempfile.TemporaryDirectory(prefix='FlexDMO-runtime-') as directory:
        def smoke_mainloop(root, *args, **kwargs):
            deadline = time.monotonic() + 40
            state = global_vars['test_module']

            def fail(kind, error, traceback):
                errors.append(error)
                root.event_generate('<<CloseApp>>')
            root.report_callback_exception = fail

            def start_failure():
                root.geometry('720x560')
                run_in_test_mode({'folder_name': '/missing/FlexDMO/strategy'}, {}, {}, [], {})
                root.after(20, check_failure)

            def check_failure():
                if state.get('run_status') != 'failed':
                    assert time.monotonic() < deadline, 'failure status never arrived'
                    root.after(20, check_failure)
                    return
                assert 'FileNotFoundError' in state['status_label'].cget('text')
                assert state['current_process'].exitcode != 0
                assert str(state['scale'].cget('state')) == 'normal'
                state['selected_dynamic'].set('D-NSGA-II-B')
                state['selected_search'].set('NSGAII')
                state['selected_problem'].set('CDP6')
                state['runtime_config'] = {
                    'selected_dynamic': {}, 'selected_search': {'seed': 7},
                    'selected_problem': {'decision_num': 4, 'solution_num': 20,
                                         'n': 10, 'tau': 10, 'total_evaluate_time': 500},
                }
                on_continue_button_click()
                root.after(20, check_live)

            def check_live():
                if not state.get('runtime_populations'):
                    assert time.monotonic() < deadline, 'no live frames arrived'
                    root.after(20, check_live)
                    return
                assert state['current_process'].is_alive()
                on_pause_button_click()
                assert state['run_status'] == 'paused'
                process = state['current_process']
                state['selected_module'].set('Experiment Module')
                state['selected_module'].set('Test Module')
                assert state['current_process'] is process
                root.after(100, resume)

            def resume():
                process = state['current_process']
                on_continue_button_click()
                assert state['current_process'] is process
                assert state['run_status'] == 'running'
                root.after(50, stop_and_save)

            def stop_and_save():
                process = state['current_process']
                on_stop_button_click()
                assert not process.is_alive()
                assert state['run_status'] == 'stopped'
                assert state['runtime_populations']
                assert state['replay_timeline']
                with patch('views.test_module.test_module_handler.filedialog.askdirectory', return_value=directory), \
                     patch('views.test_module.test_module_handler.messagebox.showinfo'):
                    on_save_button_click()
                files = list(Path(directory).glob('*.json'))
                assert len(files) == 1
                assert load_selected_result(str(files[0])) is not None
                assert state['run_status'] == 'replay'
                completed.append(True)
                print('RUNTIME_SMOKE_OK: visible worker failure, pause/resume, terminate, partial save/replay', flush=True)
                root.event_generate('<<CloseApp>>')

            root.after(300, start_failure)
            original_mainloop(root, *args, **kwargs)

        with patch.object(tk.Tk, 'mainloop', smoke_mainloop):
            main.main()
    if errors:
        raise RuntimeError(errors)
    assert completed, 'runtime smoke did not complete'


if __name__ == '__main__':
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn')
    run_smoke()
