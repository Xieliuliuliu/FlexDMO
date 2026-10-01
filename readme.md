# FlexDMO

<div align="center"><img src="views/resources/images/icon.png" alt="FlexDMO" width="160"/></div>

[![Tests](https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml/badge.svg)](https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml)

FlexDMO 是一个 Python 动态多目标优化实验平台。组合响应策略、搜索算法和测试问题，
观察环境变化后的种群恢复过程，再用重复实验比较结果。带约束的问题使用可行性优先规则。

在本地选择组合、查看运行过程、安排重复实验。启动入口为 `python main.py`；
详细操作见下文与[官网文档](https://flexdmo.cn)。

## 主要功能

- 单次测试：实时观察 PF、PS、IGD、约束违反量，支持暂停、继续和终止。
- 运行回放：结束即可在内存回放；右侧环境按钮跳到末帧，时间轴按实际快照移动。
- 批量实验：多选组件、扫描 n/tau、设置独立重复与并行数，同次重复使用相同 seed。
- 结果对比：在同一问题与预算下比较环境末帧 IGD、可行率、同环境 PF、重复 MIGD。
- 代码接入：写一个 `.py` 文件实现 response 或 step，不要求生成模板或补写 JSON。
- 保存与导出：默认不保存运行数据；手动或明确开启自动保存，统计可导出 CSV/Excel。

## 安装与启动

### macOS

使用 Python 3.12，在项目目录执行：

```bash
git clone https://github.com/Xieliuliuliu/FlexDMO.git
cd FlexDMO
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements-macos.txt
.venv/bin/python main.py
```

也可以双击 `Start-FlexDMO.command`。已有环境请先重新安装依赖再启动。
自定义算法需要的额外包也安装到同一环境，不自动下载或安装。

### Windows

使用 Python 3.10，PowerShell 中执行：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### Linux

Ubuntu / Debian 若缺少图形运行库，先执行：

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 fonts-noto-cjk
```

使用 Python 3.10，在图形会话中执行：

```bash
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

桌面需要图形会话，纯 SSH 终端不能直接显示窗口。当前实机操作检查覆盖 macOS；
其他系统安装后建议先做小规模试跑，不把单一系统检查当成全部平台保证。

## 第一次运行

默认选择 `D-NSGA-II-B / NSGAII / CDP1`，使用小规模试跑：
20 个体、6 决策变量、5 环境、变化间隔 3 代。点“开始 / 继续”即可。
这组参数用于检查操作流程，不是论文实验的推荐配置。

“算法与问题”页选择组合，“参数”页调整输入。同一组件切换回来恢复上次输入，
只有“恢复原算法默认参数”会重置。运行期间配置锁定。

默认同时显示 PF / PS / IGD，也可单图或加入 CV。宽窗口用网格，窄窗口纵向滚动。
设置和历史面板可以隐藏、浮动；关闭后用顶部按钮或“视图”恢复。图表各自有缩放、
平移和导出工具栏，“主页”恢复当前帧的自动范围。

- PF：青色为可行解，红叉为不可行解，橙色为真实前沿；灰色背景表示问题提供的不可行域。
- PS：当前决策向量；橙线为真实解集逐维中位数，不表示真实 PS 只有一条线。
- IGD：使用可行目标点，按当前回放位置之前各环境的最新种群计算，不读取未来帧；无可行解为 ∞。
- CV：约束违反量。高于二维的 PF 仅显示 f1–f2 投影，不能代替全维目标分析。

## 回放与数据保留

默认结果只在当前会话，重跑或关闭后不保留，不反复询问是否保存。
需要留档就点“保存结果”，或者运行前勾选“自动保存结果”。
自动保存目录为 `results/autosaved/`，顶部“打开结果”加载回放。
自动保存模式下，重跑前先保护旧结果；保存失败不清空历史。

| 回放记录方式 | 内容 | 限制 |
| --- | --- | --- |
| 完整快照（默认） | 平台收到的运行快照 | 绘图刷新合并，不是每次函数评价都重绘 |
| 环境末帧 | 每个环境最后一个收到的快照 | 仍实时绘图；结束后不能看同环境中间帧 |

轻量方式减少界面副本和保存文件，不裁剪预测策略可能读取的算法历史，
不是整个进程的内存上限。终止后的部分历史可回放，但不能当作完整实验。
旧版仅保存决策值的 JSON 仍可加载，缺失目标和约束按记录环境重算。

## 批量实验与对比

顶部“批量实验”勾选组件。n/tau 支持 `5,10` 或 `5:15:5`；
重复使用起始 seed、seed+1…，同次重复的所有组合使用相同 seed。
先“更新任务”检查数量，再“开始实验”；启动时按可见配置重新生成，不运行过期计划。

默认并行 1，上限 8；任务上限 10,000。更多并行不一定更快，特别是有大量历史或训练模型的算法。
失败任务显示错误，不阻塞其他任务。问题规模和种子在批量页统一配置，
额外组件参数单独编辑；整套配置可以保存为 JSON 并重新加载。

完成后双击任务回放。“比较结果”按问题、问题参数和预算分组。
IGD/可行率每条线代表一次运行；PF 只使用所选环境和 seed，不以其他环境代替。
MIGD 点图保留独立重复，无穷大明确计数，不当作零。
参数不同或单文件代码指纹不同的算法不合并为同一变体。

汇总只纳入完整成功任务，显示均值和样本标准差。MHV 使用当前真实 PF 逐维最大值 + 0.5
作为参考点，目前只支持二维，高维显示未支持。内置对比不自动执行显著性检验，不等于论文结论。

默认不写磁盘。勾选“保存实验结果”才会创建独立批次目录，写快照 JSON、
`runs.csv`、`summary.csv`、`statistics.xlsx`、`manifest.json`。
未勾选也可手动“导出统计”，但这不保存原始快照。

## 直接写算法代码

把以下示例保存为 `MySearch.py`，在“组件管理”中作为搜索算法导入：

```python
import numpy as np

def step(population, problem, scale: float = 0.05):
    if scale < 0:
        raise ValueError("scale 不能为负数")
    X = population.get_decision_matrix()
    noise = np.random.normal(0, scale, X.shape) * (problem.xu - problem.xl)
    return np.clip(X + noise, problem.xl, problem.xu)
```

这是接口演示，没有精英选择，不是论文算法。返回完整下一代，不是交给平台筛选的候选集。
平台负责初始化、种子、环境切换、评价、控制和快照；动态策略对应
`response(population, problem, ...)`。普通类可保留跨代状态，
完整循环可继承 Algorithm；原目录式接口继续兼容。

参数从签名和默认值读取。“刷新”只解析语法；“检查并快速试跑”才在子进程运行，
使用小规模 CDP1、20 秒上限、不保存数据。运行不是安全沙箱，只用可信代码；
额外依赖不会自动安装。返回值检查尺寸、有限性和边界，错误保留文件与实际行号。

[完整代码接口](flexdmo_app/CODE_API.md) 包含必填参数、类接口、评价预算和辅助模块说明。

## 内置组件与研究边界

搜索算法：NSGA-II、RMMEDA、SPEA2、MOEA/D。
动态策略：NoResponse、DIP、MDA、MDP、RNN、D-NSGA-II-A/B、PPS、FGTTMP、PSCA、LR-DMOEA。
问题：DF、FDA、dMOP、DP、F、HE、JY、UDF，以及 CDP1–CDP6。

CDP1–CDP6 是本项目动态约束套件，不宣称是同名标准论文基准。
论文策略在框架内拆分、组合运行，不自动等同于原论文的完整算法与实验设置。
请核对原文、参数及适配说明，不以界面年份代替文献核验。

目前没有正式安装包和全进程磁盘历史缓存，也不保证所有组件与参数组合均兼容。
自定义图表和统计输出的开发方式见官网对应说明。

## 检查与文档

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s flexdmo_app/tests
# 以下需要 macOS 桌面会话
.venv/bin/python -m flexdmo_app.replay_smoke
.venv/bin/python -m flexdmo_app.code_smoke
```

[使用说明](flexdmo_app/README.md) · [本轮变更](CHANGELOG.md) · [官网文档](https://flexdmo.cn)

文档截图来自真实小规模运行，不是算法性能证据。自动测试检查运行链路，不能代替论文实验核验。

反馈：[GitHub Issues](https://github.com/Xieliuliuliu/FlexDMO/issues)，请附组合、参数、系统、复现步骤和错误记录。
联系：xiejinsong@whu.edu.cn / hyhhyh@whu.edu.cn。许可：Apache-2.0；Qt 分发还需核对其依赖许可。
