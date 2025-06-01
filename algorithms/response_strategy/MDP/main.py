from algorithms.response_strategy.MDP.Reinitial import get_C, get_pop
from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population


class MDP(ResponseStrategy):
    def __init__(self):
        super().__init__()
        self.C_arr = None

    def response(self,population, problem, algorithm):
        if self.C_arr is None:
            self.C_arr = []
        runtime_populations = algorithm.history["runtime"]
        if len(runtime_populations.keys()) < 2:
            Y1 = population.get_objective_matrix()
            population.update_objective_constrain(problem)
            self.C_arr.append(get_C(X0 = population.get_decision_matrix(), Y0=population.get_objective_matrix(), Y1=Y1))
            # 重新初始化
            population = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
            population.update_objective_constrain(problem)
        else:
            t_1 = list(runtime_populations.keys())[-1]
            # 获取最后一次进化结果作为历史PS
            env_1 = runtime_populations[t_1]
            env_1_last_eval = list(env_1.keys())[-1]
            PS1 = env_1[env_1_last_eval]

            Y1 = population.get_objective_matrix()
            population.update_objective_constrain(problem)
            self.C_arr.append(get_C(X0 = population.get_decision_matrix(), Y0=population.get_objective_matrix(), Y1=Y1))
            population = get_pop(PS1, self.C_arr[-1], self.C_arr[-2], problem.xl, problem.xu)

            population.update_objective_constrain(problem)
        return population