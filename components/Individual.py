import numpy as np

class Individual:
    def __init__(self, X):
        self.X = np.array(X)       # 决策变量
        self.F = None              # 目标函数值
        self.G = None              # 约束函数值
        self.feasible = True       # 是否可行（可由算法计算）
        self.rank = None           # NSGA-II等排序等级
        self.crowding_distance = None  # 拥挤距离

    def __repr__(self):
        return f"Individual(X={self.X}, F={self.F}, feasible={self.feasible})"

    def copy(self):
        new_ind = Individual(self.X.copy())  # 决策变量复制
        new_ind.F = None if self.F is None else self.F.copy()
        new_ind.G = None if self.G is None else self.G.copy()
        new_ind.feasible = self.feasible
        new_ind.rank = self.rank
        new_ind.crowding_distance = self.crowding_distance
        return new_ind
