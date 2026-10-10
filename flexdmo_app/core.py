"""UI-independent bridge to the existing algorithms and JSON results."""
import importlib
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import traceback

import numpy as np

from components.Population import Population
from utils import information_parser as catalog
from .dependencies import IMPORTS, check_dependencies, missing_dependency

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("dynamic", "search", "problem")
GETTERS = (catalog.get_all_dynamic_strategy, catalog.get_all_search_algorithm,
           catalog.get_all_problem)
PARAM_LABELS = {
    "seed": "随机种子", "decision_num": "决策变量数", "n": "环境变化强度",
    "tau": "变化间隔（代）", "total_evaluate_time": "环境总数",
    "solution_num": "种群规模", "neighbor_size": "邻域大小",
    "delta": "邻域选择概率", "max_replacements": "最大替换数量",
    "differential_weight": "差分权重", "proM": "变异系数",
    "disM": "变异分布指数", "proC": "交叉概率", "disC": "交叉分布指数",
    "replacement_rate": "替换比例", "mutation_probability": "变异概率",
    "distribution_index": "分布指数", "history_length": "历史长度",
    "cluster_num": "聚类数量", "weak_learners": "弱学习器数量",
    "random_multiplier": "随机补充倍数",
    "key_points": "关键点数量", "regularization": "正则化系数",
    "predicted_fraction": "预测个体比例", "mutation_fraction": "变异个体比例",
    "noise_scale": "扰动尺度", "ar_order": "自回归阶数",
    "covariance_regularization": "协方差正则化", "u": "代表个体数量",
    "hidden_size": "隐藏层大小", "dropout": "随机失活概率", "lr": "学习率",
    "K": "局部模型数量",
    "random_fraction": "随机补充比例",
}


def records(errors=None):
    result = dict(zip(KINDS, (getter() for getter in GETTERS)))
    from .components import discover_plugins
    plugins, plugin_errors = discover_plugins()
    if errors is not None:
        errors.extend(plugin_errors)
    for kind, entries in plugins.items():
        existing = {record["name"] for record in result[kind]}
        for record in entries:
            if record["name"] in existing:
                if errors is not None:
                    errors.append(f"{record['folder_name']}：名称 {record['name']} 与现有同类算法重复；请修改 NAME")
                continue
            result[kind].append(record)
            existing.add(record["name"])
    for entries in result.values():
        for record in entries:
            if record.get("format") == "python-file":
                continue
            info_path = Path(record.get("info_path", Path(record["folder_name"]) / "info.json"))
            info = json.loads(info_path.read_text(encoding="utf-8"))
            labels = info.get("parameter_labels", {})
            record["parameter_labels"] = labels if isinstance(labels, dict) else {}
            # Built-in components can declare types just like code plugins.
            # Their constructor owns the numeric domain; a shared parameter
            # name must not force the same positive-only domain on every method.
            specs = info.get("parameter_specs", {})
            if isinstance(specs, dict):
                typed = {key: spec for key, spec in specs.items()
                         if isinstance(spec, dict) and spec.get("type")
                         in {"int", "float", "bool", "str", "list", "dict", "tuple"}}
                if typed:
                    record["parameter_specs"] = typed
            if isinstance(info.get("publication_type"), str):
                record["publication_type"] = info["publication_type"]
    return result


def parameter_label(record, key):
    return str(record.get("parameter_labels", {}).get(key, PARAM_LABELS.get(key, key)))


def defaults(record):
    if record.get("format") == "python-file":
        import copy
        return copy.deepcopy(record["defaults"])
    path = Path(record.get("config_path", Path(record["folder_name"]) / "config.json"))
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registered_class(record):
    check_dependencies(record)
    try:
        if record.get("format") == "python-file":
            from .plugin_runtime import load_code_class
            return load_code_class(record)
        if record.get("format") == "benchmark-file":
            from problems.benchmark import load_benchmark_class
            # 只允许注册表中的系列源码，不信任结果文件提供的任意模块路径。
            source = Path(record["folder_name"]).resolve()
            expected = ROOT / "problems" / "benchmark" / record["family"] / (record["class_name"] + ".py")
            if source != expected.resolve():
                raise ValueError("Benchmark 源码不在对应系列注册目录中")
            return load_benchmark_class(record["class_name"])
        # Only load modules from the repository's discovered registry, never a
        # path supplied by a result file. Preserve relative-import support.
        folder = Path(record["folder_name"]).resolve()
        module_name = ".".join(folder.relative_to(ROOT).parts) + ".main"
        return getattr(importlib.import_module(module_name), folder.name)
    except ModuleNotFoundError as error:
        if error.name in IMPORTS.values():
            raise missing_dependency(record, error.name) from error
        raise


