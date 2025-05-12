import random
import numpy as np
from components.Population import Population
from problems.Problem import Problem


def quick_non_dominate_sort(population):
    """快速非支配排序（向量化实现）
    
    Args:
        population: 待排序的种群
    """
    from typing import List
    
    if not population.individuals:
        return
    
    # 提取所有个体的目标函数值
    n = len(population.individuals)
    objectives = np.array([ind.F for ind in population.individuals])
    
    # 1. 计算支配关系矩阵 (n, n)
    # 使用广播比较所有个体对 (i,j): [n,1,m] <= [1,n,m] → [n,n,m]
    less_or_equal = np.all(objectives[:, None] <= objectives[None, :], axis=2)
    strictly_less = np.any(objectives[:, None] < objectives[None, :], axis=2)
    domination = less_or_equal & strictly_less

    # 排除自支配 (i,i)
    np.fill_diagonal(domination, False)

    # 2. 计算被支配次数 (axis=0: 列求和)
    dominated_counts = np.sum(domination, axis=0)

    # 3. 分配前沿
    fronts = []
    remaining_mask = np.ones(n, dtype=bool)  # 未分配个体掩码

    while np.any(remaining_mask):
        # 当前前沿：remaining中未被支配的个体
        current_front = np.where(remaining_mask & (dominated_counts == 0))[0]
        fronts.append(current_front)

        # 更新remaining_mask
        remaining_mask[current_front] = False

        # 向量化更新被支配次数：当前前沿支配的所有remaining个体计数减1
        if np.any(remaining_mask):
            # 获取remaining个体的索引
            remaining_indices = np.where(remaining_mask)[0]

            # 计算被当前前沿支配的remaining个体
            dominated_by_front = np.sum(domination[current_front][:, remaining_indices], axis=0)
            dominated_counts[remaining_indices] -= dominated_by_front
    
    # 将分层结果设置到种群中
    for i, front in enumerate(fronts):
        for idx in front:
            population.individuals[idx].rank = i


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
