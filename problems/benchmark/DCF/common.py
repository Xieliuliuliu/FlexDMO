"""Shared implementation helpers for the CEC2023 DCF benchmark suite.

The paper writes constraints using both ``c >= 0`` and ``c <= 0``.  Every
class below exposes constraints in DynOptForge's convention: ``G <= 0`` is
feasible.  The environment counter maintained by :class:`Problem` is divided
by ``n`` (the change-severity parameter), matching
``t = floor(generation / tau_t) / n_t`` from the benchmark definition.
"""

from __future__ import annotations

import numpy as np

from problems.Problem import Problem
from utils.evolution_tools import fast_non_dominated_sort


class DCFBase(Problem):
    """DCF1-DCF10 的共享基类。

    模块逻辑分为三层：

    1. 子类实现论文中的目标函数与约束函数；
    2. 基类统一把论文约束转换成平台的 ``G <= 0`` 形式，并数值构造 PF/PS；
    3. 可视化接口直接在二维目标空间分类规则网格，不启动任何优化算法。

    Attributes:
        constraint_count: 当前问题的约束数量，默认 1。
        all_unit_bounds: 是否所有决策变量都使用 ``[0, 1]``；仅 DCF2 为真。
        problem_number: 论文中的问题编号，由 DCF1Base-DCF10Base 固定指定。
    """

    constraint_count = 1
    all_unit_bounds = False
    problem_number = None

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        if decision_num < 2:
            raise ValueError(f"{type(self).__name__} 至少需要两个决策变量")
        super().__init__(
            decision_num,
            2,
            self.constraint_count,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            "DynamicConstrained",
        )
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)
        if not self.all_unit_bounds:
            self.xl[1:] = -1.0

        # The competition grants 6000 evaluations before the first change
        # for N=100, i.e. 60 generations rather than Problem's default 50.
        self.initial_convergence = 60 * solution_num
        self._reference_t = None
        self._reference_ps = None
        self._reference_pf = None

    def _time(self, t):
        """把离散环境编号转换成 benchmark 连续时间 ``t/n_t``。

        注意 MP-DFR 论文 Algorithm 1 的 ``t`` 是环境序号；DCF 公式中的时间量
        实际为 ``floor(generation/tau_t)/n_t``。本项目由 ``Problem`` 维护前半部分
        的离散序号，所以这里仅除以变化强度 ``n_t``。
        """
        return float(t) / self.n

    def _g(self, t):
        """返回多数 DCF 问题共用的动态量 ``sin(0.5*pi*t/n_t)``。"""
        return np.sin(0.5 * np.pi * self._time(t))

    def _position_index(self, t):
        """返回位置变量下标；默认是 x1，DCF2 会动态切换。"""
        return 0

    def _distance_target(self, t):
        """Optimum value of every distance-related decision variable."""
        return self._g(t)

    def _decisions_from_pairs(self, position, level, t):
        """Build decisions from a position variable and a distance level.

        ``level=0`` lies on the unconstrained optimal manifold (g=1).  Larger
        levels monotonically move all distance variables towards the farther
        bound, so the first feasible level is the best point on that ray.
        """
        position = np.asarray(position, dtype=float).reshape(-1)
        level = np.asarray(level, dtype=float).reshape(-1)
        if position.shape != level.shape:
            raise ValueError("position 和 level 的形状必须一致")

        target = float(self._distance_target(t))
        target_vector = np.full(self.decision_num, target)
        position_index = self._position_index(t)
        # The position-related variable is supplied separately; the remaining
        # variables must stay on their dynamic optimum when level=0.
        target_vector[position_index] = 0.5
        farther = np.where(
            np.abs(self.xu - target_vector) >= np.abs(target_vector - self.xl),
            self.xu,
            self.xl,
        )
        decisions = target_vector + level[:, None] * (farther - target_vector)
        decisions[:, position_index] = position
        return np.clip(decisions, self.xl, self.xu)

    def _evaluate_constraints(self, X, t):
        """评价平台形式的约束矩阵，正值表示约束违反。"""
        objectives = self._evaluate_objectives(X, t)
        constraints = np.asarray(self._constraint_values(X, objectives, t), dtype=float)
        if constraints.ndim == 1:
            constraints = constraints[:, None]
        return constraints

    def _constraint_values(self, X, F, t):
        """由目标矩阵计算约束；具体论文公式由各 DCF 子类实现。"""
        raise NotImplementedError

    def _reference(self, t):
        """Numerically construct the constrained PF/PS at one environment.

        For each position variable, a coarse grid brackets the first feasible
        distance level.  A vectorized bisection then puts boundary solutions
        accurately on dynamic constraints.  Only the first non-dominated
        front is returned.
        """
        if t == self._reference_t:
            return self._reference_ps, self._reference_pf

        position = np.linspace(0.0, 1.0, 1001)
        levels = np.linspace(0.0, 1.0, 257) ** 2
        p_grid = np.repeat(position, len(levels))
        l_grid = np.tile(levels, len(position))
        decisions = self._decisions_from_pairs(p_grid, l_grid, t)
        objectives = self._evaluate_objectives(decisions, t)
        constraints = self._evaluate_constraints(decisions, t)
        feasible = np.all(constraints <= 1e-10, axis=1).reshape(len(position), len(levels))
        has_feasible = feasible.any(axis=1)
        first = np.argmax(feasible, axis=1)

        valid_position = position[has_feasible]
        first = first[has_feasible]
        high = levels[first].copy()
        low = levels[np.maximum(first - 1, 0)].copy()
        boundary = first > 0

        # Refine only rows whose unconstrained level is infeasible.
        for _ in range(30):
            if not np.any(boundary):
                break
            mid = (low + high) / 2.0
            mid_x = self._decisions_from_pairs(valid_position, mid, t)
            mid_g = self._evaluate_constraints(mid_x, t)
            mid_feasible = np.all(mid_g <= 1e-10, axis=1)
            high = np.where(boundary & mid_feasible, mid, high)
            low = np.where(boundary & ~mid_feasible, mid, low)

        candidate_x = self._decisions_from_pairs(valid_position, high, t)
        candidate_f = self._evaluate_objectives(candidate_x, t)
        candidate_g = self._evaluate_constraints(candidate_x, t)
        keep = np.all(candidate_g <= 1e-7, axis=1)
        candidate_x = candidate_x[keep]
        candidate_f = candidate_f[keep]
        if len(candidate_f):
            first_front = fast_non_dominated_sort(candidate_f)[0]
            candidate_x = candidate_x[first_front]
            candidate_f = candidate_f[first_front]
            order = np.argsort(candidate_f[:, 0])
            candidate_x = candidate_x[order]
            candidate_f = candidate_f[order]

        self._reference_t = t
        self._reference_ps = candidate_x
        self._reference_pf = candidate_f
        return candidate_x, candidate_f

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t
        return self._reference(t)[1]

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        return self._reference(t)[0]

    def reset(self):
        """复位动态问题状态，并清除额外的 PF/PS 联合缓存。"""
        super().reset()
        self._reference_t = None
        self._reference_ps = None
        self._reference_pf = None

    # ------------------------------------------------------------------
    # Benchmark-only viewer API
    # ------------------------------------------------------------------
    def get_original_pareto_front(self, t=None, point_count=1001):
        """返回未施加约束时 ``g=1`` 的原始 Pareto Front。

        Args:
            t: 离散环境编号；省略时使用问题当前环境。
            point_count: 沿位置变量均匀采样的点数。默认 1001，与论文
                推荐的 MIGD 参考点规模一致。

        Returns:
            形状为 ``(point_count, 2)`` 的目标矩阵。原始 PF 可能部分或
            全部位于不可行域，它与 :meth:`get_pareto_front` 不同。
        """
        if t is None:
            t = self.t
        if point_count < 2:
            raise ValueError("point_count 至少为 2")
        position = np.linspace(0.0, 1.0, point_count)
        decisions = self._decisions_from_pairs(
            position, np.zeros_like(position), t
        )
        return self._evaluate_objectives(decisions, t)

    def get_objective_visualization_bounds(self):
        """返回动画使用的固定二维目标范围。

        固定坐标轴能避免播放时因自动缩放产生虚假的“整体移动”。这些范围
        覆盖各问题原始 PF、受约束 PF 及主要动态可行域；它们不是优化边界。
        """
        upper_bounds = {
            1: 2.2,
            2: 2.0,
            3: 2.4,
            4: 4.5,
            5: 2.0,
            6: 2.0,
            7: 2.2,
            8: 4.0,
            9: 4.0,
            10: 2.7,
        }
        upper = upper_bounds[self.problem_number]
        return (0.0, upper), (0.0, upper)

    def get_objective_space_regions(self, t=None, resolution=260):
        """在二维目标空间采样并分类可行域与不可行域。

        Args:
            t: 离散环境编号；省略时使用当前环境。
            resolution: 每个坐标轴的网格点数。总评价点数为
                ``resolution**2``；平台默认 260，在清晰度和绘制速度间折中。

        Returns:
            ``(f1_grid, f2_grid, feasible_mask)``。三个数组形状均为
            ``(resolution, resolution)``，布尔掩码为真表示所有约束均满足。

        Notes:
            DCF1-DCF10 的约束均只依赖目标值和时间，因此可以直接分类目标
            网格，不需要先运行算法或从决策空间近似投影可行域。
        """
        if t is None:
            t = self.t
        if resolution < 20:
            raise ValueError("resolution 至少为 20")
        (f1_min, f1_max), (f2_min, f2_max) = self.get_objective_visualization_bounds()
        f1_values = np.linspace(f1_min, f1_max, resolution)
        f2_values = np.linspace(f2_min, f2_max, resolution)
        f1_grid, f2_grid = np.meshgrid(f1_values, f2_values)
        objectives = np.column_stack((f1_grid.ravel(), f2_grid.ravel()))

        # 子类约束公式均不读取 X，传入 None 明确表示这里是在目标空间评价。
        constraints = np.asarray(
            self._constraint_values(None, objectives, t), dtype=float
        )
        if constraints.ndim == 1:
            constraints = constraints[:, None]
        feasible = np.all(constraints <= 0.0, axis=1).reshape(f1_grid.shape)
        return f1_grid, f2_grid, feasible


