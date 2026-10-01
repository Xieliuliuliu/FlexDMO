#!/bin/zsh
set -eu
project_dir="${0:A:h}"
cd "$project_dir"
if [[ -x .venv/bin/python ]] && .venv/bin/python -c 'import PySide6' >/dev/null 2>&1; then
  exec .venv/bin/python main.py
fi
# Support installations created before desktop dependencies were unified.
if [[ -x .venv/qt-preview/bin/python ]]; then
  exec .venv/qt-preview/bin/python main.py
fi
if [[ ! -x .venv/bin/python ]]; then
  print '请先按 README 的 macOS 安装步骤创建 .venv。'
  read '?按回车关闭…'
  exit 1
fi
print '请先运行 .venv/bin/python -m pip install -r requirements-macos.txt 更新依赖。'
read '?按回车关闭…'
exit 1
