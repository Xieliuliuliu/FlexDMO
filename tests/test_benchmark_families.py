"""系列目录、原导入兼容、参数隔离与追加 benchmark 的独立运行回归。"""

import importlib
import unittest
from pathlib import Path

import numpy as np

from problems.benchmark import expand_benchmarks, iter_benchmarks, load_benchmark_class
from utils.information_parser import get_all_problem, get_problem_config

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {"CDP": 6, "DP": 10, "DF": 14, "DCF": 10, "DCP": 9, "DCTP": 8}


class BenchmarkFamilyTests(unittest.TestCase):
    def test_physical_layout_and_numeric_order(self):
        root = ROOT / "problems" / "benchmark"
        directories = {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")}
        self.assertEqual(directories, set(COUNTS))
        entries = list(iter_benchmarks())
        self.assertEqual(len(entries), 57)
        for family, count in COUNTS.items():
            names = expand_benchmarks(family)
            self.assertEqual(names, [family + str(i) for i in range(1, count + 1)])
            for name in names:
                self.assertTrue((root / family / (name + ".py")).is_file())
                self.assertTrue((root / family / (name + ".info.json")).is_file())
                self.assertTrue((root / family / (name + ".config.json")).is_file())
        self.assertEqual(expand_benchmarks(["DCP", "DCP1"]), expand_benchmarks("DCP"))

    def test_unique_registry_and_independent_configs(self):
        rows = get_all_problem()
        self.assertEqual(len(rows), 57)
        self.assertEqual(len({r["folder_name"] for r in rows}), 57)
        for record in rows:
            self.assertEqual(record["class_name"], record["name"])
            self.assertEqual(get_problem_config(record["name"])["decision_num"],
                             30 if record["family"] == "DCTP" else 10)
        first = get_problem_config("DCF1")
        first["n"] = 999
        self.assertNotEqual(get_problem_config("DCF2")["n"], 999)
        self.assertNotEqual(get_problem_config("DCF1")["n"], 999)

    def test_legacy_imports_are_the_same_classes(self):
        for family, count in {"CDP": 6, "DP": 10, "DF": 1}.items():
            for i in range(1, count + 1):
                name = family + str(i)
                old = importlib.import_module(f"problems.benchmark.{name}.main")
                new = importlib.import_module(f"problems.benchmark.{family}.{name}")
                self.assertIs(getattr(old, name), getattr(new, name))
        old_common = importlib.import_module("problems.benchmark.dynamic_constrained")
        new_common = importlib.import_module("problems.benchmark.CDP.common")
        self.assertIs(old_common.DynamicConstrainedZDT, new_common.DynamicConstrainedZDT)

    def test_every_problem_can_evaluate_multiple_environments(self):
        rng = np.random.default_rng(42)
        for record in get_all_problem():
            with self.subTest(problem=record["name"]):
                problem = load_benchmark_class(record["name"])(**get_problem_config(record["name"]))
                self.assertEqual(problem.n_con, record["constraints"])
                X = rng.uniform(problem.xl, problem.xu, (7, problem.decision_num))
                for environment in (0, 3, 7):
                    F, G = problem.evaluate(X, need_count=False, t=environment)
                    self.assertEqual(F.shape, (7, problem.n_obj))
                    self.assertTrue(np.isfinite(F).all())
                    if problem.n_con:
                        self.assertEqual(G.shape, (7, problem.n_con))
                        self.assertTrue(np.isfinite(G).all())
                    else:
                        self.assertTrue(G is None or G.shape == (7, 0))
                self.assertEqual(problem.evaluate_time, 0)
                self.assertEqual(problem.t, 0)

    def test_qt_core_registry_and_parameter_identity(self):
        from flexdmo_app.core import defaults, records, registered_class

        rows = records()["problem"]
        self.assertEqual(len(rows), 57)
        for record in rows:
            self.assertIs(registered_class(record), load_benchmark_class(record["name"]))
            self.assertEqual(defaults(record), get_problem_config(record["name"]))

    def test_added_suites_support_pareto_front_and_optimizer(self):
        from algorithms.response_strategy.NoResponse.main import NoResponse
        from algorithms.search_algorithm.NSGA2.main import NSGA2

        for name in ("DCF1", "DCP1", "DCTP1", "DF10"):
            with self.subTest(problem=name):
                config = {**get_problem_config(name), "solution_num": 8,
                          "tau": 3, "total_evaluate_time": 2}
                problem = load_benchmark_class(name)(**config)
                # 小规模回归只压缩预热预算，不改变 benchmark 公式。
                problem.initial_convergence = 0
                front = problem.get_pareto_front(t=0)
                self.assertEqual(front.shape[1], problem.n_obj)
                self.assertTrue(len(front))
                self.assertTrue(np.isfinite(front).all())
                optimizer = NSGA2(seed=12)
                optimizer.optimize(problem, NoResponse())
                self.assertTrue(problem.is_ended())
                self.assertEqual(problem.t, 1)
                self.assertEqual(set(optimizer.history["runtime"]), {0, 1})


if __name__ == "__main__":
    unittest.main()
