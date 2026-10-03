"""Single-file discovery, parameter inference and real numerical adapter tests."""
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest

import main_qt  # Bootstrap reused scientific packages in the isolated Qt venv.
import numpy as np

from flexdmo_app.code_plugins import inspect_code
from flexdmo_app.components import PLUGIN_ROOT, discover_plugins, import_code
from flexdmo_app.core import defaults, optimize_worker, parameter_text, parse_parameters, records, registered_class
from flexdmo_app.experiments import build_plan, experiment_worker
from flexdmo_app.plugin_runtime import checked_population


SEARCH = '''import numpy as np
def step(population, problem, scale: float = 0.02):
    X = population.get_decision_matrix()
    return np.clip(X + np.random.normal(0, scale, X.shape), problem.xl, problem.xu)
'''
RESPONSE = '''def response(population, problem, rate: float = 0.2):
    return population.get_decision_matrix().copy()
'''


class CodePluginTests(unittest.TestCase):
    def setUp(self):
        PLUGIN_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="_test_code_", dir=PLUGIN_ROOT)
        self.root = Path(self.temp.name)
        registry = records()
        self.baseline = {k: next(r for r in registry[k] if r["name"] == name) for k, name in
                         (("dynamic", "NoResponse"), ("search", "NSGAII"), ("problem", "CDP1"))}

    def tearDown(self):
        self.temp.cleanup()

    def code(self, source=SEARCH, kind="search", name="TrialCode"):
        folder = self.root / ("search_algorithm" if kind == "search" else "response_strategy")
        folder.mkdir(exist_ok=True)
        path = folder / (name + ".py")
        path.write_text(source, encoding="utf-8")
        return inspect_code(path, kind)

    def problem(self):
        return registered_class(self.baseline["problem"])(decision_num=3, n=10, tau=1,
                                                        solution_num=6, total_evaluate_time=2)

    def request(self, dynamic=None, search=None):
        selected = dict(self.baseline)
        selected["dynamic"] = dynamic or selected["dynamic"]
        selected["search"] = search or selected["search"]
        params = {k: defaults(r) for k, r in selected.items()}
        params["problem"].update(decision_num=3, n=10, tau=1, solution_num=6, total_evaluate_time=2)
        return {"records": selected, "params": params}

    def spawn(self, target, request):
        ctx = multiprocessing.get_context("spawn")
        receiver, sender = ctx.Pipe(duplex=False)
        state = ctx.Value("i", 0)
        from flexdmo_app.core import RunState
        process = ctx.Process(target=target, args=(request, RunState(state), sender))
        process.start()
        sender.close()
        messages = []
        try:
            while True:
                try:
                    if not receiver.poll(20):
                        break
                    messages.append(receiver.recv())
                except (EOFError, BrokenPipeError):
                    break
            process.join(3)
            self.assertFalse(process.is_alive(), "single-file worker timed out")
            return process.exitcode, messages
        finally:
            if process.is_alive():
                process.terminate()
                process.join(3)
            receiver.close()
            process.close()

    def test_discovery_parses_code_without_executing_imports_defaults_or_decorators(self):
        self.code("raise RuntimeError('must not execute')\n" + SEARCH)
        found, errors = discover_plugins(self.root)
        self.assertFalse(errors)
        record = found["search"][0]
        self.assertEqual(defaults(record), {"seed": 1, "scale": 0.02})
        self.assertEqual(record["entry_name"], "step")

    def test_class_constructor_parameters_and_optional_algorithm_hook(self):
        record = self.code('''class CustomResponse:
    def __init__(self, rate: float = 0.3, enabled: bool = True):
        self.rate = rate
    def response(self, population, problem, algorithm):
        return population
''', "dynamic")
        self.assertEqual(defaults(record), {"rate": 0.3, "enabled": True})
        self.assertEqual(record["callback_args"], ["population", "problem", "algorithm"])

    def test_signature_types_required_optional_literal_and_json_values(self):
        record = self.code('''from typing import Literal, Optional
def step(population, problem, count: int, scale: float = 1, enabled: bool = False,
         policy: Literal["a", "b"] = "a", weights: list[float] = [1.0, 2.0],
         offset: Optional[float] = None, settings: dict = {}, pair: tuple = (1, 2)):
    return population
''')
        values = {k: parameter_text(v, record["parameter_specs"][k]) for k, v in defaults(record).items()}
        values["count"] = "9007199254740993"
        parsed = parse_parameters(values, defaults(record), record)
        self.assertEqual(parsed["count"], 9007199254740993)
        self.assertIsInstance(parsed["scale"], float)
        self.assertIsNone(parsed["offset"])
        self.assertEqual(parsed["pair"], (1, 2))
        self.assertEqual(parsed["weights"], [1.0, 2.0])
        for key, raw in (("count", ""), ("count", "1.5"), ("policy", "wrong"),
                         ("scale", "nan"), ("weights", "[NaN]"), ("settings", "[]")):
            with self.subTest(key=key, raw=raw), self.assertRaises(ValueError):
                parse_parameters(dict(values, **{key: raw}), defaults(record), record)

    def test_bad_interfaces_are_explained_without_importing(self):
        for source in ("def wrong(population, problem): pass", "def step(problem): pass",
                       "async def step(population, problem): pass",
                       "def step(population, problem, scale=make_value()): pass",
                       "def step(population, problem, unknown): pass",
                       "def step(population, problem, seed=1): pass"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.code(source)

    def test_callback_argument_names_do_not_require_copying_a_template(self):
        record = self.code("def step(pop, task, scale=0.02): return pop\n")
        self.assertEqual(defaults(record), {"seed": 1, "scale": 0.02})
        algorithm = registered_class(record)()
        problem = self.problem()
        algorithm.optimize(problem, registered_class(self.baseline["dynamic"])())
        self.assertTrue(problem.is_ended())

    def test_multiple_entries_require_explicit_selection(self):
        source = SEARCH + "\nclass Chosen:\n    def step(self, population, problem): return population\n"
        with self.assertRaises(ValueError):
            self.code(source)
        record = self.code("ALGORITHM = 'Chosen'\nNAME = 'My algorithm'\nYEAR = 2026\n" + source)
        self.assertEqual(record["entry_name"], "Chosen")
        self.assertEqual(record["name"], "My algorithm")

    def test_import_copies_only_code_and_never_overwrites(self):
        source = self.root / "Imported.py"
        source.write_text(SEARCH, encoding="utf-8")
        destination = import_code(source, "search", self.root)
        self.assertEqual(destination.read_text(), SEARCH)
        with self.assertRaises(FileExistsError):
            import_code(source, "search", self.root)
        self.assertFalse((destination.parent / "config.json").exists())

    def test_nested_invalid_defaults_are_rejected_at_discovery(self):
        for default in ("[1e309]", "{'bad': {1, 2}}"):
            with self.subTest(default=default), self.assertRaises(ValueError):
                self.code(f"def step(population, problem, values={default}): return population\n")
        with self.assertRaisesRegex(ValueError, "不一致"):
            self.code("def step(population, problem, count: int = 0.2): return population\n")

    def test_complete_loop_rejects_uncomputed_snapshots(self):
        record = self.code('''from algorithms.search_algorithm.Algorithm import Algorithm
from components.Population import Population
class Uncomputed(Algorithm):
    def optimize(self, problem, response_strategy):
        pop = Population(xl=problem.xl, xu=problem.xu, n_init=problem.solution_num)
        self.collect_information(pop, problem, response_strategy)
''')
        with self.assertRaisesRegex(RuntimeError, "评价"):
            registered_class(record)().optimize(self.problem(), registered_class(self.baseline["dynamic"])())

    def test_result_fingerprint_matches_executed_code_even_after_file_changes(self):
        import hashlib
        from flexdmo_app.core import result_settings
        record = self.code(SEARCH)
        path = Path(record["source_file"])
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        registered_class(record)
        path.write_text(SEARCH + "# changed after loading\n", encoding="utf-8")
        settings = result_settings({}, self.request(search=record))
        self.assertEqual(settings["code_plugins"]["search"]["sha256"], fingerprint)

    def test_output_validation_shape_bounds_and_finiteness(self):
        problem = self.problem()
        for output in (np.zeros((5, 3)), np.zeros((6, 2)), np.full((6, 3), np.nan),
                       np.full((6, 3), -1), None):
            with self.subTest(output=str(output)), self.assertRaises(ValueError):
                checked_population(output, problem, "Trial")

    def test_single_file_search_reuses_state_and_has_reproducible_history(self):
        record = self.code(SEARCH)
        results = []
        for _ in range(2):
            algorithm = registered_class(record)(seed=12, scale=0.01)
            strategy = registered_class(self.baseline["dynamic"])()
            problem = self.problem()
            algorithm.optimize(problem, strategy)
            self.assertTrue(problem.is_ended())
            self.assertEqual(set(algorithm.history["runtime"]), {0, 1})
            settings = algorithm.history["settings"]
            self.assertEqual(settings["search_algorithm_class"], "TrialCode")
            self.assertEqual(settings["search_algorithm_params"]["scale"], 0.01)
            results.append([p.get_decision_matrix() for group in algorithm.history["runtime"].values() for p in group.values()])
        self.assertEqual(len(results[0]), len(results[1]))
        for first, second in zip(*results):
            np.testing.assert_array_equal(first, second)

    def test_step_class_state_is_preserved_and_user_evaluations_not_double_counted(self):
        record = self.code('''class Stateful:
    def __init__(self, offset: float = 0.0): self.calls = 0
    def step(self, population, problem):
        self.calls += 1
        population.update_objective_constrain(problem)
        return population
''')
        algorithm = registered_class(record)()
        problem = self.problem()
        algorithm.optimize(problem, registered_class(self.baseline["dynamic"])())
        self.assertGreater(algorithm.target.calls, 1)
        self.assertEqual(problem.evaluate_time, 6 * (1 + algorithm.target.calls + 1))

    def test_response_function_works_with_existing_search_algorithm(self):
        record = self.code(RESPONSE, "dynamic")
        algorithm = registered_class(self.baseline["search"])(**defaults(self.baseline["search"]))
        problem = self.problem()
        algorithm.optimize(problem, registered_class(record)(rate=0.2))
        self.assertTrue(problem.is_ended())
        self.assertEqual(set(algorithm.history["runtime"]), {0, 1})

    def test_complete_optimize_class_keeps_history_and_runtime_controls(self):
        record = self.code('''from algorithms.search_algorithm.NSGA2.main import NSGA2
class Complete(NSGA2):
    def __init__(self, proM=1.0, **args): super().__init__(proM=proM, **args)
    def optimize(self, problem, response_strategy):
        return super().optimize(problem, response_strategy)
''')
        algorithm = registered_class(record)(seed=13)
        problem = self.problem()
        algorithm.optimize(problem, registered_class(self.baseline["dynamic"])())
        self.assertTrue(problem.is_ended())
        self.assertTrue(algorithm.history["runtime"])
        self.assertEqual(algorithm.target.seed, 13)

    def test_full_class_receives_controls_even_without_forwarding_constructor_kwargs(self):
        record = self.code('''from algorithms.search_algorithm.Algorithm import Algorithm
class SimpleConstructor(Algorithm):
    def __init__(self, offset=0.0): super().__init__()
    def optimize(self, problem, response_strategy): pass
''')
        class Stopped:
            value = "stop"
        state = Stopped()
        algorithm = registered_class(record)(state=state, seed=24)
        self.assertIs(algorithm.target.state, state)
        self.assertEqual(algorithm.target.seed, 24)
        self.assertFalse(algorithm.target.control_process())

    def test_missing_dependency_and_early_return_are_reported_as_failures(self):
        missing = self.code("import definitely_missing_flexdmo_dependency\n" + SEARCH)
        exitcode, messages = self.spawn(optimize_worker, self.request(search=missing))
        self.assertNotEqual(exitcode, 0)
        self.assertIn("definitely_missing_flexdmo_dependency", next(m["traceback"] for m in messages if m.get("kind") == "error"))
        early = self.code('''from algorithms.search_algorithm.Algorithm import Algorithm
class Early(Algorithm):
    def optimize(self, problem, response_strategy): return None
''')
        for target in (optimize_worker, experiment_worker):
            exitcode, messages = self.spawn(target, self.request(search=early))
            self.assertNotEqual(exitcode, 0)
            self.assertIn("提前返回", next(m["traceback"] for m in messages if m.get("kind") == "error"))

    def test_edited_signature_requires_refresh_but_logic_reload_is_immediate(self):
        record = self.code(SEARCH)
        path = Path(record["source_file"])
        path.write_text(SEARCH.replace("0.02", "0.03"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "刷新"):
            registered_class(record)
        record = inspect_code(path, "search")
        self.assertIsNotNone(registered_class(record))

    def test_worker_spawn_single_run_and_batch_share_code_and_do_not_save(self):
        dynamic = self.code(RESPONSE, "dynamic")
        search = self.code(SEARCH)
        request = self.request(dynamic, search)
        exitcode, messages = self.spawn(optimize_worker, request)
        self.assertEqual(exitcode, 0, messages)
        snapshots = [m for m in messages if "population" in m]
        self.assertEqual({m["t"] for m in snapshots}, {0, 1})
        self.assertEqual(snapshots[0]["settings"]["search_algorithm_params"]["scale"], 0.02)
        exitcode, messages = self.spawn(experiment_worker, request)
        self.assertEqual(exitcode, 0, messages)
        result = next(m for m in messages if m.get("kind") == "result")
        self.assertFalse(result["partial"])
        self.assertIn("frames", result)
        self.assertNotIn("path", result)
        self.assertIn("MIGD", result["metrics"])
        self.assertFalse(list(self.root.rglob("*.json")))

    def test_broken_plugin_fails_in_child_and_next_good_run_succeeds(self):
        record = self.code("def step(population, problem):\n    raise ValueError('deliberate failure')\n")
        exitcode, messages = self.spawn(optimize_worker, self.request(search=record))
        self.assertNotEqual(exitcode, 0)
        error = next(m for m in messages if m.get("kind") == "error")
        self.assertIn("deliberate failure", error["traceback"])
        self.assertIn("line 2", error["traceback"])
        record = self.code(SEARCH)
        exitcode, _ = self.spawn(optimize_worker, self.request(search=record))
        self.assertEqual(exitcode, 0)

    def test_batch_plan_uses_inferred_parameters_and_shared_repeat_seeds(self):
        record = self.code(SEARCH)
        selection = {k: [r] for k, r in self.baseline.items()}
        selection["search"] = [record]
        tasks = build_plan(selection, {"tau": "1", "n": "10", "repeats": 2, "seed": 21,
                                      "decision_num": 3, "solution_num": 6, "total_evaluate_time": 2})
        self.assertEqual([t["request"]["params"]["search"]["seed"] for t in tasks], [21, 22])
        self.assertEqual(tasks[0]["request"]["params"]["search"]["scale"], 0.02)


if __name__ == "__main__":
    unittest.main()
