"""Azzouz et al. (2015) DCTP1-DCTP8 benchmark 的共享实现。

论文使用 ``c_j(x) >= 0`` 表示可行，而 DynOptForge 的统一约定是
``G_j(x) <= 0``。本模块将论文公式集中实现为 :func:`evaluate_paper`，并在
``DCTPBase`` 的平台接口处统一取反，避免算法和 benchmark 各维护一份公式。

论文印刷式 (1)、(2) 的 ``g`` 求和项遗漏了平方。若按字面实现，``g`` 可能为负，
平方根失去定义，而且不能得到文中随 ``sin(0.01*pi*t)`` 移动的 Pareto Set。
因此沿用 CTP/ZDT 构造所要求的平方项。这一复现选择也记录在实验 README 中。
"""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

import numpy as np

from problems.Problem import Problem

# 表 1 的 (a_j, b_j, c_j, d_j, e_j, theta_j)。DCTP8 有两条约束。
CONSTRAINT_PARAMETERS: dict[
    int, tuple[tuple[float, float, float, float, float, float], ...]
] = {
    2: ((0.2, 10.0, 1.0, 6.0, 1.0, -0.2 * np.pi),),
    3: ((0.1, 10.0, 1.0, 0.5, 1.0, -0.2 * np.pi),),
    4: ((0.75, 10.0, 1.0, 0.5, 1.0, -0.2 * np.pi),),
    5: ((0.1, 10.0, 2.0, 0.5, 1.0, -0.2 * np.pi),),
    6: ((40.0, 0.5, 1.0, 2.0, -2.0, 0.1 * np.pi),),
    7: ((40.0, 5.0, 1.0, 6.0, 0.0, -0.05 * np.pi),),
    8: (
        (40.0, 0.5, 1.0, 2.0, -2.0, 0.1 * np.pi),
        (40.0, 2.0, 1.0, 6.0, 0.0, -0.05 * np.pi),
    ),
}


def constraints_from_objectives(
    problem_number: int,
    objectives: np.ndarray,
    paper_time: int,
) -> np.ndarray:
    """直接在目标空间计算论文约束 ``C>=0``。

    DCTP1--DCTP8 的约束只依赖 ``f1``、``f2`` 和论文时刻 ``t``，不依赖原始
    决策向量。因此 Pareto Front 查看器可在规则目标网格上精确分类可行域，
    无需运行优化算法或从决策空间随机投影。

    Args:
        problem_number: DCTP 编号，范围 1--8。
        objectives: ``N x 2`` 目标矩阵。
        paper_time: 论文从 1 开始的离散动态时刻。

    Returns:
        论文符号约定的约束矩阵；每一列均满足 ``C_j>=0`` 时可行。
    """

    if problem_number not in range(1, 9):
        raise ValueError("problem_number 必须位于 1..8")
    if paper_time < 1:
        raise ValueError("paper_time 必须至少为 1")
    values = np.atleast_2d(np.asarray(objectives, dtype=float))
    if values.shape[1] != 2:
        raise ValueError("DCTP 目标矩阵必须恰好包含 f1、f2 两列")
    f1, f2 = values[:, 0], values[:, 1]
    t = float(paper_time)
    if problem_number == 1:
        return np.column_stack(
            (
                f2 / t - 0.858 * np.exp(-0.541 * f1),
                f2 / t - 0.728 * np.exp(-0.295 * f1),
            )
        )

    columns = []
    for a_j, b_j, c_j, d_j, e_j, theta_j in CONSTRAINT_PARAMETERS[problem_number]:
        rotated_y = (f2 / t - e_j) * np.cos(theta_j) - f1 * np.sin(theta_j)
        rotated_x = (f2 / t - e_j) * np.sin(theta_j) + f1 * np.cos(theta_j)
        boundary = a_j * np.abs(np.sin(b_j * np.pi * np.power(rotated_x, c_j))) ** d_j
        columns.append(rotated_y - boundary)
    return np.column_stack(columns)


