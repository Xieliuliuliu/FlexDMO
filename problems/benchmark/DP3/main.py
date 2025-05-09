import numpy as np
from problems.Problem import Problem


class DP3(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP3')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # 动态参数计算
        times = t / self.n
        k = 10 * np.cos(2.5 * np.pi * times)
        a = 0.5 * np.abs(np.sin(np.pi * times))

        # g 函数
        y = X[:, 1:] - 0.5
        g = np.sum((y ** 2) * (1 + np.abs(np.cos(8 * np.pi * X[:, 1:]))), axis=1)

        x0 = X[:, 0]
        f1 = (1 + g) * np.cos(0.5 * np.pi * x0)

        # f2 分段计算
        f2 = np.zeros_like(f1)
        mask = x0 <= a
        f2[mask] = (1 + g[mask]) * np.abs(k * np.cos(0.5 * np.pi * x0[mask]) - np.cos(0.5 * np.pi * a) + np.sin(0.5 * np.pi * a))
        f2[~mask] = (1 + g[~mask]) * np.sin(0.5 * np.pi * x0[~mask])

        return np.column_stack([f1, f2])

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t

        times = t / self.n
        k = 10 * np.cos(2.5 * np.pi * times)
        a = 0.5 * np.abs(np.sin(np.pi * times))
        g = 0  # PF 时 g=0

        x = np.linspace(0, 1, 1500)
        f1 = (1 + g) * np.cos(0.5 * np.pi * x)

        f2 = np.zeros_like(f1)
        mask = x <= a
        f2[mask] = (1 + g) * np.abs(k * np.cos(0.5 * np.pi * x[mask]) - np.cos(0.5 * np.pi * a) + np.sin(0.5 * np.pi * a))
        f2[~mask] = (1 + g) * np.sin(0.5 * np.pi * x[~mask])

        return self.get_nondominate([f1, f2])

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n

        size = 100
        PS = np.ones((size, self.decision_num)) * 0.5  # 其他变量保持在0.5
        PS[:, 0] = np.linspace(0, 1, size)

        return PS