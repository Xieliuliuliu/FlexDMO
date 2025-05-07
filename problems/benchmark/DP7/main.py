import numpy as np
from problems.Problem import Problem


class DP7(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP7')
        # 设置决策变量范围：第一个变量在[0,1]，其他在[-1,1]
        self.xl = np.array([0.0] + [-1.0] * (decision_num - 1))
        self.xu = np.array([1.0] + [1.0] * (decision_num - 1))

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # ===== 动态参数计算 =====
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)  # 基础环境参数
        a = 2.25 + 2 * np.cos(2 * np.pi * times)  # 指数形状参数

        # ===== 变量分解 =====
        x0 = X[:, 0]  # 第一决策变量
        other_vars = X[:, 1:]  # 其他决策变量

        # ===== 计算中间量tmp =====
        tmp = G * np.sin(4 * np.pi * x0) / (1 + np.abs(G))  # 动态偏移量（与x0相关）

        # ===== 计算g函数 =====
        g = 1 + np.sum((other_vars - tmp[:, np.newaxis]) ** 2, axis=1)  # 维度对齐

        # ===== 目标函数计算 =====
        f1 = g * (x0 + 0.1 * np.sin(3 * np.pi * x0))
        f2 = g * ((1 - x0 + 0.1 * np.sin(3 * np.pi * x0)) ** a)  # 修正：整个表达式都加上指数

        return np.column_stack([f1, f2])

    def get_pareto_front(self, t=None):
        if t is None:
            t = self.t

        # ===== 动态参数 =====
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)
        a = 2.25 + 2 * np.cos(2 * np.pi * times)

        # ===== 生成理想前沿 =====
        x = np.linspace(0, 1, 1500)  # 高密度采样
        g = 1  # 在帕累托前沿上，其他变量都等于tmp，所以g=1
        f1 = g * (x + 0.1 * np.sin(3 * np.pi * x))
        f2 = g * ((1 - x + 0.1 * np.sin(3 * np.pi * x)) ** a)

        return np.column_stack([f1, f2])

    def get_pareto_set(self, t=None):
        if t is None:
            t = self.t

        # ===== 动态参数 =====
        times = t / self.n
        G = np.sin(0.5 * np.pi * times)

        # ===== 构造解集 =====
        x0_values = np.linspace(0, 1, 1500)
        tmp = G * np.sin(4 * np.pi * x0_values) / (1 + np.abs(G))  # 每个x0对应tmp

        PS = np.empty((1500, self.decision_num))
        PS[:, 0] = x0_values
        if self.decision_num > 1:
            # 其他维度填充对应tmp值（每行的其他变量等于该行x0对应的tmp）
            PS[:, 1:] = tmp[:, np.newaxis]  # 维度扩展

        return PS