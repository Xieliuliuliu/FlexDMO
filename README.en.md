<div align="center">
  <img src="flexdmo_app/resources/images/icon.png" alt="FlexDMO logo" width="112"/>
  <h1>FlexDMO</h1>
  <p><strong>A research platform for dynamic multiobjective optimization</strong></p>
  <p>Compose algorithms · Inspect evolution · Replay runs · Compare experiments</p>
  <p>
    <a href="https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml"><img src="https://github.com/Xieliuliuliu/FlexDMO/actions/workflows/tests.yml/badge.svg" alt="Test status"/></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-167d8d?style=flat" alt="Apache-2.0 license"/></a>
    <a href="https://flexdmo.cn"><img src="https://img.shields.io/badge/Docs-flexdmo.cn-167d8d?style=flat" alt="FlexDMO documentation"/></a>
  </p>
  <p>
    <a href="#quick-start">Quick start</a> ·
    <a href="https://flexdmo.cn">Documentation</a> ·
    <a href="flexdmo_app/CODE_API.md">Algorithm API</a> ·
    <a href="https://github.com/Xieliuliuliu/FlexDMO/issues">Issues</a>
  </p>
  <p><a href="README.md">简体中文</a> · English</p>
</div>

FlexDMO separates **search algorithms, environment response strategies, and test problems**.
Use the desktop workspace to inspect population recovery after an environmental change,
revisit earlier solutions, and run repeated experiments across algorithm combinations.

![FlexDMO workspace with synchronized PF, PS, IGD, and environment history](docs/assets/workspace.png)

*An actual D-NSGA-II-B / NSGA-II / CDP1 run with small demonstration settings, not evidence of algorithm performance.*

## Capabilities

| Area | What you can do |
| --- | --- |
| Modular experiments | Select search algorithms, response strategies, and problems independently; retain component parameters when switching |
| Inspection and replay | Synchronize PF, PS, IGD, and CV; navigate environments and snapshots; pause, resume, or stop |
| Batch experiments | Select multiple components, scan parameters, repeat with matched seeds, and inspect plots and statistics |
| Python extensions | Import a Python file implementing `step` or `response`; derive parameters from the function signature |

Constrained problems distinguish feasible and infeasible solutions, with gray shading for
the two-dimensional infeasible regions supplied by the problem. Narrow windows stack charts
vertically; settings and history panels can be hidden or floated.

<details>
<summary><strong>Batch experiments and result comparison</strong></summary>

### Batch experiments

Select components and parameter ranges, preview the task count, then run the batch.
Test and batch views use the same selector component, ordered by year.
All combinations within a repetition use the same seed.

![Two response strategies with two independent repetitions](docs/assets/batch-experiments.png)

### Result comparison

Group runs by matching problem parameters and budgets. Inspect environment-end IGD,
feasibility, same-environment PF, and repeated MIGD. Each curve retains its individual run identity.

![Environment-end IGD comparison under matching problem settings](docs/assets/result-comparison.png)

