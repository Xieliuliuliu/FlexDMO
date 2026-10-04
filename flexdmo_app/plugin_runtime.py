"""Adapters for trusted user algorithms. Only loaded inside run subprocesses."""
import importlib
import hashlib
import importlib.util
import inspect
from pathlib import Path
import sys

import numpy as np

from algorithms.search_algorithm.Algorithm import Algorithm
from components.Population import Population


def checked_population(output, problem, label):
    """Reject malformed code output instead of silently clipping or resampling."""
    try:
        X = np.asarray(output.get_decision_matrix() if isinstance(output, Population) else output, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} 必须返回 Population 或二维决策矩阵：{error}") from None
    shape = (problem.solution_num, problem.decision_num)
    if X.shape != shape or not np.isfinite(X).all():
        raise ValueError(f"{label} 输出必须是有限数值的 {shape} 决策矩阵，实际 {X.shape}；不能含 NaN/Inf")
    if np.any(X < problem.xl - 1e-12) or np.any(X > problem.xu + 1e-12):
        raise ValueError(f"{label} 输出越过变量边界；请在算法代码中处理边界")
    population = output if isinstance(output, Population) else Population(X=X, xl=problem.xl, xu=problem.xu)
    population.xl, population.xu = problem.xl, problem.xu
    return population


def _evaluate(population, problem, label, need_count=True):
    if need_count:
        population.update_objective_constrain(problem)
    else:
        F, G = problem.evaluate(population.get_decision_matrix(), need_count=False, t=problem.t)
        for i, individual in enumerate(population):
            individual.F = F[i]
            individual.G = G[i] if G is not None else None
            individual.constraint_violation = float(np.maximum(individual.G, 0).sum()) if G is not None else 0.0
            individual.feasible = individual.constraint_violation <= 1e-12
    if not np.isfinite(population.get_objective_matrix()).all():
        raise ValueError(f"{label} 评价产生了 NaN/Inf 目标值")
    if problem.n_con and not np.isfinite(population.get_constrain_matrix()).all():
        raise ValueError(f"{label} 评价产生了 NaN/Inf 约束值")
    return population


def _checked_call(callback, args, kwargs, record):
    try:
        return callback(*args, **kwargs)
    except Exception as error:
        raise RuntimeError(f"算法 {record['name']}：{type(error).__name__}: {error}\n"
                           f"文件 {record['source_file']}，接口起始行 {record['line']}；详细堆栈包含实际出错行。") from error


