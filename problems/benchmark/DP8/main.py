import numpy as np

from problems.Problem import Problem


class DP8(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP8')
         # 设置决策变量范围：第一个变量在[0,1]，其他在[-1,1]
        self.xl = np.array([0.0] + [-1.0] * (decision_num - 1))
        self.xu = np.array([1.0] + [1.0] * (decision_num - 1))

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        N = 1 + np.floor(10 * np.abs(np.sin(0.5 * np.pi * times)))

        # g 函数计算
        g = np.ones(X.shape[0])
        for i in range(1, self.decision_num):
            tmp = X[:, i] - np.cos(4 * times + X[:, 0] + X[:, i-1])
            g += tmp ** 2

        x0 = X[:, 0]
        sin_term = np.maximum(0, (0.1 + 0.5 / N) * np.sin(2 * N * np.pi * x0))

        f1 = g * (x0 + sin_term)
        f2 = g * (1 - x0 + sin_term)
        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        if t is None:
            t = self.t
        x = np.linspace(0, 1, 1500)
        N = 1 + np.floor(10 * np.abs(np.sin(0.5 * np.pi * t / self.n)))
        sin_term = np.maximum(0, (0.1 + 0.5 / N) * np.sin(2 * N * np.pi * x))
        g = 1  # 在帕累托前沿上 g=1
        f1 = g * (x + sin_term)
        f2 = g * (1 - x + sin_term)
        return self.get_nondominate([f1, f2])

    def get_pareto_set(self, t=None):
        PS = np.zeros((1500, self.decision_num))
        PS[:, 0] = np.linspace(0, 1, 1500)  # 第一维在[0,1]均匀分布
        if t is not None:
            times = t / self.n
            for i in range(1, self.decision_num):
                PS[:, i] = np.cos(4 * times + PS[:, 0] + PS[:, i-1])  # 直接使用前一维的值
        return PS
