import os
import unittest

from utils.run_executor import load_main_class_from_folder
from utils.information_parser import (
    get_all_dynamic_strategy,
    get_all_problem,
    get_all_search_algorithm,
    get_dynamic_response_config,
)
from views.test_module.test_module_handler import (
    format_parameter_label,
    get_problem_summary,
    validate_runtime_config,
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
        errors = validate_runtime_config({
            "selected_problem": {
                "decision_num": "0",
                "tau": "",
                "solution_num": "100",
            },
            "selected_search": {"proM": "1.5"},
            "selected_dynamic": {
                "replacement_rate": "0",
                "ar_order": "3.5",
                "history_length": "3",
                "key_points": "1",
                "predicted_fraction": "0.9",
                "mutation_fraction": "0.2",
                "noise_scale": "-0.1",
            },
        })

        self.assertIn("decision_num: must be greater than 0", errors)
        self.assertIn("tau: must be a number", errors)
        self.assertIn("proM: must be between 0 and 1", errors)
        self.assertIn(
            "replacement_rate: must be greater than 0 and at most 1",
            errors,
        )
        self.assertIn("ar_order: must be an integer", errors)
        self.assertIn(
            "history_length: must be greater than ar_order",
            errors,
        )
        self.assertIn("key_points: must be at least 2", errors)
        self.assertIn(
            "predicted_fraction + mutation_fraction: "
            "must not exceed 1",
            errors,
        )
        self.assertIn("noise_scale: must be non-negative", errors)
        self.assertEqual(
            format_parameter_label("decision_num"),
            "决策变量数",
        )
        self.assertEqual(
            format_parameter_label("replacement_rate"),
            "种群替换比例",
        )
        self.assertEqual(
            format_parameter_label("ar_order"),
            "自回归阶数",
        )
        self.assertEqual(
            format_parameter_label("random_multiplier"),
            "候选种群倍数",
        )
        self.assertEqual(
            format_parameter_label("predicted_fraction"),
            "预测个体比例",
        )
        self.assertIn("动态组合约束", get_problem_summary("CDP6"))
        self.assertNotIn("Moving", get_problem_summary("CDP1"))

    def test_all_discovered_components_are_importable(self):
        for item in (
            get_all_dynamic_strategy()
            + get_all_search_algorithm()
            + get_all_problem()
        ):
            component_class = load_main_class_from_folder(item["folder_name"])
            self.assertTrue(callable(component_class), item["folder_name"])


if __name__ == "__main__":
    unittest.main()
