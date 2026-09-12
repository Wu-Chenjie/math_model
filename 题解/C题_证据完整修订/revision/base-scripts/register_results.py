"""Independently recompute fixed-terminal bills, feasibility and paired statistics."""
from pathlib import Path
import json,sys,shutil,hashlib
import numpy as np
O=Path(__file__).resolve().parents[1];R=O.parent
KINDS=['q2','q3','q4_2','q4_3'];data=dict(np.load(R/'artifacts/data.npz'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def read(p):return dict(np.load(p))
def metrics(a):
 q,r,e,p=(a[k] for k in ['q','r','emergency','price'])
 parts={'planned_cost':(p*q).sum(1),'increase_cost':(1.5*p*np.maximum(r-q,0)).sum(1),'reduction_net_cost':(-.5*p*np.maximum(q-r,0)).sum(1),'emergency_cost':(5*p*e).sum(1)}
 parts['total_cost']=sum(parts.values());parts['emergency_energy']=e.sum(1);parts['spill_energy']=a['spill'].sum(1);parts['projection_count']=(a['projection']>1e-6).sum(1)
 bal=r+e+a['d']-a['c']-a['spill']-(data['load'][a['days']]-data['pv'][a['days']])/6
 val={'balance_max_abs':float(abs(bal).max()),'soc_recurrence_max_abs':float(abs(np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9).max()),'midnight_jump_max_abs':float(abs(a['state'][1:,0]-a['state'][:-1,-1]).max()),'soc_min':float(a['state'].min()),'soc_max':float(a['state'].max()),'power_max_kw':float(6*max(a['c'].max(),a['d'].max())),'simultaneous_max':float(np.minimum(a['c'],a['d']).max()),'initial_inventory':float(a['state'][0,0]),'final_inventory':float(a['state'][-1,-1])}
 assert max(val[k] for k in ['balance_max_abs','soc_recurrence_max_abs','midnight_jump_max_abs','simultaneous_max'])<1e-5
 assert val['soc_min']>=1200-1e-5 and val['soc_max']<=10800+1e-5 and val['power_max_kw']<=5000+1e-5
 assert abs(val['initial_inventory']-6000)<1e-5 and abs(val['final_inventory']-6000)<1e-5
 return {'daily':[{'date':str(d),**{k:float(v[i]) for k,v in parts.items()},'ending_inventory':float(a['state'][i,-1])} for i,d in enumerate(a['dates'])],'totals':{k:float(v.sum()) for k,v in parts.items()},'validation':val}
def stats(delta,dates,seed):
 n=len(delta);res={'cumulative_yuan':float(delta.sum()),'mean_yuan':float(delta.mean()),'positive_days':int((delta>1e-8).sum()),'negative_days':int((delta< -1e-8).sum()),'zero_days':int((abs(delta)<=1e-8).sum()),'lag1_correlation':float(np.corrcoef(delta[:-1],delta[1:])[0,1]),'bootstrap':{}}
 for b in [3,7,14]:
  rng=np.random.default_rng(np.random.SeedSequence([seed,b]));starts=rng.integers(0,n-b+1,size=(10000,int(np.ceil(n/b))))
  ids=(starts[:,:,None]+np.arange(b)).reshape(10000,-1)[:,:n];means=delta[ids].mean(1);ci=np.quantile(means,[.025,.975])
  res['bootstrap'][str(b)]={'mean_95_percentile_yuan':ci.tolist(),'cumulative_95_percentile_yuan':(ci*n).tolist(),'replicates':10000,'seed_sequence':[seed,b],'method':'overlapping noncircular moving blocks, concatenate then truncate to 334'}
 months=np.array([str(d)[:7] for d in dates]);res['monthly_yuan']={m:float(delta[months==m].sum()) for m in np.unique(months)};res['positive_months']=sum(v>1e-8 for v in res['monthly_yuan'].values());return res
def main():
 claims={'source_commit':'59af4e054e079f18484889b6bc899bd83cc1527f','evaluation':['2025-02-01','2025-12-31'],'days':334,'initial_final_kwh':[6000,6000],'claim_classes':{'A':'mathematical result under stated assumptions','B':'model-specific optimum or bound','C':'finite-sample numerical finding','D':'scope or extrapolation boundary'},'models':{},'ablation':{},'development':{},'sensitivity':{}}
 oracle=json.loads((R/'review/global-oracle.json').read_text())['results']
 for ki,k in enumerate(KINDS):
  a=read(R/f'artifacts/global-terminal/{k}_markov_mpc.npz');m=metrics(a);np.savez_compressed(O/f'artifacts/{k}.npz',**a);dump(O/f'artifacts/{k}.json',m)
  b=metrics(read(R/f'artifacts/annual/{k}_closed_baseline.npz'));af=metrics(read(R/f'artifacts/global-terminal/{k}_affine_mpc.npz'));closed=metrics(read(R/f'artifacts/annual/{k}_closed_affine.npz'))
  dc=np.array([x['total_cost'] for x in b['daily']])-np.array([x['total_cost'] for x in m['daily']]);bound=oracle['variable_fixed6000' if k.startswith('q4') else 'fixed_fixed6000']['objective_cost_yuan']
  claims['models'][k]={'class':'C','main':m['totals'],'validation':m['validation'],'baseline_daily_greedy':b['totals'],'cross_affine':af['totals'],'closed_affine':closed['totals'],'cross_saving_yuan':closed['totals']['total_cost']-af['totals']['total_cost'],'feedback_saving_yuan':af['totals']['total_cost']-m['totals']['total_cost'],'paired_vs_daily_greedy':stats(dc,a['dates'],202609110+ki),'perfect_information_cost_yuan':bound,'optimistic_distance_percent':100*(m['totals']['total_cost']-bound)/bound}
  vals={c:json.loads((O/f'artifacts/development_fixed/{k}_{c}.json').read_text())['totals']['total_cost'] for c in ['cross_baseline','affine_mpc','markov_mpc','sddp_mpc','sddp_markov']};chosen=min(vals,key=vals.get)
  if vals['markov_mpc']<=min(vals.values())*1.0001:chosen='markov_mpc'
  claims['development'][k]={'costs_yuan':vals,'selected':chosen,'retrospective_terminal_consistency_check':True}
 for name in ['0only','without6','without12','without18']:
  m=metrics(read(O/f'artifacts/ablation_fixed/q3_{name}.npz'));claims['ablation'][name]={'class':'C','full_fixed_totals':m['totals'],'extra_cost_yuan':m['totals']['total_cost']-claims['models']['q3']['main']['total_cost'],'validation':m['validation']}
 for name in ['reference','grid161','grid641','scenarios14','horizon3','tail_zero','tail_double','stress_load_up_pv_down']:
  p=R/f'artifacts/experiments/{name}.json'
  if p.exists():
   m=json.loads(p.read_text());claims['sensitivity'][name]={'source':str(p.relative_to(R)),'configuration':m['configuration'],'totals':m['totals'],'validation':m['validation']}
 claims['q1']=json.loads((R/'artifacts/q1.json').read_text())
 claims['warmup']=json.loads((R/'artifacts/summary.json').read_text())['warmup']
 claims['gain_diagnostic']={k:{kk:vv for kk,vv in json.loads((O/f'artifacts/gain-{k}.json').read_text()).items() if kk!='records'} for k in KINDS if (O/f'artifacts/gain-{k}.json').exists()}
 claims['gain_scope_note']='All bounded gain variables, including structurally unused or degenerate columns. Boundary frequency is not effective feedback saturation.'
 claims['provenance']={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((R/'artifacts/global-terminal').glob('*.npz'))+list((O/'artifacts/ablation_fixed').glob('*.npz'))}
 dump(O/'artifacts/result-claims.json',claims)
 for name in ['data.npz','q1.npz','q1.json','selection.json']:shutil.copy2(R/'artifacts'/name,O/'artifacts'/name)
 source=(R/'src/export_results.py').read_text();start=source.index('    for kind,candidate in selection');end=source.index('    data=dict',start)
 source=source[:start]+source[end:];source=source.replace('主策略SOC跨日连续、年末库存自由；一次全局期末6000仅作对照。','主策略SOC跨日连续，真实年末固定6000；全部CSV和工作簿采用同一固定终点轨迹。')
 (O/'scripts/export_fixed.py').write_text(source)
 print(json.dumps({k:{'cost':v['main']['total_cost'],'cross':v['cross_saving_yuan'],'feedback':v['feedback_saving_yuan'],'bootstrap':v['paired_vs_daily_greedy']} for k,v in claims['models'].items()},ensure_ascii=False))
if __name__=='__main__':main()
