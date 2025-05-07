import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from views.common.GlobalVar import global_vars

class DIP(ResponseStrategy):
    def __init__(self):
        super().__init__()

    def response(self,population, problem, algorithm):
        population.update_objective_constrain(problem)
        # PS1, PS2 = None, None
        runtime_populations = algorithm.history["runtime"]
        print(runtime_populations)
        # if len(runtime_populations.keys()) < 2:
        #     # 重新初始化
        #     pop = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
        #     pop.update_objective_constrain(problem)
        # else:
        #     # 获取runtime_populations的倒数二个键
        #     second_last_key, last_key = list(runtime_populations.keys())[-2:]
        #     second_last_value, last_value = runtime_populations[second_last_key, last_key]
        #
        #     last_key_in_second_last_value = list(second_last_value.keys())[-2]
        #     PS2 = second_last_value[last_key_in_second_last_value]["decision"]
        #     last_key_in_second_last_value = list(second_last_value.keys())[-1]
        #     PS1 = second_last_value[last_key_in_second_last_value]["decision"]
        return population