"""Causal Jan25-31 paired sensitivity. Original src remains immutable.
Only replace convex delivered-contract epigraph from max(1.5R-.5Q,.5R+.5Q)
to max(1.5R-.5Q,-.5R+1.5Q); same physics, forecasts, tail and feedback.
"""
from pathlib import Path
import sys,json,inspect,hashlib,time
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'C题_跨日随机控制/vendor'))
sys.path.insert(0,str(ROOT/'src'))
import run,control,dispatch
OUT=ROOT/'revision/numeric-audit';OUT.mkdir(exist_ok=True)
def worker(job):
 kind,alternative=job
 source=inspect.getsource(control.affine_plan)
 replacements={'.5*R+.5*Q-F':'-.5*R+1.5*Q-F','-.5*q0-.5*r0':'-1.5*q0+.5*r0','.5*rs+.5*qs':'-.5*rs+1.5*qs'}
 if alternative:
  for old,new in replacements.items():
   assert source.count(old)==1,(old,source.count(old))
   source=source.replace(old,new)
  namespace=dict(control.__dict__);exec(compile(source,'billing_epigraph_variant','exec'),namespace)
  run.affine_plan=namespace['affine_plan']
  run.settlement=lambda q,r,em,p:dispatch.settlement(q,r,em,p,refund=False)
 else:run.affine_plan=control.affine_plan;run.settlement=dispatch.settlement
 data=dict(np.load(ROOT/'artifacts/data.npz'));selection=json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
 a,m=run.simulate(data,selection,list(range(24,31)),kind,'markov_mpc',final=6000.)
 q,r,em,p=[a[k] for k in ['q','r','emergency','price']]
 bill=p*(q+1.5*np.maximum(r-q,0)+(.5 if alternative else -.5)*np.maximum(q-r,0)+5*em)
 assert abs(bill.sum()-m['totals']['total_cost'])<1e-6
 m['billing_variant']='additive_penalty' if alternative else 'replacement_refund';m['transformed_planner_sha256']=hashlib.sha256(source.encode()).hexdigest()
 m['retreated_kwh']=float(np.maximum(q-r,0).sum());m['billing_recompute_gap']=float(abs(bill.sum()-m['totals']['total_cost']))
 stem=OUT/f'jan_{kind}_{m["billing_variant"]}'
 np.savez_compressed(str(stem)+'.npz',**a);Path(str(stem)+'.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 return {'kind':kind,'variant':m['billing_variant'],'total_cost':m['totals']['total_cost'],'retreated_kwh':m['retreated_kwh'],'validation':m['validation'],'runtime_seconds':m['runtime_seconds']}
if __name__=='__main__':
 results=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for fut in as_completed([pool.submit(worker,j) for j in [(k,a) for k in ['q3','q4_3'] for a in [False,True]]]):
   r=fut.result();results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
 (OUT/'january-billing-replan.json').write_text(json.dumps({'status':'PASS','results':results,'scope':'January 25-31 only; unchanged pre-existing parameters; no formal-period tuning. Not full-year optimal values.','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
