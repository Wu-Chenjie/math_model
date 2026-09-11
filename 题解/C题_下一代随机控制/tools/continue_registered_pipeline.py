"""Continue already-running baseline/development jobs without duplicate dispatch.

This is a local, resumable task process, not a scheduler. It waits for completed
stage artifacts, closes the unchanged baseline gate, and dispatches the frozen
334-day register. It never overwrites the January selection.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT.parent/'C题_下一代基线复现'
RUNTIME = Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime')
PYTHON = RUNTIME/'dependencies/python/bin/python3'
NODE = RUNTIME/'dependencies/node/bin/node'
MARKER = RUNTIME/'plugins/openai-primary-runtime/plugins/spreadsheets/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs'
START = time.perf_counter(); RECORDS = []


def state(stage, status='running', **extra):
    value = {'status': status, 'stage': stage, 'pid': os.getpid(),
        'updated_utc': datetime.now(timezone.utc).isoformat(), 'elapsed_seconds': time.perf_counter()-START,
        'records': RECORDS, **extra}
    (ROOT/'artifacts/pipeline-execution.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def run(command, cwd, label):
    state(label); before=time.perf_counter()
    log = ROOT/f'artifacts/pipeline-logs/{label}.log'; log.parent.mkdir(exist_ok=True)
    with log.open('w') as f: proc=subprocess.run([str(x) for x in command],cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
    RECORDS.append({'stage':label,'command':[str(x) for x in command],'cwd':str(cwd),
        'exit_code':proc.returncode,'runtime_seconds':time.perf_counter()-before,'log':str(log.relative_to(ROOT))})
    state(label)
    if proc.returncode: raise RuntimeError(f'{label}: exit {proc.returncode}; inspect {log}')


def wait_for(path, label):
    state(label, awaited=str(path))
    while not path.is_file(): time.sleep(10)


def baseline_outputs():
    wait_for(REPLAY/'artifacts/execution-export.json','wait_unchanged_baseline_replay')
    # The unchanged numerical orchestrator writes export only after its audits.
    if not (REPLAY/'artifacts/workbook-validation.json').exists():
        module_link=REPLAY/'node_modules'
        if not module_link.exists():module_link.symlink_to(RUNTIME/'dependencies/node/node_modules',target_is_directory=True)
        (REPLAY/'artifacts/previews').mkdir(exist_ok=True)
        marker_record=ROOT/'artifacts/xlsx-authoring-operation.json'
        if not marker_record.exists():
            run([NODE,MARKER,'--operation-kind','create','--expected-output-count','10','--output-format','xlsx'],ROOT,'xlsx_authoring_marker')
            marker_record.write_text(json.dumps({'started_utc':datetime.now(timezone.utc).isoformat(),
                'scope':'Five unchanged baseline workbooks and five selected-policy workbooks'},ensure_ascii=False)+'\n')
        run([NODE,'src/build_workbooks.mjs'],REPLAY,'baseline_workbooks')
        run([PYTHON,'src/verify_workbooks.py'],REPLAY,'baseline_workbook_readback')
    run([sys.executable,'review/check-final-supplement.py'],REPLAY,'baseline_final_numeric_review')
    run([PYTHON,'review/check-final-supplement.py','--workbooks'],REPLAY,'baseline_final_workbook_review')
    run([sys.executable,'tools/check_baseline_reproduction.py'],ROOT,'baseline_full_comparison')


def main(workers,inherited_lock_fd=None):
    lock=(ROOT/'artifacts/pipeline.lock').open('a') if inherited_lock_fd is None else os.fdopen(inherited_lock_fd,'a')
    assert os.fstat(lock.fileno()).st_ino == (ROOT/'artifacts/pipeline.lock').stat().st_ino
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('A registered continuation process is already active')
    try:
        baseline_outputs()
        wait_for(ROOT/'artifacts/frozen-development-selection.json','wait_frozen_January_development')
        run([sys.executable,'tools/certify_model_checks.py'],ROOT,'independent_model_checks_before_formal')
        run([sys.executable,'tools/validate_formal_results.py','--phase','development'],ROOT,'independent_development_validation')
        run([sys.executable,'tools/run_incremental_experiments.py','--phase','annual','--workers',str(workers)],ROOT,'registered_334day_replays')
        run([sys.executable,'tools/validate_formal_results.py'],ROOT,'independent_formal_validation')
        run([sys.executable,'tools/compare_incremental_results.py'],ROOT,'paired_bills_and_block_bootstrap')
        run([sys.executable,'tools/certify_model_checks.py'],ROOT,'independent_model_checks_after_formal')
        run([sys.executable,'tools/evaluate_adoption.py'],ROOT,'frozen_challenger_adoption_gate')
        run([sys.executable,'tools/make_figures.py'],ROOT,'computed_figures')
        state('computed_results_ready','complete',remaining='Result-to-paper registry, final workbook export, manuscript results, final PDF rendering and independent final reviews remain author tasks.')
    except Exception as exc:
        state('stopped_on_error','failed',error=f'{type(exc).__name__}: {exc}');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8)
    p.add_argument('--inherited-lock-fd',type=int);args=p.parse_args();main(args.workers,args.inherited_lock_fd)
