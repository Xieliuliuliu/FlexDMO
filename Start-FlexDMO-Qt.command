#!/bin/zsh
set -eu
cd -- "${0:A:h}"
exec ./Start-FlexDMO.command
