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