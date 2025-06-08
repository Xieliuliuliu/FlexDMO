import numpy as np

from components.Population import Population


def linear_autoencoder(G, O, problem, lambda_reg=1e-6):
    """
    线性自编码器的映射矩阵 M
    :param G: 输入解集
    :param O: 输出解集
    lambda_reg: 正则化系数，防止矩阵奇异
    :return: 映射矩阵M
    """
    # 计算 M = O @ G.T @ (G @ G.T + λI)^(-1)
    GGT = G @ G.T
    GGT_reg = GGT + lambda_reg * np.eye(GGT.shape[0])  # 添加正则化项
    try:
        # 尝试计算逆矩阵
        GGT_inv = np.linalg.inv(GGT_reg)
    except np.linalg.LinAlgError:
        # 如果仍然奇异，使用伪逆
        GGT_inv = np.linalg.pinv(GGT_reg)
    M = O @ G.T @ np.linalg.inv(GGT_inv)
    ans1 = M @ O
    # 矢量化边界处理
    # 将 xl 和 xu 扩展为与 next_population 相同的形状
    xl_expanded = problem.xl.reshape(1, -1)
    xu_expanded = problem.xu.reshape(1, -1)

    below_lower_bound = ans1 < xl_expanded
    above_upper_bound = ans1 > xu_expanded

    ans1 = np.where(below_lower_bound, O, ans1)
    ans1 = np.where(above_upper_bound, O, ans1)
    return Population(xl=problem.xl, xu=problem.xu, X=ans1)

def kernel_autoencoder(G, O, problem, kernel='rbf', gamma=1.0, lambda_reg=1e-6):
    """
    核自编码器的映射矩阵 Mk
    :param G: 输入解集
    :param O: 输出解集
    :param kernel: 核函数类型('rbf', 'poly等)
    :param gamma: RBF核的参数
    :param lambda_reg: 正则化系数，防止矩阵奇异
    :return: 映射矩阵Mk
    """
    # 计算核矩阵K(G, G)
    K_GG = compute_kernel_matrix(G, kernel_type=kernel, gamma=gamma)
    K_OO = compute_kernel_matrix(O, kernel_type=kernel, gamma=gamma)
    # 计算 K(G, G) @ K(G, G)^T + λI
    K_GGK_GGT = K_GG @ K_GG.T
    K_GGK_GGT_reg = K_GGK_GGT + lambda_reg * np.eye(K_GGK_GGT.shape[0])  # 添加正则化项
    try:
        # 尝试计算逆矩阵
        K_GGK_GGT_inv = np.linalg.inv(K_GGK_GGT_reg)
    except np.linalg.LinAlgError:
        # 如果仍然奇异，使用伪逆
        K_GGK_GGT_inv = np.linalg.pinv(K_GGK_GGT_reg)
    # 计算映射矩阵Mk (根据论文公式(5))
    Mk = (O @ K_GG.T) @ K_GGK_GGT_inv
    ans2 = Mk @ K_OO
    # 矢量化边界处理
    # 将 xl 和 xu 扩展为与 next_population 相同的形状
    xl_expanded = problem.xl.reshape(1, -1)
    xu_expanded = problem.xu.reshape(1, -1)

    below_lower_bound = ans2 < xl_expanded
    above_upper_bound = ans2 > xu_expanded

    ans2 = np.where(below_lower_bound, O, ans2)
    ans2 = np.where(above_upper_bound, O, ans2)
    return Population(xl=problem.xl, xu=problem.xu, X=ans2)

def compute_kernel_matrix(P, kernel_type='rbf', gamma=1.0):
    """
    计算核矩阵 K(P, P)。
    :param P: 形状为[d, N]的numpy数组，表示N个d维数据点
    :param kernel_type: 核函数类型
    :param gamma: 核函数的参数
    :return: 形状为 [N, N] 的核矩阵
    """
    N = P.shape[1]  # 数据点的数量
    if kernel_type == 'rbf':
        pairwise_differences = P[:, np.newaxis, :] - P[:, :, np.newaxis]
        squared_distances = np.sum(pairwise_differences ** 2, axis=0)
        K = np.exp(-gamma * squared_distances)
    elif kernel_type == 'poly':
        K = (P.T @ P + 1) ** gamma
    else:
        raise ValueError("Unsupported kernel type")
    return K

# 示例用法
if __name__ == "__main__":
    # 生成示例数据
    np.random.seed(42)
    G = np.random.rand(10, 2)  # 输入解集 (10个解，每个解5维)
    O = np.random.rand(10, 2)  # 输出解集 (10个解，每个解5维)

    # 线性自编码器
    ans1 = linear_autoencoder(O, G)
    print("线性自编码器的映射矩阵 M (形状 {}):".format(ans1.shape))
    print(ans1)

    # 核自编码器
    ans2 = kernel_autoencoder(O, G, kernel='rbf', gamma=0.1)
    print("\n核自编码器的映射矩阵 Mk (形状 {}):".format(ans2.shape))
    print(ans2)