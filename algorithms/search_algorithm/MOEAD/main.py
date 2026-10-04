import numpy as np

from algorithms.search_algorithm.NSGA2.main import NSGA2
from components.Population import Population
from utils.evolution_tools import detection


class MOEAD(NSGA2):
    """MOEA/D using Tchebycheff decomposition and constraint domination."""

    def __init__(
        self,
        neighbor_size=20,
        delta=0.9,
        max_replacements=2,
        differential_weight=0.5,
        proM=1.0,
        disM=20,
        **args,
    ):
        super().__init__(proM=proM, disM=disM, **args)
        self.neighbor_size = int(neighbor_size)
        self.delta = float(delta)
        self.max_replacements = int(max_replacements)
        self.differential_weight = float(differential_weight)

    def optimize(self, problem, response_strategy):
        self.reset_random_state()
        population = Population(
            xl=problem.xl, xu=problem.xu, n_init=problem.solution_num
        )
        population.update_objective_constrain(problem)
        weights = self._generate_weights(problem.solution_num, problem.n_obj)
        neighbors = self._build_neighbors(weights)
        ideal = np.min(population.get_objective_matrix(), axis=0)

        while not problem.is_ended() and self.control_process():
            if detection(
                population, problem, max(1, int(0.1 * problem.solution_num))
            ):
                population = response_strategy.response(population, problem, self)
                if not self.control_process():
                    break
                ideal = np.min(population.get_objective_matrix(), axis=0)
                self.collect_information(population, problem, response_strategy)
                continue

            decisions = population.get_decision_matrix()
            child_decisions = np.empty_like(decisions)
            mating_pools = []
            for index in range(problem.solution_num):
                if np.random.random() < self.delta:
                    pool = neighbors[index]
                else:
                    pool = np.arange(problem.solution_num)
                mating_pools.append(pool)
                if len(pool) >= 2:
                    parent_indices = np.random.choice(pool, 2, replace=False)
                else:
                    parent_indices = np.array([pool[0], pool[0]])
                trial = decisions[index] + self.differential_weight * (
                    decisions[parent_indices[0]] - decisions[parent_indices[1]]
                )
                child_decisions[index] = np.clip(trial, problem.xl, problem.xu)

            child_decisions = self._polynomial_mutation(
                child_decisions, self.proM, self.disM, problem
            )
            offspring = Population(
                X=child_decisions, xl=problem.xl, xu=problem.xu
            )
            offspring.update_objective_constrain(problem)

            for index, child in enumerate(offspring.individuals):
                ideal = np.minimum(ideal, child.F)
                candidates = np.random.permutation(mating_pools[index])
                replacements = 0
                for candidate in candidates:
                    current = population.individuals[candidate]
                    if self._is_better(
                        child, current, weights[candidate], ideal
                    ):
                        population.individuals[candidate] = child.copy()
                        replacements += 1
                        if replacements >= max(1, self.max_replacements):
                            break

            self.collect_information(population, problem, response_strategy)

    def _build_neighbors(self, weights):
        distance = np.linalg.norm(
            weights[:, None, :] - weights[None, :, :], axis=2
        )
        size = min(max(1, self.neighbor_size), len(weights))
        return np.argsort(distance, axis=1)[:, :size]

    @staticmethod
    def _generate_weights(size, objective_count):
        if objective_count == 2:
            first = np.linspace(0.0, 1.0, size)
            return np.column_stack((first, 1.0 - first))
        weights = np.random.dirichlet(np.ones(objective_count), size=size)
        return np.maximum(weights, 1e-12)

    @staticmethod
    def _tchebycheff(objectives, weight, ideal):
        return np.max(np.maximum(weight, 1e-6) * np.abs(objectives - ideal))

    def _is_better(self, child, current, weight, ideal):
        if child.constraint_violation < current.constraint_violation - 1e-12:
            return True
        if child.constraint_violation > current.constraint_violation + 1e-12:
            return False
        if child.constraint_violation > 1e-12:
            return False
        return self._tchebycheff(child.F, weight, ideal) <= self._tchebycheff(
            current.F, weight, ideal
        )
