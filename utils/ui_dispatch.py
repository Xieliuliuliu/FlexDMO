"""Deliver worker-thread UI updates without calling Tcl/Tk from those threads."""
from queue import Empty, SimpleQueue
import sys
import threading


_callbacks = SimpleQueue()
_pump_token = 0


def dispatch_ui(callback):
    if threading.current_thread() is threading.main_thread():
        callback()
    else:
        _callbacks.put(callback)


def drain_ui_callbacks(on_error=None, limit=100):
    """Called only on the UI thread; cap work to keep drawing responsive."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("UI callbacks must be drained on the main thread")
    for _ in range(limit):
        try:
            callback = _callbacks.get_nowait()
        except Empty:
            break
        try:
            callback()
        except Exception:
            if on_error is None:
                raise
            on_error(*sys.exc_info())


def start_ui_dispatch(root, interval_ms=20):
    global _pump_token
    _pump_token += 1
    token = _pump_token

    def pump():
        if token != _pump_token or not root.winfo_exists():
            return
        drain_ui_callbacks(root.report_callback_exception)
        if token == _pump_token and root.winfo_exists():
            root.after(interval_ms, pump)

    root.after(interval_ms, pump)


def stop_ui_dispatch():
    global _pump_token
    _pump_token += 1
    while True:
        try:
            _callbacks.get_nowait()
        except Empty:
            break
