"""Finish dependent local calculations as their already-running inputs arrive.

This is a one-shot computation pipeline, not a recurring automation. It never
marks review accepted; final independent review is a separate stage.
"""
import time,json,sys,subprocess
from concurrent.futures import ProcessPoolExecutor
from run_comparison import ROOT,BASE,CANDIDATES,dump
from convex_aggregation import run_kind

def main():
    tick=time.perf_counter();remaining={'q3','q4_2','q4_3'};pending={};done=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        while remaining or pending:
            for kind in sorted(remaining.copy()):
                if all((ROOT/f'artifacts/annual/{kind}_{c}.json').exists() for c in CANDIDATES):
                    pending[pool.submit(run_kind,kind)]=kind;remaining.remove(kind)
                    print('START_CONVEX',kind,flush=True)
            for future,kind in list(pending.items()):
                if future.done():
                    result=future.result();done.append(result);del pending[future]
                    print('DONE_CONVEX',json.dumps(result),flush=True)
            if remaining or pending:time.sleep(5)
    required=['execution-annual.json','execution-diagnostic.json','q2_convex.json','execution-grid641.json']
    while not all((ROOT/'artifacts'/name).exists() for name in required):time.sleep(5)
    commands=[([sys.executable,str(ROOT/'src/validate_extension.py'),'--phase','annual'],ROOT),
              ([sys.executable,str(ROOT/'src/summarize.py')],ROOT),
              (['/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node','src/build_workbooks.mjs'],ROOT),
              (['/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3','src/verify_workbooks.py'],ROOT)]
    logs=[]
    for command,cwd in commands:
        print('RUN',command,flush=True);t=time.perf_counter()
        result=subprocess.run(command,cwd=cwd,check=True)
        logs.append({'command':command,'cwd':str(cwd),'exit_code':result.returncode,'runtime_seconds':time.perf_counter()-t})
    dump(ROOT/'artifacts/pipeline-ready.json',{'status':'ready_for_independent_review','exit_code':0,
         'command':'python3 '+' '.join(sys.argv),'runtime_seconds':time.perf_counter()-tick,'convex_runs':done,'commands':logs})
    print('READY_FOR_INDEPENDENT_REVIEW',flush=True)

if __name__=='__main__':main()
