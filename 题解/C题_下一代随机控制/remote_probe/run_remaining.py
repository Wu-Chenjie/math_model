"""Isolated Windows annual queue; frozen policies, separate platform results."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,time,traceback,concurrent.futures,platform,msvcrt
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from nextgen_run import run_case
import numpy as np
import highspy,scipy
import importlib.util
OUT=ROOT/'artifacts/remote-formal';OUT.mkdir(parents=True,exist_ok=True)

def dump(p,v):
    t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(t,p)

def verify():
    for name,digest in json.loads((ROOT/'transfer-manifest.json').read_text(encoding='utf-8')).items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert np.__version__=='2.4.1' and scipy.__version__=='1.17.1' and highspy.Highs().version()=='1.15.1'

def one(job):
    stem=OUT/job['id'];lock=open(stem.with_suffix('.lock'),'a+b');lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        verify()
        existing=stem.with_suffix('.audit.json')
        if existing.exists() and json.loads(existing.read_text(encoding='utf-8'))['passed']:
            m=json.loads(stem.with_suffix('.json').read_text(encoding='utf-8'))
            a=json.loads(existing.read_text(encoding='utf-8'))
            assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in a['output_hashes'].items())
            return {'id':job['id'],'status':'already_complete'}
        dump(stem.with_suffix('.execution.json'),{'status':'running','pid':os.getpid(),'start_time':time.time(),'job':job})
        result=run_case(job['kind'],job['configuration'],31,365,stem)
        verify()
        spec=importlib.util.spec_from_file_location('independent',ROOT/'review/check_nextgen_physics.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        data=dict(np.load(ROOT/'artifacts/data.npz',allow_pickle=False));arrays=dict(np.load(stem.with_suffix('.npz'),allow_pickle=False));metrics=json.loads(stem.with_suffix('.json').read_text(encoding='utf-8'))
        checked=audit.audit_arrays(data,arrays,metrics,development=False)
        checked['output_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (stem.with_suffix('.json'),stem.with_suffix('.npz'))}
        dump(existing,checked)
        assert checked['passed'],checked.get('errors')
        outcome={'id':job['id'],'status':'complete','result':result,'finished_at':time.time()}
        dump(stem.with_suffix('.execution.json'),outcome);return outcome
    except Exception:
        err={'id':job['id'],'status':'failed','traceback':traceback.format_exc()};dump(stem.with_suffix('.execution.json'),err);return err
    finally:lock.close()

def main():
    guard=open(OUT/'queue.lock','a+b');guard.seek(0);msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
    verify();jobs=json.loads((ROOT/'remaining-jobs.json').read_text(encoding='utf-8'))['jobs']
    state={'status':'running','pid':os.getpid(),'workers':8,'total_jobs':len(jobs),'started_at':time.time(),'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'highs':highspy.Highs().version(),'comparability':'Separate Windows results; short-replay action differences unresolved. No automatic adoption or mixing with Mac baseline.','results':[]}
    dump(OUT/'queue-status.json',state)
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(one,j):j['id'] for j in jobs}
        for f in concurrent.futures.as_completed(futures):
            try:r=f.result()
            except Exception:r={'id':futures[f],'status':'failed','traceback':traceback.format_exc()}
            state['results'].append(r);dump(OUT/'queue-status.json',state);print(json.dumps(r,ensure_ascii=True),flush=True)
    state['status']='complete' if all(r['status'] in ('complete','already_complete') for r in state['results']) else 'completed_with_failures'
    state['finished_at']=time.time();dump(OUT/'queue-status.json',state)
if __name__=='__main__':main()
