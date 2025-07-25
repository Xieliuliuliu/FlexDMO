import random

import matplotlib.pyplot as plt
import numpy as np

from algorithms.search_algorithm.Algorithm import Algorithm
from components.Population import Population
from utils.evolution_tools import quick_non_dominate_sort, crowd_selection


class HTPSNSGA2(Algorithm):
    def __init__(self, proC=1.0, disC=10, proM=1.0, disM=10,**args):
        super().__init__(**args)
        self.proC = proC
        self.disC = disC
        self.proM = proM
        self.disM = disM

    def optimize(self, problem, response_strategy):
        # 初始化种群
        pop = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
        pop.update_objective_constrain(problem)
        self.add_pen_to_f(pop,problem)
        while not problem.is_ended() and self.control_process():
            # 检测环境变化
            if self.detection(pop, problem, int(0.1 * problem.solution_num)) == 1:
                pop = response_strategy.response(pop, problem, self)
                self.add_pen_to_f(pop, problem)
                self.collect_information(pop, problem, response_strategy)  # 收集运行信息
                continue
            # 生成子代
            offspring = self._variation(pop, problem)
            offspring.update_objective_constrain(problem)
            self.add_pen_to_f(offspring, problem)
            # 合并父代和子代
            combined = Population(individuals=pop.individuals + offspring.individuals, xl=problem.xl, xu=problem.xu)
            # 环境选择
            pop = self._environmental_selection(combined, problem)

            self.collect_information(pop, problem, response_strategy) # 收集运行信息

    def add_pen_to_f(self,population,problem):
        # 获取目标函数和约束矩阵
        F = population.get_objective_matrix()
        G = population.get_constrain_matrix()  # 每行是一个个体的所有约束残差（包括等式和不等式）
        # return
        # 针对每个个体计算罚值并更新其 F 属性（带惩罚）
        for i in range(population.n):
            # 取该个体的原始目标值
            f_i = F[i]
            g_i = G[i]

            # 罚值计算方式（常用的是等式绝对值 + max(0, 不等式残差)）
            violation = np.sum(np.abs(g_i[:problem.n_con]))

            # 加权惩罚（可调参数，例如罚因子 1e6）
            penalty_factor = 1e2
            penalized_f = f_i + penalty_factor * violation
            print(violation)
            # 更新个体的 F 属性（可选是否保留原目标 f_i）
            population.individuals[i].F = penalized_f

    def _variation(self, pop, problem):
        child = self._sbx_crossover(pop.get_decision_matrix(), problem.solution_num, problem.decision_num, self.proC, self.disC)
        child = self._polynomial_mutation(child, self.proM, self.disM, problem)
        return Population(X=child, xl=problem.xl, xu=problem.xu)

    def _sbx_crossover(self, pop, n, D, proC, disC):
        parent_1 = pop[0:n // 2]
        parent_2 = pop[n // 2:2 * (n // 2)]
        beta = np.zeros((parent_1.shape[0], D))
        rand = np.random.random((parent_1.shape[0], D))

        beta[rand < 0.5] = np.power(2 * rand[rand < 0.5], 1 / (disC + 1))
        beta[rand >= 0.5] = np.power(2 * (1 - rand[rand >= 0.5]), -1 / (disC + 1))

        # 将beta随机取正负
        beta = np.multiply(beta, (-1) ** np.random.randint(0, 2, (parent_1.shape[0], D)))
        # 随机一半的参数不变
        beta[np.random.random((parent_1.shape[0], D)) < 0.5] = 1

        # 按照ProC的杂交概率进行参数变化
        beta[np.repeat(np.random.random((parent_1.shape[0], 1)) > proC, D, 1)] = 1
        # 杂交
        return np.vstack(((parent_1 + parent_2) / 2 + np.multiply(beta, parent_1 - parent_2) / 2,
                          (parent_1 + parent_2) / 2 + np.multiply(beta, parent_2 - parent_1) / 2))

    def _polynomial_mutation(self, offspring, proM, disM, problem):
        N = problem.solution_num
        Lower = np.tile(problem.xl, (N, 1))
        Upper = np.tile(problem.xu, (N, 1))

        D = offspring.shape[1]
        Site = np.random.rand(N, D) < proM / D
        mu = np.random.rand(N, D)

        offspring = np.clip(offspring, Lower, Upper)

        temp = Site & (mu <= 0.5)
        offspring[temp] += (Upper[temp] - Lower[temp]) * (
                (2 * mu[temp] + (1 - 2 * mu[temp]) *
                 (1 - (offspring[temp] - Lower[temp]) / (Upper[temp] - Lower[temp])) ** (disM + 1))
                ** (1 / (disM + 1)) - 1)

        temp = Site & (mu > 0.5)
        offspring[temp] += (Upper[temp] - Lower[temp]) * (
                1 - (2 * (1 - mu[temp]) + 2 * (mu[temp] - 0.5) *
                     (1 - (Upper[temp] - offspring[temp]) / (Upper[temp] - Lower[temp])) ** (disM + 1))
                ** (1 / (disM + 1)))
        offspring = np.where(offspring < problem.xl, problem.xl, offspring)
        offspring = np.where(offspring > problem.xu, problem.xu, offspring)
        return offspring

    def detection(self, pop, problem, number_detector):
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
            f, g = problem.evaluate(temp.X.reshape(1, -1), False)
            # 罚值计算方式（常用的是等式绝对值 + max(0, 不等式残差)）
            violation = np.sum(np.abs(g[0][:problem.n_con]))

            # 加权惩罚（可调参数，例如罚因子 1e6）
            penalty_factor = 1e2
            penalized_f = f + penalty_factor * violation
            # 检查目标值是否发生变化
            if not np.allclose(penalized_f[0], temp.F):
                print("环境发生变化")
                return 1

        return 0

    def _environmental_selection(self, population, problem):
        # 非支配排序 + 拥挤度选择
        quick_non_dominate_sort(population)
        return crowd_selection(population, problem.solution_num)

# from problems.benchmark.DP1.main import DP1
# from algorithms.response_strategy.NoResponse.main import NoResponse
# nsga = NSGA2()
# response = NoResponse()
# df1 = DP1(10, 10, 20, 100, 30)
# nsga.optimize(df1, response)
