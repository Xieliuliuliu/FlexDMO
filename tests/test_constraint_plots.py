import unittest

import matplotlib

matplotlib.use("Agg")

import numpy as np
from matplotlib import colors
from matplotlib.figure import Figure

from components.Population import Population
from plots.test_module.draw_population import (
    draw_PF,
    draw_PS,
    draw_constraint_violation,
)
from views.common.GlobalVar import global_vars


class ConstraintPlotTests(unittest.TestCase):
    def setUp(self):
        self.original_state = dict(global_vars["test_module"])
        global_vars["test_module"].clear()
        global_vars["test_module"]["runtime_populations"] = {}

        self.population = Population(
            X=np.array([[0.1, 0.2], [0.8, 0.9]]),
            F=np.array([[0.2, 0.8], [0.8, 0.2]]),
        )
        self.population[1].feasible = False
        self.population[1].constraint_violation = 0.5
        self.information = {
            "t": 0,
            "evaluate_times": 200,
            "population": self.population,
            "POF": None,
            "POS": None,
            "objective_constraints": [
                {"axis": 0, "operator": ">=", "threshold": 0.35}
            ],
        }

    def tearDown(self):
        global_vars["test_module"].clear()
        global_vars["test_module"].update(self.original_state)

    def test_pareto_front_shades_infeasible_region_in_gray(self):
        axis = Figure().subplots()

        draw_PF(self.information, axis)

        region = next(
            patch
            for patch in axis.patches
            if patch.get_label() == "Infeasible region"
        )
        np.testing.assert_allclose(
            region.get_facecolor()[:3],
            colors.to_rgb("gray"),
        )
        self.assertAlmostEqual(region.get_x(), axis.get_xlim()[0])
        self.assertAlmostEqual(region.get_width(), 0.35 - axis.get_xlim()[0])

    def test_pareto_set_keeps_current_population_blue_and_visible(self):
        axis = Figure().subplots()

        draw_PS(self.information, axis)

        self.assertEqual(axis.get_xlim(), (1.0, 2.0))
        np.testing.assert_allclose(
            axis.collections[0].get_colors()[0][:3],
            colors.to_rgb("blue"),
        )

    def test_interval_and_circle_regions_are_supported(self):
        axis = Figure().subplots()
        information = dict(self.information)
        information["objective_constraints"] = [
            {
                "kind": "interval",
                "axis": 0,
                "lower": 0.4,
                "upper": 0.6,
            },
            {
                "kind": "circle",
                "center": [0.75, 0.35],
                "radius": 0.1,
            },
        ]

        draw_PF(information, axis)

        region_patches = [
            patch
            for patch in axis.patches
            if patch.get_label() == "Infeasible region"
        ]
        self.assertEqual(len(region_patches), 1)
        self.assertEqual(len(axis.patches), 2)

    def test_constraint_violation_keeps_infeasible_bars_crimson(self):
        axis = Figure().subplots()

        draw_constraint_violation(self.information, axis)

        np.testing.assert_allclose(
            axis.patches[1].get_facecolor()[:3],
            colors.to_rgb("crimson"),
        )


if __name__ == "__main__":
    unittest.main()
