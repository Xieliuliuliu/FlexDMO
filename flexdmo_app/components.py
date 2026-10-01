"""Qt-only algorithm discovery/import; never changes production algorithms."""
import ast
import json
from pathlib import Path
import re
import tempfile
import shutil

PLUGIN_ROOT = Path(__file__).resolve().parent / "plugins"
FOLDERS = {"dynamic": "response_strategy", "search": "search_algorithm"}


def discover_plugins(root=PLUGIN_ROOT):
    result = {"dynamic": [], "search": []}
    errors = []
    for kind, subfolder in FOLDERS.items():
        folder = Path(root) / subfolder
        if not folder.exists():
            continue
        for item in sorted(folder.iterdir()):
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                try:
                    from .code_plugins import inspect_code
                    result[kind].append(inspect_code(item, kind))
                except Exception as error:
                    errors.append(f"{item}：{error}")
                continue
            if not item.is_dir() or not (item / "info.json").exists():
                continue
            try:
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item.name):
                    raise ValueError("文件夹名称必须是 Python 类名")
                info = json.loads((item / "info.json").read_text(encoding="utf-8"))
                config = json.loads((item / "config.json").read_text(encoding="utf-8"))
                tree = ast.parse((item / "main.py").read_text(encoding="utf-8"))
                if not info.get("name") or not isinstance(config, dict):
                    raise ValueError("缺少显示名称或参数字典")
                if not any(isinstance(node, ast.ClassDef) and node.name == item.name for node in tree.body):
                    raise ValueError("main.py 中没有与文件夹同名的类")
                result[kind].append({"folder_name": str(item.resolve()), "name": str(info["name"]),
                                     "year": info.get("year", ""), "template": info.get("template", False)})
            except Exception as error:
                errors.append(f"{item.name}：{error}")
    return result, errors


def import_code(source, kind, root=PLUGIN_ROOT):
    """Copy a user-selected source without running it or replacing existing code."""
    from .code_plugins import inspect_code
    source = Path(source)
    if kind not in FOLDERS or source.suffix != ".py":
        raise ValueError("请选择 Python 算法文件和正确的组件类型")
    inspect_code(source, kind)
    folder = Path(root) / FOLDERS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / source.name
    if source.resolve() == destination.resolve():
        return destination
    # Exclusive creation prevents overwriting another algorithm, even if two
    # imports race. Read first so a failed source read cannot create an empty file.
    data = source.read_bytes()
    with destination.open("xb") as output:
        try:
            output.write(data)
        except Exception:
            destination.unlink()
            raise
    return destination


def create_scaffold(kind, class_name, display_name, year, root=PLUGIN_ROOT):
    if kind not in FOLDERS or not re.fullmatch(r"[A-Z][A-Za-z0-9_]{1,63}", class_name):
        raise ValueError("类名需以大写英文字母开头，长度 2–64，仅含字母、数字、下划线")
    if not display_name.strip():
        raise ValueError("请输入显示名称")
    # Disallow ambiguous classes even across component kinds.
    from .core import records
    if any(Path(record["folder_name"]).name == class_name or record["name"] == display_name.strip()
           for rows in records().values() for record in rows):
        raise ValueError("类名或显示名称已存在，请换一个")
    parent = Path(root) / FOLDERS[kind]
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / class_name
    if destination.exists():
        raise ValueError("目标目录已存在，不会覆盖")
    if kind == "search":
        source = ('"""Runnable NSGA-II starter; not a new published algorithm."""\n'
                  'from algorithms.search_algorithm.NSGA2.main import NSGA2\n\n\n'
                  f'class {class_name}(NSGA2):\n'
                  '    # Override optimize() or variation/selection to implement your method.\n'
                  '    pass\n')
        config = {"seed": 1, "proC": 1.0, "disC": 20, "proM": 1.0, "disM": 20}
    else:
        source = ('"""Runnable random-immigrant starter; not a paper reproduction."""\n'
                  'import numpy as np\n'
                  'from algorithms.response_strategy.ResponseStrategy import ResponseStrategy\n'
                  'from components.Population import Population\n\n\n'
                  f'class {class_name}(ResponseStrategy):\n'
                  '    def __init__(self, random_fraction=0.2):\n'
                  '        super().__init__()\n'
                  '        if not 0 <= random_fraction <= 1:\n'
                  '            raise ValueError("random_fraction must be between 0 and 1")\n'
                  '        self.random_fraction = random_fraction\n\n'
                  '    def response(self, population, problem, algorithm):\n'
                  '        # Replace this method with your dynamic response.\n'
                  '        result = population.copy()\n'
                  '        count = min(len(result), int(np.ceil(len(result) * self.random_fraction)))\n'
                  '        indices = np.random.choice(len(result), count, replace=False)\n'
                  '        for index in indices:\n'
                  '            result[index].X = np.random.uniform(problem.xl, problem.xu)\n'
                  '        result.update_objective_constrain(problem)\n'
                  '        return result\n')
        config = {"random_fraction": 0.2}
    temporary = Path(tempfile.mkdtemp(prefix=".scaffold-", dir=parent))
    try:
        files = {"main.py": source, "__init__.py": "",
                 "info.json": json.dumps({"name": display_name.strip(), "year": int(year), "template": True,
                    "parameter_labels": {"random_fraction": "随机补充比例"} if kind == "dynamic" else {}}, ensure_ascii=False, indent=2),
                 "config.json": json.dumps(config, indent=2),
                 "README.md": "# 算法起步模板\n\n这不是新的论文算法或已完成复现。请实现 main.py，维护 config.json，更新 info.json。\n"
                               "界面和批量实验自动发现参数，无需改 Qt 界面。点击组件管理中的刷新即可。\n"
                               "运行前请只使用可信来源的算法代码。\n"}
        for name, content in files.items():
            (temporary / name).write_text(content, encoding="utf-8")
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination
