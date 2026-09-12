"""Exact prefix reuse for this two-midnight MPC's global terminal comparison."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,sys,time,hashlib
import numpy as np
from run import ROOT,simulate,dump

def worker(job):
    kind,candidate=job;folder='annual_sddp' if candidate.startswith('sddp') else 'annual'
    path=ROOT/f'artifacts/{folder}/{kind}_{candidate}'
    a=dict(np.load(str(path)+'.npz'));m=json.loads(Path(str(path)+'.json').read_text())
    assert np.array_equal(a['days'],np.arange(31,365))
    assert np.array_equal(a['dates'].astype('datetime64[D]'),np.arange(np.datetime64('2025-02-01'),np.datetime64('2026-01-01')))
    assert candidate in ['affine_mpc','markov_mpc'],'Prefix proof is scoped to the linear-tail controllers.'
    assert m['configuration']['horizon_days']==2 and m['configuration']['final'] is None
    data=dict(np.load(ROOT/'artifacts/data.npz'));selection=json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
    idx=len(a['days'])-2;days=a['days'][idx:].tolist();initial=float(a['state'][idx,0])
    kwargs={k:m['configuration'][k] for k in ['count','horizon_days','tail_scale','grid']}
    free,fm=simulate(data,selection,days,kind,candidate,initial=initial,**kwargs)
    diffs={k:float(np.max(np.abs(free[k]-a[k][idx:]))) for k in ['q','r','c','d','emergency','spill','state']}
    assert max(diffs.values())<1e-5,diffs
    fixed,xm=simulate(data,selection,days,kind,candidate,initial=initial,final=6000.,**kwargs)
    combined={k:np.concatenate([v[:idx],fixed[k]],axis=0) for k,v in a.items()}
    assert np.max(np.abs(combined['state'][1:,0]-combined['state'][:-1,-1]))<1e-6
    q,r,em,p=[combined[k] for k in ['q','r','emergency','price']]
    bill=p*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0)+5*em)
    total=float(bill.sum());prefix=float(sum(z['total_cost'] for z in m['daily'][:idx]))
    assert abs(total-prefix-xm['totals']['total_cost'])<1e-5
    out=ROOT/'artifacts/global-terminal';out.mkdir(exist_ok=True)
    np.savez_compressed(out/f'{kind}_{candidate}.npz',**combined)
    result={'kind':kind,'candidate':candidate,'free_total_cost':m['totals']['total_cost'],'fixed_total_cost':total,
      'terminal_constraint_increment':total-m['totals']['total_cost'],'prefix_days':idx,'replayed_days':days,
      'suffix_initial_inventory':initial,'free_suffix_replay_differences':diffs,'free_final_inventory':fm['validation']['final_inventory'],
      'fixed_final_inventory':xm['validation']['final_inventory'],'fixed_suffix_validation':xm['validation'],
      'fixed_suffix_decisions':xm['decisions'],'fixed_suffix_configuration':xm['configuration'],'fixed_suffix_daily':xm['daily'],
      'source_trajectory_sha256':hashlib.sha256(Path(str(path)+'.npz').read_bytes()).hexdigest(),
      'source_metrics_sha256':hashlib.sha256(Path(str(path)+'.json').read_bytes()).hexdigest(),
      'prefix_proof':'Before Dec30, this fixed two-midnight controller never includes the real year-end in its planning horizon; its physical terminal-reachability interval is also inactive. At the reused midnight all old deliveries are complete and forecast history is identical. This is an exact reuse for this implemented policy, not a proof for an arbitrary long-horizon optimal policy.'}
    dump(out/f'{kind}_{candidate}.json',result);return result

def main():
    start=time.perf_counter();jobs=[(k,c) for k in ['q2','q3','q4_2','q4_3'] for c in ['affine_mpc','markov_mpc']]
    results=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            r=f.result();results.append(r);print(json.dumps({k:r[k] for k in ['kind','candidate','fixed_total_cost','terminal_constraint_increment']}),flush=True)
    dump(ROOT/'artifacts/global-terminal.json',{'results':results,'execution':{'command':'python3 '+' '.join(sys.argv),'exit_code':0,'runtime_seconds':time.perf_counter()-start}})

if __name__=='__main__':main()
