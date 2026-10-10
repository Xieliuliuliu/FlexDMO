import numpy as np
from problems.Problem import Problem


class DP4(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP4')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)
        self.xl[1:] = -1  # 第一个变量范围是[0,1]，其他变量范围是[-1,1]
        self.xu[1:] = 1

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # 计算 time
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        k = 2 * np.floor(10 * np.abs(G))

        x0 = X[:, 0]
        y = X[:, 1:] - G
        g = np.sum((4 * y**2 - np.cos(k * np.pi * y) + 1), axis=1)

        f1 = (1 + g) * (x0 + 0.1 * np.sin(3 * np.pi * x0))
        f2 = (1 + g) * (1 - x0 + 0.1 * np.sin(3 * np.pi * x0))

        return np.column_stack([f1, f2])

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        x = np.linspace(0, 1, 1500)
        g = 0  # PF 时 g=0
        f1 = (1 + g) * (x + 0.1 * np.sin(3 * np.pi * x))
        f2 = (1 + g) * (1 - x + 0.1 * np.sin(3 * np.pi * x))
        return np.column_stack([f1, f2])

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        x0_values = np.linspace(0, 1, 100)
        # 构造决策变量矩阵X：x0变化，其他变量固定为G
        X = np.zeros((100, self.decision_num))
        X[:, 0] = x0_values
        X[:, 1:] = G  # 其他变量设为当前G值
        return X