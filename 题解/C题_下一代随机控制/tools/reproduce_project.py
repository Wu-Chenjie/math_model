"""One command for reproducible baseline, frozen experiments and result exports."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import fcntl
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
REPLAY=ROOT.parent/'C题_下一代基线复现'
RUNTIME=Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime')


def run(*command,cwd=ROOT,pass_fds=()):
    result=subprocess.run([str(x) for x in command],cwd=cwd,pass_fds=pass_fds)
    if result.returncode:raise SystemExit(result.returncode)


def execute_locked(workers,rerun_year,lock_fd):
    manifest_path=ROOT/'modeling-manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        manifest['project'].update(status='in_progress',stage='reproducing')
        manifest['pending']=['Complete this reproduction and revalidate final artifact-bound reviews before closing the ledger.']
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    if not (REPLAY/'src/run.py').exists():
        REPLAY.mkdir(exist_ok=True)
        for name in ('src','review','vendor','inputs'):
            shutil.copytree(ROOT/'baseline_frozen'/name,REPLAY/name,dirs_exist_ok=True)
        for source in (ROOT/'baseline_frozen').iterdir():
            if source.is_file():shutil.copy2(source,REPLAY/source.name)
        shutil.copytree(ROOT/'baseline_frozen/paper',REPLAY/'paper',dirs_exist_ok=True)
        (REPLAY/'figures').mkdir(exist_ok=True)
        (REPLAY/'artifacts').mkdir(exist_ok=True)
    if not (REPLAY/'artifacts/execution-export.json').exists():
        run(sys.executable,'tools/reproduce_baseline.py')
    if not (ROOT/'artifacts/frozen-development-selection.json').exists():
        run(sys.executable,'tools/run_incremental_experiments.py','--phase','development','--workers',workers)
    run(sys.executable,'tools/summarize_development.py')
    if rerun_year and (ROOT/'artifacts/formal').exists():
        archive=ROOT/'artifacts/replay-history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        archive.mkdir(parents=True)
        shutil.move(ROOT/'artifacts/formal',archive/'formal')
        for name in ('execution-formal.json','formal-validation.json','incremental-comparisons.json','model-adoption.json'):
            p=ROOT/'artifacts'/name
            if p.exists():shutil.move(p,archive/name)
    run(sys.executable,'tools/continue_registered_pipeline.py','--workers',workers,
        '--inherited-lock-fd',lock_fd,pass_fds=(lock_fd,))
    run(sys.executable,'tools/match_information_ablation_endpoints.py')
    run(sys.executable,'review/check_information_terminal_independent.py')
    run(sys.executable,'tools/export_selected.py')
    link=ROOT/'node_modules'
    if not link.exists():link.symlink_to(RUNTIME/'dependencies/node/node_modules',target_is_directory=True)
    (ROOT/'artifacts/previews').mkdir(exist_ok=True)
    run(RUNTIME/'dependencies/node/bin/node','tools/build_workbooks.mjs')
    run(RUNTIME/'dependencies/python/bin/python3','tools/verify_workbooks.py')
    # These final stages are called once their authored, reviewed builders exist.
    for script in ('build_paper_results.py','build_paper.py'):
        if not (ROOT/'tools'/script).exists():raise RuntimeError(f'Numerical reproduction complete; missing final authoring stage {script}')
        run(sys.executable,'tools/'+script)


def main(workers,rerun_year):
    # Keep the same open-file-description lock across parent/child dispatch and
    # all export stages. A second wrapper or standalone continuation must fail.
    with (ROOT/'artifacts/pipeline.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('The local pipeline is already running; inspect artifacts/pipeline-execution.json')
        execute_locked(workers,rerun_year,lock.fileno())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8)
    p.add_argument('--rerun-year',action='store_true',help='Preserve old formal outputs in replay-history and rerun every frozen annual candidate.')
    args=p.parse_args();main(args.workers,args.rerun_year)
