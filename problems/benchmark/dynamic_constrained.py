import numpy as np

from problems.Problem import Problem


class DynamicConstrainedZDT(Problem):
    """Shared dynamic bi-objective landscape for the FlexDMO CDP suite."""

    def __init__(
        self,
        decision_num,
        n,
        tau,
        solution_num,
        total_evaluate_time,
        n_con,
    ):
        if decision_num < 2:
            raise ValueError("动态约束问题至少需要两个决策变量")
        super().__init__(
            decision_num,
            2,
            n_con,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            "DynamicConstrained",
        )

    def _phase(self, t):
        return np.pi * float(t) / self.n

    def _center(self, t):
        return 0.5 + 0.25 * np.sin(self._phase(t))

    def _evaluate_objectives(self, X, t):
        center = self._center(t)
        g = 1.0 + np.sum((X[:, 1:] - center) ** 2, axis=1)
        f1 = X[:, 0]
        f2 = g * (1.0 - np.sqrt(f1 / g))
        return np.column_stack((f1, f2))

    def _evaluate_constraints(self, X, t):
        objectives = self._evaluate_objectives(X, t)
        return self._constraints_from_objectives(objectives, t)

    def _constraints_from_objectives(self, objectives, t):
        raise NotImplementedError

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t
        f1 = np.linspace(0.0, 1.0, 4001)
        objectives = np.column_stack((f1, 1.0 - np.sqrt(f1)))
        constraints = self._constraints_from_objectives(objectives, t)
        feasible = np.all(constraints <= 1e-12, axis=1)
        return objectives[feasible]

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        f1 = self._calculate_pareto_front(t)[:, 0]
        result = np.full((len(f1), self.decision_num), self._center(t))
        result[:, 0] = f1
        return result
