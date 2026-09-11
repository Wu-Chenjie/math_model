#!/bin/zsh
set -eu
cd "${0:A:h}"
python3 tools/reproduce_project.py "$@"
