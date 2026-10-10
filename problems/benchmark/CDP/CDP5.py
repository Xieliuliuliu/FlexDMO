import numpy as np

from problems.benchmark.CDP.common import DynamicConstrainedZDT


class CDP5(DynamicConstrainedZDT):
    """Moving circular infeasible obstacle in objective space."""

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(
            decision_num,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            n_con=1,
        )

    def _obstacle(self, t):
        center_x = 0.48 + 0.14 * np.sin(self._phase(t))
        center_y = 1.0 - np.sqrt(center_x)
        radius = 0.12 + 0.025 * np.cos(self._phase(t))
        return center_x, center_y, radius

    def _constraints_from_objectives(self, objectives, t):
        center_x, center_y, radius = self._obstacle(t)
        values = (
            radius ** 2
            - (objectives[:, 0] - center_x) ** 2
            - (objectives[:, 1] - center_y) ** 2
        )
        return values.reshape(-1, 1)

    def get_objective_constraints(self, t=None):
        if t is None:
            t = self.t
        center_x, center_y, radius = self._obstacle(t)
        return [{
            "kind": "circle",
            "center": [float(center_x), float(center_y)],
            "radius": float(radius),
        }]
