import random
import numpy as np

from algorithms.response_strategy.RNN import RNN_prediction
from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import quick_non_dominate_sort, crowd_selection

class RNN(ResponseStrategy):
    def __init__(self, u = 10, hidden_size = 10, dropout = 0.2, lr = 0.0001):
        super().__init__()
        self.u = u
        self.hidden_size = hidden_size
        self.dropout = dropout
        self.lr = lr
        self.X_arr = []  # 用于存储输入数据
        self.L_arr = []  # 用于存储损失
        self.H = None

    def response(self,population, problem, algorithm):
        if self.H is None:
            # 用于存储隐藏状态，在t=0时H不参与运算，但通过设置H为0以及H没有偏置，可以达成这一效果
            self.H = np.zeros([1, problem.decision_num])

        quick_non_dominate_sort(population)
        dec_u = crowd_selection(population, self.u).get_decision_matrix()
        self.X_arr.append(dec_u)

        runtime_populations = algorithm.history["runtime"]

        if problem.t < 2:# 重新初始化
            population = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
            population.update_objective_constrain(problem)
        else:
            # 获取runtime_populations的倒数二个键(最后两个t)
            t_2, t_1 = list(runtime_populations.keys())[-2:]
            # 获取最后两个环境(t)的最后一次进化结果作为历史PS
            env_2 = runtime_populations[t_2]
            env_2_last_eval = list(env_2.keys())[-1]
            X2 = env_2[env_2_last_eval].get_decision_matrix()
            env_1 = runtime_populations[t_1]
            env_1_last_eval = list(env_1.keys())[-1]
            X1 = env_1[env_1_last_eval].get_decision_matrix()

            """Step1:论文原文Algorithm 2（PSRNN）"""
            #神经网络训练，H初始为全0，则可视为无H，否则使用上一时刻得到的H
            input_size = problem.decision_num
            output_size = problem.decision_num
            rnn = RNN_prediction.RNN(input_size, self.hidden_size, output_size, self.dropout)
            H_new, L = RNN_prediction.train(rnn, self.X_arr[-2], self.X_arr[-1], self.H, self.lr)

            O = RNN_prediction.predict_by_rnn(rnn, X1, self.H)

            # 矢量化边界处理
            # 将 xl 和 xu 扩展为与 next_population 相同的形状
            xl_expanded = problem.xl.reshape(1, -1)
            xu_expanded = problem.xu.reshape(1, -1)

            below_lower_bound = O < xl_expanded
            above_upper_bound = O > xu_expanded

            O = np.where(below_lower_bound, X1, O)
            O = np.where(above_upper_bound, X1, O)

            population = Population(xl=problem.xl, xu=problem.xu, X=np.concatenate((X1, O), axis=0))
            population.update_objective_constrain(problem)
            quick_non_dominate_sort(population)
            population = crowd_selection(population, problem.solution_num)

            """Step2.1:论文原文Algorithm 3（AS）第一部分：基于损失值的多样性引入"""
            # 计算历史损失值中的大于当前损失值的数量
            l1 = 0
            aerfa = 0
            if len(self.L_arr) != 0:
                for i in range(len(self.L_arr)):
                    l1 = np.sum(L <= self.L_arr)  # 向量化比较和求和
                aerfa = l1 / len(self.L_arr)
            if aerfa > 0.5:
                X0 = population.get_decision_matrix()
                row_indices = np.random.choice(problem.solution_num, int(0.2 * problem.solution_num), replace=False)  # 生成随机索引
                select = X0[row_indices, :]

                # 一次性生成所有随机决策数
                a_values = np.random.random(len(select))
                random_mask = a_values < aerfa
                # 处理随机策略部分
                if np.any(random_mask):
                    select[random_mask] = [
                        random_strategy(x, problem.xl, problem.xu)
                        for x in select[random_mask]
                    ]
                # 处理变异部分（可进一步优化polynomial_mutation的批量处理）
                if np.any(~random_mask):
                    # 使用列表推导式代替np.array转换
                    select[~random_mask] = [
                        polynomial_mutation(x, 1 / select.shape[1], 20, problem.xl, problem.xu)
                        for x in select[~random_mask]
                    ]
                pop1 = Population(xl=problem.xl, xu=problem.xu, X=select)
                pop1.update_objective_constrain(problem)

                pop_com_1 = Population(xl=problem.xl, xu=problem.xu, individuals = pop1.individuals+population.individuals)
                quick_non_dominate_sort(pop_com_1)
                population = crowd_selection(pop_com_1, problem.solution_num)

            """Step2.2:论文原文Algorithm 3（AS）第二部分：基于U检验的解修正"""
            good = population.get_decision_matrix()[:int(0.2 * problem.solution_num), :]
            new_good = U_test(good, X1, X2)

            # 矢量化边界处理
            # 将 xl 和 xu 扩展为与 next_population 相同的形状
            xl_expanded = problem.xl.reshape(1, -1)
            xu_expanded = problem.xu.reshape(1, -1)

            below_lower_bound = new_good < xl_expanded
            above_upper_bound = new_good > xu_expanded

            new_good = np.where(below_lower_bound, good, new_good)
            new_good = np.where(above_upper_bound, good, new_good)

            pop2 = Population(xl=problem.xl, xu=problem.xu, X=new_good)
            pop2.update_objective_constrain(problem)

            population = Population(xl=problem.xl, xu=problem.xu, individuals=pop2.individuals + population.individuals[int(0.2 * problem.solution_num):])

            self.L_arr.append(L)
            self.H = H_new
        return population

