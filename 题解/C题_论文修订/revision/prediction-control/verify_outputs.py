"""Direct array physics and bill recomputation, without importing model code."""
from pathlib import Path
import numpy as np,json,hashlib,platform,sys
H=Path(__file__).resolve().parent
B=H.parents[1].parent/'C题_跨日随机控制';D=np.load(B/'artifacts/data.npz')
records=[]
for stem in ['january-causal-greedy']+[f'gain-{k}-{g}' for k in ['q2','q3','q4_2','q4_3'] for g in [10,20]]:
 a=np.load(H/(stem+'.npz'));m=json.loads((H/(stem+'.json')).read_text());warm=stem.startswith('january');days=np.arange(31) if warm else a['days']
 y=(D['load'][days]-D['pv'][days])/6
 residuals={'bus':float(abs(a['r']+a['emergency']+a['d']-a['c']-a['spill']-y).max()),'soc':float(abs(np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9).max()),'midnight':float(abs(a['state'][1:,0]-a['state'][:-1,-1]).max()),'terminal':float(abs(a['state'][-1,-1]-6000)),'initial':float(abs(a['state'][0,0]-6000)),'simultaneous':float(np.minimum(a['c'],a['d']).max()),'lower':float(max(0,1200-a['state'].min())),'upper':float(max(0,a['state'].max()-10800)),'power':float(max(0,max(a['c'].max(),a['d'].max())-5000/6))}
 prices=[('fixed',np.broadcast_to(D['day_price'],a['q'].shape)),('variable',D['price'][days])] if warm else [('total',D['price'][days] if 'q4' in stem else np.broadcast_to(D['day_price'],a['q'].shape))]
 for name,p in prices:
  cost=np.sum(p*(a['q']+1.5*np.maximum(a['r']-a['q'],0)-.5*np.maximum(a['q']-a['r'],0)+5*a['emergency']))
  target=m['cost_'+name] if warm else m['total_cost'];residuals['bill_'+name]=float(abs(cost-target))
 assert max(residuals.values())<1e-5,(stem,residuals)
 records.append({'output':stem,'checks':residuals,'status':'PASS'})
files=[p for p in H.iterdir() if p.suffix in ['.py','.json','.npz','.csv','.pdf','.png','.tex'] and p.name not in ['verification.json','evidence-manifest.json']]
(H/'verification.json').write_text(json.dumps({'status':'PASS_ARRAY_RECOMPUTATION','independence':'Separate algebraic validator; author-generated, not a substitute for external independent review.','cases':records},indent=2))
(H/'evidence-manifest.json').write_text(json.dumps({'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'deterministic':True,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},indent=2))
print('9 output trajectories and bills PASS')
