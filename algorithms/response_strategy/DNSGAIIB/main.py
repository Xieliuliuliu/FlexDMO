import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from algorithms.response_strategy.dynamic_nsga2 import (
    finish_population,
    polynomial_mutation,
    random_population,
    replacement_count,
    select_survivors,
    validate_rate,
)
from components.Population import Population


class DNSGAIIB(ResponseStrategy):
    """D-NSGA-II-B response using mutated elite immigrants."""

    def __init__(
        self,
        replacement_rate=0.2,
        mutation_probability=0.1,
        distribution_index=20,
    ):
        super().__init__()
        self.replacement_rate = validate_rate(
            "replacement_rate",
            replacement_rate,
        )
        self.mutation_probability = validate_rate(
            "mutation_probability",
            mutation_probability,
        )
        self.distribution_index = float(distribution_index)
        if self.distribution_index <= 0:
            raise ValueError("distribution_index must be positive.")

    def response(self, population, problem, algorithm):
        del algorithm
        population.update_objective_constrain(problem)
        replace_count = replacement_count(
            problem.solution_num,
            self.replacement_rate,
        )
        survivors = select_survivors(
            population,
            problem.solution_num - replace_count,
        )
        newcomer_count = problem.solution_num - len(survivors)

        if not population.individuals:
            newcomers = random_population(problem, newcomer_count)
        else:
            parent_indices = np.random.choice(
                population.n,
                size=newcomer_count,
                replace=population.n < newcomer_count,
            )
            parents = population.get_decision_matrix()[parent_indices]
            decisions = polynomial_mutation(
                parents,
                problem.xl,
                problem.xu,
                self.mutation_probability,
                self.distribution_index,
            )
            newcomers = Population(
                X=decisions,
                xl=problem.xl,
                xu=problem.xu,
            )
            newcomers.update_objective_constrain(problem)

        return finish_population(problem, survivors, newcomers)