def evaluate_paper(
    problem_number: int,
    decisions: np.ndarray,
    paper_time: int,
) -> tuple[np.ndarray, np.ndarray]:
    """计算论文时刻 ``t>=1`` 的目标 ``F`` 和纸面约束 ``C>=0``。

    Args:
        problem_number: DCTP 编号，范围 1--8。
        decisions: ``N x D`` 决策矩阵，所有变量定义域均为 ``[0, 1]``。
        paper_time: 论文的离散时刻 ``t``；正式实验依次为 1、2、3、4。

    Returns:
        ``(F, C)``。``F`` 为 ``N x 2``，``C`` 中每一项非负时个体可行。
    """

    if problem_number not in range(1, 9):
        raise ValueError("problem_number 必须位于 1..8")
    if paper_time < 1:
        raise ValueError("paper_time 必须至少为 1")
    x = np.atleast_2d(np.asarray(decisions, dtype=float))
    t = float(paper_time)
    f1 = x[:, 0]
    dynamic_target = np.sin(0.01 * np.pi * t)
    # 论文的动态 Pareto Set：x_i=sin(0.01*pi*t), i=2,...,D。
    g = 1.0 + np.sum((x[:, 1:] - dynamic_target) ** 2, axis=1)

    if problem_number == 1:
        f2 = t * g * np.exp(-f1 / g)
    else:
        f2 = t * g * (1.0 - np.sqrt(np.maximum(f1 / g, 0.0)))
    objectives = np.column_stack((f1, f2))
    constraints = constraints_from_objectives(problem_number, objectives, paper_time)
    return objectives, constraints


def _nondominated_2d(objectives: np.ndarray) -> np.ndarray:
    """按 ``f1`` 扫描二维最小化点集，返回第一非支配前沿。"""

    if len(objectives) == 0:
        return np.empty((0, 2), dtype=float)
    order = np.lexsort((objectives[:, 1], objectives[:, 0]))
    ordered = objectives[order]
    keep = np.zeros(len(ordered), dtype=bool)
    best_f2 = np.inf
    for index, f2 in enumerate(ordered[:, 1]):
        if f2 < best_f2 - 1e-12:
            keep[index] = True
            best_f2 = float(f2)
    return ordered[keep]


@lru_cache(maxsize=128)
def _true_front_cached(
    problem_number: int,
    paper_time: int,
    point_count: int,
) -> np.ndarray:
    """在可达的 ``(x1,g)`` 流形上数值构造受约束真实 PF。"""

    x1_values = np.linspace(0.0, 1.0, point_count)
    shift = np.sin(0.01 * np.pi * paper_time)
    # D=30 是论文规定维度；此上界覆盖 29 个距离变量的最远角点。
    g_max = 1.0 + 29.0 * max(shift**2, (1.0 - shift) ** 2)
    g_values = np.linspace(1.0, g_max, max(2001, point_count))
    candidates: list[np.ndarray] = []
    for start in range(0, len(x1_values), 128):
        x1 = x1_values[start : start + 128, None]
        g = g_values[None, :]
        t = float(paper_time)
        if problem_number == 1:
            f2 = t * g * np.exp(-x1 / g)
            columns = (
                f2 / t - 0.858 * np.exp(-0.541 * x1),
                f2 / t - 0.728 * np.exp(-0.295 * x1),
            )
        else:
            f2 = t * g * (1.0 - np.sqrt(x1 / g))
            dynamic_columns = []
            for a_j, b_j, c_j, d_j, e_j, theta_j in CONSTRAINT_PARAMETERS[
                problem_number
            ]:
                rotated_y = (f2 / t - e_j) * np.cos(theta_j) - x1 * np.sin(theta_j)
                rotated_x = (f2 / t - e_j) * np.sin(theta_j) + x1 * np.cos(theta_j)
                boundary = (
                    a_j * np.abs(np.sin(b_j * np.pi * np.power(rotated_x, c_j))) ** d_j
                )
                dynamic_columns.append(rotated_y - boundary)
            columns = tuple(dynamic_columns)
        feasible = np.logical_and.reduce([item >= -1e-12 for item in columns])
        has_feasible = np.any(feasible, axis=1)
        first_feasible = np.argmax(feasible, axis=1)
        rows = np.flatnonzero(has_feasible)
        if len(rows):
            candidates.append(
                np.column_stack((x1[rows, 0], f2[rows, first_feasible[rows]]))
            )
    if not candidates:
        return np.empty((0, 2), dtype=float)
    return _nondominated_2d(np.vstack(candidates))


