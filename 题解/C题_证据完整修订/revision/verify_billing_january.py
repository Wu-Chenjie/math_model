"""Independent validation of stored January variant outputs, no planner imports."""
from pathlib import Path
import numpy as np,json,hashlib,csv
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'revision/numeric-audit';data=np.load(ROOT/'artifacts/data.npz'); rows=[];files={}
for k in ['q3','q4_3']:
 for variant in ['replacement_refund','additive_penalty']:
  p=O/f'jan_{k}_{variant}.npz';a=dict(np.load(p));m=json.loads(p.with_suffix('.json').read_text());files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  q,r,em,px,c,d,s,E=[a[t] for t in ['q','r','emergency','price','c','d','spill','state']]
  bill=px*(q+1.5*np.maximum(r-q,0)+(-.5 if variant=='replacement_refund' else .5)*np.maximum(q-r,0)+5*em)
  phys=max(float(abs(r+em+d-c-s-(data['load'][a['days']]-data['pv'][a['days']])/6).max()),float(abs(np.diff(E,axis=1)-.9*c+d/.9).max()),float(abs(E[1:,0]-E[:-1,-1]).max()))
  assert phys<1e-6 and abs(E[0,0]-6000)<1e-6 and abs(E[-1,-1]-6000)<1e-6
  assert E.min()>=1200-1e-6 and E.max()<=10800+1e-6 and np.minimum(c,d).max()<1e-6 and max(c.max(),d.max())*6<=5000+1e-6
  assert abs(bill.sum()-m['totals']['total_cost'])<1e-6
  assert np.array_equal(a['days'],np.arange(24,31))
  assert np.min([q.min(),r.min(),em.min(),s.min(),c.min(),d.min()])>=-1e-6
  # Before a release, all effective deliveries must equal the already published latest valid contract.
  for i in range(7):
   assert abs(a['releases'][i,0]-q[i]).max()<1e-6
   for j in range(4):
    assert abs(a['releases'][i,j,j*36:(j+1)*36]-r[i,j*36:(j+1)*36]).max()<1e-6
  repriced=px*(q+1.5*np.maximum(r-q,0)+.5*np.maximum(q-r,0)+5*em)
  rows.append({'kind':k,'variant':variant,'original_meter_bill':float(bill.sum()),'new_meter_bill':float(repriced.sum()),'retreated_kwh':float(np.maximum(q-r,0).sum()),'max_physics_error':phys})
for k in ['q3','q4_3']:
 old,new=[next(r for r in rows if r['kind']==k and r['variant']==v) for v in ['replacement_refund','additive_penalty']]
 new['improvement_vs_old_policy_new_meter']=old['new_meter_bill']-new['new_meter_bill']
 new['new_bill_increase_vs_old_bill']=new['new_meter_bill']-old['original_meter_bill']
 new['new_bill_increase_percent']=100*new['new_bill_increase_vs_old_bill']/old['original_meter_bill']
r={'status':'PASS','rows':rows,'input_sha256':files,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'revision/billing_january_replan.py',ROOT/'artifacts/data.npz',ROOT/'artifacts/forecast-selection.json',*sorted((ROOT/'src').glob('*.py'))]},'scope':'Independent recomputation of outputs; January development diagnostic, not an out-of-sample performance claim.'}
(O/'january-billing-independent.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rows,ensure_ascii=False,indent=2))
