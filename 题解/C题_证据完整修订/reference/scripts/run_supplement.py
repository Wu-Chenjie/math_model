"""Supplemental terminal-matched audit; imports frozen main code unchanged."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import sys,json,time,hashlib
import numpy as np
O=Path(__file__).resolve().parents[1];R=O.parent.parent/'C题_跨日随机控制'
sys.path.insert(0,str(R/'src'))
import run,control,forecasting,validate

def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def worker(job):
 mode,kind,candidate=job;start=time.perf_counter();data=dict(np.load(R/'artifacts/data.npz'));selection=json.loads((R/'artifacts/forecast-selection.json').read_text())
 gain=[];original=control.lp_solve
 def measured(obj,A,b,bounds,solver='ipm'):
  sol=original(obj,A,b,bounds,solver);ids=[i for i,v in enumerate(bounds) if v==(-10,10)]
  x=sol.x[ids];gain.append({'count':len(ids),'near_bound':int((abs(x)>=10-1e-6).sum()),'max_abs':float(abs(x).max()) if len(x) else 0})
  return sol
 control.lp_solve=measured
 if mode=='development':
  arrays,m=run.simulate(data,selection,list(range(24,31)),kind,candidate,final=6000.)
  target=O/'artifacts/development_fixed'/f'{kind}_{candidate}'
  m['audit_design']={'original_selection':'January free-terminal; retained as historical selection record','supplement':'January fixed-terminal retrospective consistency check; February-December not used to choose','initial':6000,'final':6000}
 elif mode=='ablation':
  name=candidate;allowed={'0only':[0],'without6':[0,2,3],'without12':[0,1,3],'without18':[0,1,2]}[name]
  forecasting.forecast_as_of=validate.forecast_with_releases(allowed)
  source=R/f'artifacts/experiments/annual_pv_{name}';a=dict(np.load(str(source)+'.npz'));initial=float(a['state'][-2,0]);days=a['days'][-2:].tolist()
  free,fm=run.simulate(data,selection,days,'q3','markov_mpc',initial=initial)
  diffs={k:float(abs(free[k]-a[k][-2:]).max()) for k in ['q','r','c','d','emergency','spill','state']}
  assert max(diffs.values())<1e-5,diffs
  fixed,m=run.simulate(data,selection,days,'q3','markov_mpc',initial=initial,final=6000.)
  arrays={k:np.concatenate([v[:-2],fixed[k]]) for k,v in a.items()}
  m['prefix_reuse']={'days':332,'original_trajectory':str(source.relative_to(R))+'.npz','sha256':sha(Path(str(source)+'.npz')),'free_suffix_max_differences':diffs,'proof_scope':'unchanged two-midnight policy, no terminal-visible plan before Dec30 and inactive earlier terminal reachability'}
  target=O/'artifacts/ablation_fixed'/f'q3_{name}'
 else:raise ValueError(mode)
 m['gain_probe']={'scope':mode,'lp_calls':len(gain),'gain_entries':sum(x['count'] for x in gain),'near_bound_entries':sum(x['near_bound'] for x in gain),'max_abs':max((x['max_abs'] for x in gain),default=0),'method':'read returned primal values for bounds exactly [-10,10], no objective/constraints/actions altered'}
 m['execution']={'job':job,'exit_code':0,'runtime_seconds':time.perf_counter()-start,'script_sha256':sha(Path(__file__)),'source_hashes':{p.name:sha(p) for p in (R/'src').glob('*.py')}}
 target.parent.mkdir(exist_ok=True,parents=True);np.savez_compressed(str(target)+'.npz',**arrays);dump(Path(str(target)+'.json'),m)
 return {'job':job,'runtime_seconds':m['execution']['runtime_seconds'],'cost':m['totals']['total_cost'],'gain_probe':m['gain_probe']}

def main():
 jobs=[('development',k,c) for k in run.KINDS for c in ['cross_baseline','affine_mpc','markov_mpc','sddp_mpc','sddp_markov']]+[('ablation','q3',x) for x in ['0only','without6','without12','without18']]
 started=time.perf_counter();done=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for f in as_completed([pool.submit(worker,j) for j in jobs]):
   r=f.result();done.append(r);print(json.dumps(r,ensure_ascii=False),flush=True);dump(O/'artifacts/supplement-progress.json',{'completed':len(done),'total':len(jobs),'results':done})
 dump(O/'artifacts/supplement-execution.json',{'command':'python3 theory_revision/scripts/run_supplement.py','exit_code':0,'runtime_seconds':time.perf_counter()-started,'results':done})
if __name__=='__main__':main()
