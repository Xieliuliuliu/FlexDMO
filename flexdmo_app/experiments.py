"""Experiment planning, worker result persistence, and reproducible statistics."""
import copy
import csv
from itertools import product
import json
import math
from pathlib import Path
import statistics
import time
import traceback

import numpy as np

from .core import defaults, history_policy, parse_parameters, registered_class, result_settings, save_frames
from utils.metrics import calculate_MIGD, calculate_MGD, calculate_MHV


def parse_sweep(text):
    result = []
    for part in text.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            raise ValueError("扫描值不能为空，例如 5,10 或 5:15:5")
        try:
            if ":" in part:
                values = [int(v) for v in part.split(":")]
                if len(values) not in (2, 3):
                    raise ValueError()
                start, end = values[:2]
                step = values[2] if len(values) == 3 else 1
                if step <= 0 or end < start or (end - start) // step > 1000:
                    raise ValueError()
                expanded = range(start, end + 1, step)
            else:
                expanded = [int(part)]
            for value in expanded:
                if value <= 0:
                    raise ValueError()
                if value not in result:
                    result.append(value)
        except ValueError:
            raise ValueError("扫描值必须为正整数，范围格式为 起点:终点:步长") from None
    return result


def build_plan(selection, shared, profiles=None):
    profiles = profiles or {}
    policy = history_policy(shared.get("history_policy", "full"))
    if any(not selection.get(kind) for kind in ("dynamic", "search", "problem")):
        raise ValueError("请至少选择一个动态策略、搜索算法和测试问题")
    taus, severities = parse_sweep(shared["tau"]), parse_sweep(shared["n"])
    repeats = int(shared["repeats"])
    seed = int(shared["seed"])
    count = math.prod(len(selection[kind]) for kind in selection) * len(taus) * len(severities) * repeats
    if repeats < 1 or not 0 <= seed <= seed + repeats - 1 < 2**32:
        raise ValueError("重复次数或随机种子范围无效")
    if count > 10000:
        raise ValueError(f"将生成 {count:,} 个任务，超过本轮 10,000 上限，请缩小扫描范围")
    tasks = []
    templates = {(kind, record["folder_name"]): defaults(record)
                 for kind, entries in selection.items() for record in entries}
    for dynamic, search, problem, tau, n, repeat in product(
            selection["dynamic"], selection["search"], selection["problem"], taus, severities, range(repeats)):
        selected = {"dynamic": dynamic, "search": search, "problem": problem}
        params = {}
        for kind, record in selected.items():
            template = templates[(kind, record["folder_name"])]
            values = dict(template)
            values.update(profiles.get((kind, record["folder_name"]), {}))
            if kind == "problem":
                for key in ("decision_num", "solution_num", "total_evaluate_time"):
                    if key in values:
                        values[key] = shared[key]
                values.update(tau=tau, n=n)
            if kind == "search":
                # Algorithm accepts seed through **args, even if an old config
                # doesn't expose it. Same repeat uses the same seed for fairness.
                values["seed"] = seed + repeat
                template = dict(template, seed=1)
            params[kind] = parse_parameters(values, template, record)
        tasks.append({"id": len(tasks), "repeat": repeat + 1, "seed": seed + repeat,
                      "tau": tau, "n": n, "status": "pending", "progress": 0,
                      "request": {"records": copy.deepcopy(selected), "params": params, "history_policy": policy}})
    return tasks


def history_frames(algorithm, problem, policy="full"):
    history_policy(policy)
    for t, snapshots in sorted(algorithm.history["runtime"].items()):
        pof, pos = problem.get_pareto_front(t), problem.get_pareto_set(t)
        retained = {max(snapshots): snapshots[max(snapshots)]} if policy == "environment" and snapshots else snapshots
        for count, population in sorted(retained.items()):
            yield {"settings": algorithm.history["settings"], "population": population,
                   "t": t, "evaluate_times": count, "POF": pof, "POS": pos,
                   "bound": [population.xl, population.xu],
                   "objective_constraints": problem.get_objective_constraints(t)}


def summarize_frames(frames):
    runtime = {}
    for frame in frames:
        runtime.setdefault(frame["t"], {})[frame["evaluate_times"]] = frame
    latest = [group[max(group)] for group in runtime.values()]
    feasibility = np.mean([sum(i.feasible for i in f["population"]) / len(f["population"]) for f in latest])
    # HV uses the repository convention: PF.max(axis=0) + 0.5. The existing
    # implementation supports only two objectives; never invent a 3D value.
    hv = float(calculate_MHV(runtime)) if np.asarray(frames[0]["POF"]).shape[1] == 2 else None
    return {"MIGD": float(calculate_MIGD(runtime)), "MGD": float(calculate_MGD(runtime)),
            "MHV": hv, "feasibility": float(feasibility), "environments": len(latest)}


class ProgressPipe:
    def __init__(self, pipe):
        self.pipe = pipe
        self.last = None
        self.problem = None

    def send(self, message):
        value = message.get("progress")
        if self.problem is not None:
            total = self.problem.initial_convergence + self.problem.change_each_evaluations * self.problem.total_change_time
            value = 100 * self.problem.evaluate_time / total
        marker = min(99, int(value))
        if marker != self.last:
            self.last = marker
            self.pipe.send({"kind": "progress", "progress": marker})