class DCF1Base(DCFBase):
    """DCF1：静态线性目标与动态圆形约束。"""

    problem_number = 1
    def _distance_target(self, t):
        return 0.5

    def _evaluate_objectives(self, X, t):
        g = 1.0 + np.sum((X[:, 1:] - 0.5) ** 2, axis=1)
        return np.column_stack((g * X[:, 0], g * (1.0 - X[:, 0])))

    def _constraint_values(self, X, F, t):
        radius = 0.7 + abs(self._g(t))
        paper_c = F[:, 0] ** 2 + F[:, 1] ** 2 - radius**2
        return -paper_c  # paper: c >= 0


class DCF2Base(DCFBase):
    """DCF2：位置变量动态切换，静态约束形成断裂 PF。"""

    problem_number = 2
    all_unit_bounds = True

    def _distance_target(self, t):
        return abs(self._g(t))

    def _position_index(self, t):
        return int(np.floor((self.decision_num - 1) * abs(self._g(t))))

    def _evaluate_objectives(self, X, t):
        r = self._position_index(t)
        mask = np.arange(self.decision_num) != r
        g = 1.0 + np.sum((X[:, mask] - abs(self._g(t))) ** 2, axis=1)
        xr = X[:, r]
        return np.column_stack((g * xr, g * (1.0 - xr**2)))

    def _constraint_values(self, X, F, t):
        angle = -0.15 * np.pi
        rotated = np.sin(angle) * F[:, 1] + np.cos(angle) * F[:, 0]
        return (
            np.cos(angle) * F[:, 1]
            - np.sin(angle) * F[:, 0]
            - (2.0 * np.sin(4.0 * np.pi * rotated)) ** 6
        )  # paper: c <= 0


