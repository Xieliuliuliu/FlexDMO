"""DCP 动态约束多目标测试套件的公共实现。

公式来源于 Chen 等人在 IEEE TEVC 2024 论文中给出的式 (14)-(22)。论文中的
约束同时使用 ``>= 0`` 与 ``<= 0`` 两种可行方向，而本项目的 ``Individual``、
约束支配关系及约束违反度计算统一约定为 ``G <= 0`` 可行，因此本模块会在
``_constraints_from_objectives`` 中把所有论文约束归一化到该约定。

实现分为三层：

1. ``_evaluate_objectives`` 精确实现九个问题的目标函数；
2. ``_constraints_from_objectives`` 精确实现目标空间约束；
3. ``_calculate_reference`` 在 ``(u, g)`` 参数空间构造真实受约束 PF，并将其
   映射回可供动态响应算法调用的代表性 PS。

论文中的连续动态时间记为 t；平台内部使用离散环境编号，所以公式实际使用
``time = environment_index / n``，其中 ``n`` 控制变化强度。

这里的 ``n`` 对应 MP-DFR 实验设置中的变化强度 ``n_t``，每个环境保持
``tau_t`` 代；不要把 ``n_t`` 与算法伪代码里的种群规模 ``N`` 混淆。
"""

from __future__ import annotations

import numpy as np

from problems.Problem import Problem


