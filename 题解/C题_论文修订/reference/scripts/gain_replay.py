"""Re-solve frozen main planning LPs at saved actual states; no policy change."""
from pathlib import Path
import sys,json,time
import numpy as np
from concurrent.futures import ProcessPoolExecutor
O=Path(__file__).resolve().parents[1];R=O.parent.parent/'C题_跨日随机控制'
sys.path.insert(0,str(R/'src'))
import control
from forecasting import scenarios
def job(kind):
 data=dict(np.load(R/'artifacts/data.npz'));selection=json.loads((R/'artifacts/forecast-selection.json').read_text())
 a=dict(np.load(R/f'artifacts/global-terminal/{kind}_markov_mpc.npz'))
 official=kind in ['q3','q4_3'];variable=kind.startswith('q4');records=[];raw=control.lp_solve;probe=[]
 def measured(*args,**kw):
  sol=raw(*args,**kw);bounds=kw.get('bounds',args[3] if len(args)>3 else None)
  ix=[j for j,b in enumerate(bounds) if b[0]==-10 and b[1]==10]
  g=sol.x[ix];probe.append((len(g),int(np.sum(abs(g)>=10-1e-6)),float(max(abs(g),default=0))));return sol
 control.lp_solve=measured
 for i,day in enumerate(a['days']):
  for t in [0,36,72,108]:
   now=int(day)*144+t;end=min((int(day)+2)*144,365*144)
   net,prices,meta=scenarios(data,selection,now,end,official,variable,count=7)
   base=None if t==0 else np.r_[a['q'][i,t:],np.zeros(end-(int(day)+1)*144)]
   terminal=6000. if end==365*144 else None
   lam=0. if terminal is not None else float(np.quantile(prices[:,-min(144,len(prices[0])):],.25))/.9
   plan=control.affine_plan(net,prices,now,float(a['state'][i,t]),base,official,True,lam,terminal,None,daily_closed=False)
   expected=a['q'][i] if t==0 else a['releases'][i,t//36,t:]
   found=plan['q'][:144] if t==0 else plan['r'][:144-t]
   gap=float(np.max(abs(expected-found))) if t==0 or official else 0.
   assert gap<1e-5,(kind,day,t,gap)
   n,b,m=probe[-1];records.append({'date':str(a['dates'][i]),'slot':t,'gain_entries':n,'near_bound_entries':b,'max_abs':m,'contract_replay_max_abs':gap})
 result={'kind':kind,'scope':'all 1336 planning LPs on saved fixed-terminal main trajectory','records':records,'gain_entries':sum(r['gain_entries'] for r in records),'near_bound_entries':sum(r['near_bound_entries'] for r in records),'max_contract_replay_error':max(r['contract_replay_max_abs'] for r in records)}
 result['near_bound_fraction']=result['near_bound_entries']/result['gain_entries']
 (O/f'artifacts/gain-{kind}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return {k:v for k,v in result.items() if k!='records'}
if __name__=='__main__':
 with ProcessPoolExecutor(max_workers=4) as ex:
  for r in ex.map(job,['q2','q3','q4_2','q4_3']):print(json.dumps(r),flush=True)