def polynomial_mutation(chromosome, mutation_prob, eta_m, xl, xu):
    """
    多项式变异操作
    参数：
    chromosome: list - 实值编码的染色体 (个体)
    mutation_prob: float - 变异概率
    eta_m: float - 多项式变异分布指数
    xl: float - 基因值的最小边界
    xu: float - 基因值的最大边界
    返回：
    mutated_chromosome: list - 经过多项式变异后的染色体
    """
    # 生成随机数决定哪些基因需要变异
    mask = np.random.random(len(chromosome)) < mutation_prob
    # 生成所有基因的随机数u
    u = np.random.random(len(chromosome))
    # 计算delta值（矢量化计算）
    delta = np.where(u < 0.5,
                     (2 * u) ** (1 / (eta_m + 1)) - 1,
                     1 - (2 * (1 - u)) ** (1 / (eta_m + 1)))
    # 计算变异后的基因值
    mutated_genes = chromosome + delta * (xu - xl)
    # 修剪超出边界的值
    mutated_genes = np.clip(mutated_genes, xl, xu)
    # 组合结果：变异的基因使用新值，不变的基因保留原值
    mutated_chromosome = np.where(mask, mutated_genes, chromosome)
    return mutated_chromosome

def random_strategy(chromosome, xl, xu):
    chromosome = np.random.random(len(chromosome)) * (xu - xl) + xl
    return chromosome

def U_test(good, X1, X2):
    result = good.copy()  # 避免修改原数组
    centroid_1 = np.mean(X1, axis=0)
    centroid_2 = np.mean(X2, axis=0)
    severity = calculate_severity(X1, X2)

    # 创建布尔掩码
    mask = severity > 0.05
    # 矢量化更新结果
    result[:, mask] += (centroid_1[mask] - centroid_2[mask])

    return result

def calculate_centorid(X):
    centroid = np.mean(X, axis=0)
    return centroid

def calculate_severity(X1, X2):
    N = len(X1)
    E = np.abs(np.mean(X1, axis=0) - np.mean(X2, axis=0))

    # 更稳定的方差计算方式
    Var1 = np.var(X1, axis=0, ddof=1)  # 使用无偏估计
    Var2 = np.var(X2, axis=0, ddof=1)

    # 防止除以零
    var = np.sqrt((Var1 ** 2 + Var2 ** 2) / N)
    var = np.where(var == 0, 1e-10, var)  # 极小值替代零

    return E / var