class DCF3Base(DCFBase):
    """DCF3：动态距离函数与动态环带约束。"""

    problem_number = 3
    def _evaluate_objectives(self, X, t):
        g = 1.0 + np.sum((X[:, 1:] - self._g(t)) ** 2, axis=1)
        return np.column_stack((g * X[:, 0], g * np.sqrt(np.maximum(0.0, 1.0 - X[:, 0] ** 2))))

    def _constraint_values(self, X, F, t):
        radius2 = F[:, 0] ** 2 + F[:, 1] ** 2
        angle = np.arctan2(F[:, 1], F[:, 0])
        t1 = radius2 - 2.0
        t2 = radius2 - (2.0 - (0.5 - 0.4 * self._g(t)) * np.sin(10.0 * angle))
        return -(t1 * t2)  # paper: c >= 0


class DCF4Base(DCFBase):
    """DCF4：静态目标与随时间变化的小可行域。"""

    problem_number = 4
    def _distance_target(self, t):
        return 0.0

    def _evaluate_objectives(self, X, t):
        g = 1.0 + np.sum(X[:, 1:] ** 2, axis=1)
        return np.column_stack((g * X[:, 0], g * np.sqrt(np.maximum(0.0, 1.0 - X[:, 0] ** 2))))

    def _constraint_values(self, X, F, t):
        dynamic = np.cos(np.pi * self._time(t))
        t1 = 3.0 - dynamic - np.exp(F[:, 0]) - 0.3 * np.sin(4.0 * np.pi * F[:, 0]) - F[:, 1]
        t2 = 4.1 - (1.0 + F[:, 0] + 0.3 * F[:, 0] ** 2) - 0.3 * np.sin(4.0 * np.pi * F[:, 0]) - F[:, 1]
        return t1 * t2  # paper: c <= 0


