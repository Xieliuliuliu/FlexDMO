"""Comparable runs and environment-end measurements, without Qt state."""
import json
from pathlib import Path

from .core import load_frames
from utils.metrics import calculate_IGD


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def comparison_runs(tasks, canceled=lambda: False):
    runs, errors = [], []
    for task in tasks:
        if canceled():
            break
        result = task.get("result", {})
        if task["status"] != "completed" or result.get("partial"):
            continue
        try:
            frames = result.get("frames")
            if frames is None:
                frames = load_frames(Path(result["path"]))
            if not frames:
                raise ValueError("结果没有快照")
            settings = frames[0]["settings"]
            request = task["request"]
            # Problem code, parameters and budget must match. Never combine
            # different decision dimensions or severities merely by name.
            group = canonical([request["records"]["problem"]["name"], request["params"]["problem"],
                               settings.get("code_plugins", {}).get("problem")])
            params = {k: dict(request["params"][k]) for k in ("dynamic", "search")}
            params["search"].pop("seed", None)
            variant = canonical([request["records"]["dynamic"]["name"],
                                 request["records"]["search"]["name"], params,
                                 settings.get("code_plugins", {})])
            ends = {}
            for frame in frames:
                if frame["t"] not in ends or frame["evaluate_times"] > ends[frame["t"]]["evaluate_times"]:
                    ends[frame["t"]] = frame
            points = [(t, float(calculate_IGD(f["population"].get_feasible_objective_matrix(), f["POF"])),
                       sum(i.feasible for i in f["population"]) / len(f["population"]))
                      for t, f in sorted(ends.items())]
            label = request["records"]["dynamic"]["name"] + " / " + request["records"]["search"]["name"]
            runs.append({"task": task, "group": group, "variant": variant, "label": label,
                         "ends": ends, "points": points})
        except Exception as error:
            errors.append(f"任务 {task['id'] + 1}：{error}")
    return runs, errors
