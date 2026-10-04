import numpy as np

from algorithms.search_algorithm.NSGA2.main import NSGA2
from components.Population import Population
from utils.evolution_tools import detection, domination_matrix


class SPEA2(NSGA2):
    """Strength Pareto Evolutionary Algorithm 2 with constraint domination."""

    def optimize(self, problem, response_strategy):
        self.reset_random_state()
        population = Population(
            xl=problem.xl, xu=problem.xu, n_init=problem.solution_num
        )
        population.update_objective_constrain(problem)

        while not problem.is_ended() and self.control_process():
            if detection(
                population, problem, max(1, int(0.1 * problem.solution_num))
            ):
                population = response_strategy.response(population, problem, self)
                if not self.control_process():
                    break
                self.collect_information(population, problem, response_strategy)
                continue

            offspring = self._variation(population, problem)
            offspring.update_objective_constrain(problem)
            combined = Population(
                individuals=population.individuals + offspring.individuals,
                xl=problem.xl,
                xu=problem.xu,
            )
            population = self._environmental_selection(
                combined, problem.solution_num
            )
            self.collect_information(population, problem, response_strategy)

    def _environmental_selection(self, population, target_size):
        objectives = population.get_objective_matrix()
        violations = population.get_constraint_violation_vector()
        dominates = domination_matrix(objectives, violations)
        strength = np.sum(dominates, axis=1)
        raw_fitness = dominates.T @ strength

        span = np.ptp(objectives, axis=0)
        normalized = (objectives - np.min(objectives, axis=0)) / np.where(
            span > 0, span, 1.0
        )
        distances = np.linalg.norm(
            normalized[:, None, :] - normalized[None, :, :], axis=2
        )
        np.fill_diagonal(distances, np.inf)
        neighbor_rank = min(max(0, int(np.sqrt(len(population))) - 1), len(population) - 1)
        kth_distance = np.partition(distances, neighbor_rank, axis=1)[:, neighbor_rank]
        density = 1.0 / (kth_distance + 2.0)
        fitness = raw_fitness + density

        selected = list(np.flatnonzero(fitness < 1.0))
        if len(selected) < target_size:
            remaining = [i for i in np.argsort(fitness) if i not in selected]
            selected.extend(remaining[: target_size - len(selected)])
        elif len(selected) > target_size:
            selected = self._truncate(selected, distances, target_size)

        return Population(
            individuals=[population.individuals[i] for i in selected],
            xl=population.xl,
            xu=population.xu,
        )

    @staticmethod
    def _truncate(selected, distances, target_size):
        selected = list(selected)
        while len(selected) > target_size:
            local = distances[np.ix_(selected, selected)].copy()
            np.fill_diagonal(local, np.inf)
            distance_profiles = np.sort(local, axis=1)
            remove_position = min(
                range(len(selected)),
                key=lambda position: tuple(distance_profiles[position]),
            )
            selected.pop(remove_position)
        return selected
