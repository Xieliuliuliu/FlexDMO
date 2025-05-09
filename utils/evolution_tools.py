import random
import numpy as np
from components.Population import Population
from problems.Problem import Problem


def quick_non_dominate_sort(population):
    """快速非支配排序
    
    Args:
        population: 待排序的种群
    """
    if not population.individuals:
        return
        
    # 初始化支配关系
    for individual in population.individuals:
        individual.dominate = []
        individual.bedominated = 0
        
    # 计算支配关系
    for i, ind1 in enumerate(population.individuals):
        for j, ind2 in enumerate(population.individuals):
            if i != j:
                domination = isDominated(ind1, ind2)
                if domination == 1:  # ind1支配ind2
                    ind1.dominate.append(ind2)
                elif domination == 0:  # ind1被ind2支配
                    ind1.bedominated += 1
                    
    # 生成非支配层
    front = []
    for individual in population.individuals:
        if individual.bedominated == 0:
            individual.rank = 1
            front.append(individual)
            
    # 迭代生成后续的非支配层
    current_rank = 1
    while front:
        next_front = []
        for non_dominated in front:
            for dominated in non_dominated.dominate:
                dominated.bedominated -= 1
                if dominated.bedominated == 0:
                    dominated.rank = current_rank + 1
                    next_front.append(dominated)
        current_rank += 1
        front = next_front


def crowd_selection(population, N):
    """拥挤度选择
    
    Args:
        population: 待选择的种群
        N: 需要选择的个体数量
        
    Returns:
        选择后的新种群
    """
    if not population.individuals:
        return Population(xl=population.xl, xu=population.xu)
        
    target_pop = []
    obj_dim = population.get_objective_matrix().shape[1]
    current_count = 0
    current_rank = 1
    
    while current_count < N:
        # 获取当前秩的所有个体
        current_rank_pop = [ind for ind in population.individuals if ind.rank == current_rank]
        
        if not current_rank_pop:
            current_rank += 1
            continue
            
        need = N - current_count
        if len(current_rank_pop) <= need:
            # 如果当前秩的个体数量小于等于需要的数量，全部选择
            for individual in current_rank_pop:
                # 清除临时属性
                for attr in ['dominate', 'bedominated']:
                    if hasattr(individual, attr):
                        delattr(individual, attr)
                target_pop.append(individual.copy())
                current_count += 1
            current_rank += 1
        else:
            # 如果当前秩的个体数量大于需要的数量，使用拥挤度选择
            for individual in current_rank_pop:
                individual.crowding_dist = 0
                
            # 对每个目标维度计算拥挤度
            for i in range(obj_dim):
                # 按当前目标值排序
                current_rank_pop.sort(key=lambda ind: ind.F[i])
                
                # 设置边界点的拥挤度为无穷大
                current_rank_pop[0].crowding_dist = float('inf')
                current_rank_pop[-1].crowding_dist = float('inf')
                
                # 计算中间点的拥挤度
                f_max = current_rank_pop[-1].F[i]
                f_min = current_rank_pop[0].F[i]
                range_diff = f_max - f_min
                
                if range_diff > 0:
                    for j in range(1, len(current_rank_pop) - 1):
                        current_rank_pop[j].crowding_dist += (
                            current_rank_pop[j + 1].F[i] - 
                            current_rank_pop[j - 1].F[i]
                        ) / range_diff
                else:
                    # 当目标值相同时，使用均匀分布
                    for j in range(1, len(current_rank_pop) - 1):
                        current_rank_pop[j].crowding_dist += 1.0
                        
            # 按拥挤度降序排序
            current_rank_pop.sort(key=lambda ind: ind.crowding_dist, reverse=True)
            
            # 选择需要的个体
            for i in range(need):
                individual = current_rank_pop[i]
                # 清除临时属性
                for attr in ['dominate', 'bedominated']:
                    if hasattr(individual, attr):
                        delattr(individual, attr)
                target_pop.append(individual.copy())
                current_count += 1
                
            return Population(individuals=target_pop, xl=population.xl, xu=population.xu)
            
    return Population(individuals=target_pop, xl=population.xl, xu=population.xu)


def isDominated(A, B):
    """判断支配关系
    
    Args:
        A: 第一个个体
        B: 第二个个体
        
    Returns:
        1: A支配B
        0: A被B支配
        2: A和B互不支配
    """
    obj_dim = A.F.shape[0]
    better_count = 0
    worse_count = 0
    equal_count = 0
    
    for i in range(obj_dim):
        if A.F[i] < B.F[i]:
            better_count += 1
        elif A.F[i] == B.F[i]:
            equal_count += 1
        else:
            worse_count += 1
            
    if better_count == obj_dim:
        return 1  # A支配B
    if better_count + equal_count == obj_dim and better_count > 0:
        return 1  # A支配B
    if worse_count == obj_dim:
        return 0  # A被B支配
    if worse_count + equal_count == obj_dim and worse_count > 0:
        return 0  # A被B支配
    return 2  # A和B互不支配


def getNonDominate(population: Population):
    """
    选取非支配解集
    Args:
        population: 待选择的种群
    Returns:
        种群的非支配解集矩阵
    """
    # 对种群进行快速非支配排序
    quick_non_dominate_sort(population)
    # 筛选出 rank 等于 1 的个体
    non_inds = [ind.copy() for ind in population.individuals if ind.rank == 1]
    return Population(individuals=non_inds, xl=population.xl, xu=population.xu)


def detection(pop: Population, problem: Problem, number_detector):
    """检测环境变化
    
    Args:
        pop: 当前种群
        problem: 问题实例
        number_detector: 检测个体数量
        
    Returns:
        1: 检测到环境变化
        0: 未检测到环境变化
    """
    if not pop.individuals:
        return 0
        
    seq = range(pop.n)
    detector = random.sample(seq, min(number_detector, pop.n))
    
    for i in detector:
        temp = pop.individuals[i]
        f, _ = problem.evaluate(temp.X.reshape(1, -1), False)
        
        # 检查目标值是否发生变化
        if not np.allclose(f[0], temp.F):
            print("环境发生变化")
            return 1
            
    return 0
