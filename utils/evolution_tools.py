import random
import numpy as np
from typing import List
from components.Population import Population
from problems.Problem import Problem


def fast_non_dominated_sort(objectives: np.ndarray) -> List[np.ndarray]:
    """
    完全向量化的快速非支配排序（无显式循环），作为工具使用，便于之后的crowd_selection和quick_non_dominate_sort
    :param objectives: 目标函数矩阵，形状 (n, m), n为个体数, m为目标数
    :return: 前沿列表，每个元素是前沿个体的索引数组
    """
    n = objectives.shape[0]

    # 1. 计算支配关系矩阵 (n, n)
    # 使用广播比较所有个体对 (i,j): [n,1,m] <= [1,n,m] → [n,n,m]
    less_or_equal = np.all(objectives[:, None] <= objectives[None, :], axis=2)
    strictly_less = np.any(objectives[:, None] < objectives[None, :], axis=2)
    domination = less_or_equal & strictly_less

    # 排除自支配 (i,i)
    np.fill_diagonal(domination, False)

    # 2. 计算被支配次数 (axis=0: 列求和)
    dominated_counts = np.sum(domination, axis=0)

    # 3. 分配前沿 (完全向量化实现)
    fronts = []
    remaining_mask = np.ones(n, dtype=bool) # 未分配个体掩码

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

    return fronts

def crowding_distance(objectives: np.ndarray, front_indices: np.ndarray) -> np.ndarray:
    """
    计算指定前沿个体的拥挤距离（向量化实现），作为工具使用，便于之后的crowd_selection和quick_non_dominate_sort
    :param objectives: 所有个体的目标函数矩阵，形状为 (n, m)
    :param front_indices: 当前前沿的个体索引数组
    :return: 每个前沿个体的拥挤距离数组，形状为 (len(front_indices),)
    """
    if len(front_indices) <= 2:
        return np.full(len(front_indices), np.inf)

    front = objectives[front_indices]
    m = front.shape[1] # 目标数
    dist = np.zeros(len(front))

    # 对每个目标归一化后计算距离
    norm = (front - front.min(axis=0)) / (front.max(axis=0) - front.min(axis=0) + 1e-10)
    # norm = front

    for i in range(m):
        order = np.argsort(norm[:, i])
        dist[order[[0, -1]]] = np.inf # 边界个体距离设为无穷
        dist[order[1:-1]] += norm[order[2:], i] - norm[order[:-2], i] # 内部个体累加距离

    return dist


def quick_non_dominate_sort(population):
    """快速非支配排序
    population: 待排序的种群
    """
    if not population.individuals:
            return

    # 提取目标函数矩阵
    objectives = population.get_objective_matrix()
    # 调用 fast_non_dominated_sort 获取前沿列表
    fronts_indices = fast_non_dominated_sort(objectives)

    # 为每个个体分配排名
    for rank, front_indices in enumerate(fronts_indices, start=1):
        for index in front_indices:
            population.individuals[index].rank = rank


def crowd_selection(population, N):
    """拥挤度选择
    population: 待选择的种群
    N: 需要选择的个体数量
    Returns:选择后的新种群
    """
    if not population.individuals:
        return Population(xl=population.xl, xu=population.xu)

    # 提取目标函数矩阵
    objectives = population.get_objective_matrix()
    # 执行快速非支配排序
    fronts = fast_non_dominated_sort(objectives)

    target_pop = []
    current_count = 0

    for front_indices in fronts:
        front = [population.individuals[i] for i in front_indices]

        if current_count + len(front) <= N:
            # 如果当前前沿的个体数量小于等于需要的数量，全部选择
            target_pop.extend(front)
            current_count += len(front)
        else:
            # 如果当前前沿的个体数量大于需要的数量，使用拥挤度选择
            objectives = population.get_objective_matrix()
            dist = crowding_distance(objectives, front_indices)
            sorted_indices = front_indices[np.argsort(-dist)]
            target_pop.extend([population.individuals[i] for i in sorted_indices[:N - current_count]])
            break

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


def getNonDominate(population: Population, type = 'population'):
    """
    选取非支配解集
    Args:
        population: 待选择的种群
    Returns:
        种群的非支配种群/解集矩阵
    """
    # 对种群进行快速非支配排序
    quick_non_dominate_sort(population)
    if type == 'population':
        # 筛选出 rank 等于 1 的个体
        non_inds = [ind.copy() for ind in population.individuals if ind.rank == 1]
        return Population(individuals=non_inds, xl=population.xl, xu=population.xu)
    elif type == 'decision':
        # 筛选出 rank 等于 1 的个体的决策变量
        non_dec = [ind.X for ind in population.individuals if ind.rank == 1]
        return non_dec
    else:
        return None


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
