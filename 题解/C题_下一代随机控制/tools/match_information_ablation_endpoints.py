"""Same-endpoint information ablations via the verified two-midnight prefix.

The original full334-day release-restricted runs are reproduced first. A free
last-two-day rerun must match their stored prefix continuation exactly before
replacing it with a hard-final6000 continuation. No parameter is selected here.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
REPLAY=ROOT.parent/'C题_下一代基线复现'
sys.path.insert(0,str(REPLAY/'src'))
from run import simulate
import forecasting
from validate import forecast_with_releases


def worker(name):
    started=time.perf_counter()
    source=REPLAY/f'artifacts/experiments/annual_pv_{name}'
    with np.load(source.with_suffix('.npz'),allow_pickle=False) as a:arrays=dict(a)
    m=json.loads(source.with_suffix('.json').read_text());cfg=m['configuration']
    assert np.array_equal(arrays['days'],np.arange(31,365))
    assert cfg['horizon_days']==2 and cfg['final'] is None and not cfg['closed_daily']
    allowed=m['validation_design']['releases']
    data=dict(np.load(REPLAY/'artifacts/data.npz'))
    selection=json.loads((REPLAY/'artifacts/forecast-selection.json').read_text())
    forecasting.forecast_as_of=forecast_with_releases(allowed)
    cut=332;initial=float(arrays['state'][cut,0]);days=arrays['days'][cut:].tolist()
    kwargs={k:cfg[k] for k in ('count','horizon_days','tail_scale','grid')}
    free,_=simulate(data,selection,days,'q3','markov_mpc',initial=initial,**kwargs)
    gaps={}
    for k,original in arrays.items():
        expected=original[cut:];actual=free[k]
        assert expected.shape==actual.shape,k
        if np.issubdtype(expected.dtype,np.number):
            assert np.array_equal(np.isnan(expected),np.isnan(actual)),k
            finite=np.isfinite(expected);assert np.array_equal(finite,np.isfinite(actual)),k
            gaps[k]=float(np.max(np.abs(actual[finite]-expected[finite]),initial=0))
        else:
            assert np.array_equal(expected,actual),k;gaps[k]=0.
    assert max(gaps.values())<1e-5,gaps
    fixed,fixed_m=simulate(data,selection,days,'q3','markov_mpc',initial=initial,final=6000.,**kwargs)
    combined={k:np.concatenate((v[:cut],fixed[k]),axis=0) for k,v in arrays.items()}
    assert np.max(np.abs(combined['state'][1:,0]-combined['state'][:-1,-1]))<1e-6
    daily=m['daily'][:cut]+fixed_m['daily'];totals={k:float(sum(d[k] for d in daily)) for k in m['totals']}
    q,r,e,p=(combined[k] for k in ('q','r','emergency','price'))
    bill=p*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0)+5*e)
    assert abs(float(bill.sum())-totals['total_cost'])<1e-5
    m.update(configuration={**cfg,'initial':6000.,'final':6000.},daily=daily,totals=totals,
             decisions=m['decisions'][:cut*4]+fixed_m['decisions'])
    E,c,d,spill=(combined[k] for k in ('state','c','d','spill'))
    net=(data['load'][31:]-data['pv'][31:])/6
    m['validation']={
        'balance_max_abs':float(np.abs(r+e+d-c-spill-net).max()),
        'soc_recurrence_max_abs':float(np.abs(np.diff(E,axis=1)-.9*c+d/.9).max()),
        'midnight_jump_max_abs':float(np.abs(E[1:,0]-E[:-1,-1]).max()),
        'soc_min':float(E.min()),'soc_max':float(E.max()),'power_max_kw':float(6*max(c.max(),d.max())),
        'simultaneous_max':float(np.minimum(c,d).max()),'initial_inventory':float(E[0,0]),'final_inventory':float(E[-1,-1]),
        'negative_energy_violation':float(max(0,-min(v.min() for v in (q,r,e,c,d,spill)))),
        'lp_violation_max':max(m['validation']['lp_violation_max'],fixed_m['validation']['lp_violation_max']),
        'lp_objective_recompute_gap':max(m['validation']['lp_objective_recompute_gap'],fixed_m['validation']['lp_objective_recompute_gap'])}
    m['suffix_reproduction_seconds']=time.perf_counter()-started
    m['prefix_reuse']={'full_run_source':str(source),'reused_days':cut,'replayed_days':days,
        'free_suffix_max_errors':gaps,'source_npz_sha256':hashlib.sha256(source.with_suffix('.npz').read_bytes()).hexdigest(),
        'proof_scope':'Unchanged two-midnight policy, zero old delivery at reused midnight, identical legal forecasts/history. BeforeDec30 trueyearend is outside planning and physical terminal reachability is inactive. Not a proof for arbitrary longH policies.'}
    out=ROOT/f'artifacts/information-terminal/q3_{name}';out.parent.mkdir(exist_ok=True)
    np.savez_compressed(out.with_suffix('.npz'),**combined)
    out.with_suffix('.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('independent_info_physics',ROOT/'review/check_nextgen_physics.py')
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    verification=auditor.audit_arrays(data,combined,m)
    assert verification['passed'],verification['errors']
    check=ROOT/f'review/information-terminal/{name}.json';check.parent.mkdir(exist_ok=True)
    verification.update(status='PASS',input_npz_sha256=hashlib.sha256(out.with_suffix('.npz').read_bytes()).hexdigest(),
        input_json_sha256=hashlib.sha256(out.with_suffix('.json').read_bytes()).hexdigest())
    check.write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
    return {'name':name,'total_cost_yuan':totals['total_cost'],'source':str(out.relative_to(ROOT)),
            'validation':str(check.relative_to(ROOT)),'validation_sha256':hashlib.sha256(check.read_bytes()).hexdigest()}


def main():
    assert json.loads((ROOT/'artifacts/baseline-reproduction-check.json').read_text())['status']=='PASS'
    start=time.perf_counter();rows=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(worker,n) for n in ('0only','without6','without12','without18')]):rows.append(f.result())
    record={'status':'complete','results':rows,'source':'Reproduced full334day original information ablations with exact terminal suffix replacement',
            'execution':{'command':sys.argv,'exit_code':0,'runtime_seconds':time.perf_counter()-start}}
    (ROOT/'artifacts/information-terminal-execution.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
