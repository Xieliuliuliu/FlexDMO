"""Own exactly one spawned optimizer. Never touch widgets from its reader."""
import multiprocessing
import queue
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from .core import RunState, optimize_worker


class RunController(QObject):
    frame_received = Signal(object)
    message_received = Signal(object)
    status_changed = Signal(str)
    error_received = Signal(str)
    finished = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.state = None
        self.inbox = None
        self.cancel_reader = None
        self.reader = None
        self.status = "idle"
        self.error = False
        self.stop_deadline = None
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._drain)

    @property
    def active(self):
        return self.process is not None

    def _status(self, value):
        self.status = value
        self.status_changed.emit(value)

    def start(self, request, target=optimize_worker):
        if self.active:
            raise RuntimeError("已有运行中的任务")
        context = multiprocessing.get_context("spawn")
        self.state = RunState(context.Value("i", 0))
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=target, args=(request, self.state, sender),
                                  name="FlexDMO-Qt-Optimizer")
        try:
            process.start()
        except Exception:
            receiver.close()
            sender.close()
            self.state = None
            raise
        sender.close()  # Essential for EOF on worker completion/failure.
        self.process = process
        self.inbox = queue.Queue(maxsize=32)
        self.cancel_reader = threading.Event()
        self.error = False
        self.stop_deadline = None
        self.reader = threading.Thread(target=self._receive,
                                       args=(receiver, self.inbox, self.cancel_reader), daemon=True)
        self.reader.start()
        self._status("running")
        self.timer.start()

    @staticmethod
    def _receive(receiver, inbox, cancel):
        def put(value):
            while not cancel.is_set():
                try:
                    inbox.put(value, timeout=0.1)
                    return True
                except queue.Full:
                    continue
            return False
        try:
            while not cancel.is_set():
                if not put(receiver.recv()):
                    break
        except EOFError:
            pass
        except Exception as error:
            put({"kind": "error", "message": f"结果通道异常：{error}"})
        finally:
            receiver.close()
            put({"kind": "eof"})

    def _drain(self):
        if not self.active:
            return
        # Bound work per GUI tick; the reader applies back-pressure, never drops
        # snapshots. The view redraws only the latest frame independently.
        for _ in range(8):
            try:
                message = self.inbox.get_nowait()
            except queue.Empty:
                break
            if message.get("kind") == "error":
                self.error = True
                self.error_received.emit(message.get("traceback") or message["message"])
            elif message.get("kind") == "eof":
                self._saw_eof = True
            elif "population" in message:
                self.frame_received.emit(message)
            else:
                self.message_received.emit(message)
        if self.stop_deadline is not None and time.monotonic() >= self.stop_deadline:
            if self.process.is_alive():
                self.process.terminate()
            self.stop_deadline = None
        if getattr(self, "_saw_eof", False) and not self.process.is_alive() and self.inbox.empty():
            stopped = self.status == "stopping"
            status = "stopped" if stopped else ("failed" if self.error or self.process.exitcode else "completed")
            self.shutdown()
            self._status(status)
            self.finished.emit(status)

    def pause(self):
        if self.active and self.status == "running":
            self.state.value = "pause"
            self._status("paused")

    def resume(self):
        if self.active and self.status == "paused":
            self.state.value = "running"
            self._status("running")

    def stop(self):
        if self.active:
            self.state.value = "stop"
            self.stop_deadline = time.monotonic() + 2
            self._status("stopping")

    def shutdown(self):
        self.timer.stop()
        if self.cancel_reader:
            self.cancel_reader.set()
        if self.process:
            if self.process.is_alive():
                self.state.value = "stop"
                self.process.terminate()
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            self.process.close()
        if self.reader:
            self.reader.join(timeout=0.2)
        self.process = None
        self.state = None
        self.inbox = None
        self.cancel_reader = None
        self.reader = None
        self._saw_eof = False
