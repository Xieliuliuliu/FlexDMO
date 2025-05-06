import numpy as np

from problems.Problem import Problem


class DP8(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP8')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t
        times = t / self.n
        N = 1 + np.floor(10 * np.abs(np.sin(0.5 * np.pi * times)))

        # g 函数计算（链式）
        g = np.ones(X.shape[0])
        prev_term = X[:, 0]
        for i in range(1, self.decision_num):
            tmp = X[:, i] - np.cos(4 * times + X[:, 0] + prev_term)
            g += tmp ** 2
            prev_term = X[:, i]

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
        return np.column_stack([x + sin_term, 1 - x + sin_term])

    def get_pareto_set(self, t=None):
        PS = np.zeros((1500, self.decision_num))
        PS[:, 0] = np.linspace(0, 1, 1500)
        if t is not None:
            times = t / self.n
            prev_term = PS[:, 0]
            for i in range(1, self.decision_num):
                PS[:, i] = np.cos(4 * times + PS[:, 0] + prev_term)
                prev_term = PS[:, i]
        return PS
