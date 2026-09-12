"""Diagnostic only: test whether reported equal current-day contracts are unique."""
from pathlib import Path
import sys,json
import numpy as np
from scipy.sparse import vstack,csr_matrix
HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1].parent/'C题_跨日随机控制'
sys.path[:0]=[str(BASE/'src'),str(BASE/'vendor')]
import control
from forecasting import scenarios
D=dict(np.load(BASE/'artifacts/data.npz'));S=json.loads((BASE/'artifacts/forecast-selection.json').read_text());raw=control.lp_solve;records=[]
for kind in ['q3','q4_3']:
 a=dict(np.load(BASE/f'artifacts/global-terminal/{kind}_markov_mpc.npz'))
 for date,slots in [('2025-06-21',[108,120]),('2025-09-23',[72,84])]:
  ix=int(np.flatnonzero(a['dates']==date)[0]);day=int(a['days'][ix]);now=day*144;end=(day+2)*144;net,p,meta=scenarios(D,S,now,end,True,kind=='q4_3',count=7);captured={}
  def capture(obj,A,b,bounds,solver='ipm'):
   sol=raw(obj,A,b,bounds,solver);captured.update(obj=obj,A=A,b=b,bounds=bounds,sol=sol);return sol
  control.lp_solve=capture
  plan=control.affine_plan(net,p,now,float(a['state'][ix,0]),None,True,True,float(np.quantile(p[:,-144:],.25))/.9)
  gap=float(abs(a['q'][ix]-plan['q'][:144]).max());assert gap<1e-5
  obj=captured['obj'];primary=captured['sol'].fun;tol=1e-7;A=vstack([captured['A'],csr_matrix(obj[None,:])]);b=np.r_[captured['b'],primary+tol];secondary=np.zeros_like(obj);secondary[slots[0]]=1;secondary[slots[1]]=-1
  lo=raw(secondary,A,b,captured['bounds']);hi=raw(-secondary,A,b,captured['bounds']);records.append({'kind':kind,'date':date,'slots':slots,'contract_replay_max_abs':gap,'original_pair_difference':float(plan['q'][slots[0]]-plan['q'][slots[1]]),'optimal_difference_min':float(secondary@lo.x),'optimal_difference_max':float(secondary@hi.x),'objective_allowance_yuan':tol,'primary_objective_yuan':primary,'min_solution_primary_increase':float(obj@lo.x-primary),'max_solution_primary_increase':float(obj@hi.x-primary),'primary_gain_columns_for_current_q':'identically zero by release/asof restriction; current q has independent per-slot intercept','interpretation':'secondary LP over near-optimal face, not physical re-execution or adopted strategy'})
(HERE/'duplicate-lp-probe.json').write_text(json.dumps({'records':records},indent=2));print(json.dumps(records))
