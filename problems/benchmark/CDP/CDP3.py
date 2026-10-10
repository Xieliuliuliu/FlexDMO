import numpy as np

from problems.benchmark.CDP.common import DynamicConstrainedZDT


class CDP3(DynamicConstrainedZDT):
    """Dynamic feasible window bounded by two constraints."""

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(
            decision_num,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            n_con=2,
        )

    def _window(self, t):
        shift = 0.12 * np.sin(self._phase(t))
        return 0.18 + shift, 0.78 + shift

    def _constraints_from_objectives(self, objectives, t):
        lower, upper = self._window(t)
        return np.column_stack((
            lower - objectives[:, 0],
            objectives[:, 0] - upper,
        ))

    def get_objective_constraints(self, t=None):
        if t is None:
            t = self.t
        lower, upper = self._window(t)
        return [
            {"axis": 0, "operator": ">=", "threshold": float(lower)},
            {"axis": 0, "operator": "<=", "threshold": float(upper)},
        ]