def parameter_text(value, spec=None):
    if value is None:
        return "" if (spec or {}).get("required") else "None"
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return str(value)


def _typed_parameter(raw, default, spec, label):
    if raw is None or isinstance(raw, str) and raw.strip().lower() in ("", "none", "null"):
        if spec.get("nullable") and (not spec.get("required") or raw not in (None, "")):
            return None
        if default is None:
            raise ValueError(f"{label}：请填写{'必填' if spec.get('required') else ''}参数")
    kind = spec["type"]
    try:
        if kind == "bool":
            if str(raw).strip().lower() not in ("true", "false"):
                raise ValueError()
            value = str(raw).strip().lower() == "true"
        elif kind == "int":
            if isinstance(raw, bool):
                raise ValueError()
            # Never round a large integer through IEEE double precision.
            value = int(str(raw).strip())
        elif kind == "float":
            if isinstance(raw, bool):
                raise ValueError()
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError()
        elif kind in ("list", "dict", "tuple"):
            value = json.loads(raw) if isinstance(raw, str) else raw
            expected = dict if kind == "dict" else list
            if kind == "tuple" and isinstance(value, tuple):
                value = list(value)
            if not isinstance(value, expected):
                raise ValueError()
            json.dumps(value, allow_nan=False)
            if kind == "tuple":
                value = tuple(value)
        else:
            value = str(raw)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"{label}：请输入有效的 {kind} 参数；列表/字典使用 JSON 格式") from None
    if "choices" in spec and value not in spec["choices"]:
        raise ValueError(f"{label}：请选择 {spec['choices']}")
    return value


def parse_parameters(values, template, record=None):
    probabilities = {"delta", "proC", "replacement_rate", "mutation_probability",
                     "random_fraction", "predicted_fraction", "mutation_fraction", "dropout"}
    allow_zero = probabilities | {"proM", "noise_scale"}
    result = {}
    for key, default in template.items():
        raw = values.get(key)
        label = PARAM_LABELS.get(key, key)
        spec = (record or {}).get("parameter_specs", {}).get(key)
        try:
            if spec:
                value = _typed_parameter(raw, default, spec, label)
            elif isinstance(default, bool):
                if str(raw).lower() not in ("true", "false"):
                    raise ValueError()
                value = str(raw).lower() == "true"
            elif isinstance(default, (int, float)):
                value = float(raw)
                if not math.isfinite(value):
                    raise ValueError()
                if isinstance(default, int):
                    if not value.is_integer():
                        raise ValueError()
                    value = int(value)
            else:
                value = str(raw)
        except (TypeError, ValueError):
            if spec:
                raise
            raise ValueError(f"{label}：请输入有效的{'整数' if type(default) is int else '数值'}") from None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if key == "seed":
                if not 0 <= value < 2**32:
                    raise ValueError("随机种子必须在 0 到 4294967295 之间")
            elif not spec and key in PARAM_LABELS and (value < 0 or
                    (default > 0 and value == 0 and key not in allow_zero)):
                raise ValueError(f"{label}：必须为正数")
            # Custom parameter domains belong to the component constructor;
            # a positive default does not imply positive-only values.
            if not spec and key in probabilities and not 0 <= value <= 1:
                raise ValueError(f"{label}：必须在 0 到 1 之间")
        result[key] = value
    return result


