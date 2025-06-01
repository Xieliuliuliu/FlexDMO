import math
import numpy as np

from components.Population import Population
from utils.evolution_tools import getNonDominate

def get_delta(Y0, Y1):
    """
    计算环境变化的严重程度δ(t)。
    参数:
    Y0:当前时刻t的目标值矩阵，形状为(N, M)。
    Y1:前一时刻t-1的目标值矩阵，形状为(N, M)。
    返回:
    delta:环境变化的严重程度。
    """
    N, M = Y0.shape  # 获取种群大小N和目标数量M
    # 计算每个目标的最大值和最小值
    u = np.max(Y0, axis=0)
    l = np.min(Y0, axis=0)
    # 初始化 delta
    delta = 0
    # 遍历每个目标
    for j in range(M):
        if u[j] != l[j]:  # 避免除以零
            # 计算每个个体在第j个目标上的归一化变化量
            f = (Y0[:, j] - Y1[:, j]) / (u[j] - l[j])
            # 计算平均变化量
            miu = np.mean(f)
            # 累加每个个体的变化量与平均变化量的差的绝对值
            delta += np.sum(np.abs(f - miu))
    return delta

def get_K(delta, M):
    """
    自适应地计算代表性个体的数量K。
    参数:
    delta(float):环境变化的严重程度，取值范围为[0, 1]。
    M (int):目标数量。
    返回:
    int:自适应计算得到的代表性个体数量K。
    """
    K1 = M + 1
    K2 = 3 * M
    K = math.ceil(K1 + delta * (K2 - K1))
    return K

def select_c(X0, Y0, K):
    N = X0.shape[0]
    dim = X0.shape[1]
    M = Y0.shape[1]

    # 计算种群的中心，即所有个体的平均值
    center = np.sum(X0, axis=0) / N
    C = [center]

    for i in range(M):
        # 原文说the M extreme solutions of the PF
        # 假设选择最小值作为极端解
        index_min = np.argmin(Y0[:, i])
        C.append(X0[index_min])
    # 转换为 NumPy 数组
    C = np.array(C)
    # 如果 C 的数量已经大于等于 K，则直接返回
    if len(C) > K:
        return C[:K]
    # 使用矢量化计算距离矩阵
    while len(C) <= K:
        # 计算每个个体到代表性个体的距离
        distances = np.linalg.norm(X0[:, np.newaxis] - C, axis=2)
        closest = np.argmin(distances, axis=1)

        # 找到每个聚类中最远的个体
        max_dist = -1
        new_rep = None

        for i in range(len(C)):
            # 获取属于当前聚类的个体
            cluster_indices = np.where(closest == i)[0]
            if len(cluster_indices) > 0:
                # 找到当前聚类中距离最远的个体
                cluster_distances = distances[cluster_indices, i]
                farthest_idx = cluster_indices[np.argmax(cluster_distances)]

                if cluster_distances.max() > max_dist:
                    max_dist = cluster_distances.max()
                    new_rep = X0[farthest_idx]
        # 如果没有找到新的代表性个体，终止循环
        if new_rep is None:
            break
        # 添加新的代表性个体
        C = np.vstack((C, new_rep))
    return C[:K]

def get_C(X0, Y0, Y1):
    delta = get_delta(Y0, Y1)
    K = get_K(delta, Y0.shape[1])
    C = select_c(X0, Y0, K)
    return C

def get_delta_c(C, C_prev):
    # 计算每个当前代表性个体到每个前一个时间步代表性个体的距离
    distance_C = np.linalg.norm(C[:, np.newaxis] - C_prev, axis=2)
    # 找到每个当前代表性个体最近的前一个时间步的代表性个体
    id = np.argmin(distance_C, axis=1)
    # 选择最近的前一个时间步的代表性个体
    temp_c = C_prev[id]
    # 计算变化量 ΔC
    delta_c = C - temp_c
    return delta_c

def get_e(sigma, mu=0):
    """
    生成一个随机扰动向量e，每个元素服从均值为mu、标准差为sigma的正态分布。
    参数:
    sigma(numpy.ndarray):标准差数组。
    mu(float, optional):均值，默认为0。
    返回:
    numpy.ndarray:随机扰动向量e。
    """
    # 生成两个独立的均匀分布随机数数组
    u = np.random.uniform(size=sigma.shape)
    v = np.random.uniform(size=sigma.shape)
    # 使用Box-Muller变换生成标准正态分布的随机数
    z = np.sqrt(-2 * np.log(u)) * np.cos(2 * np.pi * v)
    # 转换为均值为mu、标准差为sigma的正态分布随机数
    e = 0.1 * sigma * z + mu
    return e

def generate(X1_non, delta_c, C, xl, xu):
    N = X1_non.shape[0]
    dim = X1_non.shape[1]
    # 计算每个个体到每个代表性个体的距离
    distance = np.linalg.norm(X1_non[:, np.newaxis] - C, axis=2)
    # 找到每个个体最近的代表性个体的索引
    closest = np.argmin(distance, axis=1)
    # 初始化新种群
    new_pop = np.zeros((N, dim))
    # 计算随机扰动的方差
    sigma = np.sum(np.abs(delta_c), axis=0) / len(delta_c)
    # 生成随机扰动
    e = get_e(sigma)
    # 生成新的种群
    for i in range(len(C)):
        indices = np.where(closest == i)[0]
        if len(indices) > 0:
            new_pop[indices] = X1_non[indices] + delta_c[i] + e
    # 矢量化边界处理
    # 将 xl 和 xu 扩展为与 new_pop 相同的形状
    xl_expanded = xl.reshape(1, -1)
    xu_expanded = xu.reshape(1, -1)
    below_lower_bound = new_pop < xl_expanded
    above_upper_bound = new_pop > xu_expanded
    new_pop = np.where(below_lower_bound, X1_non, new_pop)
    new_pop = np.where(above_upper_bound, X1_non, new_pop)

    return new_pop

def get_pop(PS1, C, C_prev, xl, xu):
    X1 = PS1.get_decision_matrix()
    PS_non = getNonDominate(PS1)
    # X_non = PS_non.get_decision_matrix()
    X_non = PS1.get_decision_matrix()

    add = X1.shape[0] - X_non.shape[0]
    population_add = Population(xl = xl, xu = xu, n_init=add)

    delta_c = get_delta_c(C, C_prev)
    new_pop = generate(X_non, delta_c, C, xl, xu)

    population_non = Population(xl=xl, xu=xu, X=new_pop)
    population = Population(xl=xl, xu=xu, individuals=population_non.individuals+population_add.individuals)
    return population


if __name__ == "__main__":
    Y_0 = np.array([[1.2, 2.3], [1.5, 2.5], [1.8, 2.7]])
    Y_1 = np.array([[1.0, 2.0], [1.3, 2.2], [1.6, 2.4]])
    delta = get_delta(Y_0, Y_1)
    print("环境变化的严重程度 δ(t):", delta)