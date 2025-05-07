import numpy as np
from problems.Problem import Problem


class DP6(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP6')
        # 设置决策变量范围：第一个变量在[0,1]，其他在[-1,1]
        self.xl = np.array([0.0] + [-1.0] * (decision_num - 1))
        self.xu = np.array([1.0] + [1.0] * (decision_num - 1))

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # 动态参数计算
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)  # 环境参数
        w = np.floor(10 * G)  # 震荡频率参数

        x0 = X[:, 0]  # 第一维决策变量
        other_vars = X[:, 1:]  # 其他维度变量

        # 计算g函数（带动态偏移）
        g = 1 + np.sum((other_vars - G) ** 2, axis=1)

        # 计算目标函数（带频率调制震荡项）
        sin_term = 0.02 * np.sin(w * np.pi * x0)
        f1 = g * (x0 + sin_term)
        f2 = g * (1 - x0 + sin_term)
        f2 = np.where(f2<1e-6, 0, f2)
        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        if t is None:
            t = self.t

        # 生成理想帕累托前沿
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        w = np.floor(10 * G)

        x = np.linspace(0, 1, 1500)  # 高密度采样
        g = 1  # 在帕累托前沿上，其他变量都等于G，所以g=1
        sin_term = 0.02 * np.sin(w * np.pi * x)
        f1 = g * (x + sin_term)
        f2 = g * (1 - x + sin_term)
        return np.column_stack([f1, f2])

    def get_pareto_set(self, t=None):
        if t is None:
            t = self.t

        # 构造动态帕累托最优解集
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)

        PS = np.full((1500, self.decision_num), G)  # 所有维度初始化为G
        PS[:, 0] = np.linspace(0, 1, 1500)  # 第一维均匀分布
        return PS