import os
import unittest

from flexdmo_app.core import registered_class, parse_parameters, parameter_label
from utils.information_parser import (
    get_all_dynamic_strategy,
    get_all_problem,
    get_all_search_algorithm,
    get_dynamic_response_config,
)


class InformationParserTests(unittest.TestCase):
    def test_discovers_built_in_extensions_independent_of_entrypoint(self):
        original_argv0 = __import__("sys").argv[0]
        try:
            __import__("sys").argv[0] = os.path.join("unrelated", "runner.py")
            strategies = get_all_dynamic_strategy()
            algorithms = get_all_search_algorithm()
            problems = get_all_problem()
        finally:
            __import__("sys").argv[0] = original_argv0

        self.assertIn("NoResponse", {item["name"] for item in strategies})
        self.assertIn("D-NSGA-II-A", {item["name"] for item in strategies})
        self.assertIn("D-NSGA-II-B", {item["name"] for item in strategies})
        self.assertIn("PPS", {item["name"] for item in strategies})
        self.assertIn("PSCA", {item["name"] for item in strategies})
        self.assertIn("LR-DMOEA", {item["name"] for item in strategies})
        self.assertIn("NSGAII", {item["name"] for item in algorithms})
        self.assertIn("SPEA2", {item["name"] for item in algorithms})
        self.assertIn("MOEA/D", {item["name"] for item in algorithms})
        self.assertIn("DF1", {item["name"] for item in problems})
        self.assertIn("CDP1", {item["name"] for item in problems})
        self.assertIn("CDP6", {item["name"] for item in problems})
        cdp6 = next(item for item in problems if item["name"] == "CDP6")
        self.assertEqual(cdp6["category"], "Constrained")
        self.assertEqual(cdp6["constraints"], 2)
        self.assertTrue(cdp6["description"])

    def test_unknown_response_strategy_has_empty_config(self):
        self.assertEqual(get_dynamic_response_config("does-not-exist"), {})

    def test_dynamic_nsga2_configs_are_available(self):
        self.assertEqual(
            get_dynamic_response_config("D-NSGA-II-A"),
            {"replacement_rate": 0.2},
        )
        self.assertEqual(
            get_dynamic_response_config("D-NSGA-II-B"),
            {
                "replacement_rate": 0.2,
                "mutation_probability": 0.1,
                "distribution_index": 20,
            },
        )
        self.assertEqual(
            get_dynamic_response_config("PPS"),
            {"ar_order": 3, "history_length": 23},
        )
        self.assertEqual(
            get_dynamic_response_config("PSCA")["cluster_num"],
            3,
        )
        self.assertEqual(
            get_dynamic_response_config("LR-DMOEA")["key_points"],
            12,
        )

    def test_parameter_validation_provides_actionable_errors(self):
        cases = (("decision_num", "0", 10), ("tau", "", 10),
                 ("ar_order", "3.5", 3), ("noise_scale", "-0.1", 0.1))
        for key, raw, default in cases:
            with self.subTest(key=key), self.assertRaises(ValueError) as raised:
                parse_parameters({key: raw}, {key: default})
            self.assertIn(parameter_label({}, key), str(raised.exception))
        self.assertEqual(parameter_label({}, "decision_num"), "决策变量数")

    def test_all_discovered_components_are_importable(self):
        for item in (
            get_all_dynamic_strategy()
            + get_all_search_algorithm()
            + get_all_problem()
        ):
            component_class = registered_class(item)
            self.assertTrue(callable(component_class), item["folder_name"])


if __name__ == "__main__":
    unittest.main()
