import numpy as np

from algorithms.response_strategy.MDA.AutoencodingSearch import linear_autoencoder, kernel_autoencoder
from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import getNonDominate, quick_non_dominate_sort, crowd_selection
from scipy.stats import mannwhitneyu

class MDA(ResponseStrategy):
    def __init__(self):
        super().__init__()
        self.H = {}  # 用于存储历史信息，键为时间步，值为(检测器目标值, 非支配解集)
        self.D = None  # 用于检测和匹配环境

    def response(self,population, problem, algorithm):
        dim = problem.decision_num
        N = problem.solution_num
        runtime_populations = algorithm.history["runtime"]

        if self.D is None:
            # 初始化检测器
            self.D = Population(xl=problem.xl, xu=problem.xu, individuals=[ind.copy() for ind in population.individuals[:int(0.1*N)]])

        # 此处执行共有步骤：存档
        Ht = self.D.get_objective_matrix() # 直接获取，获取的是更新前的obj，即上一时刻obj
        Vt = getNonDominate(population, type = 'population')# 直接获取，获取的是更新前的dec，即上一时刻dec
        # 将Ht和Vt保存到存储池H中
        self.H[problem.t - 1] = (Ht, Vt)
        self.D.update_objective_constrain(problem)
        Ht_1 = self.D.get_objective_matrix()

        if len(runtime_populations.keys()) < 2:
            # 重新初始化
            population = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
            population.update_objective_constrain(problem)
        else:
            """Step1:论文原文Algorithm 1 Preestimation Based on MD"""
            # 主处理流程
            O, G = self._determine_OG_sets(Ht_1, problem)
            O.update_objective_constrain(problem)
            G.update_objective_constrain(problem)
            """Step2:论文原文Algorithm 2 Dynamic Strategy Based on Preestimation"""
            # 计算Np，即O和G中解的数量的较小值
            Np = min(O.n, G.n)
            # 从O和G中分别选择Np个解，使用基于拥挤度的选择方法
            quick_non_dominate_sort(O)
            quick_non_dominate_sort(G)
            O_np = crowd_selection(O, Np)
            G_np = crowd_selection(G, Np)
            """Step2.1:这里G_np作为输入集，O_np作为输出集，通过线性自编码器映射预测新解集"""
            Pl = linear_autoencoder(G_np.get_decision_matrix(), O_np.get_decision_matrix(), problem)
            Pl.update_objective_constrain(problem)
            """Step2.2:同样，G_np作为输入集，O_np作为输出集，通过核自编码器（这里使用径向基函数RBF核）映射预测新解集"""
            Pnl = kernel_autoencoder(G_np.get_decision_matrix(), O_np.get_decision_matrix(), problem, kernel='rbf', gamma=1.0)
            Pnl.update_objective_constrain(problem)
            """Step2.2:基于U检验的Pb"""
            Pb = u_test_based_adjustment(O_np, G_np, problem)
            Pb.update_objective_constrain(problem)
            """Step2.3:合并与选择"""
            population_to_select = Population(xl=problem.xl, xu=problem.xu, individuals=Pl.individuals + Pnl.individuals + Pb.individuals)
            if population_to_select.n < N:
                # 如果合并后种群大小不足N，补充随机解
                num_to_add = N - population_to_select.n
                print("种群大小不足N，补充随机解数:"+str(num_to_add))
                random_pop = Population(xl=problem.xl, xu=problem.xu, n_init=num_to_add)
                random_pop.update_objective_constrain(problem)
                population = Population(xl=problem.xl, xu=problem.xu, individuals=population_to_select.individuals+random_pop.individuals)
            else:
                # 如果合并后种群大小超过N，使用环境选择
                # 1. 快速非支配排序
                quick_non_dominate_sort(population_to_select)
                # 2. 拥挤度计算和排序
                population = crowd_selection(population_to_select, N)
            population.update_objective_constrain(problem)
        return population


    def _determine_OG_sets(self, Ht_1, problem):
        """根据历史匹配确定O和G解集"""
        match_t = self._find_best_matching_history(Ht_1, problem)

        if match_t is not None:
            print("O来自环境："+str(match_t))
            O = self.H[match_t][1]
            G = self._determine_G_set(match_t)
        else:
            # 未找到匹配时的回退方案
            print("未找到匹配，执行回退方案！！！")
            history_keys = list(self.H.keys())
            O = self.H[history_keys[-1]][1] if len(history_keys) > 0 else None
            G = self.H[history_keys[-2]][1] if len(history_keys) > 1 else None

        return O, G

    def _determine_G_set(self, match_t):
        """根据匹配的O集确定G集"""
        last_t = max(self.H.keys())

        if match_t != last_t:
            # 情况1：O不是最新集合，使用最新集合作为G
            print("G来自环境："+str(last_t))
            return self.H[last_t][1]

        # 情况2：O是最新集合，寻找次优匹配
        Hi = self.H[match_t][0]
        other_history = {t: self.H[t] for t in self.H if t != match_t}

        if not other_history:
            return None

        # 找到与Hi最接近的历史记录
        best_t = self._find_closest_history(Hi, other_history)
        print("G来自环境："+str(best_t))
        return other_history[best_t][1] if best_t is not None else None

    def _find_closest_history(self, Hi, history_dict):
        """找到与给定Hi矩阵最接近的历史记录"""
        H_prev_list = np.stack([history_dict[t][0] for t in history_dict], axis=0)

        # 计算马氏距离
        md_matrices = np.stack([mahalanobis_distance(Hi, H_prev) for H_prev in H_prev_list], axis=0)
        avg_dists = np.mean(np.abs(md_matrices), axis=2)

        # 找到最小距离的条目
        min_idx = np.argmin(np.mean(avg_dists, axis=1))
        return list(history_dict.keys())[min_idx]


    def _find_best_matching_history(self, Ht_1, problem):
        """
        通过马氏距离匹配历史最优解集并返回最佳匹配时间步
        :param Ht_1: 当前检测器目标值矩阵
        :return: match_t最佳匹配时间步
        """
        if not self.H:
            return None

        # 1. 计算马氏距离并选择候选Vt
        H_prev_list = np.stack([self.H[t][0] for t in self.H], axis=0)  # [num_prev, 0.1*n, m]

        # 矢量化计算马氏距离
        md_matrices = np.stack([mahalanobis_distance(Ht_1, H_prev) for H_prev in H_prev_list], axis=0)
        avg_dists = np.mean(np.abs(md_matrices), axis=2)  # [num_prev, m]

        # 按维度选择最佳Vt
        selected_Vts = {}
        for dim in range(Ht_1.shape[1]):
            min_idx = np.argmin(avg_dists[:, dim])
            best_t = list(self.H.keys())[min_idx]
            if best_t not in selected_Vts:
                selected_Vts[best_t] = self.H[best_t][1]

        if not selected_Vts:
            return None

        # 2. 合并候选Vt并快速非支配排序
        m = Ht_1.shape[1]
        selected_individuals = []
        source_times = []

        for best_t, Vt in selected_Vts.items():
            if Vt.n >= 2 * m:
                indices = np.random.choice(Vt.n, size=2 * m, replace=False)
            else:
                indices = np.random.choice(Vt.n, size=2 * m, replace=True)

            selected_individuals.extend(Vt.individuals[i] for i in indices)
            source_times.extend([best_t] * (2 * m))

        if not selected_individuals:
            return None

        pop_select_O = Population(xl=self.D.xl, xu=self.D.xu, individuals=selected_individuals)
        pop_select_O.update_objective_constrain(problem)
        quick_non_dominate_sort(pop_select_O)

        # 3. 统计rank1来源
        rank1_counts = {}
        for i, ind in enumerate(pop_select_O.individuals):
            if ind.rank == 1:
                t = source_times[i]
                rank1_counts[t] = rank1_counts.get(t, 0) + 1

        return max(rank1_counts, key=rank1_counts.get) if rank1_counts else None


