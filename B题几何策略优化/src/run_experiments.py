"""Frozen paired experiments; raw seeds are never selected from final results."""
import argparse,concurrent.futures,hashlib,json,platform,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(job):
 name,start,n,stress,method=job;cmd=[str(R/'bin/benchmark_final'),str(R/'results'/f'{name}.csv'),str(start),str(n),str(stress),str(method),str(method)]
 begin=time.time();out=subprocess.run(cmd,capture_output=True,text=True);record={'command':cmd,'exit_code':out.returncode,'started_unix':begin,'runtime_s':time.time()-begin,'stdout':out.stdout,'stderr':out.stderr,'output':f'results/{name}.csv'}
 if out.returncode==0:record['output_sha256']=sha(R/record['output'])
 (R/'artifacts'/f'run-{name}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(name,out.returncode,round(record['runtime_s'],2),flush=True)
 if out.returncode:raise RuntimeError(record)
 return record
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--suite',choices=['iid','stress','dev'],required=True);p.add_argument('--workers',type=int,default=3);a=p.parse_args()
 if a.suite=='iid':jobs=[(f'iid{m}',2610001,200,0,m) for m in [56,78,84]]
 elif a.suite=='stress':jobs=[(f'stress{s}_{m}',2620001+(s-1)*10000,40,s,m) for s in range(1,6) for m in [56,84]]
 else:jobs=[(f'dev{m}_replay',2110001,40,0,m) for m in [56,78,84]]
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:records=list(pool.map(run,jobs))
 (R/'artifacts'/f'execution-{a.suite}.json').write_text(json.dumps({'suite':a.suite,'environment':platform.platform(),'binary_sha256':sha(R/'bin/benchmark_final'),'records':records},ensure_ascii=False,indent=2))
