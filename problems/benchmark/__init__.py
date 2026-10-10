"""按系列组织的 Benchmark 注册入口，以及旧导入路径的惰性兼容层。

物理布局为 FAMILY/NAME.py，参数和元信息分别为 NAME.config.json 和
NAME.info.json。问题名、动态参数与约束符号不因目录整理而改变。
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import ModuleType

from problems.Problem import Problem

BENCHMARK_ROOT = Path(__file__).resolve().parent


def iter_benchmarks():
    """只发现系列中的同名问题源码；按系列及数值序号排序，不导入公式。"""
    for directory in sorted(BENCHMARK_ROOT.iterdir()):
        if not directory.is_dir() or not re.fullmatch(r"[A-Z]+", directory.name):
            continue
        pattern = re.compile(rf"{directory.name}([0-9]+)")
        sources = [p for p in directory.glob("*.py") if pattern.fullmatch(p.stem)]
        for source in sorted(sources, key=lambda p: int(pattern.fullmatch(p.stem)[1])):
            yield directory.name, source.stem, source.resolve()


def expand_benchmarks(selectors):
    """展开系列名或单个问题名，按选择顺序去重，供批量调用使用。"""
    values = [selectors] if isinstance(selectors, str) else selectors
    if not values:
        raise ValueError("Benchmark 名称列表不能为空")
    entries = list(iter_benchmarks())
    names = []
    for selector in values:
        if not isinstance(selector, str):
            raise ValueError("Benchmark 选择项必须为字符串")
        name = selector.strip().upper()
        matches = [entry for family, entry, _ in entries if family == name or entry == name]
        if not matches:
            raise ValueError(f"未知 Benchmark 或系列: {selector!r}")
        for match in matches:
            if match not in names:
                names.append(match)
    return names


def load_benchmark_class(name):
    """通过固定系列路径加载 Problem 子类，不接受任意模块/文件路径。"""
    match = re.fullmatch(r"([A-Z]+)[0-9]+", name)
    if match is None or name not in expand_benchmarks(name):
        raise ValueError(f"无效 Benchmark 名称: {name!r}")
    module = importlib.import_module(f"{__name__}.{match[1]}.{name}")
    problem_class = getattr(module, name)
    if not isinstance(problem_class, type) or not issubclass(problem_class, Problem):
        raise TypeError(f"{name} 未实现 FlexDMO Problem 接口")
    return problem_class


def _legacy_getattr(module_name):
    """只在旧路径真正访问类时加载规范模块，不在发现目录时计算 PF。"""
    def resolve(attribute):
        return getattr(importlib.import_module(module_name), attribute)
    return resolve


def _install_legacy_aliases():
    """兼容 problems.benchmark.DF1.main 等历史调用，无需保留旧物理目录。

    所有别名与规范导入返回同一个类，已有算法、测试和 pickle 类路径可继续加载。
    元信息及默认配置统一从系列侧车文件读取，不复制第二份问题公式。
    """
    for family, name, source in iter_benchmarks():
        legacy_name = f"{__name__}.{name}"
        canonical = f"{__name__}.{family}.{name}"
        package = ModuleType(legacy_name)
        package.__path__ = []
        package.__package__ = legacy_name
        package.__file__ = str(source)
        main = ModuleType(legacy_name + ".main")
        main.__package__ = legacy_name
        main.__file__ = str(source)
        main.__getattr__ = _legacy_getattr(canonical)
        package.main = main
        package.__getattr__ = _legacy_getattr(canonical)
        sys.modules.setdefault(legacy_name, package)
        sys.modules.setdefault(legacy_name + ".main", main)
        setattr(sys.modules[__name__], name, sys.modules[legacy_name])


_install_legacy_aliases()
