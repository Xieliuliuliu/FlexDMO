from algorithms.search_algorithm.Algorithm import Algorithm
from components.Population import Population
from utils.evolution_tools import detection,crowd_selection,quick_non_dominate_sort
import numpy as np
import random
from algorithms.search_algorithm.RMMEDA.LocalPCA import LocalPCA


class RMMEDA(Algorithm):
    def __init__(self, K=5,**args):
        super().__init__(**args)
        self.K = K

    def optimize(self, problem, response_strategy):
         # 初始化种群
        pop = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
        pop.update_objective_constrain(problem)
        while not problem.is_ended() and self.control_process():
            # 检测环境变化
            if detection(pop, problem, int(0.1 * problem.solution_num)) == 1:
                pop = response_strategy.response(pop, problem, self)
                self.collect_information(pop, problem, response_strategy)  # 收集运行信息
                continue
            # 生成子代
            offspring = self._rmmeda_operator(pop, problem)
            offspring.update_objective_constrain(problem)
            # 合并父代和子代
            combined = Population(individuals=pop.individuals + offspring.individuals, xl=problem.xl, xu=problem.xu)
            quick_non_dominate_sort(combined)
            pop = crowd_selection(combined,problem.solution_num)
            self.collect_information(pop, problem, response_strategy) 

    def _rmmeda_operator(self, pop, problem):
        # 获取决策变量
        PopDec = np.array([ind.X for ind in pop.individuals])
        N, D = PopDec.shape
        M = problem.n_obj
        
        # 建模
        Model, cn = LocalPCA(PopDec, M, self.K)
        
        # 生成子代
        OffspringDec = np.zeros((N, D))
        tn = 0
        ast = 0
        
        for k in range(self.K):
            # 生成子代
            LInd = np.ones([int(cn[0,k]), M-1])
            for i in range(M-1):
                LInd[:,i] = random.sample(range(int(cn[0,k])), int(cn[0,k]))
                
            for i in range(int(cn[0,k])):
                if cn[0,k] > 2:
                    lower = Model[k]['a'] - 0.25 * (Model[k]['b'] - Model[k]['a'])
                    upper = Model[k]['b'] + 0.25 * (Model[k]['b'] - Model[k]['a'])
                    trial = (LInd[i,:] - np.random.random([1,M-1]))/cn[0,k] * (upper - lower) + lower
                    sigma = np.sum(np.abs(Model[k]['eValue'][M-1:D])) / (D - M + 1)
                    ast = sigma
                    OffspringDec[int(i + tn), :] = Model[k]['mean'] + np.dot(Model[k]['eVector'][:,:M-1], np.transpose(trial)).transpose() + np.random.randn(D) * np.sqrt(sigma)
                else:
                    OffspringDec[int(i + tn), :] = Model[k]['mean'] + np.random.randn(D) * np.sqrt(ast)
            tn = tn + cn[0,k]
            
        # 边界处理
        low = np.tile(problem.xl, (N, 1))
        upp = np.tile(problem.xu, (N, 1))
        lbnd = OffspringDec < low
        ubnd = OffspringDec > upp
        
        for i in range(N):
            for j in range(D):
                if lbnd[i, j]:
                    OffspringDec[i, j] = 0.5 * (PopDec[i, j] + low[0, j])
                if ubnd[i, j]:
                    OffspringDec[i, j] = 0.5 * (PopDec[i, j] + upp[0, j])
        
        # 创建新的种群
        offspring = Population(xl=problem.xl, xu=problem.xu, n_init=N)
        for i in range(N):
            offspring.individuals[i].X = OffspringDec[i]
            
        return offspring
        