class DCF5Base(DCFBase):
    """DCF5：动态凹凸 PF 与两个混合静态约束。"""

    problem_number = 5
    constraint_count = 2

    def _evaluate_objectives(self, X, t):
        y = X[:, 1:] - self._g(t)
        g = 1.0 + np.sum(y**2 + np.sin(0.5 * np.pi * y) ** 2, axis=1)
        wave = 0.2 * self._g(t) * np.sin(np.pi * X[:, 0])
        return np.column_stack((g * (X[:, 0] + wave), g * (1.0 - X[:, 0] + wave)))

    def _constraint_values(self, X, F, t):
        c1 = (F[:, 0] + 2.0 * F[:, 1] - 1.0) * (F[:, 0] + 0.5 * F[:, 1] - 0.5)
        c2 = F[:, 0] ** 2 + F[:, 1] ** 2 - 1.4
        return np.column_stack((-c1, c2))  # paper: c1 >= 0, c2 <= 0


class DCF6Base(DCFBase):
    """DCF6：动态目标偏好和周期性断裂 PF。"""

    problem_number = 6
    def _evaluate_objectives(self, X, t):
        g = 1.0 + np.sum((X[:, 1:] - self._g(t)) ** 2, axis=1)
        return np.column_stack((g * X[:, 0], g * np.sqrt(np.maximum(0.0, 1.0 - X[:, 0] ** 2))))

    def _constraint_values(self, X, F, t):
        dynamic = self._g(t)
        h = 1.0 if dynamic >= 0 else -1.0
        ratio = F[:, 1] / np.maximum(F[:, 0], 1e-12)
        if h < 0:
            ratio = 1.0 / np.maximum(ratio, 1e-12)
        w = np.cos(5.0 * np.arctan(ratio) ** 4) ** 6
        d1 = 0.9 + (0.1 + 0.7 * abs(dynamic)) * w
        d2 = 0.9 + (0.8 - 0.7 * abs(dynamic)) * w
        paper_c = 1.1 - (F[:, 0] / d1) ** 2 - (F[:, 1] / d2) ** 2
        return -paper_c  # paper: c >= 0


