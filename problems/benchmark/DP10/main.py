import numpy as np

from problems.Problem import Problem


class DP10(Problem):
    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(decision_num, 2, 0, n, tau, solution_num, total_evaluate_time, 'DP10')
        self.xl = np.zeros(decision_num)
        self.xu = np.ones(decision_num)

    def _evaluate_objectives(self, X, t=None):
        if t is None:
            t = self.t

        # ===== 动态参数计算 =====
        times = t / self.n
        G = np.abs(np.sin(0.5 * np.pi * times))  # 基础环境参数
        p = np.floor(6 * G)  # 震荡频率系数

        # ===== 计算参考值 =====
        with np.errstate(divide='ignore', invalid='ignore'):  # 忽略除零警告
            cot_term = 1.0 / np.tan(3 * np.pi * times ** 2)  # 余切计算
            ref_value = (1.0 / np.pi) * np.abs(np.arctan(cot_term)) ** 2  # 参考值公式

        # ===== 变量分解 =====
        x0 = X[:, 0]  # 第一决策变量
        other_vars = X[:, 1:]  # 其他决策变量

        # ===== 计算g函数 =====
        g = np.sum((other_vars - ref_value) ** 2, axis=1)  # 平方和

        # ===== 目标函数计算 =====
        cos_px = np.cos(p * np.pi * x0)  # 频率依赖的余弦项

        f1 = (1 + g) * (np.cos(0.5 * np.pi * x0)) ** 2 + G
        f2 = (np.sin(0.5 * np.pi * x0)) ** 2 + np.sin(0.5 * np.pi * x0) * (cos_px) ** 2 + G

        return np.column_stack([f1, f2])

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t

        # ===== 动态参数 =====
        times = t / self.n
        G = np.abs(np.sin(0.5 * np.pi * times))
        p = np.floor(6 * G)

        # ===== 生成理想前沿 =====
        x = np.linspace(0, 1, 1500)
        cos_px = np.cos(p * np.pi * x)
        f1 = np.cos(0.5 * np.pi * x) ** 2 + G

        f2 = np.sin(0.5 * np.pi * x) ** 2 + np.sin(0.5 * np.pi * x) * cos_px ** 2 + G
        return self.get_nondominate([f1, f2])

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t

        # ===== 计算参考值 =====
        times = t / self.n
        with np.errstate(divide='ignore', invalid='ignore'):
            cot_term = 1.0 / np.tan(3 * np.pi * times ** 2)
            ref_value = (1.0 / np.pi) * np.abs(np.arctan(cot_term)) ** 2

        # ===== 构造解集 =====
        PS = np.full((1500, self.decision_num), ref_value)  # 其他维度填充参考值
        PS[:, 0] = np.linspace(0, 1, 1500)  # 第一维均匀分布
        return PS