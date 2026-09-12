"""Independent periodic-inventory LP and two billing interpretations.
Run: python3 revision/q1_and_billing.py ; immutable source results read only.
"""
from pathlib import Path
import json, hashlib, csv, platform, sys
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'revision/numeric-audit';OUT.mkdir(exist_ok=True)
BASE=ROOT.parent/'C题_跨日随机控制'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
data=dict(np.load(ROOT/'artifacts/data.npz'));T=144; eta=.9; power=5000/6
# Independent variable layout q[144], c[144], d[144], E[145].
net=(data['day_load']-data['day_pv'])/6;p=data['day_price'];n=4*T+1
obj=np.r_[p,np.zeros(3*T+1)]
ri=[];ci=[];vv=[]
for t in range(T):
 for c,v in [(T+t,-eta),(2*T+t,1/eta),(3*T+t,-1),(3*T+t+1,1)]:ri.append(t);ci.append(c);vv.append(v)
ri.extend([T,T]);ci.extend([3*T,4*T]);vv.extend([-1,1])
Aeq=coo_matrix((vv,(ri,ci)),shape=(T+1,n)).tocsr()
Aub=coo_matrix((np.tile([-1,1,-1],T),(np.repeat(np.arange(T),3),np.array([[t,T+t,2*T+t] for t in range(T)]).ravel())),shape=(T,n)).tocsr()
resall=[]
for fixed in [6000,None]:
 bounds=[(0,None)]*T+[(0,power)]*(2*T)+[(1200,10800)]*(T+1)
 if fixed is not None:bounds[3*T]=(fixed,fixed)
 z=linprog(obj,A_ub=Aub,b_ub=-net,A_eq=Aeq,b_eq=np.zeros(T+1),bounds=bounds,method='highs',options={'dual_feasibility_tolerance':1e-8,'primal_feasibility_tolerance':1e-8})
 assert z.success,z.message
 q=z.x[:T];c=z.x[T:2*T].copy();d=z.x[2*T:3*T].copy();E=z.x[3*T:]
 remove=np.minimum(c,d/eta**2);c-=remove;d-=eta**2*remove
 spill=q+d-c-net
 dual=-net@z.ineqlin.marginals+sum(lo*m for (lo,hi),m in zip(bounds,z.lower.marginals) if lo is not None)+sum(hi*m for (lo,hi),m in zip(bounds,z.upper.marginals) if hi is not None)
 check={'balance_max_abs':float(abs(q+d-c-spill-net).max()),'soc_recurrence_max_abs':float(abs(np.diff(E)-eta*c+d/eta).max()),'cyclic_gap':float(abs(E[-1]-E[0])),'power_max_kw':float(max(c.max(),d.max())*6),'soc_min':float(E.min()),'soc_max':float(E.max()),'simultaneous_charge_discharge_max':float(np.minimum(c,d).max()),'spill_min':float(spill.min()),'duality_gap':float(abs(z.fun-dual))}
 assert max(check[k] for k in ['balance_max_abs','soc_recurrence_max_abs','cyclic_gap','duality_gap'])<1e-6
 assert check['soc_min']>=1200-1e-6 and check['soc_max']<=10800+1e-6 and check['power_max_kw']<=5000+1e-6 and check['spill_min']>=-1e-6
 tag='fixed6000' if fixed else 'free_cyclic'
 np.savez_compressed(OUT/f'q1_{tag}.npz',q=q,c=c,d=d,state=E,spill=spill)
 resall.append({'model':tag,'total_cost':float(p@q),'initial_inventory':float(E[0]),'final_inventory':float(E[-1]),'purchase_energy':float(q.sum()),'validation':check})
resall[1]['saving']=resall[0]['total_cost']-resall[1]['total_cost'];resall[1]['saving_percent']=100*resall[1]['saving']/resall[0]['total_cost']
assert abs(resall[0]['total_cost']-json.loads((ROOT/'artifacts/q1.json').read_text())['expected_cost'])<1e-6
rows=[];daily=[];inputs={}
for endpoint in ['free','fixed6000']:
 for kind in ['q2','q3','q4_2','q4_3']:
  f=BASE/'artifacts'/('annual' if endpoint=='free' else 'global-terminal')/f'{kind}_markov_mpc.npz';a=dict(np.load(f));inputs[str(f)]=sha(f)
  q,r,em,price=[a[k] for k in ['q','r','emergency','price']];red=np.maximum(q-r,0);inc=np.maximum(r-q,0)
  old=price*(q+1.5*inc-.5*red+5*em);new=price*(q+1.5*inc+.5*red+5*em)
  # Causal shadow-policy construction: retain q, battery and emergency; refuse returns and spill surplus.
  rn=np.maximum(q,r);sn=a['spill']+red
  dominated_free=price*(q+1.5*np.maximum(rn-q,0)+5*em)
  balance=rn+em+a['d']-a['c']-sn-(data['load'][a['days']]-data['pv'][a['days']])/6
  assert abs(balance).max()<1e-6 and np.min(price)>=0
  assert abs((new-old-price*red).max())<1e-6
  row={'endpoint':endpoint,'kind':kind,'original_bill':float(old.sum()),'alternative_bill_same_trajectory':float(new.sum()),'bill_increase':float((new-old).sum()),'bill_increase_percent':float(100*(new-old).sum()/old.sum()),'retreated_kwh':float(red.sum()),'no_return_shadow_policy_bill':float(dominated_free.sum()),'shadow_bill_saving_vs_repriced':float((new-dominated_free).sum()),'shadow_balance_max_abs':float(abs(balance).max()),'initial_inventory':float(a['state'][0,0]),'final_inventory':float(a['state'][-1,-1]),'min_price':float(price.min())}
  rows.append(row)
  for i,date in enumerate(a['dates']):daily.append({'endpoint':endpoint,'kind':kind,'date':str(date),'original_bill':float(old[i].sum()),'alternative_bill_same_trajectory':float(new[i].sum()),'bill_increase':float((new[i]-old[i]).sum()),'no_return_shadow_policy_bill':float(dominated_free[i].sum())})
for name,rs in [('billing-summary',rows),('billing-daily',daily)]:
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
report={'status':'PASS','q1':resall,'billing':rows,'interpretation':'Alternative billing reprices identical trajectories; shadow no-return policy is feasible but neither is claimed optimal under alternative billing.','input_sha256':{str(ROOT/'artifacts/data.npz'):sha(ROOT/'artifacts/data.npz'),**inputs},'script_sha256':sha(__file__),'python':sys.version,'platform':platform.platform()}
(OUT/'q1-billing-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'q1':resall,'billing':rows},ensure_ascii=False,indent=2))