[Detailed experiment guide — Chinese](docs/usage.md#批量实验与对比)

</details>

## Quick start

```bash
git clone https://github.com/Xieliuliuliu/FlexDMO.git
cd FlexDMO
```

<details open>
<summary><strong>macOS · Python 3.12</strong></summary>

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements-macos.txt
.venv/bin/python main.py
```

After installation, you can also launch `Start-FlexDMO.command`.

</details>

<details>
<summary><strong>Windows · Python 3.10 / PowerShell</strong></summary>

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

</details>

<details>
<summary><strong>Linux · Python 3.10 / graphical session</strong></summary>

On Ubuntu or Debian, install the graphical system libraries first:

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 fonts-noto-cjk
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

A plain SSH session does not display the desktop window.

</details>

The base environment does not require PyTorch or scikit-learn. Install the additional
requirements only when using DIP, RNN, FGTTMP, or PSCA; the app reports missing packages
for the selected algorithm. See the [installation guide — Chinese](docs/installation.md).

The default `D-NSGA-II-B / NSGAII / CDP1` combination uses small settings to get you started.
The current desktop interface is in Chinese; click “开始运行” to start.
For research experiments, configure the problem size, environmental changes, and repetitions.
Replay remains available in the current session; save results or export statistics when needed.

## Algorithms and problems

### Search algorithms

| Algorithm | Year | Approach | Original reference |
| --- | --- | --- | --- |
| [RM-MEDA](algorithms/search_algorithm/RMMEDA) | 2008 | Regularity model-based distribution estimation | [IEEE TEVC](https://doi.org/10.1109/TEVC.2007.894202) |
| [MOEA/D](algorithms/search_algorithm/MOEAD) | 2007 | Decomposition and neighborhood search | [IEEE TEVC](https://doi.org/10.1109/TEVC.2007.892759) |
| [NSGA-II](algorithms/search_algorithm/NSGA2) | 2002 | Nondominated sorting and crowding distance | [IEEE TEVC](https://doi.org/10.1109/4235.996017) |
| [SPEA2](algorithms/search_algorithm/SPEA2) | 2001 | Strength fitness and external archive | [ETH TIK Report 103](https://sop.tik.ee.ethz.ch/publicationListFiles/zlt2001a.pdf) |

### Selected environment response strategies

| Strategy | Year | Approach | Original reference |
| --- | --- | --- | --- |
| [LR-DMOEA](algorithms/response_strategy/LRDMOEA) | 2025 | Key-point correlations and linear regression | [Algorithms](https://doi.org/10.3390/a18060372) |
| [FGTTMP](algorithms/response_strategy/FGTTMP) | 2024 | Feedback-guided transfer and trend manifold prediction | [IEEE TSMC: Systems](https://doi.org/10.1109/TSMC.2024.3443143) |
| [PSCA](algorithms/response_strategy/PSCA) | 2024 | Joint subspace and correlation alignment | [Complex & Intelligent Systems](https://doi.org/10.1007/s40747-024-01369-4) |
| [PPS](algorithms/response_strategy/PPS) | 2014 | Population center and manifold prediction | [IEEE TCYB](https://doi.org/10.1109/TCYB.2013.2245892) |

Also included: D-NSGA-II-A/B, DIP, MDA, MDP, RNN, and the NoResponse baseline.
See the [algorithm catalog and adaptation notes — Chinese](docs/algorithms.md).

Problem families include DF, FDA, dMOP, DP, F, HE, JY, and UDF, plus the project's
CDP1–CDP6 dynamic constrained suite. Response methods are adapted as composable components;
reproducing a paper's complete algorithm requires matching its operators, parameters,
evaluation budgets, and experiment settings.

## Write your own algorithm

Save the following as `MySearch.py` and import it as a search algorithm in “组件管理”:

```python
import numpy as np

def step(population, problem, scale: float = 0.05):
    if scale < 0:
        raise ValueError("scale must be non-negative")
    X = population.get_decision_matrix()
    noise = np.random.normal(0, scale, X.shape) * (problem.xu - problem.xl)
    return np.clip(X + noise, problem.xl, problem.xu)
```

This interface example has no elitist selection. A search component returns the complete next
generation; the platform handles initialization, evaluation, environmental changes, run control,
and snapshots. Response strategies implement `response(population, problem, ...)`.
Classes and full optimization loops are supported without additional registration JSON.

[Code API](flexdmo_app/CODE_API.md) · [Examples](flexdmo_app/examples) · [Plugin directories](flexdmo_app/plugins/README.md)

## Documentation and contribution

The [installation guide](docs/installation.md), [user guide](docs/usage.md),
[algorithm notes](docs/algorithms.md), and [contribution guide](CONTRIBUTING.md) are currently in Chinese.
Version changes are listed in the [changelog](CHANGELOG.md).

Report reproducible problems through [Issues](https://github.com/Xieliuliuliu/FlexDMO/issues),
or improve algorithms, tests, and documentation through a Pull Request.
The app currently runs from source. Native interaction checks primarily cover macOS;
Linux CI covers algorithm and offscreen UI regression tests.
High-dimensional PF is a two-objective projection, HV is limited to two objectives,
and statistical significance tests are not run automatically.

## Citation and license

When using FlexDMO in research, cite the [repository](https://github.com/Xieliuliuliu/FlexDMO),
record the commit or version and experiment configuration, and cite the original algorithm papers.

Released under the [Apache License 2.0](LICENSE). Dependencies retain their own licenses,
which must also be considered when distributing the software.
Contact: [xiejinsong@whu.edu.cn](mailto:xiejinsong@whu.edu.cn) · [hyhhyh@whu.edu.cn](mailto:hyhhyh@whu.edu.cn)
