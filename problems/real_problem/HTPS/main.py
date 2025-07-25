import numpy as np
import json
import os

from problems.Problem import Problem


class HTPS(Problem):
    def __init__(self):
        self.M = 4
        self.tT = 48/self.M
        self.Nh = 2
        self.Ns = 4
        decision_num =  self.Ns = 4
        super().__init__(decision_num, 2, 1,0, 50, 240, self.M, 'HTPS')
        self.json_path = './problems/real_problem/HTPS/data.json'
        self._load_problem_data()
        self._set_variable_bounds()

    def _load_problem_data(self):
        with open(self.json_path, 'r') as f:
            data = json.load(f)

        self.hydro_units = data['hydro_units']
        self.thermal_cost_units = data['thermal_cost_units']
        self.thermal_emission_units = data['thermal_emission_units']
        self.B = np.array(data['B_loss_matrix']) * data['B_loss_scale']

        self.load_demand = [900, 1000, 1100, 1300]

    def _set_variable_bounds(self):
        xl, xu = [], []
        for s in self.thermal_cost_units:
            xl.append(s['Pmin'])
            xu.append(s['Pmax'])
        self.xl = np.array(xl)
        self.xu = np.array(xu)


    def _evaluate_objectives(self, X, t=None):
        f1_list, f2_list = [], []
        for Pst in X:
            obj1 = 0.0
            obj2 = 0.0
            for s, P in enumerate(Pst):
                # 成本参数
                c_param = self.thermal_cost_units[s]
                a, b, c, d, e, Pmin_s = c_param['a'], c_param['b'], c_param['c'], c_param['d'], c_param['e'], c_param[
                    'Pmin']
                cost = a + b * P + c * P ** 2 + abs(d * np.sin(e * (Pmin_s - P)))
                obj1 += self.tT * cost

                # 排放参数
                e_param = self.thermal_emission_units[s]
                alpha, beta, gamma, eta, delta = e_param['alpha'], e_param['beta'], e_param['gamma'], e_param['eta'], \
                e_param['delta']
                emis = alpha + beta * P + gamma * P ** 2 + eta * np.exp(delta * P)
                obj2 += self.tT * emis

            f1_list.append(obj1)
            f2_list.append(obj2)

        return np.column_stack([f1_list, f2_list])

    def _evaluate_constraints(self, X, t):
        """
        动态问题下的约束计算：
        - 当前时刻 t 的火电出力 X (N, 4)
        - 水电出力固定，由 water availability 反解而得
        - 仅考虑功率平衡等式约束
        """
        Pht = self.compute_constant_Pht()  # [Nh]
        cons = []
        for x in X:
            pt = np.concatenate([Pht, x])  # [Nh + Ns]
            total_gen = np.sum(pt)
            PLt = pt @ self.B @ pt.T
            residual = self.load_demand[t] + PLt - total_gen
            cons.append([residual])
        return np.array(cons)  # shape (N, 1)

    def compute_constant_Pht(self):
        Pht = []
        for h, h_param in enumerate(self.hydro_units):
            a0, a1, a2 = h_param['a0h'], h_param['a1h'], h_param['a2h']
            Wh = h_param['Wh']

            A = a2
            B = a1
            C = a0 - Wh / (self.M * self.tT)

            delta = B ** 2 - 4 * A * C
            if delta < 0:
                raise ValueError(f"Discriminant < 0 for hydro unit {h}, no real root")

            roots = [(-B + np.sqrt(delta)) / (2 * A), (-B - np.sqrt(delta)) / (2 * A)]
            # 选择在 [Pmin, Pmax] 范围内的那个解
            Pmin, Pmax = h_param['Pmin'], h_param['Pmax']
            feasible_roots = [r for r in roots if Pmin <= r <= Pmax]
            if not feasible_roots:
                raise ValueError(f"No feasible root in bounds for hydro unit {h}")
            Pht.append(feasible_roots[0])  # 任选一个可行根
        return np.array(Pht)  # [Nh]

    def _calculate_pareto_front(self, t=None):
        return np.empty((0, 2))

    def _calculate_pareto_set(self, t=None):
        return np.empty((0, self.decision_num))