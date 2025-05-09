import numpy as np
from problems.Problem import Problem


class DP2(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP2')
        # 第一个变量在[0,1]，其他变量在[-1,1]
        self.xl = np.array([0.0] + [-1.0] * (decision_num - 1))
        self.xu = np.array([1.0] + [1.0] * (decision_num - 1))

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

            # 计算时间变量 t'
        times = t / self.n

        p = np.floor(5 * np.abs(np.sin(np.pi * times)))
        y = X[:, 1:] - np.cos(times)
        g = np.sum((4 * y ** 2 - np.cos(2 * p * np.pi * y) + 1), axis=1)

        f1 = (1 + g) * (1 - X[:, 0] + 0.05 * np.sin(6 * np.pi * X[:, 0]))
        f2 = (1 + g) * (X[:, 0] + 0.05 * np.sin(6 * np.pi * X[:, 0]))
        f1 = np.where(f1 < 1e-3, 0.0, f1)
        return np.column_stack([f1, f2])

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t

        # 生成决策变量
        x = np.linspace(0, 1, 1500)
        
        # 计算目标函数值
        g = 0  # Pareto 前沿对应 g=0
        f1 = (1 + g) * (1 - x + 0.05 * np.sin(6 * np.pi * x))
        f2 = (1 + g) * (x + 0.05 * np.sin(6 * np.pi * x))

        return np.column_stack([f1, f2])

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n

        size = 100
        PS = np.ones((size, self.decision_num)) * np.cos(times)
        PS[:, 0] = np.linspace(0, 1, size)

        return PS