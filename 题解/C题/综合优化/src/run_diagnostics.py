"""Additional structural controls; excluded from the predeclared six-expert selector."""
import time,json,sys
from concurrent.futures import ProcessPoolExecutor,as_completed
import run_comparison as run

EXTRA={'common_saa_mpc':('common','saa_mpc'),'common_sdp':('common','sdp')}

def job(args):
    run.CANDIDATES.update(EXTRA)
    return run.worker(args)

def main():
    tick=time.perf_counter()
    jobs=[('diagnostic',k,c,list(range(31,365)),321) for c in EXTRA for k in run.KINDS]
    results=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(job,x) for x in jobs]):
            r=f.result();results.append(r);print(json.dumps(r),flush=True)
    run.dump(run.ROOT/'artifacts/execution-diagnostic.json',{'command':'python3 '+' '.join(sys.argv),
        'exit_code':0,'runtime_seconds':time.perf_counter()-tick,'results':results,
        'scope':'Structural controls added during annual execution to isolate the upper planner; not used to refit six-expert selection or claimed as a new untouched holdout.'})

if __name__=='__main__':main()
