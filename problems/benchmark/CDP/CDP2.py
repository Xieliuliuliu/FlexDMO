import numpy as np

from problems.benchmark.CDP.common import DynamicConstrainedZDT


class CDP2(DynamicConstrainedZDT):
    """Dynamic upper-bound constraint in the first objective."""

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(
            decision_num,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            n_con=1,
        )

    def _upper_bound(self, t):
        return 0.65 + 0.15 * np.cos(self._phase(t))

    def _constraints_from_objectives(self, objectives, t):
        return (objectives[:, 0] - self._upper_bound(t)).reshape(-1, 1)

    def get_objective_constraints(self, t=None):
        if t is None:
            t = self.t
        return [{
            "axis": 0,
            "operator": "<=",
            "threshold": float(self._upper_bound(t)),
        }]
