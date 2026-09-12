"""January-only post-review sensitivity, NOT retrospective parameter selection.
Original modules stay unchanged. The LP wrapper changes only gain bounds and
records columns identically absent from BOTH constraint matrix and objective.
"""
from pathlib import Path
import sys,json,time,hashlib
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1].parent/'C题_跨日随机控制'
sys.path[:0]=[str(BASE/'src'),str(BASE/'vendor')]
import run,control

def job(kind,bound):
 start=time.perf_counter();records=[];raw=control.lp_solve
 def measured(obj,A,b,bounds,solver='ipm'):
  cols=[j for j,v in enumerate(bounds) if v==(-10,10)];new=list(bounds)
  for j in cols:new[j]=(-bound,bound)
  sol=raw(obj,A,b,new,solver);Ac=A.tocsc(copy=True);Ac.eliminate_zeros()
  null=(np.diff(Ac.indptr)[cols]==0)&(np.asarray(obj)[cols]==0)
  vals=sol.x[cols];touch=abs(vals)>=bound-1e-6
  records.append({'gain_count':len(cols),'touch_count':int(touch.sum()),'zero_columns':int(null.sum()),'zero_columns_touch':int((null&touch).sum()),'active_columns':int((~null).sum()),'active_touch':int((~null&touch).sum()),'zero_column_indices':[int(j) for j,n in zip(cols,null) if n],'active_touch_indices':[int(j) for j,n in zip(cols,~null&touch) if n],'gain_values':vals.tolist()})
  return sol
 control.lp_solve=measured
 data=dict(np.load(BASE/'artifacts/data.npz'));selection=json.loads((BASE/'artifacts/forecast-selection.json').read_text())
 a,m=run.simulate(data,selection,list(range(24,31)),kind,'markov_mpc',count=7,horizon_days=2,tail_scale=1.,grid=321,final=6000.)
 summary={k:sum(r[k] for r in records) for k in ['gain_count','touch_count','zero_columns','zero_columns_touch','active_columns','active_touch']}
 summary['active_touch_fraction']=summary['active_touch']/summary['active_columns'];summary['raw_touch_fraction']=summary['touch_count']/summary['gain_count']
 out={'kind':kind,'gain_bound':bound,'dates':'2025-01-25 through 2025-01-31','initial':6000,'final':6000,'status':'POST_REVIEW_DIAGNOSTIC_NOT_MODEL_SELECTION','total_cost':m['totals']['total_cost'],'totals':m['totals'],'validation':m['validation'],'column_statistics':summary,'records':records,'daily':m['daily'],'runtime_seconds':time.perf_counter()-start,'source_sha256':{f:hashlib.sha256((BASE/'src'/f).read_bytes()).hexdigest() for f in ['control.py','run.py','forecasting.py']}}
 np.savez_compressed(HERE/f'gain-{kind}-{bound}.npz',**a)
 (HERE/f'gain-{kind}-{bound}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));return {k:v for k,v in out.items() if k not in ['records','daily','source_sha256']}
if __name__=='__main__':
 results=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  fs=[pool.submit(job,k,b) for k in ['q2','q3','q4_2','q4_3'] for b in [10,20]]
  for f in as_completed(fs):r=f.result();results.append(r);print(json.dumps(r),flush=True)
 pairs=[]
 for k in ['q2','q3','q4_2','q4_3']:
  a=next(r for r in results if r['kind']==k and r['gain_bound']==10);b=next(r for r in results if r['kind']==k and r['gain_bound']==20)
  pairs.append({'kind':k,'cost_gain10':a['total_cost'],'cost_gain20':b['total_cost'],'saving_gain20':a['total_cost']-b['total_cost'],'saving_percent':100*(a['total_cost']-b['total_cost'])/a['total_cost'],'gain10_active_touch':a['column_statistics'],'gain20_active_touch':b['column_statistics']})
 (HERE/'gain-summary.json').write_text(json.dumps({'status':'PASS_JANUARY_DIAGNOSTIC','notes':'Frozen historical predictor selected on January15-31. This is a retrospective development-window diagnostic; no claim that January selection was known at January25. No formal-result-based tuning or adoption. Zero column means exactly zero coefficient in objective and all constraints, verified in assembled LP. Annual raw bound ratios cannot be corrected from old scalar counts without replay; do not extrapolate these January ratios to whole year.','comparisons':pairs,'results':results},indent=2))
