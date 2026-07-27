import unittest

import numpy as np

from components.Population import Population
from utils.evolution_tools import (
    crowd_selection,
    fast_non_dominated_sort,
    quick_non_dominate_sort,
)
from utils.metrics import calculate_HV, calculate_IGD


class EvolutionToolsTests(unittest.TestCase):
    def test_fast_non_dominated_sort_assigns_expected_fronts(self):
        objectives = np.array([
            [1.0, 1.0],
            [2.0, 2.0],
            [1.0, 3.0],
            [3.0, 1.0],
        ])

        fronts = fast_non_dominated_sort(objectives)

        np.testing.assert_array_equal(fronts[0], np.array([0]))
        self.assertEqual(set(fronts[1]), {1, 2, 3})

    def test_crowd_selection_respects_requested_size(self):
        population = Population(
            X=np.arange(10, dtype=float).reshape(5, 2),
            F=np.array([
                [1.0, 5.0],
                [2.0, 4.0],
                [3.0, 3.0],
                [4.0, 2.0],
                [5.0, 1.0],
            ]),
        )

        selected = crowd_selection(population, 3)

        self.assertEqual(selected.n, 3)

    def test_constraint_domination_prefers_feasible_solution(self):
        population = Population(
            X=np.array([[0.0], [1.0], [2.0]]),
            F=np.array([[10.0, 10.0], [0.0, 0.0], [1.0, 1.0]]),
        )
        population.individuals[0].constraint_violation = 0.0
        population.individuals[1].constraint_violation = 1.0
        population.individuals[2].constraint_violation = 0.5

        quick_non_dominate_sort(population)

        self.assertEqual(population.individuals[0].rank, 1)
        self.assertGreater(population.individuals[1].rank, 1)
        self.assertLess(
            population.individuals[2].rank,
            population.individuals[1].rank,
        )


class MetricsTests(unittest.TestCase):
    def test_igd_is_zero_for_identical_fronts(self):
        front = np.array([[0.0, 1.0], [1.0, 0.0]])
        self.assertEqual(calculate_IGD(front, front), 0.0)

    def test_hypervolume_for_simple_two_objective_front(self):
        front = np.array([[1.0, 3.0], [2.0, 2.0], [3.0, 1.0]])
        self.assertAlmostEqual(calculate_HV(front, np.array([4.0, 4.0])), 6.0)

    def test_hypervolume_ignores_dominated_points(self):
        front = np.array([[2.0, 2.0], [1.0, 1.0], [1.0, 1.0]])
        self.assertAlmostEqual(calculate_HV(front, np.array([4.0, 4.0])), 9.0)


if __name__ == "__main__":
    unittest.main()
