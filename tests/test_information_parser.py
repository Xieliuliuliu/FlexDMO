import os
import unittest

from utils.run_executor import load_main_class_from_folder
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
        self.assertIn("NSGAII", {item["name"] for item in algorithms})
        self.assertIn("SPEA2", {item["name"] for item in algorithms})
        self.assertIn("MOEA/D", {item["name"] for item in algorithms})
        self.assertIn("DF1", {item["name"] for item in problems})
        self.assertIn("CDP1", {item["name"] for item in problems})

    def test_unknown_response_strategy_has_empty_config(self):
        self.assertEqual(get_dynamic_response_config("does-not-exist"), {})

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
