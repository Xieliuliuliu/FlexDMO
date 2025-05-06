import numpy as np

from problems.Problem import Problem


class DP9(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP9')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        if t is None: t = self.t
        times = t / self.n

        G = np.sin(0.5 * np.pi * times)
        W = 10 ** (1 + np.abs(G))

        x0 = X[:, 0]
        other_vars = X[:, 1:]

        g = np.sum((other_vars - G) ** 2, axis=1)
        sin_term = 0.05 * np.sin(W * np.pi * x0)

        f1 = (1 + g) * (x0 + sin_term)
        f2 = (1 + g) * (1 - x0 + sin_term)
        f2 = np.where(f2<1e-6,0,f2)
        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        if t is None: t = self.t
        x = np.linspace(0, 1, 1500)
        G = np.sin(0.5 * np.pi * t / self.n)
        W = 10 ** (1 + np.abs(G))
        sin_term = 0.05 * np.sin(W * np.pi * x)
        return np.column_stack([x + sin_term, 1 - x + sin_term])

    def get_pareto_set(self, t=None):
        if t is None: t = self.t
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        PS = np.full((1500, self.decision_num), G)
        PS[:, 0] = np.linspace(0, 1, 1500)
        return PS