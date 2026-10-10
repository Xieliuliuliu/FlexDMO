import numpy as np

from problems.benchmark.CDP.common import DynamicConstrainedZDT


class CDP6(DynamicConstrainedZDT):
    """Combined moving boundary and circular objective-space obstacle."""

    def __init__(self, decision_num, n, tau, solution_num, total_evaluate_time):
        super().__init__(
            decision_num,
            n,
            tau,
            solution_num,
            total_evaluate_time,
            n_con=2,
        )

    def _lower_bound(self, t):
        return 0.16 + 0.10 * np.sin(self._phase(t))

    def _obstacle(self, t):
        center_x = 0.68 - 0.10 * np.sin(self._phase(t))
        center_y = 1.0 - np.sqrt(center_x)
        return center_x, center_y, 0.105

    def _constraints_from_objectives(self, objectives, t):
        center_x, center_y, radius = self._obstacle(t)
        circle = (
            radius ** 2
            - (objectives[:, 0] - center_x) ** 2
            - (objectives[:, 1] - center_y) ** 2
        )
        return np.column_stack((
            self._lower_bound(t) - objectives[:, 0],
            circle,
        ))

    def get_objective_constraints(self, t=None):
        if t is None:
            t = self.t
        center_x, center_y, radius = self._obstacle(t)
        return [
            {
                "axis": 0,
                "operator": ">=",
                "threshold": float(self._lower_bound(t)),
            },
            {
                "kind": "circle",
                "center": [float(center_x), float(center_y)],
                "radius": float(radius),
            },
        ]
