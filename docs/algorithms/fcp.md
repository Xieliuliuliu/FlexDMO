# FCP 响应组件：来源核对与适配边界

FCP 是 Gong、Xia、Zou、Hou、Liu 的动态约束多目标方法。本组件独立用
Python/NumPy 实现作者发布代码中的响应路径，可与 FlexDMO 的静态搜索算法组合。
它不是完整原版 FCP 优化器，也不声明复现论文实验数值或 MATLAB 随机轨迹。

## 核对来源

- 论文：*Enhancing Dynamic Constrained Multiobjective Optimization With
  Multicenters-Based Prediction*，IEEE Transactions on Evolutionary Computation，
  29(5)，1604–1618，2025；[DOI 10.1109/TEVC.2025.3551399](https://doi.org/10.1109/TEVC.2025.3551399)。
  题名、作者、卷页由 [Crossref 元数据](https://api.crossref.org/works/10.1109/TEVC.2025.3551399)核对；
  本轮实现依据是下列发布代码，不声称已取得并逐式核对论文全文。
- 作者仓库：[zoujuan1/Q-Gong-FCP](https://github.com/zoujuan1/Q-Gong-FCP)。
  核对版本：`4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26`（2026-10-04 查阅）。
  以下链接均固定到该版本。
- 核对时文件树没有 `LICENSE`，GitHub 仓库元数据的 `license` 为 `null`。
  部分 MATLAB 文件包含 PlatEMO 的研究用途声明，但不能据此假定整个作者仓库具有统一授权。
  因此作者源码仅作机制参考：仓库内没有引入第三方 `.m`、`.asv` 文件或复制其实现；
  本组件是独立编写的 NumPy 实现。

## 实际执行机制

| 发布源码 | 实际作用 | Python 对应 |
| --- | --- | --- |
| [FCP.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/FCP.m) | 首次变化重初始化；第二次起使用全种群均值差平移多个中心 | `FCP.response`、`predict_centers` |
| [ModifyObj.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/ModifyObj.m) | 归一化约束违反量、可行比例和目标惩罚辅助空间 | `modify_objectives` |
| [ClassP.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/ClassP.m) | 对惩罚向量聚类，再求每群决策均值；随机排列中心编号 | `penalty_clustering`、`center_spacing` |
| [ClassDis2.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/ClassDis2.m) | 配对中心之差的逐维绝对值 | `center_spacing` |
| [exDiversity.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/exDiversity.m) | 围绕预测中心，以逐维中心间距为半宽均匀生成，再评估 | `generate_population`、`FCP._evaluate` |
| [NewReinitialization.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/NewReinitialization.m) | 新环境评估后的可行比例决定保留数，其余通过 GA 产生，再与旧决策的新评估合并 | `FCP._bootstrap`、`FCP._variation` |

### 惩罚辅助聚类

约束统一为 `G <= 0` 可行，正值为违反。设约束数为 `L`，可行比例为 `rf`：

```text
v_i = mean_j(max(G_ij, 0) / max_l(max(G_lj, 0)))
```

最大正违反量为零的约束列贡献零，但仍计入 `L`。无约束时定义 `v_i = 0`、`rf = 1`。
有可行解时，逐目标 min–max 归一化得到 `fbar_ij`；常数目标列取 **1**，不是零。
实际发布代码的惩罚向量为：

```text
rf == 0: penalty_ij = v_i
rf > 0:  penalty_ij = hypot(fbar_ij, v_i) + (1-rf) * v_i
```

这是核对代码后的实际行为：源码在填充 `normPopObj` 之前计算 `Y`，所以 `Y` 一直为零。
本实现保留该行为，没有默默改成含非零 `rf * Y` 的另一套惩罚公式。
数值上先缩放再归一化，避免有限但极端的目标范围相减溢出。
FlexDMO 的可行判定采用总正违反量 `<= 1e-12`，与源码严格 `G > 0` 判定存在容差差异。

NumPy k-means++/Lloyd 的输入是这些**惩罚向量，不是决策向量**。
每群对应的决策均值形成中心。所有个体（包括不可行个体）参与聚类；
不能把该方法替换成只对可行决策做通用 k-means，再为每个簇独立外推。

### 中心对应、位移和生成

作者实际主循环只存相邻两环境的种群，计算：

```text
delta = mean(X_current) - mean(X_previous)
predicted_center_i = center_i + delta
pair = random_permutation(0, ..., k-1)
spacing_i = abs(center_i - center_pair[i])
X_new = predicted_center_i + Uniform(-1, 1, each coordinate) * spacing_i
```

`delta` 是**全种群**均值位移，不是可行集均值差，也不是逐簇历史速度。
`pair` 是同一环境中心的随机排列，允许自身配对；其作用是生成半宽。
没有调用跨环境最近邻匹配、Hungarian 对应、AR、PCA、分类器或高斯噪声。
原版固定 `k=10`、每中心 `N/k` 个体；本实现均分配额、前若干中心补余数，保证恰好返回 `N`。

### 已核对但未在主循环使用的辅助函数

- [GetCl.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/GetCl.m)
  计算输入差的行平方距离并取最小若干索引，但 `FCP.m` 不调用它。
  因此不能把它解读为实际使用的跨环境多中心匹配。
- [GetMid.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/GetMid.m)
  循环各维时始终读取第一列；`FCP.m` 不调用它，而直接使用逐维 `mean`。
  本组件使用实际主循环均值，不引入这个闲置函数的列索引问题。
- [Reinitialization.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/Reinitialization.m)
  是按 `type/zeta` 随机选部分个体进行 GA 或随机替换的通用版本。
  主循环实际调用的是 `NewReinitialization.m`，不是这个版本。
- [Changed.m](https://github.com/zoujuan1/Q-Gong-FCP/blob/4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26/Changed.m)
  抽样重评估并比较目标和约束。FlexDMO 的变更检测由搜索算法及共享 `detection` 提供；
  FCP 不再自行检测，不调整检测函数或偷偷扣减评估次数。

## 与完整原版优化器的差异

| 项目 | 发布代码 | 本响应组件 |
| --- | --- | --- |
| 静态进化与收敛预热 | 惩罚版 NSGA-II；`gen_count <= 80` 预热并把 `FE` 改为 200 | 使用所选 FlexDMO 搜索算法；不实现此预热、不改写评估预算 |
| 环境选择 | `EnvironmentalSelectionByPenalty` 对惩罚目标非支配排序及拥挤度；初始化保留阶段按原目标排序 | 可行优先、不可行按总正违反量、可行间按原目标 Pareto 排序；仅拥挤度使用惩罚空间。返回真实新目标、真实约束和约束优先 rank |
| 首次响应 | 重评估 OldP；保留 `2*floor(N*rf/2)`；GA 其余；再合并选 N | 保留该偶数配额及合并路径，但采用约束优先选择；独立实数 SBX + 有界多项式变异，不调用外部 MATLAB OperatorGA |
| 特定规模分支 | NewReinitialization 对保留数 100 有硬编码分支 | 所有规模统一处理；奇数/单个体也保持规模 |
| 聚类实现 | MATLAB `kmeans` | NumPy k-means++/Lloyd；初始化、停止条件及随机序列不保证 MATLAB 数值相同 |
| 簇数与退化 | 固定 10；重复数据可能空群 | 有效簇数不超过唯一惩罚向量数；空群从仍有多个成员的群拆点 |
| 零中心间距 | 自身配对可得到零宽 | 正常配对保留零宽；仅当所有半宽都为零时使用下述退化保障 |
| 边界修复 | 负数先 abs，再随机回弹，可能多次 while | 保留合法坐标；越界作有界三角反射；支持负区间、固定坐标，无无限 while |
| 输出与档案 | 可行档案 A、AllPop 和作者终止逻辑 | 返回 N 个已评估个体；最终可行档案和终止逻辑归所组合的搜索算法 |

退化保障半宽为 `max(0.5 * ptp(X_current), diversity_floor * (upper-lower))`。
只在**所有中心间距全零**时启用，不是普通路径上的额外噪声；固定维度仍为零。
`diversity_floor=0` 禁用下限部分，种群自身范围部分仍保留。

空输入在新环境随机补齐；不足 N 的首次输入也先随机补齐，过量输入按约束优先截断。
未评估或决策已被修复的输入执行初始化路径，且不把与旧 F/G 不一致的决策冒充有效旧环境快照。
决策 NaN 用区间中点，正/负无穷用上/下界修复；非法边界、非有限参数、
非有限新评估目标/约束、总违反量溢出则明确报错，不把错误评估伪造成可行解。
仅支持实值盒约束；没有复现作者头部标记中的整数、标签、二进制、排列编码。

## 默认参数与使用

`info.json` 提供 `name=FCP`、`year=2025`、DOI 和中文 `parameter_labels`；
`config.json` 经现有目录扫描发现，不需要修改共享 registry 或 README。
仅依赖 NumPy 及项目现有 Population/排序工具，不依赖 sklearn、scipy 或 torch。

| 参数 | 默认 | 取值与作用 |
| --- | --- | --- |
| `cluster_num` | 10 | 正整数，作者主循环簇数；退化时自动缩减 |
| `max_iter` | 100 | 正整数，NumPy Lloyd 迭代上限 |
| `crossover_eta` | 20.0 | 有限非负数，仅首次/回退初始化的 SBX 分布指数 |
| `mutation_eta` | 20.0 | 有限非负数，仅首次/回退初始化的多项式变异分布指数 |
| `diversity_floor` | 0.02 | 有限 [0,1]，全零半宽退化时的区间比例下限 |
| `evaluation_batch_size` | 64 | 正整数，每批新环境评估的最大个体数及取消检查粒度 |

SBX 交叉概率取 1，每维变异概率取 `1/D`；分布指数 20 是本组件明确选定的常规值。
作者仓库未提供 `OperatorGA` 本体，故不将该初始化实现宣称为作者 GA 的逐随机数移植。

```python
from algorithms.response_strategy.FCP import FCP

response = FCP(cluster_num=10)
updated_population = response.response(old_population, problem, algorithm)
```

使用局部 `default_rng(SeedSequence([algorithm.seed, successful_response_count]))`。
没有 algorithm 或 `seed=None` 时使用 0；种子必须为非负整数。
不改变全局 NumPy 随机状态，相同输入、调用序列、种子和 NumPy 版本可复现。
每次**成功响应**递增序号，重复环境调用也算一次成功响应。

最多保留两个不同环境的输入决策快照。每次调用发生在检测切换后的新 `problem.t`，
输入通常仍带上一环境的目标和约束；聚类使用这些历史评价，输出必须重新在新环境评估。
同一 problem 的 `t` 或 `evaluate_time` 倒退、切换 problem 实例、修改 bounds 都清空历史并重启序号。
同一 `t` 重复调用替换当前环境槽位，不 append；预测只使用前一个不同环境的槽位。
仅一个独立环境时，重复调用仍走初始化路径。没有 `t` 的自定义问题只能按调用序列保存历史；
没有评估计数时仍可通过 `t` 倒退识别重置。

## 中断与评估边界

调用 `algorithm.control_process()`，在入口、聚类初始化/迭代/空群处理、
逐中心生成、选择阶段和每批评估前后检查。hook 返回假值时立即返回原输入 Population；
不提交新的历史、时间标记或随机序号。hook 自己抛出的异常保持传播。
已完成的评估仍计入 problem 预算，无法回滚；单个正在执行的 `problem.evaluate` 调用不能被本组件抢占。
外层优化器收到停止状态后应跳过结果记录，不能把取消后返回的旧 F/G 记录为新环境结果。

本组件不使用 `need_count=False` 做响应评估，不修改 `t` 或 FE。
正常预测评估恰好 N 行；首次响应评估补齐后的旧决策及 GA 新个体，预算通常更大。
依赖 FlexDMO Problem 将环境推进限制在检测边界；自定义 evaluator 若在响应批次间自行切换环境，
不属于此适配接口的支持范围。

## 专属验证

```bash
.venv/bin/python -W error -m unittest tests.test_fcp -v
```

专属测试覆盖实际惩罚公式和零 Y、无可行解惩罚聚类、非决策空间聚类、
全局位移、随机中心配对及均匀盒生成、空群/重复中心、小规模及奇数规模、
负/固定边界、非有限参数、新环境重评估、约束优先、输入隔离、确定种子、
中途取消及重试、同一 problem 重置/计数倒退/重复环境、无可选依赖的干净进程导入、
中文参数自动发现，以及真实 NSGA-II + CDP1 多环境工作流。
这是功能和机制验证，不是性能实验或论文复现成绩。
