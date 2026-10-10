import numpy as np

from problems.Problem import Problem


class CDP1(Problem):
    """A constrained dynamic bi-objective benchmark.

    The feasible part of the Pareto front changes over time while the
    decision-space manifold also moves. Constraint values follow the project
    convention: values less than or equal to zero are feasible.
    """

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        if decision_num < 2:
            raise ValueError("CDP1 至少需要两个决策变量")
        super().__init__(
            decision_num,
            2,
            1,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            "DynamicConstrained",
        )

    def _dynamic_state(self, t):
        phase = np.pi * t / self.n
        center = 0.5 + 0.25 * np.sin(phase)
        threshold = 0.35 + 0.15 * np.sin(phase)
        return center, threshold

    def _evaluate_objectives(self, X, t):
        center, _ = self._dynamic_state(t)
        g = 1.0 + np.sum((X[:, 1:] - center) ** 2, axis=1)
        f1 = X[:, 0]
        f2 = g * (1.0 - np.sqrt(f1 / g))
        return np.column_stack((f1, f2))

    def _evaluate_constraints(self, X, t):
        _, threshold = self._dynamic_state(t)
        return (threshold - X[:, 0]).reshape(-1, 1)

    def _calculate_pareto_front(self, t=None):
        if t is None:
            t = self.t
        _, threshold = self._dynamic_state(t)
        f1 = np.linspace(threshold, 1.0, 1001)
        return np.column_stack((f1, 1.0 - np.sqrt(f1)))

    def _calculate_pareto_set(self, t=None):
        if t is None:
            t = self.t
        center, threshold = self._dynamic_state(t)
        x0 = np.linspace(threshold, 1.0, 1001)
        result = np.full((len(x0), self.decision_num), center)
        result[:, 0] = x0
        return result

    def get_objective_constraints(self, t=None):
        if t is None:
            t = self.t
        _, threshold = self._dynamic_state(t)
        return [
            {
                "axis": 0,
                "operator": ">=",
                "threshold": float(threshold),
            }
        ]
