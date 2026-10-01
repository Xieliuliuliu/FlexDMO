"""Bounded process scheduler shared by the batch UI and integration tests."""
import copy
from datetime import datetime
from pathlib import Path
import queue
import threading
import uuid

from PySide6.QtCore import QObject, QTimer, Signal

from .controller import RunController
from .experiments import experiment_worker, export_reports


class BatchRunner(QObject):
    task_changed = Signal(object)
    state_changed = Signal(str)
    finished = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = []
        self.controllers = {}
        self.active = False
        self.paused = False
        self.canceling = False
        self.exporting = False
        self.directory = None
        self.report_path = None
        self.report_error = None
        self._export_queue = queue.Queue()
        self.export_timer = QTimer(self)
        self.export_timer.setInterval(50)
        self.export_timer.timeout.connect(self._finish_export)

    def start(self, tasks, parallel, directory=None, save_results=False):
        if self.active:
            raise ValueError("批量实验仍在运行或保存结果")
        if not tasks:
            raise ValueError("请先生成实验任务")
        if not 1 <= int(parallel) <= 8:
            raise ValueError("并行数必须为 1–8")
        if save_results and not directory:
            raise ValueError("请选择实验保存目录")
        self.tasks = copy.deepcopy(tasks)
        self.parallel = int(parallel)
        self.save_results = bool(save_results)
        self.directory = None
        if self.save_results:
            self.directory = Path(directory) / (datetime.now().strftime("batch_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])
            self.directory.mkdir(parents=True, exist_ok=False)
        self.active = True
        self.paused = False
        self.canceling = False
        self.report_path = None
        self.report_error = None
        for task in self.tasks:
            task.update(status="pending", progress=0)
            task.pop("result", None)
            task.pop("error", None)
            task["request"].pop("output_path", None)
            if self.save_results:
                task["request"]["output_path"] = str(self.directory / f"task_{task['id'] + 1:05d}_seed{task['seed']}.json")
        self.state_changed.emit("running")
        self._launch_next()

    def _launch_next(self):
        if not self.active or self.exporting:
            return
        if not self.paused and not self.canceling:
            for task in self.tasks:
                if len(self.controllers) >= self.parallel:
                    break
                if task["status"] != "pending":
                    continue
                controller = RunController(self)
                self.controllers[task["id"]] = controller
                controller.message_received.connect(lambda message, t=task: self._message(t, message))
                controller.error_received.connect(lambda message, t=task: self._error(t, message))
                controller.status_changed.connect(lambda state, t=task: self._state(t, state))
                controller.finished.connect(lambda state, t=task: self._done(t, state))
                try:
                    controller.start(task["request"], target=experiment_worker)
                except Exception as error:
                    task.update(status="failed", error=str(error))
                    controller.shutdown()
                    controller.deleteLater()
                    self.controllers.pop(task["id"])
                    self.task_changed.emit(task)
        if not self.controllers and not any(t["status"] == "pending" for t in self.tasks):
            self._export()

    def _message(self, task, message):
        if message.get("kind") == "progress":
            task["progress"] = message["progress"]
        elif message.get("kind") == "result":
            task["result"] = message
        self.task_changed.emit(task)

    def _error(self, task, message):
        task["error"] = message
        self.task_changed.emit(task)

    def _state(self, task, state):
        if state in ("running", "paused", "stopping"):
            task["status"] = state
            self.task_changed.emit(task)

    def _done(self, task, state):
        result = task.get("result", {})
        has_result = bool(result.get("path") or result.get("frames"))
        if state in ("completed", "stopped") and has_result and not result.get("partial") and not task.get("error"):
            # A complete result may already be queued when cancel is clicked.
            # Keep that successful run instead of relabeling it as partial.
            task.update(status="completed", progress=100)
        elif self.canceling or state == "stopped" or result.get("partial"):
            task["status"] = "canceled"
        elif state == "completed" and has_result:
            task.update(status="completed", progress=100)
        else:
            task["status"] = "failed"
            task.setdefault("error", "任务退出但没有完整结果")
        controller = self.controllers.pop(task["id"])
        controller.deleteLater()
        self.task_changed.emit(task)
        self._launch_next()

    def pause(self):
        if self.active and not self.exporting and not self.canceling:
            self.paused = True
            for controller in self.controllers.values():
                controller.pause()
            self.state_changed.emit("paused")

    def resume(self):
        if self.active and self.paused:
            self.paused = False
            for controller in self.controllers.values():
                controller.resume()
            self.state_changed.emit("running")
            self._launch_next()

    def cancel(self):
        if not self.active or self.exporting:
            return
        self.canceling = True
        self.paused = False
        for task in self.tasks:
            if task["status"] == "pending":
                task["status"] = "canceled"
                self.task_changed.emit(task)
        for controller in self.controllers.values():
            controller.stop()
        self.state_changed.emit("stopping")
        self._launch_next()

    def export_statistics(self, directory):
        if self.active or not self.tasks:
            raise ValueError("请等待实验结束后再导出统计")
        self.directory = Path(directory) / (datetime.now().strftime("summary_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])
        self.directory.mkdir(parents=True, exist_ok=False)
        self.report_error = None
        self.active = True
        self._export(force=True)

    def _export(self, force=False):
        if not self.save_results and not force:
            self._finish_batch()
            return
        self.exporting = True
        self.state_changed.emit("exporting")
        snapshot = copy.deepcopy([{**task, "result": {key: value for key, value in task.get("result", {}).items()
                                                     if key != "frames"}} for task in self.tasks])
        directory = self.directory
        inbox = self._export_queue
        def worker():
            try:
                inbox.put((str(export_reports(directory, snapshot)), None))
            except Exception as error:
                inbox.put((None, str(error)))
        threading.Thread(target=worker, name="Qt-Batch-Reports", daemon=True).start()
        self.export_timer.start()

    def _finish_export(self):
        try:
            self.report_path, self.report_error = self._export_queue.get_nowait()
        except queue.Empty:
            return
        self.export_timer.stop()
        self._finish_batch()

    def _finish_batch(self):
        self.active = False
        self.exporting = False
        failed = self.report_error or any(t["status"] == "failed" for t in self.tasks)
        status = "failed" if failed else "canceled" if self.canceling else "completed"
        self.state_changed.emit(status)
        self.finished.emit(status)

    def shutdown(self):
        self.active = False
        self.export_timer.stop()
        for controller in self.controllers.values():
            controller.shutdown()
            controller.deleteLater()
        self.controllers.clear()
