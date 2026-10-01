#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ ! -x .venv/qt-preview/bin/python ]]; then
  exec ./Start-FlexDMO.command
  exit 1
fi
exec .venv/qt-preview/bin/python main.py