def validate_request(request):
    problem = registered_class(request["records"]["problem"])(**request["params"]["problem"])
    registered_class(request["records"]["dynamic"])(**request["params"]["dynamic"])
    registered_class(request["records"]["search"])(**request["params"]["search"])
    return problem.initial_convergence + problem.change_each_evaluations * problem.total_change_time


class RunState:
    """String-valued API expected by Algorithm, backed by a shared integer."""
    STATES = {"running": 0, "pause": 1, "stop": 2}

    def __init__(self, shared):
        self.shared = shared

    @property
    def value(self):
        return ("running", "pause", "stop")[self.shared.value]

    @value.setter
    def value(self, value):
        self.shared.value = self.STATES[value]


def result_settings(settings, request):
    """Keep inferred parameters and source fingerprints in saved/replayed runs."""
    import copy
    result = copy.deepcopy(settings)
    result["history_policy"] = history_policy(request.get("history_policy", "full"))
    for kind, key in (("dynamic", "response_strategy_name"), ("search", "search_algorithm_name"),
                      ("problem", "problem_name")):
        result[key] = request["records"][kind]["name"]
    sources = {}
    for kind, key in (("dynamic", "response_strategy_params"), ("search", "search_algorithm_params")):
        result.setdefault(key, {}).update(request["params"][kind])
        record = request["records"][kind]
        if record.get("format") == "python-file":
            source = Path(record["source_file"])
            fingerprint = record.get("loaded_sha256") or hashlib.sha256(source.read_bytes()).hexdigest()
            sources[kind] = {"file": source.name, "sha256": fingerprint,
                             "entry": record["entry_name"], "api": record["api"]}
    if sources:
        result["code_plugins"] = sources
    return result


def history_policy(value):
    if value not in ("full", "environment"):
        raise ValueError("回放记录方式必须为 full 或 environment")
    return value


class SnapshotPipe:
    def __init__(self, pipe, request):
        self.pipe, self.request = pipe, request
        self.settings = None

    def send(self, message):
        if "settings" in message:
            if self.settings is None:
                self.settings = result_settings(message["settings"], self.request)
            message = dict(message, settings=self.settings)
        self.pipe.send(message)


def optimize_worker(request, state, pipe):
    try:
        history_policy(request.get("history_policy", "full"))
        algorithm = registered_class(request["records"]["search"])(
            **request["params"]["search"], state=state, pip=SnapshotPipe(pipe, request), mode="test")
        strategy = registered_class(request["records"]["dynamic"])(**request["params"]["dynamic"])
        problem = registered_class(request["records"]["problem"])(**request["params"]["problem"])
        algorithm.optimize(problem, strategy)
        if (request["records"]["search"].get("format") == "python-file"
                and not problem.is_ended() and state.value != "stop"):
            raise RuntimeError("自定义算法提前返回，尚未完成环境/评价预算；完整 optimize 循环需运行至 problem.is_ended()")
    except Exception as error:
        try:
            pipe.send({"kind": "error", "message": f"{type(error).__name__}: {error}",
                       "traceback": traceback.format_exc()})
        except (OSError, EOFError):
            pass
        raise
    finally:
        pipe.close()


def _json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"不能保存 {type(value).__name__}")


def save_frames(path, frames):
    if not frames:
        raise ValueError("没有可保存的快照")
    information = {}
    for frame in frames:
        snapshot = frame["population"].to_dict()
        for key in ("POS", "POF", "bound", "objective_constraints", "t", "evaluate_times"):
            snapshot[key] = frame.get(key)
        information.setdefault(str(frame["t"]), {})[str(frame["evaluate_times"])] = snapshot
    data = {"settings": frames[0]["settings"], "information": information}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement avoids corrupting an existing result on failure.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as output:
            temporary = output.name
            json.dump(data, output, ensure_ascii=False, allow_nan=False, default=_json_value)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _matrix(raw, columns, label):
    array = np.asarray(raw, dtype=float)
    if array.ndim != 2 or array.shape[1] != columns or not len(array) or not np.isfinite(array).all():
        raise ValueError(f"{label}的尺寸或数值无效")
    return array


