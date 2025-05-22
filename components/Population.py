import numpy as np

import problems.Problem
from components.Individual import Individual
import copy

class Population:
    def __init__(self, individuals=None, xl=None, xu=None, n_init=0, X=None):
        """
        Population 支持三种初始化方式：
        1. individuals：传入已构造好的个体列表
        2. xl/xu + n_init：随机生成 n_init 个个体
        3. X：直接从一个决策矩阵初始化（每行一个个体）
        """
        if individuals:
            self.individuals = individuals

        elif X is not None:
            self.individuals = [Individual(x) for x in np.atleast_2d(X)]

        elif xl is not None and xu is not None and n_init > 0:
            self.individuals = [Individual(np.random.uniform(low=xl, high=xu)) for _ in range(n_init)]

        else:
            self.individuals = []

        # 自动更新 n
        self.n = len(self.individuals)
        self.xl = xl
        self.xu = xu

    def get_decision_matrix(self):
        return np.array([ind.X for ind in self.individuals])

    def get_objective_matrix(self):
        return np.array([ind.F for ind in self.individuals if ind.F is not None])

    def get_constrain_matrix(self):
        return np.array([ind.G for ind in self.individuals if ind.G is not None])

    def update_X(self, X):
        """
        批量更新种群中每个个体的决策变量 X。
        :param X: numpy array, shape: (n_individuals, n_var)
        """
        assert len(X) == len(self.individuals), "X 行数与个体数不一致"
        for i, ind in enumerate(self.individuals):
            ind.X = np.array(X[i])

    def copy(self):
        return copy.deepcopy(self)

    def update_objective_constrain(self,problem:problems.Problem):
        F, G = problem.evaluate(self.get_decision_matrix())
        for i, ind in enumerate(self.individuals):
            ind.F = F[i]
            if G is not None:
                ind.G = G[i]
                ind.feasible = np.all(G[i] <= 0)
            else:
                ind.G = None
                ind.feasible = True

    def __len__(self):
        return len(self.individuals)

    def __getitem__(self, idx):
        return self.individuals[idx]

    def to_dict(self):
        result = {
            "decision": [],
            # "objective": [],
            # "constrain": []
        }

        for ind in self.individuals:
            result["decision"].append(ind.X.tolist())

            # if ind.F is not None:
            #     result["objective"].append(ind.F.tolist())
            # else:
            #     pass

            # if ind.G is not None:
            #     result["constrain"].append(ind.G.tolist())
            # else:
            #     pass

        return result

    def __repr__(self):
        total = len(self.individuals)
        evaluated = sum([ind.F is not None for ind in self.individuals])
        feasible = sum([ind.feasible for ind in self.individuals])
        return f"Population(size={total}, evaluated={evaluated}, feasible={feasible})"
