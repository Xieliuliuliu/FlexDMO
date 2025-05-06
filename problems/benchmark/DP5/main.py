import numpy as np
from problems.Problem import Problem


class DP5(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP5')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # 计算动态参数
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        a = 0.2 + 2.8 * np.abs(G)  # DP3特有的形状参数

        x0 = X[:, 0]
        y = X[:, 1:] - G

        # 计算g函数（Rastrigin形式）
        g = np.sum(y ** 2 - 10 * np.cos(2 * np.pi * y) + 10, axis=1)

        # 计算目标函数（增加指数项）
        base_f1 = x0 + 0.1 * np.sin(3 * np.pi * x0)
        base_f2 = 1 - x0 + 0.1 * np.sin(3 * np.pi * x0)

        f1 = (1 + g) * (base_f1 ** a)
        f2 = (1 + g) * (base_f2 ** a)

        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        if t is None:
            t = self.t

        # 生成理想帕累托前沿
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        a = 0.2 + 2.8 * np.abs(G)

        # 构造最优解集
        x0_values = np.linspace(0, 1, 1001)
        X = np.zeros((1001, self.decision_num))
        X[:, 0] = x0_values
        X[:, 1:] = G

        # 计算目标值（此时g=0）
        base_f1 = x0_values + 0.1 * np.sin(3 * np.pi * x0_values)
        base_f2 = 1 - x0_values + 0.1 * np.sin(3 * np.pi * x0_values)

        f1 = base_f1 ** a
        f2 = base_f2 ** a

        return np.column_stack([f1, f2])

    def get_pareto_set(self, t=None):
        if t is None:
            t = self.t

        times = t / self.n
        G = np.sin(0.5 * np.pi * times)

        # 生成帕累托最优解集
        x0_values = np.linspace(0, 1, 100)
        X = np.zeros((100, self.decision_num))
        X[:, 0] = x0_values
        X[:, 1:] = G  # 其他变量保持最优值

        return X