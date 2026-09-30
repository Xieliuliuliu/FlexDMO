import threading
import unittest

from utils.ui_dispatch import (
    dispatch_ui, drain_ui_callbacks, start_ui_dispatch, stop_ui_dispatch,
)


class FakeRoot:
    def __init__(self):
        self.callbacks = []
        self.errors = []

    def after(self, delay, callback):
        if threading.current_thread() is not threading.main_thread():
            raise AssertionError("worker thread accessed Tk")
        self.callbacks.append(callback)

    def winfo_exists(self):
        return True

    def report_callback_exception(self, *error):
        self.errors.append(error)


class UIDispatchTests(unittest.TestCase):
    def setUp(self):
        stop_ui_dispatch()

    def tearDown(self):
        stop_ui_dispatch()

    def test_worker_callback_waits_for_main_thread_pump(self):
        root = FakeRoot()
        threads = []
        start_ui_dispatch(root)
        worker = threading.Thread(target=lambda: dispatch_ui(
            lambda: threads.append(threading.current_thread())))
        worker.start()
        worker.join(timeout=2)
        self.assertEqual(threads, [])
        root.callbacks.pop(0)()
        self.assertEqual(threads, [threading.main_thread()])
        self.assertEqual(root.errors, [])

    def test_callbacks_preserve_order_and_errors_do_not_stop_pump(self):
        root = FakeRoot()
        calls = []
        def fail():
            raise ValueError("test error")
        def enqueue():
            dispatch_ui(lambda: calls.append(1))
            dispatch_ui(fail)
            dispatch_ui(lambda: calls.append(2))
        worker = threading.Thread(target=enqueue)
        worker.start()
        worker.join(timeout=2)
        drain_ui_callbacks(root.report_callback_exception)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(len(root.errors), 1)
        self.assertIs(root.errors[0][0], ValueError)

    def test_stop_discards_pending_callbacks_and_invalidates_pump(self):
        root = FakeRoot()
        calls = []
        start_ui_dispatch(root)
        worker = threading.Thread(target=lambda: dispatch_ui(lambda: calls.append(1)))
        worker.start()
        worker.join(timeout=2)
        stop_ui_dispatch()
        root.callbacks.pop(0)()
        drain_ui_callbacks()
        self.assertEqual(calls, [])
        self.assertEqual(root.callbacks, [])


if __name__ == "__main__":
    unittest.main()
