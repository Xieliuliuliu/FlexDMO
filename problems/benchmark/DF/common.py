"""CEC 2018 DF1-DF14 动态多目标 benchmark 公共实现。

平台离散环境编号 ``t`` 按论文转换为连续时间 ``t/n_t``。DF1-DF9 为双目标，
DF10-DF14 为三目标，全部无约束。公式和变量边界来自 CEC'2018 官方报告。
"""
from __future__ import annotations

import numpy as np

from problems.Problem import Problem
from utils.evolution_tools import fast_non_dominated_sort


class DFBase(Problem):
    """DF 公共基类；具体问题只声明 ``problem_number``。"""
    problem_number = None

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        p = self.problem_number
        if p not in range(1, 15):
            raise TypeError("DFBase 需要 problem_number=1..14")
        if decision_num < (3 if p >= 10 else 2):
            raise ValueError(f"DF{p} 的决策变量维数不足")
        super().__init__(decision_num, 2 if p <= 9 else 3, 0, n, tau,
                         solution_num, total_evaluate_time, "Dynamic")
        self.xl, self.xu = np.zeros(decision_num), np.ones(decision_num)
        if p == 3:
            self.xl[1:], self.xu[1:] = -1.0, 2.0
        elif p == 4:
            self.xl[:], self.xu[:] = -2.0, 2.0
        elif p in {5, 6, 8, 9}:
            self.xl[1:], self.xu[1:] = -1.0, 1.0
        elif p == 7:
            self.xl[0], self.xu[0] = 1.0, 4.0
        elif p in {10, 12, 13, 14}:
            self.xl[2:], self.xu[2:] = -1.0, 1.0

    def _time(self, t=None):
        """论文连续时间：离散环境编号除以变化严重度 ``n_t``。"""
        return float(self.t if t is None else t) / self.n

    def _evaluate_objectives(self, X, t=None):
        """按官方式 (1)-(14) 批量计算目标。"""
        X, time, p = np.asarray(X, float), self._time(t), self.problem_number
        x1 = X[:, 0]
        if p == 1:
            G, H = abs(np.sin(.5*np.pi*time)), .75*np.sin(.5*np.pi*time)+1.25
            g = 1 + np.sum((X[:, 1:]-G)**2, axis=1)
            return np.c_[x1, g*(1-(x1/g)**H)]
        if p == 2:
            G = abs(np.sin(.5*np.pi*time)); r = int(np.floor((self.decision_num-1)*G))
            mask = np.ones(self.decision_num, bool); mask[r] = False
            g = 1 + np.sum((X[:, mask]-G)**2, axis=1); f1 = X[:, r]
            return np.c_[f1, g*(1-np.sqrt(f1/g))]
        if p == 3:
            G = np.sin(.5*np.pi*time); H = 1.5+G
            g = 1 + np.sum((X[:, 1:]-G-x1[:, None]**H)**2, axis=1)
            return np.c_[x1, g*(1-(x1/g)**H)]
        if p == 4:
            a = np.sin(.5*np.pi*time); b = 1+abs(np.cos(.5*np.pi*time)); H = 1.5+a
            target = a*x1[:, None]**2/np.arange(2, self.decision_num+1)
            g = 1 + np.sum((X[:, 1:]-target)**2, axis=1)
            return np.c_[g*abs(x1-a)**H, g*abs(x1-a-b)**H]
        if p == 5:
            G = np.sin(.5*np.pi*time); w = np.floor(10*G)
            g = 1 + np.sum((X[:, 1:]-G)**2, axis=1); wave = .02*np.sin(w*np.pi*x1)
            return np.c_[g*(x1+wave), g*(1-x1+wave)]
        if p == 6:
            G = np.sin(.5*np.pi*time); a = .2+2.8*abs(G); y = X[:, 1:]-G
            g = 1 + np.sum(abs(G)*y**2-10*np.cos(2*np.pi*y)+10, axis=1)
            wave = .1*np.sin(3*np.pi*x1)
            return np.c_[g*np.maximum(x1+wave, 0)**a,
                         g*np.maximum(1-x1+wave, 0)**a]
        if p == 7:
            a = 5*np.cos(.5*np.pi*time)
            target = 1/(1+np.exp(a*(x1[:, None]-2.5)))
            g = 1 + np.sum((X[:, 1:]-target)**2, axis=1)
            return np.c_[g*(1+time)/x1, g*x1/(1+time)]
        if p == 8:
            G = np.sin(.5*np.pi*time); a = 2.25+2*np.cos(2*np.pi*time); beta = 100*G**2
            target = G*np.sin(4*np.pi*x1[:, None]**beta)/(1+abs(G))
            g = 1 + np.sum((X[:, 1:]-target)**2, axis=1); wave = .1*np.sin(3*np.pi*x1)
            return np.c_[g*(x1+wave), g*np.maximum(1-x1+wave, 0)**a]
        if p == 9:
            N = 1+np.floor(10*abs(np.sin(.5*np.pi*time))); g = np.ones(len(X))
            for i in range(1, self.decision_num):
                g += (X[:, i]-np.cos(4*time+x1+X[:, i-1]))**2
            bump = np.maximum(0, (.1+.5/N)*np.sin(2*N*np.pi*x1))
            return np.c_[g*(x1+bump), g*(1-x1+bump)]

        x2 = X[:, 1]
        if p == 10:
            G = np.sin(.5*np.pi*time); H = 2.25+2*np.cos(.5*np.pi*time)
            target = (np.sin(2*np.pi*(x1+x2))/(1+abs(G)))[:, None]
            g = 1 + np.sum((X[:, 2:]-target)**2, axis=1)
            return np.c_[g*np.sin(.5*np.pi*x1)**H,
                         g*(np.sin(.5*np.pi*x2)*np.cos(.5*np.pi*x1))**H,
                         g*(np.cos(.5*np.pi*x2)*np.cos(.5*np.pi*x1))**H]
        if p == 11:
            G = abs(np.sin(.5*np.pi*time))
            g = 1+G+np.sum((X[:, 2:]-.5*G*x1[:, None])**2, axis=1)
            y1 = np.pi*G/6+(np.pi/2-np.pi*G/3)*x1
            y2 = np.pi*G/6+(np.pi/2-np.pi*G/3)*x2
            return np.c_[g*np.sin(y1), g*np.sin(y2)*np.cos(y1), g*np.cos(y2)*np.cos(y1)]
        if p == 12:
            k = 10*np.sin(np.pi*time); target = np.sin(time*x1)[:, None]
            holes = abs(np.sin(np.floor(k*(2*X[:, :2]-1))*np.pi/2))
            g = 1+np.sum((X[:, 2:]-target)**2, axis=1)+np.prod(holes, axis=1)
            return np.c_[g*np.cos(.5*np.pi*x1)*np.cos(.5*np.pi*x2),
                         g*np.cos(.5*np.pi*x1)*np.sin(.5*np.pi*x2),
                         g*np.sin(.5*np.pi*x1)]
        if p == 13:
            G = np.sin(.5*np.pi*time); q = np.floor(6*G)
            g = 1+np.sum((X[:, 2:]-G)**2, axis=1)
            s1, s2 = np.sin(.5*np.pi*x1), np.sin(.5*np.pi*x2)
            return np.c_[g*np.cos(.5*np.pi*x1)**2, g*np.cos(.5*np.pi*x2)**2,
                         g*(s1**2+s1*np.cos(q*np.pi*x1)**2+s2**2+s2*np.cos(q*np.pi*x2)**2)]
        G = np.sin(.5*np.pi*time); g = 1+np.sum((X[:, 2:]-G)**2, axis=1)
        y = .5+G*(x1-.5); yw = y+.05*np.sin(6*np.pi*y)
        return np.c_[g*(1-y+.05*np.sin(6*np.pi*y)),
                     g*(1-x2+.05*np.sin(6*np.pi*x2))*yw,
                     g*(x2+.05*np.sin(6*np.pi*x2))*yw]

    def _calculate_pareto_set(self, t=None):
        """按解析 PS 关系采样决策空间；三目标采用二维规则网格。"""
        time, p = self._time(t), self.problem_number
        if p <= 9:
            if p == 7: lo, hi = 1., 4.
            elif p == 4:
                lo = np.sin(.5*np.pi*time); hi = lo+1+abs(np.cos(.5*np.pi*time))
            else: lo, hi = 0., 1.
            X = np.zeros((1001, self.decision_num)); X[:, 0] = np.linspace(lo, hi, 1001)
        else:
            a, b = np.meshgrid(np.linspace(0, 1, 33), np.linspace(0, 1, 33), indexing="xy")
            X = np.zeros((a.size, self.decision_num)); X[:, 0], X[:, 1] = a.ravel(), b.ravel()
        G = np.sin(.5*np.pi*time)
        if p == 1: X[:, 1:] = abs(G)
        elif p == 2:
            value = abs(G); r = int(np.floor((self.decision_num-1)*value)); X[:] = value
            X[:, r] = np.linspace(0, 1, len(X))
        elif p == 3: X[:, 1:] = G+X[:, [0]]**(1.5+G)
        elif p == 4: X[:, 1:] = G*X[:, [0]]**2/np.arange(2, self.decision_num+1)
        elif p in {5, 6}: X[:, 1:] = G
        elif p == 7:
            X[:, 1:] = 1/(1+np.exp(5*np.cos(.5*np.pi*time)*(X[:, [0]]-2.5)))
        elif p == 8:
            X[:, 1:] = G*np.sin(4*np.pi*X[:, [0]]**(100*G**2))/(1+abs(G))
        elif p == 9:
            for i in range(1, self.decision_num): X[:, i] = np.cos(4*time+X[:, 0]+X[:, i-1])
        elif p == 10:
            X[:, 2:] = (np.sin(2*np.pi*(X[:, 0]+X[:, 1]))/(1+abs(G)))[:, None]
        elif p == 11: X[:, 2:] = .5*abs(G)*X[:, [0]]
        elif p == 12: X[:, 2:] = np.sin(time*X[:, [0]])
        else: X[:, 2:] = G
        return np.clip(X, self.xl, self.xu)

    def _calculate_pareto_front(self, t=None):
        """将解析 PS 映射为 PF，并过滤具有孔洞/断裂的被支配采样点。"""
        front = self._evaluate_objectives(self._calculate_pareto_set(t), t)
        if self.problem_number in {9, 12, 13}:
            front = front[fast_non_dominated_sort(front)[0]]
        return front[np.argsort(front[:, 0], kind="stable")] if front.shape[1] == 2 else front


class DF1Base(DFBase): problem_number = 1
class DF2Base(DFBase): problem_number = 2
class DF3Base(DFBase): problem_number = 3
class DF4Base(DFBase): problem_number = 4
class DF5Base(DFBase): problem_number = 5
class DF6Base(DFBase): problem_number = 6
class DF7Base(DFBase): problem_number = 7
class DF8Base(DFBase): problem_number = 8
class DF9Base(DFBase): problem_number = 9
class DF10Base(DFBase): problem_number = 10
class DF11Base(DFBase): problem_number = 11
class DF12Base(DFBase): problem_number = 12
class DF13Base(DFBase): problem_number = 13
class DF14Base(DFBase): problem_number = 14
