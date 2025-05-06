import numpy as np
from problems.Problem import Problem


class DP2(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP2')
        self.xl = -1 * np.ones(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # 时间标准化处理
        times = t / self.n
        # 计算动态参数
        G = np.cos(np.pi* times)  # 余弦型环境变化
        k = np.floor(5 * np.abs(np.sin(np.pi * times)))  # 震荡频率参数

        x0 = X[:, 0]
        y = X[:, 1:] - G  # 计算变量偏移量

        # 计算g函数（改进的震荡函数）
        g_terms = 4 * y ** 2 - np.cos(2 * k * np.pi * y) + 1
        g = np.sum(g_terms, axis=1)

        # 计算目标函数（反向线性关系）
        term1 = 1 - x0 + 0.05 * np.sin(6 * np.pi * x0)
        term2 = x0 + 0.05 * np.sin(6 * np.pi * x0)

        f1 = (1 + g) * term1
        f1 = np.where(f1 < 1e-3, 0.0, f1)  # 向量化截断
        f2 = (1 + g) * term2

        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        x0 = np.linspace(0.0, 1.0, 1001)

        f1 = 1.0 - x0 + 0.05 * np.sin(6.0 * np.pi * x0)

        f2 = x0 + 0.05 * np.sin(6.0 * np.pi * x0)

        return np.column_stack((f1, f2))

    def get_pareto_set(self, t=None):
        if t is None:
            t = self.t

        times = t / self.n
        G = np.cos(np.pi* times)  # 当前最优参数

        # 构造帕累托最优解集
        x0_values = np.linspace(0, 1, 100)
        X = np.zeros((100, self.decision_num))
        X[:, 0] = x0_values
        X[:, 1:] = G  # 其他变量保持最优值

        return X