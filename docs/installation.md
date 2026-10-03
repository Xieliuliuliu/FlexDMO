# 安装与启动

[返回项目首页](../README.md) · [使用手册](usage.md)

## macOS

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

## Windows

使用 Python 3.10，PowerShell 中执行：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Linux

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

## 算法专用依赖：用到再装

基础安装不包含 PyTorch 或 scikit-learn。启动、浏览算法、切换配置不会加载这些库；
只有运行选中的算法时才导入。未安装时会提示所缺库和当前 Python 环境的安装命令，
不会自动安装，也不影响其他算法。

| 要运行的算法 | 额外依赖 | 依赖文件 |
| --- | --- | --- |
| DIP | PyTorch | `algorithms/response_strategy/DIP/requirements.txt` |
| RNN | PyTorch | `algorithms/response_strategy/RNN/requirements.txt` |
| FGTTMP | scikit-learn | `algorithms/response_strategy/FGTTMP/requirements.txt` |
| PSCA | scikit-learn | `algorithms/response_strategy/PSCA/requirements.txt` |

例如需要 DIP 时，在项目目录执行：

```bash
.venv/bin/python -m pip install -r algorithms/response_strategy/DIP/requirements.txt
```

Windows 将 `.venv/bin/python` 换成 `.\.venv\Scripts\python.exe`。安装后重新运行即可。
默认的 D-NSGA-II-B / NSGAII / CDP1 不需要上述额外库。
