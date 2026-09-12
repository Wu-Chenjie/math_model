#!/bin/sh
set -eu
cd "$(dirname "$0")"
PY=${MICROGRID_PYTHON:-python3}
mode=${1:-check}
test -f ../C题_跨日随机控制/artifacts/global-terminal/q2_markov_mpc.npz
case "$mode" in
  supplement)
    "$PY" revision/q1_and_billing.py
    "$PY" revision/strong_baseline.py
    "$PY" revision/billing_january_replan.py
    "$PY" revision/prediction-control/audit.py all
    "$PY" revision/prediction-control/gain_sensitivity.py
    "$PY" revision/prediction-control/duplicate_lp_probe.py
    ;;
  capacity)
    mkdir -p revision/storage-study/results
    for kind in q2 q3 q4_2 q4_3; do
      "$PY" revision/storage-study/run_capacity.py --kind "$kind" --width 9600 --suffix-check
    done
    "$PY" revision/storage-study/run_batch.py
    ;;
  check) ;;
  *) echo 'Usage: sh reproduce.sh [check|supplement|capacity]' >&2; exit 2 ;;
esac
"$PY" reference/scripts/register_results.py > reference/artifacts/reproduce-statistics.log
"$PY" revision/verify_billing_january.py
"$PY" revision/prediction-control/verify_outputs.py
"$PY" revision/strong_baseline.py --export-only
"$PY" revision/build_required_tables.py
"$PY" revision/restore/build_primary_evidence.py > revision/restore/reproduce-primary.log
"$PY" review/restoration_control_diagnostics.py > revision/restore/reproduce-diagnostics.log
"$PY" revision/storage-study/verify_capacity.py > revision/storage-study/reproduce-audit.log
"$PY" revision/storage-study/inventory_figures.py > revision/storage-study/reproduce-inventory.log
"$PY" revision/storage-study/zero_window_quantile.py > revision/storage-study/zero-window-quantile.log
"$PY" revision/storage-study/build_storage_evidence.py
sh compile.sh
"$PY" revision/final_math_review.py
mkdir -p output/pdf
cp main.pdf output/pdf/基于跨日随机控制与价值反馈的微网购电和储能协同调度_证据完整修订.pdf