class DCF7Base(DCFBase):
    """DCF7：目标空间平移，静态约束使 PF 在连续/断裂间切换。"""

    problem_number = 7
    def _evaluate_objectives(self, X, t):
        y = X[:, 1:] - self._g(t)
        g = 1.0 + np.sum((y**2 - np.cos(np.pi * y) + 1.0) ** 2, axis=1)
        shift = abs(self._g(t))
        return np.column_stack((g * X[:, 0] + shift, g * (1.0 - X[:, 0]) + shift))

    def _constraint_values(self, X, F, t):
        paper_c = F[:, 0] + F[:, 1] - 1.0 - np.abs(np.sin(5.0 * np.pi * (F[:, 0] - F[:, 1] + 1.0)))
        return -paper_c  # paper: c >= 0


class DCF8Base(DCFBase):
    """DCF8：真实 PF 始终位于振荡的动态约束边界。"""

    problem_number = 8
    constraint_count = 2

    def _evaluate_objectives(self, X, t):
        g = 1.0 + np.sum((X[:, 1:] - self._g(t)) ** 2, axis=1)
        return np.column_stack((g * X[:, 0], g * (1.0 - X[:, 0])))

    def _constraint_values(self, X, F, t):
        dynamic = self._g(t)
        w = np.floor(10.0 * abs(dynamic))
        c1 = F[:, 0] + F[:, 1] - 1.2 - 0.03 * np.sin(w * np.pi * F[:, 0])
        c2 = (F[:, 0] + F[:, 1] - 3.5) * (F[:, 0] + F[:, 1] - 2.2 - dynamic**2)
        return np.column_stack((-c1, -c2))  # paper: both >= 0


class DCF9Base(DCFBase):
    """DCF9：两组不可行带围绕目标点随时间旋转。"""

    problem_number = 9
    constraint_count = 2

    def _evaluate_objectives(self, X, t):
        g = 1.0 + np.sum((X[:, 1:] - self._g(t)) ** 2, axis=1)
        return np.column_stack((g * X[:, 0], g * (1.0 - X[:, 0])))

    def _constraint_values(self, X, F, t):
        w = 0.5 * np.pi * self._time(t)
        # The paper writes each T_i divided by sin(W)+cos(W).  Both products
        # contain the same denominator squared, so removing it preserves the
        # feasibility sign and remains well-defined when the denominator is 0.
        common = (
            (np.sin(w) - np.cos(w)) * F[:, 0]
            - (np.sin(w) + np.cos(w)) * F[:, 1]
            - 2.2 * (1.0 - np.cos(w))
        )
        values = [common + offset for offset in (1.3, 1.8, 2.6, 3.1)]
        return np.column_stack((-(values[0] * values[1]), -(values[2] * values[3])))


class DCF10Base(DCFBase):
    """DCF10：动态径向约束使 PF 在多段与连续形态间变化。"""

    problem_number = 10
    def _evaluate_objectives(self, X, t):
        y = X[:, 1:] - self._g(t)
        g = 1.0 + np.sum(y**2 - np.cos(np.pi * y) + 1.0, axis=1)
        return np.column_stack((g * X[:, 0], g * np.sqrt(np.maximum(0.0, 1.0 - X[:, 0] ** 2))))

    def _constraint_values(self, X, F, t):
        dynamic = abs(self._g(t))
        angle_wave = np.sin(8.0 * np.arctan2(F[:, 1], F[:, 0])) ** 12
        radius2 = F[:, 0] ** 2 + F[:, 1] ** 2
        t1 = radius2 - (1.4 + 0.5 * dynamic + (1.0 - dynamic) * angle_wave) ** 2
        t2 = radius2 - (1.4 - (1.0 - dynamic) * angle_wave) ** 2
        return -(t1 * t2)  # paper: c >= 0
