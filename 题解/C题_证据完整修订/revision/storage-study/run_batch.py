"""Run eight separate-process capacity cases; keep source and existing primary results intact."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,os,time,json,sys
R=Path(__file__).resolve().parent

def job(kind,width):
    log=R/'results'/f'{kind}_W{width}.log';start=time.perf_counter();env=dict(os.environ)
    for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS']:env[name]='1'
    args=[sys.executable,str(R/'run_capacity.py'),'--kind',kind,'--width',str(width)]
    with log.open('w') as f:p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env)
    return {'kind':kind,'width':width,'exit_code':p.returncode,'runtime_seconds':time.perf_counter()-start,'log':str(log.name),'command':args}
if __name__=='__main__':
    records=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures=[ex.submit(job,k,w) for k in ['q2','q3','q4_2','q4_3'] for w in [0,4800]]
        for fut in as_completed(futures):
            r=fut.result();records.append(r);print(json.dumps(r),flush=True)
            (R/'batch-status.json').write_text(json.dumps(records,indent=2))
    assert all(r['exit_code']==0 for r in records)
