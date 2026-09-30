"""Small shared helpers for test-run status and replay history ownership."""
import threading

from views.common.GlobalVar import global_vars


history_lock = threading.RLock()
ACTIVE_STATUSES = {"starting", "running", "paused"}


def test_run_active():
    state = global_vars["test_module"]
    process = state.get("current_process")
    return state.get("run_status") in ACTIVE_STATUSES or bool(
        process is not None and process.is_alive()
    )


def set_run_status(status, detail=None):
    """Update widgets only on the Tk main thread (or dispatch there first)."""
    state = global_vars["test_module"]
    state["run_status"] = status
    messages = {
        "idle": "就绪：选择算法和问题后开始运行",
        "starting": "正在启动优化进程…",
        "running": "运行中：图表实时更新，结束后可拖动时间轴回放",
        "paused": "已请求暂停：点击开始 / 继续恢复运行",
        "completed": "运行完成：可保存结果或拖动时间轴回放",
        "stopped": "已终止：已收到的数据仍可保存和回放",
        "failed": "运行失败",
        "replay": "回放模式：拖动时间轴查看历史快照",
    }
    state["status_text"] = messages.get(status, status) + (
        f" · {detail}" if detail else ""
    )
    label = state.get("status_label")
    if label is not None:
        label.configure(text=state["status_text"])
    active = status in ACTIVE_STATUSES
    for key in ("pause_button", "stop_button"):
        widget = state.get(key)
        if widget is not None:
            widget.configure(state="normal" if active else "disabled")
    save_button = state.get("manual_save_button")
    if save_button is not None:
        save_button.configure(state="disabled" if active else "normal")


def snapshot_history():
    """Copy dictionary topology; received snapshots themselves are immutable."""
    with history_lock:
        return {t: dict(frames) for t, frames in
                global_vars["test_module"].get("runtime_populations", {}).items()}
