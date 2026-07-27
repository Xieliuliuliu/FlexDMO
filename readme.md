# FlexDMO

<div align="center">
  <img src="views/resources/images/icon.png" alt="FlexDMO Logo" width="200"/>
</div>

[![Tests](https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml/badge.svg)](https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml)

FlexDMO 是一个可扩展的动态多目标优化实验平台，提供图形界面、算法与问题插件发现、动态环境响应、约束处理、运行回放、指标统计和批量实验功能。

## 主要功能

- 搜索算法：NSGA-II、RMMEDA、SPEA2、MOEA/D。
- 动态响应策略：NoResponse、DIP、MDA、MDP、RNN。
- 动态问题：DF、FDA、dMOP、DP、F、HE、JY、UDF 系列，以及带时变约束的 CDP1。
- 约束优化：采用可行性优先规则，依次比较可行性、总约束违反量和 Pareto 支配关系。
- 结果回放：保存每个环境和评估时刻的决策、目标、约束、可行性、排序、拥挤度、边界、POF/POS；加载后可用时间轴逐帧回放。
- 可视化：真实 Pareto 前沿、可行/不可行解、IGD、约束违反量和决策空间。
- 结果分析：MIGD Excel 对比表，支持单算法、缺失组合和多算法秩和检验。
- 可复现运行：搜索算法支持固定随机种子。

## 安装和启动

推荐 Python 3.10。

```bash
git clone https://github.com/Xieliuliuliu/FlexDMO.git
cd FlexDMO

python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows PowerShell
venv\Scripts\Activate.ps1

pip install -r requirements.txt
python main.py
```

图形界面依赖 Tk。部分 Linux 发行版需要另外安装 `python3-tk`。

## 基本使用

1. 在“测试模块”选择搜索算法、响应策略和动态问题。
2. 调整种群规模、动态变化频率、总环境数和随机种子。
3. 启动任务，在图表中查看当前种群、Pareto 前沿和约束状态。
4. 使用保存按钮写出完整结果。
5. 通过“文件 → 打开结果”加载 JSON，并拖动时间轴回放所有快照。

旧版本只保存决策变量的 JSON 仍可加载；缺失的目标和约束会按对应问题与环境重新计算。新保存格式使用 `schema_version: 2`，可以忠实还原回放状态。

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

测试覆盖组件发现与导入、约束支配、非支配排序、种群选择、指标计算、动态环境切换、五种响应策略、四种搜索算法、结果保存加载、回放时间轴和 MIGD 输出。GitHub Actions 会运行测试和 `pip-audit`，Dependabot 每周检查 Python 包与 Actions 更新。

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
