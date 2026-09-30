# FlexDMO

<div align="center">
  <img src="views/resources/images/icon.png" alt="FlexDMO Logo" width="200"/>
</div>

[![Tests](https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml/badge.svg)](https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml)

## 近期预测策略

- **PSCA（2024）**：复现局部子空间对齐与协方差相关对齐，预测动态
  Pareto 解集的平移、旋转和形变。
- **LR-DMOEA（2025）**：使用十一个分位点和一个解集中心建立带正则化的
  多变量线性预测模型，并结合高斯采样、D-NSGA-II-B 变异和随机替换。
- 两种策略均使用 FlexDMO 的约束支配规则，可与现有任一静态搜索算法组合。

FlexDMO 是一个可扩展的动态多目标优化实验平台，提供图形界面、算法与问题插件发现、动态环境响应、约束处理、运行回放、指标统计和批量实验功能。

## 主要功能

- 搜索算法：NSGA-II、RMMEDA、SPEA2、MOEA/D。
- 动态响应策略：NoResponse、DIP、MDA、MDP、RNN、D-NSGA-II-A/B、PPS、FGTTMP、PSCA、LR-DMOEA。
- 动态问题：DF、FDA、dMOP、DP、F、HE、JY、UDF 系列，以及带时变约束的 CDP1–CDP6。
- 约束优化：采用可行性优先规则，依次比较可行性、总约束违反量和 Pareto 支配关系。
- 结果回放：保存每个环境和评估时刻的决策、目标、约束、可行性、排序、拥挤度、边界、POF/POS；加载后可用时间轴逐帧回放。
- 可视化：真实 Pareto 前沿、可行/不可行解、IGD、约束违反量和决策空间。
- 结果分析：MIGD Excel 对比表，支持单算法、缺失组合和多算法秩和检验。
- 可复现运行：搜索算法支持固定随机种子。

## 安装和启动

Windows/Linux 推荐 Python 3.10。macOS 使用下面的独立安装步骤。

```bash
git clone https://github.com/Xieliuliuliu/FlexDMO.git
cd FlexDMO

python -m venv venv

# Linux
source venv/bin/activate

# Windows PowerShell
venv\Scripts\Activate.ps1

pip install -r requirements.txt
python main.py
```

图形界面依赖 Tk。部分 Linux 发行版需要另外安装 `python3-tk`。

### macOS（已验证 Apple Silicon）

使用带 Tk 支持的 Python 3.12，避免使用 macOS 自带的旧 Python/Tk。
在项目目录执行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements-macos.txt
.venv/bin/python main.py
```

安装完成后也可以在 Finder 中双击 `Start-FlexDMO.command` 启动。
首次使用源码启动器可执行 `chmod +x Start-FlexDMO.command`。
启动器自动定位项目目录，不依赖 Terminal 当前所在目录。
`requirements-macos.txt` 为 Python 3.12 使用预编译依赖；原 Windows 依赖文件仍保留。
界面随屏幕大小调整初始窗口，实验结果保存使用系统原生路径。
优化任务使用 `spawn` 子进程，避免从 Tk 窗口派生 `fork` 进程。
实时绘图、运行结束后的回放启用和实验进度更新均由 Tk 主线程处理；
后台监听线程不直接调用 Tk，避免 macOS 上回调丢失或界面卡住。

本地验证：

```bash
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests -v
# 需要桌面会话；自动检查真实窗口、子进程、保存和回放后退出
.venv/bin/python tests/gui_smoke.py
.venv/bin/python tests/runtime_smoke.py
.venv/bin/python tests/layout_smoke.py
```

## 基本使用

界面会随窗口宽度自动调整：大窗口并排显示四个区域，小窗口将设置、
图表与历史结果合并为页签。算法列表和参数区可独立滚动；调整窗口大小
不会清空参数或运行记录。开始任务或加载结果后会自动切到运行与回放区域。
切换测试运行和批量实验模块也保留各自的参数、图表与任务卡片。
图表上方显示运行、暂停、完成或失败状态；子进程异常会报告到界面。

1. 在“测试运行”选择搜索算法、响应策略和动态问题。
2. 调整种群规模、动态变化频率、总环境数和随机种子。
3. 启动任务，在图表中查看当前种群、Pareto 前沿和约束状态。
4. 完成或终止后点击“保存结果”选择目录；也可以运行前勾选“自动保存”。
5. 通过“文件 → 打开结果”加载 JSON，并拖动时间轴回放所有快照。

旧版本只保存决策变量的 JSON 仍可加载；缺失的目标和约束会按对应问题与环境重新计算。新保存格式使用 `schema_version: 2`，可以忠实还原回放状态。

终止不会清空已收到的快照，因此部分运行也能保存和回放，但不能当作完整实验结果。
运行或暂停时禁止加载另一份历史文件。开始新运行会替换内存历史，退出应用前需保存需要保留的数据。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

无图形界面的服务器可指定 Matplotlib 后端：

```bash
# Linux/macOS
MPLBACKEND=Agg python -m unittest discover -s tests -v

# Windows PowerShell
$env:MPLBACKEND = "Agg"
python -m unittest discover -s tests -v
```

测试覆盖组件发现与导入、约束支配、非支配排序、种群选择、指标计算、动态环境切换、响应策略、四种搜索算法、异常状态、手动保存、回放时间轴和 MIGD 输出。桌面检查另覆盖暂停 / 继续、终止后部分回放、模块状态保留与多档窗口布局。GitHub Actions 会运行测试和 `pip-audit`，Dependabot 每周检查 Python 包与 Actions 更新。

## 扩展项目

每个算法、响应策略、问题、图表和结果输出模块都放在独立目录中，并通过 `info.json`、`config.json` 与 `main.py` 描述。复制现有模块并保持相同接口即可加入自定义实现，无需修改中央注册表。

```text
FlexDMO/
├── algorithms/
│   ├── response_strategy/
│   └── search_algorithm/
├── components/
├── plots/
├── problems/
│   ├── benchmark/
│   └── real_problem/
├── results_output/
├── tests/
├── utils/
├── views/
└── main.py
```

详细文档：[flexdmo.cn](https://flexdmo.cn)

## 反馈与许可

- Issues: [Xieliuliuliu/FlexDMO/issues](https://github.com/Xieliuliuliu/FlexDMO/issues)
- Email: xiejinsong@whu.edu.cn / hyhhyh@whu.edu.cn
- License: Apache-2.0
