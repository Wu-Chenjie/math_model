#!/bin/bash
# Full regeneration can take hours on this machine. Run within this directory.
set -euo pipefail
cd "$(dirname "$0")"
MODEL_PYTHON="${MODEL_PYTHON:-python3}"
ARTIFACT_PYTHON="${ARTIFACT_PYTHON:-python3}"
ARTIFACT_NODE="${ARTIFACT_NODE:-node}"
WORKERS="${WORKERS:-4}"
if [ ! -e node_modules ] && [ ! -L node_modules ]; then
    ln -s "$(dirname "$ARTIFACT_NODE")/../node_modules" node_modules
fi
"$ARTIFACT_PYTHON" src/prepare_data.py
"$MODEL_PYTHON" src/run.py --phase initialize
"$MODEL_PYTHON" src/run.py --phase train --iterations 500 --workers "$WORKERS"
"$MODEL_PYTHON" src/run.py --phase train --cutoffs 14 334 --tail-days 1 --iterations 500 --workers "$WORKERS"
"$MODEL_PYTHON" src/run.py --phase train --cutoffs 14 334 --tail-days 2 --iterations 500 --workers "$WORKERS"
"$MODEL_PYTHON" src/sddp.py --cutoff 31 --days 1 --iterations 500 --output tails/q2_31_D1.json
"$MODEL_PYTHON" src/run.py --phase calibrate --start 24 --stop 31 --candidates cross_baseline affine_mpc markov_mpc --workers "$WORKERS"
"$MODEL_PYTHON" src/run.py --phase calibrate_sddp_v2 --start 24 --stop 31 --candidates sddp_mpc sddp_markov --workers "$WORKERS"
"$MODEL_PYTHON" src/select_model.py
"$MODEL_PYTHON" src/run.py --phase annual --candidates closed_baseline cross_baseline affine_mpc markov_mpc closed_affine --workers "$WORKERS"
"$MODEL_PYTHON" src/run.py --phase annual_sddp --start 31 --stop 365 --candidates sddp_markov --workers "$WORKERS"
"$MODEL_PYTHON" src/validate.py --scope short --workers "$WORKERS"
"$MODEL_PYTHON" src/validate.py --scope annual-releases --workers "$WORKERS"
"$MODEL_PYTHON" src/check_terminal.py
"$MODEL_PYTHON" review/check-sddp.py
"$MODEL_PYTHON" review/check-controllers.py
"$MODEL_PYTHON" review/check-global-oracle.py
"$MODEL_PYTHON" review/check-v2-boundaries.py
"$MODEL_PYTHON" review/check-production.py --require-complete
"$MODEL_PYTHON" src/finish.py
"$MODEL_PYTHON" src/export_results.py
"$ARTIFACT_NODE" src/build_workbooks.mjs
"$ARTIFACT_PYTHON" src/verify_workbooks.py
# Review changed outputs and update visual/reviewer evidence before freezing.
# Do not blindly reuse earlier reviewer hashes or a prior acceptance report.
echo 'Numerical regeneration and export complete. Repeat visual and independent review before freeze_evidence.py and project validation.'
