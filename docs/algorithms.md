# 算法目录与适配说明

[返回项目首页](../README.md) · [代码接口](../flexdmo_app/CODE_API.md)

FlexDMO 将环境响应与环境内搜索分成两个组件。组合一个论文响应策略和另一搜索算法，
得到的是该组合的实验结果，不等同于原论文完整算法的复现。

## 搜索算法

| 组件 | 年份 | 原始文献 | 实现 |
| --- | --- | --- | --- |
| RM-MEDA | 2008 | Zhang, Zhou & Jin. *RM-MEDA: A Regularity Model-Based Multiobjective Estimation of Distribution Algorithm*. IEEE TEVC, 12(1), 41–63. [DOI](https://doi.org/10.1109/TEVC.2007.894202) | [RMMEDA](../algorithms/search_algorithm/RMMEDA/main.py) |
| MOEA/D | 2007 | Zhang & Li. *MOEA/D: A Multiobjective Evolutionary Algorithm Based on Decomposition*. IEEE TEVC, 11(6), 712–731. [DOI](https://doi.org/10.1109/TEVC.2007.892759) | [MOEAD](../algorithms/search_algorithm/MOEAD/main.py) |
| NSGA-II | 2002 | Deb, Pratap, Agarwal & Meyarivan. *A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II*. IEEE TEVC, 6(2), 182–197. [DOI](https://doi.org/10.1109/4235.996017) | [NSGA2](../algorithms/search_algorithm/NSGA2/main.py) |
| SPEA2 | 2001 | Zitzler, Laumanns & Thiele. *SPEA2: Improving the Strength Pareto Evolutionary Algorithm*. ETH Zürich, TIK Report 103. [报告](https://sop.tik.ee.ethz.ch/publicationListFiles/zlt2001a.pdf) | [SPEA2](../algorithms/search_algorithm/SPEA2/main.py) |

## 文献响应策略

### LR-DMOEA · 2025

Ma, Sang, Xu & Wang. *A Linear Regression Prediction-Based Dynamic Multi-Objective Evolutionary
Algorithm with Correlations of Pareto Front Points*. Algorithms, 18(6), 372.
[DOI](https://doi.org/10.3390/a18060372) · [实现](../algorithms/response_strategy/LRDMOEA/main.py)

平台实现关键点提取、正则化线性预测、高斯采样、D-NSGA-II-B 变异与随机替换。
响应部分独立于搜索算法；选择其他搜索组件时，需在实验报告中记录这一变化。

### FGTTMP · 2024

Wang, Li, Wang, Gong & Li. *Solving Dynamic Multiobjective Optimization Problems via
Feedback-Guided Transfer and Trend Manifold Prediction*. IEEE Transactions on Systems, Man,
and Cybernetics: Systems, 54(12).
[DOI](https://doi.org/10.1109/TSMC.2024.3443143) · [作者公开论文](https://www.cs.newpaltz.edu/~lik/publications/Yong-Wang-IEEE-TSMC-2024) · [实现](../algorithms/response_strategy/FGTTMP/main.py)

原文的标量适应度依赖嵌入的静态优化器。平台使用排名与归一化目标构成的适应度，
使响应方法能够与不同搜索组件搭配。该适配约定应随实验配置一同说明。
额外依赖为 scikit-learn。

### PSCA · 2024

Li, Liu & Deng. *A prediction method for dynamic multiobjective optimization based on joint
subspace and correlation alignment*. Complex & Intelligent Systems, 10, 4421–4444.
[DOI](https://doi.org/10.1007/s40747-024-01369-4) · [实现](../algorithms/response_strategy/PSCA/main.py)

论文中的方法名为 PSCA。平台实现联合子空间与相关性对齐预测，
选择操作采用平台的约束支配规则。约束问题上的组合实验不应直接视为原文实验。
额外依赖为 scikit-learn。

### PPS · 2014

Zhou, Jin & Zhang. *A Population Prediction Strategy for Evolutionary Dynamic Multiobjective
Optimization*. IEEE Transactions on Cybernetics, 44(1), 40–53.
[DOI](https://doi.org/10.1109/TCYB.2013.2245892) · [作者机构记录](https://repository.essex.ac.uk/11562/) · [实现](../algorithms/response_strategy/PPS/main.py)

使用种群中心的自回归预测与历史流形估计生成新环境种群。
年份采用期刊卷期年份 2014；论文于 2013 年在线发表。

## 其他内置响应组件

| 组件 | 注册年份 | 实现 |
| --- | --- | --- |
| DIP | 2024 | [DIP](../algorithms/response_strategy/DIP/main.py) |
| MDA | 2024 | [MDA](../algorithms/response_strategy/MDA/main.py) |
| RNN | 2024 | [RNN](../algorithms/response_strategy/RNN/main.py) |
| MDP | 2019 | [MDP](../algorithms/response_strategy/MDP/main.py) |
| D-NSGA-II-A | 2007 | [DNSGAIIA](../algorithms/response_strategy/DNSGAIIA/main.py) |
| D-NSGA-II-B | 2007 | [DNSGAIIB](../algorithms/response_strategy/DNSGAIIB/main.py) |
| NoResponse | 基线，不列论文年份 | [NoResponse](../algorithms/response_strategy/NoResponse/main.py) |

本表的注册年份来自组件元数据，不能替代论文出处。
DIP 和 RNN 使用 PyTorch，基础安装不包含该依赖；安装方式见[安装指南](installation.md#算法专用依赖用到再装)。

## 测试问题与实验说明

问题族包括 DF、FDA、dMOP、DP、F、HE、JY、UDF。
CDP1–CDP6 是项目自定义动态约束套件，不以同名论文基准的身份发布。
问题实现见 [problems/benchmark](../problems/benchmark)。

正式比较应记录代码版本、算法参数、问题参数、环境变化设置、评价预算、随机种子和重复次数。
对论文方法进行复现时，还需核对原文的搜索算子与选择规则。
截图、接口试跑和回归测试用于验证功能，不作为优越性或统计显著性的证据。
