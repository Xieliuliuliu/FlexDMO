import numpy as np

from problems.benchmark.CDP.common import DynamicConstrainedZDT


class CDP4(DynamicConstrainedZDT):
    """Moving infeasible band that disconnects the Pareto front."""

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(
            decision_num,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            n_con=1,
        )

    def _band(self, t):
        center = 0.5 + 0.18 * np.sin(self._phase(t))
        half_width = 0.10 + 0.025 * np.cos(self._phase(t))
        return center - half_width, center + half_width

    def _constraints_from_objectives(self, objectives, t):
        lower, upper = self._band(t)
        values = (
            (objectives[:, 0] - lower)
            * (upper - objectives[:, 0])
        )
        return values.reshape(-1, 1)

    def get_objective_constraints(self, t=None):
        if t is None:
            t = self.t
        lower, upper = self._band(t)
        return [{
            "kind": "interval",
            "axis": 0,
            "lower": float(lower),
            "upper": float(upper),
        }]
