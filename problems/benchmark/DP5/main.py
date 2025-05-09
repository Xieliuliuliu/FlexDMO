import numpy as np
from problems.Problem import Problem


class DP5(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP5')
        # 设置决策变量范围：第一个变量在[0,1]，其他在[-1,1]
        self.xl = np.array([0.0] + [-1.0] * (decision_num - 1))
        self.xu = np.array([1.0] + [1.0] * (decision_num - 1))

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

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t

        # 生成理想帕累托前沿
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        a = 0.2 + 2.8 * np.abs(G)

        # 构造决策变量
        x = np.linspace(0, 1, 1500)
        g = 0  # 在帕累托前沿上 g = 0

        # 计算目标值
        f1 = (1 + g) * (x + 0.1 * np.sin(3 * np.pi * x)) ** a
        f2 = (1 + g) * (1 - x + 0.1 * np.sin(3 * np.pi * x)) ** a

        return np.column_stack([f1, f2])

    def _calculate_pareto_set(self, t=None):
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