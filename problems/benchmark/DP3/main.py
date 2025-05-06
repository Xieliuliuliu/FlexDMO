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
        # 时间标准化处理
        times = t / self.n
        # 动态参数
        k = 10.0 * np.cos(2.5 * np.pi * times)
        a = 0.5 * np.abs(np.sin(np.pi * times))

        x0 = X[:, 0]
        other_vars = X[:, 1:]

        # 输入验证（可选）
        assert np.all(X >= 0) and np.all(X <= 1), f"决策变量越界: {X}"

        # 正确的 g 计算（作用在 x[1:] 上）
        g = np.sum((other_vars - 0.5) ** 2 * (1.0 + np.abs(np.cos(8.0 * np.pi * other_vars))), axis=1)

        # f1 = (1 + g) * cos(0.5 * pi * x0)
        f1 = (1.0 + g) * np.cos(0.5 * np.pi * x0)

        # f2 条件分支处理（注意：k * (cos(x0) - cos(a))）
        term1 = np.abs(k * (np.cos(0.5 * np.pi * x0) - np.cos(0.5 * np.pi * a))) + np.sin(0.5 * np.pi * a)
        term2 = np.sin(0.5 * np.pi * x0)
        f2 = (1.0 + g) * np.where(x0 <= a, term1, term2)  # 注意用 <=

        return np.column_stack((f1, f2))

    def get_pareto_front(self, t=None):
        if t is None:
            t = self.t
        # 时间标准化处理
        times = t / self.n
        k = 10.0 * np.cos(2.5 * np.pi *times)
        a = 0.5 * np.abs(np.sin(np.pi * times))

        x0 = np.linspace(0.0, 1.0, 1500)
        f1 = np.cos(0.5 * np.pi * x0)

        # 分段定义 f2，根据 x <= a（注意这里用 <=）
        term1 = np.abs(k * np.cos(0.5 * np.pi * x0) - np.cos(0.5 * np.pi * a)) + np.sin(0.5 * np.pi * a)
        term2 = np.sin(0.5 * np.pi * x0)
        f2 =  np.where(x0 <= a, term1, term2)  # 注意 <=

        return np.column_stack((f1, f2))

    def get_pareto_set(self, t=None):
        PS = np.empty((100, self.decision_num))
        PS[:, 0] = np.linspace(0.0, 1.0, 100)
        if self.decision_num > 1:
            PS[:, 1:] = 0.5
        return PS