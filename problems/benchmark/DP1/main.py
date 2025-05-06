import numpy as np
from problems.Problem import Problem


class DP1(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'Dynamic')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        # 计算时间变量 t'
        times = t / self.n

        G = np.sin(0.5 * np.pi * times)
        a = 0.2 + 2.8 * np.abs(G)

        x0 = X[:, 0]
        y = X[:, 1:] - G
        g = 1 + np.sum((np.abs(G) * y ** 2 - 10 * np.cos(2 * np.pi * y) + 10), axis=1)

        f1 = g * (x0 + 0.1 * np.sin(3 * np.pi * x0)) ** a
        f2 = g * (1 - x0 + 0.1 * np.sin(3 * np.pi * x0)) ** a

        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        if t is None:
            t = self.t
        # 计算时间变量 t'
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        a = 0.2 + 2.8 * np.abs(G)

        f1 = np.linspace(0, 1, 1001)
        f1_mod = f1 + 0.1 * np.sin(3 * np.pi * f1)
        f2_mod = 1 - f1 + 0.1 * np.sin(3 * np.pi * f1)

        g = 1  # Pareto 前沿对应 g=1
        f1 = g * f1_mod ** a
        f2 = g * f2_mod ** a

        return np.column_stack([f1, f2])

    def get_pareto_set(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)

        size = 100
        PS = np.ones((size, self.decision_num)) * G
        PS[:, 0] = np.linspace(0, 1, size)

        return PS
