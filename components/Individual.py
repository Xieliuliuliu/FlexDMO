import copy
import numpy as np

class Individual:
    def __init__(self, X):
        self.X = X
        self.F = None
        self.G = None
        self.feasible = True
        self.rank = None           # NSGA-II等排序等级
        self.crowding_distance = None  # 拥挤距离

    def __repr__(self):
        return f"Individual(X={self.X}, F={self.F}, feasible={self.feasible})"
    
    def copy(self):
       return copy.deepcopy(self)