def true_front(
    problem_number: int,
    paper_time: int,
    point_count: int = 2001,
) -> np.ndarray:
    """返回 DCTP 真实 PF 的副本，防止调用者修改共享缓存。"""

    return _true_front_cached(problem_number, paper_time, point_count).copy()


class DCTPBase(Problem):
    """DCTP1--DCTP8 的 DynOptForge 问题基类。

    平台环境从 0 编号，论文时刻从 1 编号，因此所有评价都使用
    ``paper_time = environment + 1``。DCTP 没有独立的 ``n_t`` 严重度参数；
    配置中的 ``n=1`` 仅用于满足统一任务键，不参与论文公式。
    """

    problem_number: int = 0
    # DCTP 直接使用论文整数时刻 t=1,2,...，不存在 DCF/DF 的变化强度 n_t。
    uses_n_parameter = False
    # DCTP6/8 的 f2 范围可达 f1 的十余倍；等比例坐标会把景观压成狭长条。
    use_equal_objective_aspect = False
    # 仅供 plots 构造只读查看器实例；正式实验参数始终来自 expMnger/configs。
    visualization_defaults: ClassVar[dict[str, int]] = {
        "decision_num": 30,
        "n": 1,
        "total_evaluate_time": 4,
    }

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        if decision_num != 30:
            raise ValueError("Azzouz et al. (2015) 的 DCTP 实验固定 D=30")
        constraint_count = 2 if self.problem_number in {1, 8} else 1
        super().__init__(
            decision_num,
            2,
            constraint_count,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            "DynamicConstrained",
        )
        self.xl = np.zeros(decision_num, dtype=float)
        self.xu = np.ones(decision_num, dtype=float)

    @staticmethod
    def _paper_time(environment: int) -> int:
        """把平台 ``environment=0..`` 映射为论文 ``t=1..``。"""

        return int(environment) + 1

    def _evaluate_objectives(self, X, t):
        objectives, _ = evaluate_paper(self.problem_number, X, self._paper_time(t))
        return objectives

    def _evaluate_constraints(self, X, t):
        _, paper_constraints = evaluate_paper(
            self.problem_number, X, self._paper_time(t)
        )
        return -paper_constraints

    def _calculate_pareto_front(self, t=None):
        environment = self.t if t is None else int(t)
        return true_front(self.problem_number, self._paper_time(environment))

    def get_original_pareto_front(self, t=None, point_count=2001):
        """返回未施加动态约束时 ``g=1`` 的原始 Pareto Front（UPF）。

        Args:
            t: 平台从 0 开始的环境编号。
            point_count: 沿 ``x1`` 的均匀采样点数。
        """

        if point_count < 2:
            raise ValueError("point_count 至少为 2")
        environment = self.t if t is None else int(t)
        paper_time = float(self._paper_time(environment))
        f1 = np.linspace(0.0, 1.0, point_count)
        if self.problem_number == 1:
            f2 = paper_time * np.exp(-f1)
        else:
            f2 = paper_time * (1.0 - np.sqrt(f1))
        return np.column_stack((f1, f2))

    def get_objective_visualization_bounds(self):
        """返回覆盖正式四环境 UPF、CPF 和主要约束结构的固定坐标范围。

        DCTP6、DCTP8 的可行前沿会升至约 ``3.71*t``，其余问题约为
        ``1.1*t``。使用整个动画固定的上界，避免播放时坐标轴缩放造成虚假移动。
        """

        maximum_paper_time = max(1, int(self.total_change_time))
        factor = 4.0 if self.problem_number in {6, 8} else 1.2
        return (0.0, 1.05), (0.0, factor * maximum_paper_time)

    def get_objective_space_regions(self, t=None, resolution=260):
        """在二维目标空间网格上返回可行域与不可行域分类。

        返回 ``(f1_grid, f2_grid, feasible_mask)``；掩码为真表示论文全部
        ``C_j>=0``，等价于平台全部 ``G_j<=0``。
        """

        if resolution < 20:
            raise ValueError("resolution 至少为 20")
        environment = self.t if t is None else int(t)
        (f1_min, f1_max), (f2_min, f2_max) = self.get_objective_visualization_bounds()
        f1_values = np.linspace(f1_min, f1_max, resolution)
        f2_values = np.linspace(f2_min, f2_max, resolution)
        f1_grid, f2_grid = np.meshgrid(f1_values, f2_values)
        objectives = np.column_stack((f1_grid.ravel(), f2_grid.ravel()))
        paper_constraints = constraints_from_objectives(
            self.problem_number,
            objectives,
            self._paper_time(environment),
        )
        feasible = np.all(paper_constraints >= 0.0, axis=1)
        return f1_grid, f2_grid, feasible.reshape(f1_grid.shape)

    def get_dynamic_time(self, environment: int) -> float:
        """返回查看器应显示的论文离散时刻 ``t=environment+1``。"""

        return float(self._paper_time(environment))

    def get_dynamic_time_description(self, environment: int) -> str:
        """返回 DCTP 专用时间说明，避免把无效的 ``n`` 显示为变化强度。"""

        return f"论文离散时间：t = {int(environment)} + 1 = {self._paper_time(environment)}"

    def _calculate_pareto_set(self, t=None):
        """返回 PF 对应的数值 PS 近似，用于统一问题接口。"""

        environment = self.t if t is None else int(t)
        paper_time = self._paper_time(environment)
        front = true_front(self.problem_number, paper_time)
        shift = np.sin(0.01 * np.pi * paper_time)
        decisions = np.full((len(front), self.decision_num), shift, dtype=float)
        if not len(decisions):
            return decisions

        # 部分 DCTP 的受约束 PF 位于 g>1。根据保存的 (f1,f2) 对每个点反求
        # 单调距离量 g，再把 g-1 均匀分配给 D-1 个距离变量。
        farther_bound = 1.0 if 1.0 - shift >= shift else 0.0
        g_upper = 1.0 + (self.decision_num - 1) * (farther_bound - shift) ** 2
        low = np.ones(len(front), dtype=float)
        high = np.full(len(front), g_upper, dtype=float)
        f1, target_f2 = front[:, 0], front[:, 1]
        paper_t = float(paper_time)
        for _ in range(50):
            mid = (low + high) / 2.0
            if self.problem_number == 1:
                candidate_f2 = paper_t * mid * np.exp(-f1 / mid)
            else:
                candidate_f2 = (
                    paper_t * mid * (1.0 - np.sqrt(np.maximum(f1 / mid, 0.0)))
                )
            low = np.where(candidate_f2 < target_f2, mid, low)
            high = np.where(candidate_f2 >= target_f2, mid, high)
        signed_distance = np.sqrt(np.maximum(high - 1.0, 0.0) / (self.decision_num - 1))
        if farther_bound == 0.0:
            signed_distance = -signed_distance
        decisions[:, 0] = f1
        decisions[:, 1:] = shift + signed_distance[:, None]
        return decisions


class DCTP1Base(DCTPBase):
    problem_number = 1


class DCTP2Base(DCTPBase):
    problem_number = 2


class DCTP3Base(DCTPBase):
    problem_number = 3


class DCTP4Base(DCTPBase):
    problem_number = 4


class DCTP5Base(DCTPBase):
    problem_number = 5


class DCTP6Base(DCTPBase):
    problem_number = 6


class DCTP7Base(DCTPBase):
    problem_number = 7


class DCTP8Base(DCTPBase):
    problem_number = 8