def u_test_based_adjustment(O, G, problem):
    """
    基于U检验调整解集O中的解（矢量化优化版）
    :param O: 输出解集
    :param G: 输入解集
    :param problem: 问题实例，包含决策变量的数量等信息
    :return: 调整后的解集O
    """
    # 获取决策变量矩阵
    O_matrix = O.get_decision_matrix()
    G_matrix = G.get_decision_matrix()
    # 计算质心和差异向量（矢量化计算）
    centroid_O = np.mean(O_matrix, axis=0)
    centroid_G = np.mean(G_matrix, axis=0)
    delta = centroid_O - centroid_G
    # 对每个决策变量进行U检验（矢量化p值计算）
    p_values = np.array([
        mannwhitneyu(O_matrix[:, i], G_matrix[:, i], alternative='two-sided').pvalue
        for i in range(problem.decision_num)
    ])
    # 创建显著变化标志向量
    significant_flags = p_values < 0.05
    # 生成随机扰动矩阵（一次性生成所有随机数）
    random_perturb = np.random.uniform(-1, 1, size=O_matrix.shape)
    # 计算调整量矩阵
    adjustment = np.where(significant_flags, random_perturb * delta, np.broadcast_to(delta, O_matrix.shape))
    # 应用调整并裁剪到边界（矢量化操作）
    adjusted_matrix = O_matrix + adjustment
    adjusted_matrix = np.clip(adjusted_matrix, problem.xl, problem.xu)
    # 更新解集中的个体值
    for idx, ind in enumerate(O.individuals):
        ind.values = adjusted_matrix[idx].copy()
    return O

def mahalanobis_distance(H1, H2):
    """
    计算两个样本集之间的马氏距离。
    :param H1: 第一个样本集，形状为[N, d]，其中N是样本数量，d是变量数量
    :param H2: 第二个样本集，形状为[N, d]，其中N是样本数量，d是变量数量
    :return: 马氏距离
    """
    Q = H1 - H2
    # 确保均值为0（沿d维度）
    H1_centered = H1 - H1.mean(axis=1, keepdims=True)
    H2_centered = H2 - H2.mean(axis=1, keepdims=True)
    # 计算协方差矩阵
    cov_matrix = np.dot(H1_centered, H2_centered.T) / (H1.shape[1] - 1)
    inv_cov = np.linalg.pinv(cov_matrix)
    return Q.T @ inv_cov @ Q