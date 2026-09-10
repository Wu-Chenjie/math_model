#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
COMPUTE_PYTHON="${COMPUTE_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}"
SHEET_PYTHON="${SHEET_PYTHON:-/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
ARTIFACT_NODE="${ARTIFACT_NODE:-/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mode="${1:-models}"
if [[ "$mode" == "models" || "$mode" == "all" ]]; then
  "$SHEET_PYTHON" src/prepare_data.py
  "$COMPUTE_PYTHON" src/run_models.py --phase calibrate
  "$COMPUTE_PYTHON" src/run_models.py --phase main
  "$COMPUTE_PYTHON" src/run_models.py --phase extras
  "$COMPUTE_PYTHON" src/validate_models.py
  "$COMPUTE_PYTHON" src/export_results.py
  "$COMPUTE_PYTHON" src/make_figures.py
  "$COMPUTE_PYTHON" src/build_handoff.py
fi
if [[ "$mode" == "workbooks" || "$mode" == "all" ]]; then
  "$ARTIFACT_NODE" src/build_workbooks.mjs
  "$SHEET_PYTHON" src/verify_workbooks.py
fi
if [[ "$mode" != "models" && "$mode" != "workbooks" && "$mode" != "all" ]]; then
  echo 'Usage: bash 复现.sh [models|workbooks|all]' >&2
  exit 2
fi
