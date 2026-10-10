# Benchmark 系列目录

FlexDMO 通过系列目录发现问题，界面中的问题名称和参数名称保持不变。

```text
problems/benchmark/
├── CDP/    CDP1–CDP6（保留原 FlexDMO 自定义实现）
├── DP/     DP1–DP10（保留原实现）
├── DF/     DF1–DF14（保留原 DF1，追加 DF2–DF14）
├── DCF/    DCF1–DCF10
├── DCP/    DCP1–DCP9
└── DCTP/   DCTP1–DCTP8
```

共 57 个问题：原有 17 个实现保持不变，从 DynOptForge 追加 40 个问题。
与现有同名问题冲突时不覆盖原实现。DF、DCF、DCP、DCTP 的新增共享公式文件
均位于相应系列的 `common.py`；代码独立存在于 FlexDMO，不依赖父目录中的实验平台。
原 `dynamic_constrained.py` 仅作为 CDP 公共基类的兼容转发文件保留。

每个问题使用三个同名前缀文件，例如：

```text
DCP/
├── __init__.py
├── common.py
├── DCP1.py
├── DCP1.info.json
└── DCP1.config.json
```

`NAME.py` 定义同名 Problem 子类；`NAME.info.json` 用于界面分类、约束数和说明；
`NAME.config.json` 是独立默认参数，不与同系列其他问题共用参数缓存。
约束统一使用 G<=0 为可行。DCTP 的原实现固定 30 维，其默认参数也设为 30，
不应使用通用 10 维设置覆盖。DF10–DF14 为三目标，其余现有问题为双目标。

规范调用：

```python
from problems.benchmark import expand_benchmarks, load_benchmark_class
from problems.benchmark.DCP.DCP1 import DCP1

names = expand_benchmarks(["DCF", "DCP1"])
problem_class = load_benchmark_class("DCF10")
problem = problem_class(
    decision_num=10, n=5, tau=50, solution_num=100, total_evaluate_time=100,
)
X = (problem.xl + problem.xu)[None, :] / 2
F, G = problem.evaluate(X, need_count=False, t=0)
front = problem.get_pareto_front(t=0)
```

旧 `from problems.benchmark.CDP1.main import CDP1` 等导入仍通过惰性别名兼容，
不会重新出现大量单问题物理目录。已有结果按问题类名称解析，可继续回放。
目录整理不会修改动态时钟或替换 FlexDMO 的 Problem 基类。

新问题会通过公共目录扫描进入单次实验、批量实验及结果回放的同一注册表。
注册表的 `folder_name` 对系列问题是唯一源码文件路径（不是共用系列目录）；
元信息/参数分别使用 `info_path`、`config_path`，避免同系列选择和参数串线。