def load_code_class(record):
    from .core import ROOT
    from .components import PLUGIN_ROOT
    from .code_plugins import inspect_code
    path = Path(record["source_file"]).resolve()
    if not path.is_relative_to(PLUGIN_ROOT.resolve()) or path.suffix != ".py":
        raise ValueError("只运行 Qt 算法目录内的 Python 文件，不接受结果文件中的任意路径")
    # Catch edited signatures/defaults instead of executing a stale run request.
    source_bytes = path.read_bytes()
    source = source_bytes.decode("utf-8-sig")
    fresh = inspect_code(path, record["kind"], source=source)
    if any(fresh[k] != record[k] for k in ("entry_name", "api", "defaults", "parameter_specs", "callback_args")):
        raise ValueError(f"{path.name} 的接口或参数已修改，请刷新组件后重新运行")
    module_name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
    importlib.invalidate_caches()
    importlib.import_module(module_name.rpartition(".")[0])
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        # Compile source directly, avoiding stale timestamp-based bytecode when
        # users edit a file and immediately rerun it.
        exec(compile(source, str(path), "exec"), module.__dict__)
        record["loaded_sha256"] = hashlib.sha256(source_bytes).hexdigest()
        entry = getattr(module, record["entry_name"])
    except Exception:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise

    class UserResponse:
        def __init__(self, **params):
            self.params = params
            self.target = entry(**params) if record["is_class"] else entry

        def response(self, population, problem, algorithm):
            before = problem.evaluate_time
            callback = self.target.response if record["is_class"] else self.target
            args = [population, problem] + ([algorithm] if len(record["callback_args"]) == 3 else [])
            output = _checked_call(callback, args, {} if record["is_class"] else self.params, record)
            result = checked_population(output, problem, f"{record['name']}.response")
            # Recompute at the current environment even if the user returned an
            # old Population. Don't double-count evaluations performed by code.
            return _evaluate(result, problem, record["name"], problem.evaluate_time == before)

    class UserSearch(Algorithm):
        def __init__(self, state=None, pip=None, mode="test", seed=1, **params):
            super().__init__(state=state, pip=pip, mode=mode, seed=seed)
            self.params = params
            if record["api"] == "optimize":
                signature = inspect.signature(entry)
                accepts_extra = any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values())
                runtime = {"state": state, "pip": pip, "mode": mode, "seed": seed}
                supplied = {k: v for k, v in runtime.items() if accepts_extra or k in signature.parameters}
                self.target = entry(**params, **supplied)
                if not isinstance(self.target, Algorithm):
                    raise TypeError("完整 optimize 类需要继承 Algorithm；简单算法可只实现 step")
                # Framework controls are authoritative even when a user's
                # constructor calls super() without forwarding **args.
                self.target.state, self.target.pip, self.target.mode, self.target.seed = state, pip, mode, seed
            else:
                if record["is_class"]:
                    signature = inspect.signature(entry)
                    self.target = entry(**params, **({"seed": seed} if "seed" in signature.parameters else {}))
                else:
                    self.target = entry

        def collect_information(self, population, problem, response_strategy):
            if record["api"] == "optimize" and self.target.history is not self.history:
                self.history = self.target.history
            checked_population(population, problem, record["name"])
            try:
                F = population.get_objective_matrix()
                G = population.get_constrain_matrix()
                if F.shape != (problem.solution_num, problem.n_obj) or not np.isfinite(F).all():
                    raise ValueError("目标矩阵尺寸无效或包含 NaN/Inf")
                if problem.n_con and (G.shape != (problem.solution_num, problem.n_con) or not np.isfinite(G).all()):
                    raise ValueError("约束矩阵缺失、尺寸无效或包含 NaN/Inf")
            except ValueError as error:
                raise ValueError(f"{record['name']} 收集快照前必须完成有效的目标/约束评价：{error}") from None
            if self.history["settings"] is None:
                def attrs(obj):
                    return {k: v for k, v in vars(obj).items() if isinstance(v, (int, float, str, bool, type(None)))}
                self.history["settings"] = {
                    "problem_class": problem.__class__.__name__,
                    "search_algorithm_class": record["class_name"],
                    "response_strategy_class": response_strategy.__class__.__name__,
                    "problem_params": attrs(problem),
                    "search_algorithm_params": {"seed": self.seed, **self.params},
                    "response_strategy_params": {**attrs(response_strategy), **getattr(response_strategy, "params", {})},
                }
            super().collect_information(population, problem, response_strategy)

        def optimize(self, problem, response_strategy):
            self.reset_random_state()
            if record["api"] == "optimize":
                self.target.history = self.history
                self.target.collect_information = self.collect_information
                output = _checked_call(self.target.optimize, [problem, response_strategy], {}, record)
                return output
            population = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
            _evaluate(population, problem, record["name"])
            self.collect_information(population, problem, response_strategy)
            callback = self.target.step if record["is_class"] else self.target
            while not problem.is_ended() and self.control_process():
                # Unlike objective-only detection, this also notices changes
                # that affect constraints alone, even if F remains unchanged.
                if problem.need_change:
                    problem.evaluate(population[0].X.reshape(1, -1), need_count=False)
                    population = checked_population(response_strategy.response(population, problem, self), problem, "动态响应")
                    if not self.control_process():
                        break
                    _evaluate(population, problem, record["name"], need_count=False)
                    self.collect_information(population, problem, response_strategy)
                    continue
                before = problem.evaluate_time
                output = _checked_call(callback, [population, problem], {} if record["is_class"] else self.params, record)
                population = checked_population(output, problem, f"{record['name']}.step")
                _evaluate(population, problem, record["name"], problem.evaluate_time == before)
                self.collect_information(population, problem, response_strategy)

    wrapper = UserResponse if record["kind"] == "dynamic" else UserSearch
    wrapper.__name__ = record["class_name"]
    return wrapper
