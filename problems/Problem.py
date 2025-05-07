import math

import numpy as np


class Problem:
    def __init__(self, decision_num, n_obj, n_con, n, tau, solution_num, total_evaluate_time, label):
        self.decision_num = decision_num  # 决策变量维度
        self.n_obj = n_obj  # 目标数
        self.xl = np.array([0.0] * decision_num)  # 决策变量下界
        self.xu = np.array([1.0] * decision_num)  # 决策变量上界
        self.n_con = n_con  # 约束数
        self.evaluate_time = 0  # 评估次数
        self.change_each_evaluations = tau * solution_num  # 评估多少次就要变一次环境
        self.solution_num = solution_num  # 用于优化这个问题的个体数量
        self.total_change_time = total_evaluate_time  # 总的变化次数

        # 动态属性
        self.n = n  # 变化强度
        self.tau = tau  # 每 tau 代变化一次
        self.t = 0  # 当前时间步
        self.label = label  # 问题标签

        # 初始收敛代数
        self.initial_convergence = 50 * solution_num  # 初始50代收敛

        # 下次是否需要更新
        self.need_change = False

    def evaluate(self, X, need_count=True, t=None):
        """
        返回目标函数值，形状：[n_samples, n_obj]
        """
        if self.need_change:
            self._update_time()
            self.need_change = False
        if t is None:
            t = self.t
        F = self._evaluate_objectives(X, t)
        G = self._evaluate_constraints(X, t)
        if need_count:
            old_num = self.evaluate_time
            self.evaluate_time += X.shape[0]
            # 考虑初始收敛代数
            if old_num < self.initial_convergence:
                old_time = 0
                new_time = 0
            else:
                old_time = math.floor((old_num - self.initial_convergence) / self.change_each_evaluations)
                new_time = math.floor((self.evaluate_time - self.initial_convergence) / self.change_each_evaluations)
            if old_time != new_time and old_num != 0:
                self.need_change = True
        return F, G

    def _evaluate_objectives(self, X, t):
        raise NotImplementedError

    def _evaluate_constraints(self, X, t):
        """
        返回约束值，形状：[n_samples, n_con]，不满足为正。
        """
        if self.n_con == 0:
            return None
        raise NotImplementedError

    def get_bounds(self):
        return self.xl, self.xu

    def get_pareto_front(self, t=None):
        raise NotImplementedError

    def get_pareto_set(self, t=None):
        raise NotImplementedError


    def get_nondominate(self, f):
        """
        获取第0层非支配解（帕累托前沿）
        f: 目标函数值列表 [f1, f2, f3, ...]
        """
        h = np.column_stack(f)
        is_dominated = np.zeros(len(h), dtype=bool)
        
        # 向量化判断支配关系
        for i in range(len(h)):
            if not is_dominated[i]:
                # 检查i是否被未被支配的解支配（关键改进）
                dominates_i = (h <= h[i]).all(1) & (h < h[i]).any(1)
                dominates_i[i] = False  # 排除自身比较
                
                if not np.any(dominates_i):
                    # 标记所有被i支配的解
                    dominated_by_i = (h[i] <= h).all(1) & (h[i] < h).any(1)
                    is_dominated[dominated_by_i] = True
                    
        return h[~is_dominated]

    def get_feasible_region(self, t=None):
        """
        可选接口：返回当前时间 t 的可行区域，用于可视化或环境变化
        """
        return self.xl, self.xu  # 默认返回整个搜索空间

    def is_ended(self):
        if self.need_change and self.t+1 >= self.total_change_time:
            return True
        else:
            return False

    def _update_time(self):
        """
        时间步推进 + 环境更新
        """
        self.t += 1

    def reset(self):
        self.t = 0
        self.evaluate_time = 0
