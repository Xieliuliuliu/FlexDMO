#!/bin/zsh
set -eu
project_dir="${0:A:h}"
cd "$project_dir"
if [[ ! -x .venv/bin/python ]]; then
  print '请先按 README 的 macOS 安装步骤创建 .venv。'
  read '?按回车关闭…'
  exit 1
fi
exec .venv/bin/python main.py