def experiment_worker(request, state, pipe):
    started = time.monotonic()
    try:
        policy = history_policy(request.get("history_policy", "full"))
        progress_pipe = ProgressPipe(pipe)
        algorithm = registered_class(request["records"]["search"])(
            **request["params"]["search"], state=state, pip=progress_pipe, mode="experiment")
        strategy = registered_class(request["records"]["dynamic"])(**request["params"]["dynamic"])
        problem = registered_class(request["records"]["problem"])(**request["params"]["problem"])
        progress_pipe.problem = problem
        algorithm.optimize(problem, strategy)
        if (request["records"]["search"].get("format") == "python-file"
                and not problem.is_ended() and state.value != "stop"):
            raise RuntimeError("自定义算法提前返回，尚未完成环境/评价预算；完整 optimize 循环需运行至 problem.is_ended()")
        partial = state.value == "stop" or not problem.is_ended()
        if algorithm.history["settings"] is not None:
            algorithm.history["settings"] = result_settings(algorithm.history["settings"], request)
        frames = list(history_frames(algorithm, problem, policy))
        result = {"kind": "result", "partial": partial, "seconds": time.monotonic() - started}
        if frames:
            result.update(metrics=summarize_frames(frames), snapshots=len(frames))
            if request.get("output_path"):
                path = Path(request["output_path"])
                save_frames(path, frames)
                result["path"] = str(path)
            else:
                result["frames"] = frames
        pipe.send(result)
    except Exception as error:
        try:
            pipe.send({"kind": "error", "message": str(error), "traceback": traceback.format_exc()})
        except OSError:
            pass
        raise
    finally:
        pipe.close()


def task_row(task):
    record = task["request"]["records"]
    result = task.get("result", {})
    return {"任务": task["id"] + 1, "问题": record["problem"]["name"],
            "动态策略": record["dynamic"]["name"], "搜索算法": record["search"]["name"],
            "tau": task["tau"], "n": task["n"], "重复": task["repeat"], "seed": task["seed"],
            "状态": task["status"], **{k: result.get("metrics", {}).get(k) for k in
                ("MIGD", "MGD", "MHV", "feasibility")}, "秒": result.get("seconds"),
            "结果文件": result.get("path", ""), "错误": task.get("error", "")}


def grouped_statistics(tasks):
    groups = {}
    for task in tasks:
        row = task_row(task)
        params = copy.deepcopy(task["request"]["params"])
        params["search"].pop("seed", None)
        configuration = json.dumps(params, sort_keys=True, ensure_ascii=False, allow_nan=False)
        key = tuple(row[k] for k in ("问题", "动态策略", "搜索算法", "tau", "n")) + (configuration,)
        groups.setdefault(key, []).append((task, row))
    output = []
    for key, entries in groups.items():
        row = dict(zip(("问题", "动态策略", "搜索算法", "tau", "n", "参数配置"), key))
        complete = [entry for task, entry in entries if task["status"] == "completed"
                    and not task.get("result", {}).get("partial")]
        row.update(计划次数=len(entries), 完成次数=len(complete))
        for metric in ("MIGD", "MGD", "MHV", "feasibility"):
            values = [entry[metric] for entry in complete if entry.get(metric) is not None]
            finite = [value for value in values if math.isfinite(value)]
            # Infinity means missing feasible solutions, not an excellent score;
            # do not silently omit those runs from the reported mean.
            row[metric + "均值"] = statistics.mean(values) if values else None
            row[metric + "标准差"] = (statistics.stdev(values) if len(values) > 1 and len(finite) == len(values)
                                     else 0.0 if len(values) == 1 and finite else None)
        output.append(row)
    return output


def export_reports(directory, tasks):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rows, groups = [task_row(t) for t in tasks], grouped_statistics(tasks)
    for filename, entries in (("runs.csv", rows), ("summary.csv", groups)):
        if entries:
            with (directory / filename).open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=list(entries[0]))
                writer.writeheader()
                writer.writerows(entries)
    from openpyxl import Workbook
    book = Workbook()
    for sheet, entries in ((book.active, rows), (book.create_sheet("汇总统计"), groups)):
        sheet.title = "逐次结果" if sheet is book.active else "汇总统计"
        if entries:
            sheet.append(list(entries[0]))
            for entry in entries:
                # Keep infinity explicit; never write a misleading zero to Excel.
                sheet.append([str(v) if isinstance(v, float) and not math.isfinite(v) else v for v in entry.values()])
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(45, max(12, max(len(str(c.value or "")) for c in column) + 2))
    book.save(directory / "statistics.xlsx")
    # Portable plan stores names/configs, not machine-specific module paths.
    plan = [{"id": t["id"], "status": t["status"], "repeat": t["repeat"], "seed": t["seed"],
             "history_policy": t["request"].get("history_policy", "full"),
             "tau": t["tau"], "n": t["n"], "components": {k: r["name"] for k, r in t["request"]["records"].items()},
             "params": t["request"]["params"], "result": task_row(t)} for t in tasks]
    def portable(value):
        if isinstance(value, dict):
            return {key: portable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [portable(item) for item in value]
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    (directory / "manifest.json").write_text(json.dumps(portable(plan), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return directory / "statistics.xlsx"