class DCPBase(Problem):
    """DCP1-DCP9 的共享基类。

    各子类只需要声明 ``problem_number``。问题的约束数量、变量边界、目标函数、
    动态参数及参考前沿生成均由该基类按编号分派，从而避免九份公式实现发生漂移。
    """

    problem_number: int | None = None
    # 依次对应论文 DCP1-DCP9 的约束数量。
    _constraint_counts = (1, 2, 3, 1, 2, 3, 1, 2, 2)
    # 这些问题只有 x1 属于 [0, 1]，其余变量属于 [-1, 1]。
    _mixed_bounds = {2, 5, 6, 7, 8}

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        if self.problem_number not in range(1, 10):
            raise TypeError("DCPBase must be subclassed with problem_number=1..9")
        if decision_num < 2:
            raise ValueError(f"DCP{self.problem_number} requires at least 2 decision variables")
        super().__init__(
            decision_num=decision_num,
            n_obj=2,
            n_con=self._constraint_counts[self.problem_number - 1],
            n=n,
            tau=tau,
            solution_num=solution_num,
            total_evaluate_time=total_evaluate_time,
            label="DynamicConstrained",
        )
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)
        if self.problem_number in self._mixed_bounds:
            self.xl[1:] = -1.0
        # 键为离散环境编号，值为同一环境下成对的 (PF, PS)。成对缓存可保证
        # get_pareto_front() 与 get_pareto_set() 返回的点严格一一对应。
        self._dcp_reference_cache: dict[int | float, tuple[np.ndarray, np.ndarray]] = {}

    def reset(self):
        """重置动态问题，同时清除各环境已经生成的参考 PF/PS。"""
        super().reset()
        self._dcp_reference_cache.clear()

    def _scaled_time(self, t):
        """把平台的离散环境编号转换为论文公式中的连续时间。"""
        return float(t) / self.n

    def _dynamic_g(self, t):
        """计算各测试问题在当前环境中的动态量 G(t)。

        DCP4 的约束严重度不是这里的 G，而是在其约束分支中按论文单独计算。
        """
        time = self._scaled_time(t)
        number = self.problem_number
        if number in (1, 3):
            return abs(np.sin(0.5 * np.pi * time))
        if number in (2, 4, 7, 8):
            return np.sin(0.5 * np.pi * time)
        if number == 5:
            return 0.5 * abs(np.sin(0.5 * np.pi * time))
        if number == 6:
            return np.sqrt(abs(np.sin(0.5 * np.pi * time)))
        return abs(np.sin(0.5 * np.pi * time))

    @staticmethod
    def _angle(f1, f2):
        # f1 is non-negative in this suite; arctan2 is the stable form of
        # arctan(f2/f1) used by the paper.
        return np.arctan2(f2, f1)

    def _primary_index(self, t):
        """返回决定前沿参数 u 的变量下标；仅 DCP9 会随环境移动。"""
        if self.problem_number != 9:
            return 0
        dynamic = self._dynamic_g(t)
        # The paper uses one-based r = 1 + floor((n-1)G).
        return min(self.decision_num - 1, int(np.floor((self.decision_num - 1) * dynamic)))

    def _evaluate_objectives(self, X, t=None):
        """批量计算目标矩阵，返回形状为 ``(样本数, 2)`` 的数组。

        这里保留论文中的 1-based 变量含义：代码中的 ``u`` 对应论文的 x1；
        DCP9 则对应动态选择的 xr。其余变量主要通过距离函数 g 控制收敛难度。
        """
        if t is None:
            t = self.t
        number = self.problem_number
        dynamic = self._dynamic_g(t)

        # DCP9 的前沿控制变量 xr 随 G 从 x1 移动到 xn，故需先排除 xr，
        # 再对剩余 n-1 个变量计算距离函数 g。
        if number == 9:
            primary = self._primary_index(t)
            mask = np.ones(self.decision_num, dtype=bool)
            mask[primary] = False
            g = 1.0 + 10.0 * np.sum((X[:, mask] - dynamic) ** 2, axis=1)
            u = X[:, primary]
            return np.column_stack((g * u, g * (1.0 - u)))

        u = X[:, 0]
        tail = X[:, 1:]
        # DCP1-DCP8 均由 x1 参数化原始前沿，但距离函数与波形各不相同。
        if number == 1:
            g = 1.0 + np.sum((tail - dynamic) ** 2, axis=1)
            return np.column_stack((g * u + dynamic, g * (1.0 - u) + dynamic))
        if number == 2:
            delta = tail - dynamic
            g = 1.0 + np.sum(delta**2 + np.sin(0.5 * np.pi * delta) ** 2, axis=1)
            wave = 0.25 * dynamic * np.sin(np.pi * u)
            return np.column_stack((g * (u + wave), g * (1.0 - u + wave)))
        if number == 3:
            g = 1.0 + np.sum(np.sqrt(np.abs(tail - dynamic)), axis=1)
            return np.column_stack((g * u + dynamic**2, g * (1.0 - u) + dynamic**2))
        if number == 4:
            term = (tail - 0.5) ** 2 - np.cos(np.pi * (tail - 0.5)) + 1.0
            g = 1.0 + np.sum(term**2, axis=1)
            wave = 0.25 * np.sin(np.pi * u)
            return np.column_stack((g * (u + wave), g * (1.0 - u + wave)))
        if number == 5:
            target = 0.5 * np.sin(2.0 * np.pi * u)
            g = 1.0 + np.sum(np.abs(tail - target[:, None]), axis=1)
            return np.column_stack((g * u, g * (1.0 - u)))
        if number == 6:
            g = 1.0 + 6.0 * np.sum(tail**2, axis=1)
            return np.column_stack((g * u, g * (1.0 - u)))
        if number == 7:
            g = 1.0 + np.sum((tail - dynamic) ** 2, axis=1)
            frequency = 10.0 - np.floor(abs(10.0 * dynamic))
            wave = 0.02 * np.sin(frequency * np.pi * u)
            return np.column_stack((g * (u + wave), g * (1.0 - u + wave)))
        if number == 8:
            delta = tail - dynamic
            term = abs(dynamic) * delta**2 - np.cos(np.pi * delta) + 1.0
            g = 1.0 + np.sum(term**2, axis=1)
            return np.column_stack((g * u, g * (1.0 - u)))
        raise AssertionError("unreachable")

    def _constraints_from_objectives(self, F, t):
        """计算归一化后的约束矩阵。

        参数 ``F`` 是目标矩阵而不是决策矩阵，因为论文的全部 DCP 约束都定义
        在目标空间。每个返回值都遵循 ``<= 0`` 可行；论文中原本为 ``>= 0``
        的表达式会乘以 -1。这样现有算法无需任何 DCP 特判。
        """
        number = self.problem_number
        dynamic = self._dynamic_g(t)
        f1, f2 = F[:, 0], F[:, 1]
        angle = self._angle(f1, f2)

        if number == 1:
            # 先将目标坐标旋转 -0.15*pi，再用六次正弦形成多个断裂可行段。
            rotation = -0.15 * np.pi
            lhs = np.cos(rotation) * f2 - np.sin(rotation) * f1
            coordinate = np.sin(rotation) * f2 + np.cos(rotation) * f1
            rhs = (2.0 * np.sin(5.0 * np.pi * coordinate)) ** 6
            return (rhs - lhs)[:, None]
        if number == 2:
            c1 = -(4.0 * f1 + f2 - 1.0) * (0.3 * f1 + f2 - 0.3)
            c2 = (
                1.85 - f1 - f2 - (0.3 * np.sin(3.0 * np.pi * (f2 - f1))) ** 2
            ) * (f1 + f2 - 1.3)
            return np.column_stack((c1, c2))
        if number == 3:
            # 两个小圆、一个外圆和带角度扰动的环共同形成小型可行区域。
            c1 = -(
                ((f1 - 1.0) ** 2 + (f2 - 0.2) ** 2 - 0.3**2)
                * ((f1 - 0.2) ** 2 + (f2 - 1.0) ** 2 - 0.3**2)
            )
            c2 = f1**2 + f2**2 - 4.0**2
            c3 = -(
                (f1**2 + f2**2 - (3.1 + 0.2 * np.sin(4.0 * angle) ** 2) ** 2)
                * (f1**2 + f2**2 - 2.3**2)
            )
            return np.column_stack((c1, c2, c3))
        if number == 4:
            # 论文中的阶梯变化参数：在每个 0.1 时间单位改变正弦波频率。
            time = self._scaled_time(t)
            severity = 2.0 * np.floor(10.0 * abs(((time + 1.0) % 2.0) - 1.0))
            inner = f1**2 + f2**2 - (
                1.3 - 0.45 * np.sin(severity * angle) ** 2
            ) ** 2
            outer = f1**2 + f2**2 - (
                1.5 + 0.4 * np.sin(4.0 * angle) ** 16
            ) ** 2
            return (-(inner * outer))[:, None]
        if number == 5:
            c1 = -(
                ((0.2 + dynamic) * f1**2 + f2 - 2.0)
                * (0.7 * f1**2 + f2 - 2.5)
            )
            c2 = -(f1**2 + f2**2 - (0.6 + dynamic) ** 2)
            return np.column_stack((c1, c2))
        if number == 6:
            # c2 是旋转椭圆外部约束；分母可能很小，但 G>=0 保证其非零。
            c1 = f1 + f2 - (
                4.5 + 0.08 * np.sin(2.0 * np.pi * (f2 - f1 / 1.6))
            )
            rotation = -np.pi / 4.0
            rotated_1 = f1 * np.cos(rotation) - f2 * np.sin(rotation)
            rotated_2 = f1 * np.sin(rotation) + f2 * np.cos(rotation)
            ellipse = rotated_1**2 / 1.1**2 + rotated_2**2 / (0.1 + dynamic) ** 2
            c2 = (0.1 + dynamic) ** 2 - ellipse
            first = f1 + f2 - (
                3.2 - dynamic - 0.08 * np.sin(2.0 * np.pi * (f2 - f1 / 1.5))
            )
            second = f1 + f2 - (
                2.0 - 0.08 * np.sin(2.0 * np.pi * (f2 - f1 / 1.5))
            )
            c3 = -(first * second)
            return np.column_stack((c1, c2, c3))
        if number == 7:
            c = f1 + f2 - dynamic - np.sin(5.0 * np.pi * (f1 - f2 + 1.0)) ** 2
            return (-c)[:, None]
        if number == 8:
            # DCP8 在 t=0 时会覆盖整个原始 PF，真实 PF 因而落到约束边界上。
            c1 = -(
                (np.sqrt(np.maximum(f1, 0.0)) + np.sqrt(np.maximum(f2, 0.0)) - 0.95 - 0.5 * abs(dynamic))
                * (f1**1.5 + f2**1.5 - 1.2**1.5)
            )
            c2 = -(
                (0.8 * f1 + f2 - (2.5 + 0.08 * np.sin(2.0 * np.pi * (f2 - f1))))
                * (
                    (0.93 + abs(dynamic) / 3.0) * f1
                    + f2
                    - (2.7 + 0.5 * abs(dynamic) + 0.08 * np.sin(2.0 * np.pi * (f2 - f1)))
                )
            )
            return np.column_stack((c1, c2))
        if number == 9:
            # h 控制第一条幂函数边界，第二条约束产生多个狭窄不可行区域。
            h = 0.75 + 1.25 * dynamic
            radius = f1**2 + f2**2
            c1 = (f1**h + f2**h - 4.0**h) * (radius - (0.2 + dynamic) ** 2)
            angular = 6.0 * angle**3
            first_denominator = 1.0 + 0.15 * np.cos(angular) ** 10
            second_denominator = 1.0 + 0.75 * np.cos(angular) ** 10
            c2 = (
                2.1
                - (f1 / first_denominator) ** 2
                - (f2 / second_denominator) ** 2
            ) * (radius - 1.6**2)
            return np.column_stack((c1, c2))
        raise AssertionError("unreachable")

    def _evaluate_constraints(self, X, t=None):
        """从决策向量求目标后计算约束；返回列数等于 ``n_con``。"""
        if t is None:
            t = self.t
        return self._constraints_from_objectives(self._evaluate_objectives(X, t), t)

    def _objectives_from_u_g(self, u, g, t):
        """用 ``(u, g)`` 参数化目标空间，供参考 PF 搜索使用。

        ``u`` 是原始前沿的位置参数，``g=1`` 是无约束原始 PF。允许 ``g>1``
        很重要：若约束覆盖原始 PF（例如 DCP8），真实受约束 PF 会位于 ``g>1``
        的约束边界，单纯过滤 ``g=1`` 的点会错误地得到空前沿。
        """
        number = self.problem_number
        dynamic = self._dynamic_g(t)
        if number == 1:
            return np.column_stack((g * u + dynamic, g * (1.0 - u) + dynamic))
        if number in (2, 4):
            amplitude = 0.25 * (dynamic if number == 2 else 1.0)
            wave = amplitude * np.sin(np.pi * u)
            return np.column_stack((g * (u + wave), g * (1.0 - u + wave)))
        if number == 3:
            return np.column_stack((g * u + dynamic**2, g * (1.0 - u) + dynamic**2))
        if number == 7:
            frequency = 10.0 - np.floor(abs(10.0 * dynamic))
            wave = 0.02 * np.sin(frequency * np.pi * u)
            return np.column_stack((g * (u + wave), g * (1.0 - u + wave)))
        return np.column_stack((g * u, g * (1.0 - u)))

    @staticmethod
    def _nondominated_indices(F):
        """以 ``O(N log N)`` 返回双目标最小化问题的非支配点下标。

        候选点先按 f1、f2 排序，随后只保留严格降低当前最小 f2 的点。相比项目
        通用的两两支配检查，该实现适合参考前沿生成时的数万候选点。
        """
        if len(F) == 0:
            return np.empty(0, dtype=int)
        order = np.lexsort((F[:, 1], F[:, 0]))
        sorted_f2 = F[order, 1]
        # 若当前 f2 严格小于此前所有点的最小 f2，则不存在同时不劣于它的
        # 已排序点。lexsort 会把相同 f1 中的最小 f2 放在最前，后续重复点也会
        # 自然被累计最小值过滤。全向量实现可避免动画首次计算时的 Python 循环。
        previous_best = np.concatenate(
            ([np.inf], np.minimum.accumulate(sorted_f2[:-1]))
        )
        return order[sorted_f2 < previous_best - 1e-12]

    def _repeat_value_for_g(self, u, target_g, t):
        """求一个共享尾变量值，使决策向量尽量实现指定的 ``target_g``。

        具有平方或绝对值距离的 DCP 使用解析逆映射；DCP2、DCP4、DCP8 的
        距离项非单调，因此在合法变量区间上使用一维细网格寻找最近值。
        """
        number = self.problem_number
        dynamic = self._dynamic_g(t)
        count = self.decision_num - 1
        desired = max(0.0, target_g - 1.0)

        if number == 1:
            displacement = np.sqrt(desired / count)
            center, lower, upper = dynamic, 0.0, 1.0
        elif number == 3:
            displacement = (desired / count) ** 2
            center, lower, upper = dynamic, 0.0, 1.0
        elif number == 5:
            displacement = desired / count
            center, lower, upper = 0.5 * np.sin(2.0 * np.pi * u), -1.0, 1.0
        elif number == 6:
            displacement = np.sqrt(desired / (6.0 * count))
            center, lower, upper = 0.0, -1.0, 1.0
        elif number == 7:
            displacement = np.sqrt(desired / count)
            center, lower, upper = dynamic, -1.0, 1.0
        elif number == 9:
            displacement = np.sqrt(desired / (10.0 * count))
            center, lower, upper = dynamic, 0.0, 1.0
        else:
            lower, upper = (-1.0, 1.0) if number in (2, 8) else (0.0, 1.0)
            grid = np.linspace(lower, upper, 1001)
            if number == 2:
                delta = grid - dynamic
                values = count * (delta**2 + np.sin(0.5 * np.pi * delta) ** 2)
            elif number == 4:
                term = (grid - 0.5) ** 2 - np.cos(np.pi * (grid - 0.5)) + 1.0
                values = count * term**2
            else:  # DCP8
                delta = grid - dynamic
                term = abs(dynamic) * delta**2 - np.cos(np.pi * delta) + 1.0
                values = count * term**2
            return float(grid[np.argmin(np.abs(values - desired))])

        plus_room = upper - center
        minus_room = center - lower
        sign = 1.0 if plus_room >= minus_room else -1.0
        if displacement > max(plus_room, minus_room):
            displacement = max(plus_room, minus_room)
        return float(np.clip(center + sign * displacement, lower, upper))

    def _decisions_from_u_g(self, u, g, t):
        """把目标空间参数批量映射为合法决策向量，作为代表性 Pareto Set。"""
        decisions = np.empty((len(u), self.decision_num), dtype=float)
        primary = self._primary_index(t)
        dynamic = self._dynamic_g(t)
        for row, (parameter, target_g) in enumerate(zip(u, g)):
            repeated = self._repeat_value_for_g(parameter, target_g, t)
            decisions[row, :] = repeated
            decisions[row, primary] = parameter
            if self.problem_number == 9:
                # All non-primary variables minimize g at G before displacement.
                decisions[row, :] = repeated
                decisions[row, primary] = parameter
            elif primary != 0:
                decisions[row, 0] = dynamic
        return np.clip(decisions, self.xl, self.xu)

    def _calculate_reference(self, t):
        """构造当前环境的受约束参考 PF 以及与之对应的 PS。

        步骤如下：

        1. 在 u 方向均匀采样原始前沿位置；
        2. 在 g 方向使用二次间距，使 g=1 附近的约束边界更密；
        3. 过滤不可行点并执行双目标非支配筛选；
        4. 将保留点映射回决策空间，再次用真实目标/约束公式复核；
        5. 缓存复核后的 PF/PS，供 IGD、动态响应和批处理绘图共同使用。
        """
        if t in self._dcp_reference_cache:
            return self._dcp_reference_cache[t]

        u_values = np.linspace(0.0, 1.0, 401)
        # Quadratic spacing resolves constraint boundaries near the original PF.
        g_values = 1.0 + 5.0 * np.linspace(0.0, 1.0, 201) ** 2
        u_grid, g_grid = np.meshgrid(u_values, g_values, indexing="xy")
        flat_u, flat_g = u_grid.ravel(), g_grid.ravel()
        candidates = self._objectives_from_u_g(flat_u, flat_g, t)
        constraints = self._constraints_from_objectives(candidates, t)
        feasible = np.all(constraints <= 1e-10, axis=1) & np.all(np.isfinite(candidates), axis=1)
        feasible_indices = np.flatnonzero(feasible)
        if len(feasible_indices) == 0:
            raise RuntimeError(f"DCP{self.problem_number} produced no feasible PF candidates at t={t}")

        front_local = self._nondominated_indices(candidates[feasible_indices])
        selected = feasible_indices[front_local]
        if len(selected) > 800:
            selected = selected[np.linspace(0, len(selected) - 1, 800, dtype=int)]

        decisions = self._decisions_from_u_g(flat_u[selected], flat_g[selected], t)
        objectives = self._evaluate_objectives(decisions, t)
        decision_constraints = self._evaluate_constraints(decisions, t)
        valid = np.all(decision_constraints <= 1e-6, axis=1) & np.all(np.isfinite(objectives), axis=1)
        decisions, objectives = decisions[valid], objectives[valid]
        final = self._nondominated_indices(objectives)
        decisions, objectives = decisions[final], objectives[final]
        if len(objectives) == 0:
            raise RuntimeError(f"DCP{self.problem_number} reference PF mapping failed at t={t}")

        self._dcp_reference_cache[t] = (objectives, decisions)
        return objectives, decisions

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t
        return self._calculate_reference(t)[0]

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        return self._calculate_reference(t)[1]

    def get_original_pareto_front(self, t=None, point_count=801):
        """返回未施加约束时的原始 PF，主要用于 Benchmark 可视化。

        原始 PF 对应距离函数的全局最小值 ``g=1``。它与
        :meth:`get_pareto_front` 返回的真实受约束 PF 不同：原始 PF 上的一部分
        甚至全部点都可能不可行。
        """
        if t is None:
            t = self.t
        u = np.linspace(0.0, 1.0, point_count)
        return self._objectives_from_u_g(u, np.ones_like(u), t)

    def get_objective_visualization_bounds(self):
        """返回与论文图示尺度相近的固定目标空间范围。

        动画播放期间保持范围固定，避免自动缩放造成“前沿在移动”的视觉假象。
        """
        upper_bounds = {
            1: 2.2,
            2: 2.0,
            3: 4.2,
            4: 2.2,
            5: 3.2,
            6: 5.0,
            7: 2.2,
            8: 3.3,
            9: 4.2,
        }
        upper = upper_bounds[self.problem_number]
        return (0.0, upper), (0.0, upper)

    def get_objective_space_regions(self, t=None, resolution=260):
        """采样目标空间并返回可行/不可行区域掩码。

        Returns:
            ``(f1_grid, f2_grid, feasible_mask)``。三个数组形状均为
            ``(resolution, resolution)``；掩码为 True 的网格点满足全部约束。

        Notes:
            DCP 的约束只依赖目标值，因此可以直接在目标空间准确分类，而无需
            先运行优化算法或从种群近似可行域。
        """
        if t is None:
            t = self.t
        if resolution < 20:
            raise ValueError("resolution must be at least 20")
        (f1_min, f1_max), (f2_min, f2_max) = self.get_objective_visualization_bounds()
        f1_values = np.linspace(f1_min, f1_max, resolution)
        f2_values = np.linspace(f2_min, f2_max, resolution)
        f1_grid, f2_grid = np.meshgrid(f1_values, f2_values)
        points = np.column_stack((f1_grid.ravel(), f2_grid.ravel()))
        constraints = self._constraints_from_objectives(points, t)
        feasible = np.all(constraints <= 0.0, axis=1).reshape(f1_grid.shape)
        return f1_grid, f2_grid, feasible
