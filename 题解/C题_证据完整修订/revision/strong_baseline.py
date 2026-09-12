from pathlib import Path
import json,sys,hashlib,concurrent.futures
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'C题_跨日随机控制'
sys.path.insert(0,str(BASE/'src'))
from run import simulate
OUT=ROOT/'revision/results';OUT.mkdir(exist_ok=True)
def one(kind):
 p=BASE/f'artifacts/annual/{kind}_cross_baseline'
 a=dict(np.load(p.with_suffix('.npz')));m=json.loads(p.with_suffix('.json').read_text());data=dict(np.load(BASE/'artifacts/data.npz'));selection=json.loads((BASE/'artifacts/forecast-selection.json').read_text())
 days=a['days'][-2:].tolist();initial=float(a['state'][-2,0]);kw={k:m['configuration'][k] for k in ['count','horizon_days','tail_scale','grid']}
 free,fm=simulate(data,selection,days,kind,'cross_baseline',initial=initial,**kw)
 differences={k:float(np.max(np.abs(free[k]-a[k][-2:]))) for k in ['q','r','c','d','emergency','spill','state']};assert max(differences.values())<1e-5
 fixed,fx=simulate(data,selection,days,kind,'cross_baseline',initial=initial,final=6000,**kw)
 combined={k:np.concatenate([v[:-2],fixed[k]]) for k,v in a.items()}
 assert np.max(np.abs(combined['state'][1:,0]-combined['state'][:-1,-1]))<1e-6
 bill=(combined['price']*(combined['q']+1.5*np.maximum(combined['r']-combined['q'],0)-.5*np.maximum(combined['q']-combined['r'],0)+5*combined['emergency'])).sum(1)
 main=dict(np.load(BASE/f'artifacts/global-terminal/{kind}_markov_mpc.npz'));mb=(main['price']*(main['q']+1.5*np.maximum(main['r']-main['q'],0)-.5*np.maximum(main['q']-main['r'],0)+5*main['emergency'])).sum(1)
 diff=bill-mb;rng=np.random.default_rng(20260911);starts=rng.integers(0,328,size=(10000,48));indices=(starts[:,:,None]+np.arange(7)).reshape(10000,-1)[:,:334];ci=np.quantile(diff[indices].sum(1),[.025,.975])
 np.savez_compressed(OUT/f'{kind}_cross_baseline_fixed.npz',**combined)
 result={'kind':kind,'baseline_total':float(bill.sum()),'main_total':float(mb.sum()),'saving':float(diff.sum()),'saving_pct':float(diff.sum()/bill.sum()*100),'saving_95ci':ci.tolist(),'positive_days':int((diff>1e-6).sum()),'negative_days':int((diff < -1e-6).sum()),'prefix_replay_differences':differences,'suffix_validation':fx['validation'],'baseline_daily':bill.tolist(),'main_daily':mb.tolist(),'source_sha256':hashlib.sha256(p.with_suffix('.npz').read_bytes()).hexdigest(),'prefix_scope':'Exact suffix reuse for unchanged two-midnight greedy model; free suffix reproduced before fixed suffix.'}
 (OUT/f'{kind}_strong_baseline.json').write_text(json.dumps(result,indent=2)+'\n');return result
def export_pairs(rows):
 import csv
 with (OUT/'daily-paired-costs.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['kind','date','baseline_yuan','main_yuan','saving_yuan'])
  for row in rows:
   dates=np.load(OUT/f"{row['kind']}_cross_baseline_fixed.npz")['dates']
   for date,b,m in zip(dates,row['baseline_daily'],row['main_daily']):w.writerow([row['kind'],str(date),b,m,b-m])
if __name__=='__main__':
 if '--export-only' in sys.argv:r=json.loads((OUT/'strong-baseline.json').read_text())
 else:
  with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:r=list(pool.map(one,['q2','q3','q4_2','q4_3']))
  (OUT/'strong-baseline.json').write_text(json.dumps(r,indent=2)+'\n')
 export_pairs(r)
