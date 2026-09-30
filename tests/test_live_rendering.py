import unittest
from unittest.mock import patch

from utils.run_executor import (
    listen_pipe,
    queue_latest_chart,
    start_live_chart_pump,
    stop_live_chart_pump,
    take_latest_chart,
)
from views.common.GlobalVar import global_vars
from views.test_module.test_module_handler import (
    on_scale_change,
    update_progress_control,
)


class FakeWidget:
    def __init__(self):
        self.callbacks = []
        self.exists = True

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))
        return len(self.callbacks)

    def winfo_exists(self):
        return self.exists

    def run_next_callback(self):
        _, callback = self.callbacks.pop(0)
        callback()


class FakeScale:
    def __init__(self, run_after_immediately=False):
        self.options = {}
        self.value = None
        self.run_after_immediately = run_after_immediately
        self.command = None

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def winfo_exists(self):
        return True

    def set(self, value):
        self.value = value
        if self.command is not None:
            self.command(str(value))

    def after(self, _delay, callback):
        if self.run_after_immediately:
            callback()


class FakeLabel:
    def __init__(self):
        self.text = ""

    def config(self, **kwargs):
        self.text = kwargs["text"]

    configure = config


class FinishedProcess:
    def is_alive(self):
        return False


class EmptyConnection:
    def __init__(self):
        self.closed = False

    def poll(self, _timeout=None):
        return False

    def close(self):
        self.closed = True


class LiveRenderingTests(unittest.TestCase):
    def setUp(self):
        self.original_state = dict(global_vars["test_module"])
        global_vars["test_module"].clear()

    def tearDown(self):
        global_vars["test_module"].clear()
        global_vars["test_module"].update(self.original_state)

    def test_pending_live_frame_is_coalesced_to_the_latest_snapshot(self):
        first = {"evaluate_times": 100}
        latest = {"evaluate_times": 300}

        queue_latest_chart(first)
        queue_latest_chart(latest)

        self.assertIs(take_latest_chart(), latest)
        self.assertIsNone(take_latest_chart())

    def test_chart_pump_draws_only_latest_frame_and_can_be_stopped(self):
        widget = FakeWidget()
        first = {"evaluate_times": 100}
        latest = {"evaluate_times": 300}

        with patch("utils.run_executor.draw_chart") as draw_chart:
            start_live_chart_pump(widget, refresh_ms=25)
            queue_latest_chart(first)
            queue_latest_chart(latest)
            widget.run_next_callback()

            draw_chart.assert_called_once_with(latest)
            self.assertEqual(
                global_vars["test_module"]["last_live_evaluation"], 300
            )

            stop_live_chart_pump()
            widget.run_next_callback()
            draw_chart.assert_called_once()
            self.assertEqual(widget.callbacks, [])

    def test_replay_slider_uses_snapshot_indexes_for_sparse_evaluations(self):
        scale = FakeScale()
        current_label = FakeLabel()
        total_label = FakeLabel()
        scale.command = lambda value: on_scale_change(
            value,
            current_label,
            total_label,
        )
        first = {"evaluate_times": 200}
        second = {"evaluate_times": 7000}
        global_vars["test_module"]["runtime_populations"] = {
            0: {200: first},
            1: {7000: second},
        }

        with patch(
            "views.test_module.test_module_handler.draw_chart"
        ) as draw_chart:
            update_progress_control(
                scale,
                current_label,
                total_label,
                start_at_end=True,
                render_selected=True,
            )

            self.assertEqual(scale.options["from_"], 0)
            self.assertEqual(scale.options["to"], 1)
            self.assertEqual(scale.value, 1)
            self.assertEqual(current_label.text, "当前评估次数： 7000")
            self.assertEqual(total_label.text, "总评估次数： 7000")
            draw_chart.assert_called_once_with(second)

            on_scale_change("0", current_label, total_label)
            self.assertEqual(current_label.text, "当前评估次数： 200")
            self.assertEqual(draw_chart.call_args_list[-1].args[0], first)

    def test_finished_run_initializes_replay_at_last_snapshot(self):
        scale = FakeScale(run_after_immediately=True)
        current_label = FakeLabel()
        total_label = FakeLabel()
        connection = EmptyConnection()
        global_vars["test_module"].update(
            {
                "scale": scale,
                "current_label": current_label,
                "total_label": total_label,
                "runtime_populations": {0: {200: {"evaluate_times": 200}}},
            }
        )

        with patch(
            "views.test_module.test_module_handler.update_progress_control"
        ) as update_replay:
            listen_pipe(connection, FinishedProcess())

        self.assertTrue(connection.closed)
        update_replay.assert_called_once_with(
            scale,
            current_label,
            total_label,
            start_at_end=True,
            render_selected=True,
        )


if __name__ == "__main__":
    unittest.main()
