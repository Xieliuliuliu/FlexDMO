import numpy as np

from problems.Problem import Problem


class DF1(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'Dynamic')
        self.xl = np.array([0.0] * decision_num)  # 决策变量下界
        self.xu = np.array([1.0] * decision_num)  # 决策变量上界

    def _evaluate_objectives(self, X, t=None):
        times = t / self.n
        H = 0.75 * np.sin(0.5 * np.pi * times) + 1.25
        G = np.abs(np.sin(0.5 * np.pi * times))

        x0 = X[:, 0]
        g = 1 + np.sum((X[:, 1:] - G) ** 2, axis=1)
        f1 = x0
        f2 = g * (1 - (x0 / g) ** H)

        return np.column_stack([f1, f2])

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        H = 0.75 * np.sin(0.5 * np.pi * times) + 1.25

        f1 = np.linspace(0, 1, 1001)
        f2 = 1 - f1 ** H

        return np.column_stack([f1, f2])

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        G = np.abs(np.sin(0.5 * np.pi * times))

        size = 100
        PS = np.ones((size, self.decision_num)) * G
        PS[:, 0] = np.linspace(0, 1, size)

        return PS
