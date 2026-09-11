"""Execute unchanged accepted sources in a fresh sibling workspace.

Only independent calculation lanes overlap. No upgraded models run here.
The caller must inspect comparison and independent audit before advancing.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys,time,json,hashlib,threading,os
ROOT=Path(__file__).resolve().parents[1]
REPLAY=ROOT.parent/'C题_下一代基线复现'
BUNDLE=Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies')
PY=str(BUNDLE/'python/bin/python3');NODE=str(BUNDLE/'node/bin/node')
LOG=ROOT/'artifacts/baseline-reproduction-execution.json'
records=[];lock=threading.Lock();started=time.perf_counter()
def save():
    LOG.write_text(json.dumps({'status':'running','elapsed_seconds':time.perf_counter()-started,'records':records},ensure_ascii=False,indent=2)+'\n')
def run(args,exe=sys.executable):
    name=('_'.join(args).replace('/','_').replace(' ','_'))[:180]
    out=ROOT/'artifacts/baseline-logs'/f'{name}.log';out.parent.mkdir(exist_ok=True)
    begin=time.perf_counter();command=[exe,*args]
    with lock: print('START',command,flush=True)
    with out.open('w') as f:
        proc=subprocess.run(command,cwd=REPLAY,stdout=f,stderr=subprocess.STDOUT)
    item={'command':command,'cwd':str(REPLAY),'exit_code':proc.returncode,'runtime_seconds':time.perf_counter()-begin,'log':str(out.relative_to(ROOT))}
    with lock:records.append(item);save();print('END',item,flush=True)
    if proc.returncode:raise RuntimeError(f'Baseline execution failed: {out}')
def train_lane():
    run(['src/run.py','--phase','train','--iterations','500','--workers','4'])
    for d in [1,2]:run(['src/run.py','--phase','train','--cutoffs','14','334','--tail-days',str(d),'--iterations','500','--workers','4'])
    run(['src/sddp.py','--cutoff','31','--days','1','--iterations','500','--output','tails/q2_31_D1.json'])
    run(['src/run.py','--phase','calibrate_sddp_v2','--start','24','--stop','31','--candidates','sddp_mpc','sddp_markov','--workers','4'])
    run(['src/run.py','--phase','annual_sddp','--start','31','--stop','365','--candidates','sddp_markov','--workers','4'])
def main_lane():
    run(['src/run.py','--phase','calibrate','--start','24','--stop','31','--candidates','cross_baseline','affine_mpc','markov_mpc','--workers','4'])
    run(['src/run.py','--phase','calibrate_closed','--start','24','--stop','31','--candidates','closed_baseline','closed_affine','--workers','4'])
    run(['src/run.py','--phase','annual','--candidates','closed_baseline','cross_baseline','affine_mpc','markov_mpc','closed_affine','--workers','4'])
    run(['src/validate.py','--scope','short','--workers','4'])
    run(['src/validate.py','--scope','annual-releases','--workers','4'])
    run(['src/check_terminal.py'])
def main():
    frozen=json.loads((ROOT/'artifacts/baseline-freeze.json').read_text())
    for name,expected in frozen['file_hashes'].items():
        if name.startswith('src/') and name.endswith(('.py','.mjs')):
            assert hashlib.sha256((REPLAY/name).read_bytes()).hexdigest()==expected,name
    run(['src/prepare_data.py'],PY)
    run(['src/run.py','--phase','initialize'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(train_lane),pool.submit(main_lane)]
        for task in tasks:task.result()
    run(['src/select_model.py'])
    for p in ['check-sddp','check-controllers','check-global-oracle','check-v2-boundaries']:
        run([f'review/{p}.py'])
    run(['review/check-production.py','--require-complete'])
    run(['src/finish.py']);run(['src/export_results.py'])
    # Output rebuilding and rendering is separate from numerical replay. The
    # artifact marker is executed by the orchestrator before first authoring.
    save()
    print('NUMERICAL BASELINE REPLAY FINISHED. Export/review/comparison gate still required.',flush=True)
if __name__=='__main__':main()
