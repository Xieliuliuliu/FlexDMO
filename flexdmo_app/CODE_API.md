# 直接写代码接入 FlexDMO

只需要一个 `.py` 文件，不需要 `info.json`、`config.json` 或修改注册表。
在顶部打开 **组件管理**，选择类型，然后导入文件；也可打开代码目录直接放入文件。
点击刷新后，它会同时出现在测试运行和批量实验中。

## 动态响应：一个函数

例如把下面代码保存为 `MyResponse.py`，导入为动态响应策略：

```python
import numpy as np


def response(population, problem, rate: float = 0.2):
    """环境变化后随机替换一部分个体；这是示例，不是论文算法。"""
    if not 0 <= rate <= 1:
        raise ValueError("rate 必须在 0 到 1 之间")
    X = population.get_decision_matrix().copy()
    count = int(len(X) * rate)
    indices = np.random.choice(len(X), count, replace=False)
    X[indices] = np.random.uniform(problem.xl, problem.xu, size=(count, X.shape[1]))
    return X
```

参数 `rate` 自动显示为浮点设置。函数前两个位置依次接收种群和问题；变量名可自行命名，
例如 `pop, task`，不需要照抄模板。
需要访问搜索算法及其历史时可以写 `response(population, problem, algorithm, rate=0.2)`。

## 搜索算法：只写一代更新

例如 `MySearch.py`，导入为搜索算法：

```python
import numpy as np


def step(population, problem, scale: float = 0.05):
    """简单扰动示例；没有精英选择，不代表 NSGA-II 或新的论文算法。"""
    if scale < 0:
        raise ValueError("scale 不能为负数")
    X = population.get_decision_matrix()
    noise = np.random.normal(0, scale, X.shape) * (problem.xu - problem.xl)
    return np.clip(X + noise, problem.xl, problem.xu)
```

平台负责初始化、种子、动态环境推进、响应策略调用、评价、暂停/终止、快照与指标。
`step` 返回的是**完整下一代**，不是子代候选集；平台不会偷偷套用 NSGA-II 选择。
可以读取 `population.get_objective_matrix()`、约束违反量以及 `problem.t`。
如果算法要先评价候选再做选择，可自行调用 `Population.update_objective_constrain(problem)`
或 `problem.evaluate(X)`，返回选好的 Population；平台会核对当前环境目标/约束，
但不会再次计入这一次已执行的评价次数。内部候选的预算由算法自身管理。

## 保留跨代状态：普通类

```python
import numpy as np


class MySearch:
    def __init__(self, scale: float = 0.05):
        self.scale = scale
        self.generation = 0

    def step(self, population, problem):
        self.generation += 1
        X = population.get_decision_matrix()
        return np.clip(X + np.random.normal(0, self.scale, X.shape), problem.xl, problem.xu)
```

不用继承平台类，参数从 `__init__` 读取；动态策略类同理实现 `response`。
实例在一次运行中复用，下次运行重新构造。每个批量任务都有独立进程和实例。

## 完整优化循环

高级算法可以在单个文件里继承 `algorithms.search_algorithm.Algorithm.Algorithm`，
自行实现 `optimize(self, problem, response_strategy)`。
构造函数可以通过 `**args` 把 `state/pip/mode/seed` 传给基类。
循环需检查 `self.control_process()`，调用 `self.collect_information(population, problem, response_strategy)`，
并推进到 `problem.is_ended()`。原有文件夹算法接口保持兼容。
平台不会给自定义完整循环添加隐含选择或修正错误的预算；未合作响应终止的进程会被强制结束。

## 参数与名称

- 默认值直接从函数签名或构造函数读取，支持 int、float、bool、str、list、dict、tuple。
- 无默认值的必填参数需要类型注解，例如 `scale: float`，界面要求填写。
- 支持 `Optional[float]`、`float | None` 和同类型 `Literal["a", "b"]`；列表/字典输入使用 JSON。
- 默认值必须是字面量。不执行 `make_default()`、`np.array(...)` 等来生成配置。
  复杂对象可在构造函数/函数体中创建。
- 文件名需为 Python 标识符，不以 `_` 开头；名称默认取文件名/类名。
  可选写 `NAME = "我的算法"`、`YEAR = 2026`，无需额外文件。
- 一个文件默认只有一个入口；多个入口时写 `ALGORITHM = "类名"` 选择。
  辅助函数可任意命名，辅助类请避免声明相同运行接口。
- seed 是搜索算法的运行参数，由平台统一管理；不要在 step 中重复声明 seed/state/pip/mode。
- 平台统一播种 Python random 和 numpy.random；自行创建 `default_rng()` 等独立随机源时，
  请在类构造函数中接收 seed 并明确传给随机源，避免无种子导致不可重复。
- 代码接口或参数修改后刷新组件，逻辑修改在下一次新进程运行时重新读取。

## 返回值与检查

返回 Population 或形状为 `(problem.solution_num, problem.decision_num)` 的二维决策矩阵。
必须有限且在变量边界内；平台拒绝 NaN/Inf、错误尺寸、越界，不静默裁剪或补充随机个体。
“检查并快速试跑”在独立进程中使用小规模 CDP1，默认不写结果。
试跑通过只说明基本接口和运行链路可用，不证明算法理论正确、论文复现成功或所有问题兼容。

发现代码只做语法解析，不执行导入和装饰器。真正运行拥有当前账户的权限，**不是安全沙箱**；
只运行可信代码。依赖缺失会显示具体模块及堆栈，不自动安装。
单文件可以使用同目录辅助模块的相对导入，但“导入文件”只复制选中的一个文件；
辅助文件请自行放入代码目录，建议以 `_` 开头避免被当作独立算法扫描。
