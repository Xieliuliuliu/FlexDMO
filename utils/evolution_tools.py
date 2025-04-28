import random

import numpy as np

from components.Population import Population
from problems.Problem import Problem


def quick_non_dominate_sort(population):
    # 进行非支配排序
    Front = []
    for individual in population.individuals:
        individual.dominate = []
        individual.bedominated = 0
        for compare_individual in population.individuals:
            if isDominated(individual, compare_individual) == 1:
                individual.dominate.append(compare_individual)
            elif isDominated(compare_individual, individual) == 1:
                individual.bedominated += 1
        if individual.bedominated == 0:
            individual.rank = 1
            Front.append(individual)
    i = 1
    while len(Front) != 0:
        Q = []
        for non_dominate_individual in Front:
            for be_dominate_individual in non_dominate_individual.dominate:
                be_dominate_individual.bedominated -= 1
                if be_dominate_individual.bedominated == 0:
                    be_dominate_individual.rank = i + 1
                    Q.append(be_dominate_individual)
        i += 1
        Front = Q


def crowd_selection(population, N):
    target_pop = []
    obj_DIM = population.get_objective_matrix().shape[1]
    now, now_rank = 0, 1
    while now < N:
        now_rank_pop = []
        for individual in population.individuals:
            if individual.rank == now_rank:
                now_rank_pop.append(individual)
        need = N - now
        if len(now_rank_pop) <= need:
            for individual in now_rank_pop:
                copy_individual = individual.copy()
                target_pop.append(copy_individual)
                now += 1
            now_rank += 1
        else:
            for individual in now_rank_pop:
                individual.crowding_dist = 0
            for i in range(obj_DIM):
                now_rank_pop.sort(key=lambda individual: individual.F[i])
                now_rank_pop[0].crowding_dist = np.inf
                now_rank_pop[-1].crowding_dist = np.inf
                range_diff = now_rank_pop[-1].F[i] - now_rank_pop[0].F[i]
                if range_diff == 0:  # 如果分母为零
                    for index in range(1, len(now_rank_pop) - 1):
                        now_rank_pop[index].crowding_dist += 1  # 设置默认值
                else:
                    for index in range(1, len(now_rank_pop) - 1):
                        now_rank_pop[index].crowding_dist = now_rank_pop[index].crowding_dist + \
                                                            (now_rank_pop[index + 1].F[i] -
                                                             now_rank_pop[index - 1].F[i]) \
                                                            / (now_rank_pop[-1].F[i] - now_rank_pop[0].F[i])
            now_rank_pop.sort(key=lambda individual: individual.crowding_dist, reverse=True)
            now_index = 0
            while now < N:
                copy_individual = now_rank_pop[now_index].copy()
                target_pop.append(copy_individual)
                now_index += 1
                now += 1
            return Population(target_pop, population.xl, population.xu)
    return Population(target_pop, population.xl, population.xu)


def isDominated(A, B):
    ODIM = A.F.shape[0]
    larger = 0
    smaller = 0
    equal = 0
    for i in range(ODIM):
        if (A.F[i] < B.F[i]):
            smaller = smaller + 1
        elif (A.F[i] == B.F[i]):
            equal = equal + 1
        else:
            larger = larger + 1
    if (smaller == ODIM):
        return 1  # 1表示A支配B
    if (smaller + equal == ODIM and smaller > 0):
        return 1
    if (larger == ODIM):
        return 0  # 0表示A被B支配
    if (larger + equal == ODIM and larger > 0):
        return 0
    if (smaller > 0 and larger > 0):
        return 2  # 2表示A,B互不支配
    if (equal == ODIM):
        return 2


def detection(pop: Population, problem: Problem, number_detector):
    seq = range(pop.n)
    detector = random.sample(seq, number_detector)
    isChange = 0
    for i in range(number_detector):
        temp = pop.individuals[detector[i]]
        f, g = problem.evaluate(temp.X.reshape(1, -1), False)
        isChange = 0
        for j in range(problem.n_obj):
            if not np.all(f == pop.individuals[detector[i]].F):
                isChange = 1
                break
        if isChange == 1:
            print("environment has changed")
            break
    return isChange
