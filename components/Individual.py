import copy
import numpy as np

class Individual:
    def __init__(self, X, F=None):
        self.X = X
        self.F = F
        self.G = None
        self.feasible = True
        self.rank = None           # NSGA-II等排序等级
        self.crowding_distance = None  # 拥挤距离

    def __repr__(self):
        return f"Individual(X={self.X}, F={self.F}, feasible={self.feasible})"
    
    def copy(self):
       return copy.deepcopy(self)

    def result_copy(self):
        # 只复制必要的属性
        new_individual = Individual(self.X.copy())
        new_individual.F = self.F.copy() if self.F is not None else None
        new_individual.G = self.G.copy() if self.G is not None else None
        new_individual.feasible = self.feasible
        new_individual.rank = self.rank
        new_individual.crowding_distance = self.crowding_distance
        return new_individual