def load_frames(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("settings"), dict):
        raise ValueError("这不是 FlexDMO 结果文件")
    settings = data["settings"]
    history_policy(settings.get("history_policy", "full"))
    record = next((r for r in records()["problem"] if
                   r.get("class_name", Path(r["folder_name"]).name) == settings.get("problem_class")), None)
    if record is None:
        raise ValueError("结果中的测试问题不在当前注册表中")
    params = defaults(record)
    stored_params = settings.get("problem_params", {})
    if not isinstance(stored_params, dict):
        raise ValueError("结果中的问题参数格式无效")
    for key in params:
        if key in stored_params:
            params[key] = stored_params[key]
    # Legacy snapshots stored total_change_time instead of the constructor name.
    if "total_evaluate_time" not in stored_params and "total_change_time" in stored_params:
        params["total_evaluate_time"] = stored_params["total_change_time"]
    problem = registered_class(record)(**params)
    information = data.get("information", {})
    if not isinstance(information, dict):
        raise ValueError("结果中的历史快照格式无效")
    result = []
    for environment in sorted(information, key=int):
        t = int(environment)
        if t < 0:
            raise ValueError("环境编号不能为负")
        if not isinstance(information[environment], dict):
            raise ValueError("结果中的环境快照格式无效")
        for evaluation in sorted(information[environment], key=int):
            count = int(evaluation)
            if count < 0:
                raise ValueError("评估次数不能为负")
            snapshot = information[environment][evaluation]
            if not isinstance(snapshot, dict):
                raise ValueError("结果中的种群快照格式无效")
            X = _matrix(snapshot["decision"], problem.decision_num, "决策矩阵")
            raw_f, raw_g = snapshot.get("objective"), snapshot.get("constraint")
            F = _matrix(raw_f, problem.n_obj, "目标矩阵") if raw_f and all(v is not None for v in raw_f) else None
            G = (_matrix(raw_g, problem.n_con, "约束矩阵")
                 if problem.n_con and raw_g and all(v is not None for v in raw_g) else None)
            if F is None or (problem.n_con and G is None):
                calculated_f, calculated_g = problem.evaluate(X, need_count=False, t=t)
                F = calculated_f if F is None else F
                G = calculated_g if G is None else G
            if len(X) != len(F) or (G is not None and len(G) != len(X)):
                raise ValueError("决策、目标与约束矩阵行数不一致")
            bounds = snapshot.get("bound")
            if bounds is None:
                bounds = [snapshot.get("xl"), snapshot.get("xu")]
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ValueError("变量边界必须包含下界与上界")
            lower = np.asarray(bounds[0] if bounds[0] is not None else problem.xl, dtype=float)
            upper = np.asarray(bounds[1] if bounds[1] is not None else problem.xu, dtype=float)
            if lower.shape != (problem.decision_num,) or upper.shape != lower.shape or not np.isfinite([lower, upper]).all() or np.any(lower > upper):
                raise ValueError("变量边界无效")
            pop = Population(X=X, F=F, xl=lower, xu=upper)
            for index, individual in enumerate(pop):
                individual.G = G[index] if G is not None else None
                individual.constraint_violation = float(np.maximum(individual.G, 0).sum()) if G is not None else 0.0
                individual.feasible = individual.constraint_violation <= 1e-12
                for attribute in ("rank", "crowding_distance"):
                    values = snapshot.get(attribute)
                    if values is not None:
                        if len(values) != len(pop):
                            raise ValueError(f"{attribute} 的长度与种群不一致")
                        setattr(individual, attribute, values[index])
            frame = {"settings": settings, "population": pop, "t": t,
                     "evaluate_times": count, "bound": [lower, upper]}
            for key, fallback in (("POF", problem.get_pareto_front), ("POS", problem.get_pareto_set),
                                  ("objective_constraints", problem.get_objective_constraints)):
                value = snapshot.get(key)
                frame[key] = fallback(t) if value is None else value
            _matrix(frame["POF"], problem.n_obj, "真实前沿")
            _matrix(frame["POS"], problem.decision_num, "真实解集")
            result.append(frame)
    if not result:
        raise ValueError("结果文件没有可回放的快照")
    return result
