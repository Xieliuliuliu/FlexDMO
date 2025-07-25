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
        decision_num = self.M * (self.Nh + self.Ns)
        super().__init__(decision_num, 2, self.M + self.Nh,0, 2000, 240, 1, 'HTPS')
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

        self.load_demand = [900, 1100, 1000, 1300]

    def _set_variable_bounds(self):
        xl, xu = [], []
        for _ in range(self.M):
            for h in self.hydro_units:
                xl.append(h['Pmin'])
                xu.append(h['Pmax'])
            for s in self.thermal_cost_units:
                xl.append(s['Pmin'])
                xu.append(s['Pmax'])
        self.xl = np.array(xl)
        self.xu = np.array(xu)

    def _evaluate_objectives(self, X, t=None):
        f1, f2 = [], []
        for x in X:
            x = x.reshape((self.M, self.Nh + self.Ns))
            obj1 = 0.0
            obj2 = 0.0
            for t_idx in range(self.M):
                Pst = x[t_idx, self.Nh:]
                for s, P in enumerate(Pst):
                    cost_param = self.thermal_cost_units[s]
                    emis_param = self.thermal_emission_units[s]

                    # 成本函数项
                    a = cost_param['a']
                    b = cost_param['b']
                    c = cost_param['c']
                    d = cost_param['d']
                    e = cost_param['e']
                    Pmin_s = cost_param['Pmin']
                    term_cost = a + b * P + c * P ** 2 + abs(d * np.sin(e * (Pmin_s - P)))
                    obj1 += self.tT * term_cost

                    # 排放函数项
                    alpha = emis_param['alpha']
                    beta = emis_param['beta']
                    gamma = emis_param['gamma']
                    eta = emis_param['eta']
                    delta = emis_param['delta']
                    term_emis = alpha + beta * P + gamma * P ** 2 + eta * np.exp(delta * P)
                    obj2 += self.tT * term_emis

            f1.append(obj1)
            f2.append(obj2)
        return np.column_stack([f1, f2])

    def _evaluate_constraints(self, X, t):
        cons = []
        for x in X:
            x = x.reshape((self.M, self.Nh + self.Ns))
            eq = []
            ineq = []
            for t_idx in range(self.M):
                pt = x[t_idx]
                Pht = pt[:self.Nh]
                Pst = pt[self.Nh:]
                total_gen = np.sum(Pht) + np.sum(Pst)
                PLt = pt @ self.B @ pt.T
                eq.append( self.load_demand[t_idx] + PLt-total_gen)

            for h, h_param in enumerate(self.hydro_units):
                total_water = 0.0
                for t_idx in range(self.M):
                    P = x[t_idx, h]
                    total_water += self.tT * (h_param['a0h'] + h_param['a1h'] * P + h_param['a2h'] * P ** 2)
                eq.append( h_param['Wh']-total_water)

            for t_idx in range(self.M):
                pt = x[t_idx]
                Pht = pt[:self.Nh]
                Pst = pt[self.Nh:]
                for h, P in enumerate(Pht):
                    h_param = self.hydro_units[h]
                    ineq.append(h_param['Pmin'] - P)
                    ineq.append(P - h_param['Pmax'])
                for s, P in enumerate(Pst):
                    s_param = self.thermal_cost_units[s]
                    ineq.append(s_param['Pmin'] - P)
                    ineq.append(P - s_param['Pmax'])

            cons.append(np.concatenate([eq, ineq]))
        return np.array(cons)

    def _calculate_pareto_front(self, t=None):
        return np.empty((0, 2))

    def _calculate_pareto_set(self, t=None):
        return np.empty((0, self.decision_num))

    def repair_X(self, X):
        repaired = []
        for x in X:
            x_fixed = self.repair_x_single(x)
            if x_fixed is None:
                repaired.append(None)  # 或者 append(x) 保留原解
            else:
                repaired.append(x_fixed)
        return repaired

    def repair_x_single(self, x):
        x = x.reshape((self.M, self.Nh + self.Ns)).copy()

        for h in range(self.Nh):
            h_param = self.hydro_units[h]
            a0, a1, a2 = h_param['a0h'], h_param['a1h'], h_param['a2h']
            Wh = h_param['Wh']
            Pmin, Pmax = h_param['Pmin'], h_param['Pmax']

            success = False
            for attempt in range(self.M):  # 尝试 M 次不同的 mu
                mu = (attempt + np.random.randint(0, self.M)) % self.M

                A = a2
                B = a1
                C = (1 / (self.tT * A)) * (
                        -Wh + a0 * self.tT +
                        sum(self.tT * a1 * x[t, h] for t in range(self.M) if t != mu) +
                        sum(self.tT * a2 * x[t, h] ** 2 for t in range(self.M) if t != mu)
                )

                delta = B ** 2 - 4 * A * C
                if delta < 0:
                    continue

                roots = [(-B + np.sqrt(delta)) / (2 * A), (-B - np.sqrt(delta)) / (2 * A)]
                valid_roots = [r for r in roots if Pmin <= r <= Pmax]
                if not valid_roots:
                    continue

                Ph_mu = valid_roots[0]
                Ph_mu_orig = x[mu, h]
                ratio = Ph_mu / Ph_mu_orig if Ph_mu_orig != 0 else 1.0
                x[mu, h] = Ph_mu

                violate = False
                for t in range(self.M):
                    if t != mu:
                        x[t, h] *= ratio
                        if not (Pmin <= x[t, h] <= Pmax):
                            violate = True
                            break
                if not violate:
                    success = True
                    break

            if not success:
                return x.flatten()

        return x.flatten()
