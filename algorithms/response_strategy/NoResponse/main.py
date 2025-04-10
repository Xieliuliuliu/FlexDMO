from algorithms.response_strategy.ResponseStrategy import ResponseStrategy


class NoResponse(ResponseStrategy):
    def __init__(self):
        super().__init__()

    def response(self,population, problem, algorithm):
        population.update_objective_constrain(problem)
        return population