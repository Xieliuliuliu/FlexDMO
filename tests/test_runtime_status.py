"""Runtime failures, partial history, and manual-save UI regressions."""
import multiprocessing
import unittest
from unittest.mock import Mock, patch

from utils.run_executor import delete_state_in_test_mode, listen_pipe, run_in_test_mode_process
from utils.test_runtime import set_run_status, snapshot_history, test_run_active
from views.common.GlobalVar import global_vars
from views.test_module.test_module_handler import load_selected_result, on_save_button_click, on_stop_button_click


class RuntimeStatusTests(unittest.TestCase):
    def setUp(self):
        self.original = dict(global_vars['test_module'])
        global_vars['test_module'].clear()

    def tearDown(self):
        global_vars['test_module'].clear()
        global_vars['test_module'].update(self.original)

    def test_status_updates_controls(self):
        state = global_vars['test_module']
        state.update(status_label=Mock(), pause_button=Mock(),
                     stop_button=Mock(), manual_save_button=Mock())
        set_run_status('running')
        self.assertTrue(test_run_active())
        state['manual_save_button'].configure.assert_called_with(state='disabled')
        set_run_status('failed', 'FileNotFoundError: missing main.py')
        self.assertFalse(test_run_active())
        self.assertIn('FileNotFoundError', state['status_text'])
        state['manual_save_button'].configure.assert_called_with(state='normal')
        state['pause_button'].configure.assert_called_with(state='disabled')

    def test_cleanup_keeps_partial_history_when_requested(self):
        frame = {'evaluate_times': 20}
        state = global_vars['test_module']
        state.update(runtime_populations={0: {20: frame}}, status_label=Mock())
        delete_state_in_test_mode(clear_history=False)
        self.assertIs(state['runtime_populations'][0][20], frame)
        self.assertIn('status_label', state)
        delete_state_in_test_mode()
        self.assertEqual(state['runtime_populations'], {})

    def test_snapshot_dictionary_is_not_changed_by_new_frames(self):
        state = global_vars['test_module']
        state['runtime_populations'] = {0: {20: {}}}
        copy = snapshot_history()
        state['runtime_populations'][0][30] = {}
        self.assertEqual(list(copy[0]), [20])

    def test_load_does_not_replace_an_active_run(self):
        set_run_status('paused')
        with patch('views.test_module.test_module_handler.messagebox.showinfo'), \
             patch('views.test_module.test_module_handler.load_test_module_information_results') as load:
            self.assertIsNone(load_selected_result('old-result.json'))
        load.assert_not_called()

    def test_cancel_manual_save_does_not_write(self):
        global_vars['test_module']['runtime_populations'] = {0: {20: {}}}
        with patch('views.test_module.test_module_handler.filedialog.askdirectory', return_value=''), \
             patch('views.test_module.test_module_handler.save_test_module_information_results') as save:
            on_save_button_click()
        save.assert_not_called()

    def test_manual_save_uses_selected_directory(self):
        global_vars['test_module']['runtime_populations'] = {0: {20: {}}}
        set_run_status('completed')
        with patch('views.test_module.test_module_handler.filedialog.askdirectory', return_value='/chosen'), \
             patch('views.test_module.test_module_handler.save_test_module_information_results', return_value='/chosen/run.json') as save, \
             patch('views.test_module.test_module_handler.messagebox.showinfo'):
            on_save_button_click()
        save.assert_called_once_with('/chosen')
        self.assertIn('/chosen/run.json', global_vars['test_module']['status_text'])

    def test_stale_listener_cannot_change_new_run_status(self):
        old = Mock()
        old.is_alive.return_value = False
        parent = Mock()
        parent.poll.return_value = False
        state = global_vars['test_module']
        state.update(run_process=object(), run_status='running')
        listen_pipe(parent, old)
        self.assertEqual(state['run_status'], 'running')
        parent.close.assert_called_once()

    def test_terminate_auto_saves_partial_history(self):
        state = global_vars['test_module']
        state.update(runtime_populations={0: {20: {}}}, save_result=Mock())
        state['save_result'].get.return_value = True
        set_run_status('running')
        with patch('views.test_module.test_module_handler.save_test_module_information_results', return_value='/partial.json') as save:
            on_stop_button_click()
        save.assert_called_once_with()
        self.assertEqual(state['run_status'], 'stopped')
        self.assertTrue(state['runtime_populations'])
        self.assertIn('/partial.json', state['status_text'])

    def test_terminate_auto_save_failure_keeps_history_and_reports_it(self):
        state = global_vars['test_module']
        state.update(runtime_populations={0: {20: {}}}, save_result=Mock())
        state['save_result'].get.return_value = True
        set_run_status('running')
        with patch('views.test_module.test_module_handler.save_test_module_information_results', side_effect=OSError('disk full')):
            on_stop_button_click()
        self.assertTrue(state['runtime_populations'])
        self.assertIn('自动保存失败', state['status_text'])
        self.assertIn('disk full', state['status_text'])

    def test_spawned_failure_reports_error_and_exits_nonzero(self):
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=run_in_test_mode_process,
                                  args=({'folder_name': '/missing/FlexDMO/strategy'},
                                        {}, {}, [], {}, None, child))
        try:
            process.start()
            child.close()
            self.assertTrue(parent.poll(15), 'worker failed without notifying parent')
            error = parent.recv()
            self.assertEqual(error['status'], 'error')
            self.assertIn('FileNotFoundError', error['error'])
            process.join(15)
            self.assertFalse(process.is_alive())
            self.assertNotEqual(process.exitcode, 0)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
            child.close()


if __name__ == '__main__':
    unittest.main()
