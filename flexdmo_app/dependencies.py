"""Check selected algorithms without importing or installing their libraries."""
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

IMPORTS = {"torch": "torch", "scikit-learn": "sklearn"}


def requirements_file(record):
    # A single-file plugin owns its imports; don't apply a directory-wide
    # requirements file to every independent user algorithm in that directory.
    if record.get("format") == "python-file":
        return None
    path = Path(record["folder_name"]) / "requirements.txt"
    return path if path.is_file() else None


def install_command(record, module):
    path = requirements_file(record)
    args = [sys.executable, "-m", "pip", "install"]
    args += ["-r", str(path.resolve())] if path else [next(
        (package for package, name in IMPORTS.items() if name == module), module)]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


def missing_dependency(record, module):
    return ModuleNotFoundError(
        f"算法 {record['name']} 缺少依赖 {module}；只在运行此算法时需要。\n"
        f"请在终端执行：\n{install_command(record, module)}\n"
        "安装后重新运行即可；平台不会自动下载或安装。", name=module)


def check_dependencies(record):
    path = requirements_file(record)
    if path is None:
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        package = re.split(r"[<>=!~;\[\s]", line.strip(), maxsplit=1)[0].lower()
        module = IMPORTS.get(package)
        # Check only known package/import-name pairs. Don't guess imports from
        # arbitrary dependency names, execute pip options or import the module.
        if module and importlib.util.find_spec(module) is None:
            raise missing_dependency(record, module)
