"""Falsification and physical checks of new causal controllers."""
from pathlib import Path
import json,time,argparse
import numpy as np
from run_comparison import ROOT,BASE,CANDIDATES,KINDS,simulate,dump
from forecasting import scenario_data
from dispatch import solve
from controllers import affine_plan

def leakage():
    data=dict(np.load(BASE/'artifacts/data.npz'));fc=dict(np.load(BASE/'artifacts/forecasts.npz'))
    results=[];day=100;cut=78
    altered={k:v.copy() for k,v in data.items()};changedfc={k:v.copy() for k,v in fc.items()}
    altered['load'][day,cut:]+=7000;altered['pv'][day,cut:]*=.2
    altered['price'][day,:]*=4 # Actual same-day prices are scoring-only throughout.
    for key in ['load','pv','price']:
        altered[key][day+1:]*=3
    for key in changedfc:
        changedfc[key][day,3,:]+=2000
        changedfc[key][day+1:]+=3000
    for candidate in CANDIDATES:
        a,_=simulate(data,fc,[day],'q4_3',candidate)
        b,_=simulate(altered,changedfc,[day],'q4_3',candidate)
        diffs={k:float(np.max(abs(a[k][:,:cut]-b[k][:,:cut]))) for k in ['q','r','c','d','emergency']}
        # Entire contracts already issued at0/6/12 must be invariant, not just prefix.
        diffs['issued_contract_snapshots']=float(np.nanmax(abs(a['releases'][:,:3]-b['releases'][:,:3])))
        assert max(diffs.values())<1e-5,(candidate,diffs)
        results.append({'name':'future_mutation_'+candidate,'status':'pass','cut_slot':cut,'max_differences':diffs})
    dominance=[]
    for kind in KINDS:
        official,variable,_=KINDS[kind]
        for k in range(4):
            n,p,_=scenario_data(data,fc,day,k,official,variable)
            common=solve(n,p);affine=affine_plan(n,p,start=k*36)
            difference=affine['expected_cost']-common['expected_cost']
            assert difference<.1,(kind,k,difference)
            dominance.append({'kind':kind,'release':k,'affine_minus_common_expected_cost':difference})
    dump(ROOT/'artifacts/falsification.json',{'status':'pass','checks':results,
         'affine_contains_zero_gain_common_policy':dominance,
         'scope':'LP dominance is in-sample within declared classes; not out-of-sample dominance.'})

def annual():
    data=dict(np.load(BASE/'artifacts/data.npz'));results=[];reproduction={}
    for kind in KINDS:
        old=dict(np.load(BASE/f'artifacts/{kind}.npz'));new=dict(np.load(ROOT/f'artifacts/annual/{kind}_baseline.npz'))
        diff={k:float(np.max(abs(old[k]-new[k]))) for k in ['q','r','c','d','state','emergency','spill']}
        assert max(diff.values())<1e-5,(kind,diff)
        reproduction[kind]=diff
        for candidate in list(CANDIDATES)+['common_saa_mpc','common_sdp','convex28']:
            phase='diagnostic' if candidate in ['common_saa_mpc','common_sdp'] else 'annual'
            stem=ROOT/(f'artifacts/{kind}_convex' if candidate=='convex28' else f'artifacts/{phase}/{kind}_{candidate}')
            a=dict(np.load(stem.with_suffix('.npz')))
            m=json.loads(stem.with_suffix('.json').read_text())
            net=(data['load'][a['days']]-data['pv'][a['days']])/6
            error=float(abs(a['r']+a['emergency']+a['d']-a['c']-a['spill']-net).max())
            costs=np.sum(a['price']*(a['q']+1.5*np.maximum(a['r']-a['q'],0)-.5*np.maximum(a['q']-a['r'],0)+5*a['emergency']),axis=1)
            stated=np.array([x['total_cost'] for x in m['daily']])
            diffcost=float(abs(costs-stated).max())
            assert error<1e-6 and diffcost<1e-5
            recurrence=float(abs(np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9).max())
            nonnegative=min(float(a[k].min()) for k in ['q','r','c','d','emergency','spill'])
            assert recurrence<1e-6 and nonnegative>=-1e-6
            assert a['state'].min()>=1200-1e-6 and a['state'].max()<=10800+1e-6
            assert max(a['c'].max(),a['d'].max())<=5000/6+1e-6
            assert abs(a['state'][:,[0,-1]]-6000).max()<1e-6
            assert np.minimum(a['c'],a['d']).max()<1e-6
            assert abs(costs.sum()-m['totals']['total_cost'])<1e-4
            # Executed contract must be precisely the latest legally released plan.
            reconstructed=a['releases'][:,0,:].copy()
            assert np.isfinite(reconstructed).all()
            release_gap=float(abs(a['q']-reconstructed).max())
            for k in range(1,4):
                snap=a['releases'][:,k,:]
                assert np.isnan(snap[:,:k*36]).all()
                finite=np.isfinite(snap);reconstructed[finite]=snap[finite]
            release_gap=max(release_gap,float(abs(a['r']-reconstructed).max()))
            assert release_gap<1e-6
            results.append({'name':kind+'_'+candidate,'status':'pass','balance_max_abs':error,'daily_cost_max_abs':diffcost,
                            **m['validation'],'independent_soc_recurrence_max_abs':recurrence,
                            'released_contract_reconstruction_max_abs':release_gap})
    dump(ROOT/'artifacts/annual-validation.json',{'status':'pass','checks':results,'baseline_reproduction':reproduction})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['leakage','annual'],default='leakage');args=p.parse_args()
    start=time.perf_counter();(leakage if args.phase=='leakage' else annual)()
    print(json.dumps({'phase':args.phase,'exit_code':0,'runtime_seconds':time.perf_counter()-start}))
