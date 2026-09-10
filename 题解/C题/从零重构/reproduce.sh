#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results
python3 tools/export_inputs.py
if [ -z "${HIGHS_ROOT:-}" ]; then
 HIGHS_ROOT="$(python3 -c 'import importlib.util,pathlib; s=importlib.util.find_spec("casadi"); print(pathlib.Path(s.origin).parent if s else "")')"
fi
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DHIGHS_ROOT="$HIGHS_ROOT"
cmake --build build -j "${BUILD_JOBS:-2}"
./build/microgrid gradient | tee results/gradient.csv
if [ ! -x build/verify ]; then
 echo 'Native HiGHS verification is required for a verified release.' >&2
 exit 1
fi
./build/verify inputs/native results/verification.csv | tee results/verify.log
{ c++ --version | head -1; uname -a; python3 -m pip freeze; } > results/environment.txt
sha256sum src/* > results/source_sha256.txt
pids=()
for kind in 0 1 2 3; do
 ./build/microgrid tune inputs/native results "$kind" >"results/tune_${kind}.log" 2>&1 & pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
sha256sum results/frozen_*.txt >results/frozen_config_sha256.txt
printf 'complete\n' >results/tuning.complete
sha256sum -c results/frozen_config_sha256.txt
pids=()
for kind in 0 1 2 3; do
 ./build/microgrid evaluate inputs/native results "$kind" >"results/evaluate_${kind}.log" 2>&1 & pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
./build/report inputs/native results | tee results/report.log
printf 'complete\n' >results/annual.complete
cat results/acceptance.json
# Successful numerical execution does not imply that the financial target passed.
