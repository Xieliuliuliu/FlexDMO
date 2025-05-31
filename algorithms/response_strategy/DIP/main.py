import math
import numpy as np

from algorithms.response_strategy.DIP import DIP_ANN
from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import getNonDominate

class DIP(ResponseStrategy):
    def __init__(self):
        super().__init__()

    def response(self,population, problem, algorithm):
        X_Low = problem.xl
        X_Upp = problem.xu
        DIM = problem.decision_num
        N = problem.solution_num
        runtime_populations = algorithm.history["runtime"]
        if len(runtime_populations.keys()) < 2:
            # 重新初始化
            population = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
            population.update_objective_constrain(problem)
        else:
            # 获取runtime_populations的倒数二个键(最后两个t)
            t_2, t_1 = list(runtime_populations.keys())[-2:]

            # 获取最后两个环境(t)的最后一次进化结果作为历史PS
            env_2= runtime_populations[t_2]
            env_2_last_eval = list(env_2.keys())[-1]
            PS2 = env_2[env_2_last_eval]
            env_1 = runtime_populations[t_1]
            env_1_last_eval = list(env_1.keys())[-1]
            PS1 = env_1[env_1_last_eval]

            ann = DIP_ANN.ANN(DIM, 5)
            input, target = get_input_target(PS2, PS1, N)
            DIP_ANN.train(ann, input, target, X_Low, X_Upp)
            population = DIP_init_pop(input, target, PS1.get_decision_matrix(), PS2.get_decision_matrix(), ann, X_Low, X_Upp, N)
            population.update_objective_constrain(problem)
        return population

def get_input_target(PS2, PS1, N):
    non_pop1 = getNonDominate(PS1)
    non_pop2 = getNonDominate(PS2)
    x1 = non_pop1.get_decision_matrix()
    x2 = non_pop2.get_decision_matrix()
    ns = min(len(x1), len(x2))

    x1 = x1[:ns,:]
    x2 = x2[:ns,:]
    #数量不够，要增加数据
    if ns < math.ceil(N / 2):
        need = math.ceil(N / 2) - ns
        std = np.std(x2, axis=0)
        indexs = np.random.choice(ns, need, replace=True)
        x1_add = x1[indexs]
        x2_add = x2[indexs]
        # 对采样的 x2 加噪声
        noise = np.random.normal(0, std, size=(need, x2.shape[1]))
        x2_add += noise

        # 合并得到最终的训练集
        input = np.vstack([x2, x2_add])
        target = np.vstack([x1, x1_add])
    else:
        input = x2
        target = x1
    return input, target

def DIP_init_pop(input, target, PS1, PS2, ann, X_Low, X_Upp, N):
    xl = DIP_ANN.predict_by_ann(ann, target, X_Low, X_Upp)
    ns = xl.shape[0]
    need = N - ns
    random_factors1 = np.random.random(size=ns)[:, np.newaxis]
    random_factors2 = np.random.random(size=ns)[:, np.newaxis]
    part1 = random_factors1 * (xl - target)
    part2 = random_factors2 * (target - input)
    xp = target + part1 + part2

    #随机选取x_fill直到满足数量需要
    x_fill = DIP_ANN.predict_by_ann(ann, PS1, X_Low, X_Upp)
    rand_arr = np.random.choice(np.arange(len(x_fill)), size=need, replace=True)
    x_add = x_fill[rand_arr]
    #合并
    new_xp = np.vstack([xp, x_add])

    # 边界处理
    for i in range(N):
        for j in range(new_xp.shape[1]):
            if new_xp[i, j] < X_Low[j]:
                new_xp[i, j] = 0.5 * (PS1[i, j] + X_Low[j])
            if new_xp[i, j] > X_Upp[j]:
                new_xp[i, j] = 0.5 * (PS1[i, j] + X_Upp[j])

    population = Population(xl=X_Low, xu=X_Upp, X = new_xp)
    return population