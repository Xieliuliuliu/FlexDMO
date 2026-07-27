import numpy as np

import problems.Problem
from components.Individual import Individual
import copy

class Population:
    def __init__(self, individuals=None, xl=None, xu=None, n_init=0, X=None, F=None):
        """
        Population 支持四种初始化方式：
        1. individuals：传入已构造好的个体列表
        2. xl/xu + n_init：随机生成 n_init 个个体
        3. X：直接从一个决策矩阵初始化（每行一个个体）
        4. X + Y：从决策矩阵和目标矩阵初始化
        """
        if individuals is not None:
            self.individuals = individuals

        elif X is not None:
            X = np.atleast_2d(np.asarray(X))
            if F is not None:
                F = np.atleast_2d(np.asarray(F))
                if len(X) != len(F):
                    raise ValueError("X 和 F 的行数必须一致")
                self.individuals = [Individual(x, y) for x, y in zip(X, F)]
            else:
                self.individuals = [Individual(x) for x in X]

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
        if any(ind.F is None for ind in self.individuals):
            raise ValueError("种群中存在尚未计算目标值的个体")
        return np.array([ind.F for ind in self.individuals])

    def get_constrain_matrix(self):
        return np.array([ind.G for ind in self.individuals if ind.G is not None])

    def get_constraint_violation_vector(self):
        return np.array(
            [float(ind.constraint_violation) for ind in self.individuals],
            dtype=float,
        )

    def get_feasible_objective_matrix(self):
        values = [
            ind.F
            for ind in self.individuals
            if ind.feasible and ind.F is not None
        ]
        if not values:
            objective_count = (
                len(self.individuals[0].F)
                if self.individuals and self.individuals[0].F is not None
                else 0
            )
            return np.empty((0, objective_count), dtype=float)
        return np.asarray(values, dtype=float)

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
        if not self.individuals:
            return
        F, G = problem.evaluate(self.get_decision_matrix())
        for i, ind in enumerate(self.individuals):
            ind.F = F[i]
            if G is not None:
                ind.G = G[i]
                ind.constraint_violation = float(np.sum(np.maximum(G[i], 0.0)))
                ind.feasible = ind.constraint_violation <= 1e-12
            else:
                ind.G = None
                ind.feasible = True
                ind.constraint_violation = 0.0

    def __len__(self):
        return len(self.individuals)

    def __getitem__(self, idx):
        return self.individuals[idx]

    def to_dict(self):
        def array_or_none(value):
            return value.tolist() if value is not None else None

        return {
            "schema_version": 2,
            "decision": [array_or_none(ind.X) for ind in self.individuals],
            "objective": [array_or_none(ind.F) for ind in self.individuals],
            "constraint": [array_or_none(ind.G) for ind in self.individuals],
            "feasible": [bool(ind.feasible) for ind in self.individuals],
            "constraint_violation": [
                float(ind.constraint_violation) for ind in self.individuals
            ],
            "rank": [ind.rank for ind in self.individuals],
            "crowding_distance": [
                float(ind.crowding_distance)
                if (
                    ind.crowding_distance is not None
                    and np.isfinite(ind.crowding_distance)
                )
                else None
                for ind in self.individuals
            ],
            "xl": array_or_none(self.xl),
            "xu": array_or_none(self.xu),
        }

    def __repr__(self):
        total = len(self.individuals)
        evaluated = sum([ind.F is not None for ind in self.individuals])
        feasible = sum([ind.feasible for ind in self.individuals])
        return f"Population(size={total}, evaluated={evaluated}, feasible={feasible})"
