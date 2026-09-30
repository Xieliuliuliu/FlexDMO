from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from algorithms.response_strategy.dynamic_nsga2 import (
    finish_population,
    random_population,
    replacement_count,
    select_survivors,
    validate_rate,
)


class DNSGAIIA(ResponseStrategy):
    """D-NSGA-II-A response using constraint-aware random immigrants."""

    def __init__(self, replacement_rate=0.2):
        super().__init__()
        self.replacement_rate = validate_rate(
            "replacement_rate",
            replacement_rate,
        )

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
        newcomers = random_population(
            problem,
            problem.solution_num - len(survivors),
        )
        return finish_population(problem, survivors, newcomers)
