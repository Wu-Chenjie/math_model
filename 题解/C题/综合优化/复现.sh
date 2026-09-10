#!/bin/zsh
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$TASK_ROOT/../../.."
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
COMPUTE_PY=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
SHEET_PY=/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
NODE_BIN=/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
SCRIPT_ROOT=题解/C题/综合优化/src
"$COMPUTE_PY" -m pip install --target "$TASK_ROOT/vendor" --no-deps highspy==1.15.1
"$COMPUTE_PY" "$SCRIPT_ROOT/prepare_project.py"
"$COMPUTE_PY" "$SCRIPT_ROOT/run_comparison.py" --phase calibrate --workers 6
"$COMPUTE_PY" "$SCRIPT_ROOT/run_comparison.py" --phase annual --workers 6
"$COMPUTE_PY" "$SCRIPT_ROOT/run_diagnostics.py"
"$COMPUTE_PY" "$SCRIPT_ROOT/convex_aggregation.py" --workers 2
"$COMPUTE_PY" "$SCRIPT_ROOT/run_comparison.py" --phase grid --grid-size 641 --workers 2 --candidates affine_sdp
"$COMPUTE_PY" "$SCRIPT_ROOT/validate_extension.py" --phase leakage
"$COMPUTE_PY" "$SCRIPT_ROOT/validate_extension.py" --phase annual
"$COMPUTE_PY" "$SCRIPT_ROOT/check_safety.py"
"$COMPUTE_PY" "$SCRIPT_ROOT/audit_regimes.py"
"$COMPUTE_PY" "$SCRIPT_ROOT/summarize.py"
cd "$TASK_ROOT"
"$NODE_BIN" src/build_workbooks.mjs
"$SHEET_PY" src/verify_workbooks.py
echo '计算、图表、结果表复现完成；更改模型或输入后需重新独立审查，再冻结验收记录。'
