"""Independent usable-storage audit. Does not import or modify producer modules."""
from pathlib import Path
import argparse, csv, hashlib, json, sys, time
from datetime import datetime, timezone
import numpy as np

HERE=Path(__file__).resolve().parent
PAPER=HERE.parents[1]
BASE=PAPER.parent/'C题_跨日随机控制'
REFERENCE=PAPER/'revision/base-artifacts'
KINDS=('q2','q3','q4_2','q4_3')
TOL=1e-5

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
    tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    tmp.replace(p)
def now(): return datetime.now(timezone.utc).isoformat()
def current_hashes():
    return {'producer_sha256':sha(HERE/'run_capacity.py'),
        'source_hashes':{f:sha(BASE/'src'/f) for f in ('control.py','run.py','forecasting.py','dispatch.py')},
        'input_hashes':{f:sha(BASE/'artifacts'/f) for f in ('data.npz','forecast-selection.json')}}
def require_small(checks):
    for name,value in checks.items():
        assert np.isfinite(value) and value<TOL, (name,value)
def path_for(kind,width):
    return REFERENCE/f'{kind}.npz' if width==9600 else HERE/'results'/f'{kind}_W{width}.npz'

def bootstrap(delta,kind_index,pair_index):
    n=len(delta);b=7;reps=10000
    rng=np.random.default_rng(np.random.SeedSequence([20260912,kind_index,pair_index]))
    starts=rng.integers(0,n-b+1,size=(reps,(n+b-1)//b))
    indexes=(starts[:,:,None]+np.arange(b)).reshape(reps,-1)[:,:n]
    means=delta[indexes].mean(1);lo,hi=np.quantile(means,[.025,.975])
    return {'seed_sequence':[20260912,kind_index,pair_index],'block_days':b,'replicates':reps,
        'method':'overlapping noncircular moving blocks, concatenate and truncate to334',
        'daily_mean_ci95_yuan':[float(lo),float(hi)],'annual_ci95_yuan':[float(lo*n),float(hi*n)],
        'scope':'single-year paired time-stability diagnosis; no cross-year or exact-policy optimality guarantee'}

def run(snapshot,baseline_only=False):
    hashes=current_hashes()
    assert hashes==snapshot['hashes'], 'Producer/source/input changed since verifier observation snapshot'
    data=dict(np.load(BASE/'artifacts/data.npz'))
    assert sha(REFERENCE/'data.npz')==hashes['input_hashes']['data.npz']
    # Gate is exact identity of the eight stored numerical variables, not merely a printed report.
    suffix_checks={}
    for kind in KINDS:
        suffixpath=HERE/f'results/{kind}_W9600_suffix.npz'
        suffix=dict(np.load(suffixpath));origpath=BASE/f'artifacts/global-terminal/{kind}_markov_mpc.npz'
        orig=dict(np.load(origpath));suffixmeta=json.loads(suffixpath.with_suffix('.json').read_text())
        suffixdiff={k:float(np.max(abs(suffix[k]-orig[k][-2:]))) for k in ('q','r','c','d','emergency','spill','state','price')}
        assert max(suffixdiff.values())==0.,(kind,suffixdiff)
        assert max(suffixmeta['reference_suffix_max_abs'].values())==0.
        assert suffixmeta['execution']['source_hashes']==hashes['source_hashes']
        assert suffixmeta['execution']['input_hashes']==hashes['input_hashes']
        assert suffixmeta['execution']['script_sha256']==hashes['producer_sha256']
        suffix_checks[kind]={'eight_variables_exact_zero':suffixdiff,'npz_sha256':sha(suffixpath),
            'reference_sha256':sha(origpath),'producer_sha256':suffixmeta['execution']['script_sha256'],
            'producer_source_input_match_current':True}
    rows=[];runs={};pairs={};dailyrows=[]
    for kind in KINDS:
        runs[kind]={}
        for width in ((9600,) if baseline_only else (0,4800,9600)):
            path=path_for(kind,width);a=dict(np.load(path));meta=json.loads(path.with_suffix('.json').read_text())
            assert np.array_equal(a['days'],np.arange(31,365))
            assert np.array_equal(a['dates'].astype('datetime64[D]'),np.arange(np.datetime64('2025-02-01'),np.datetime64('2026-01-01')))
            for k in ('q','r','c','d','emergency','spill','price','projection'):
                assert a[k].shape==(334,144) and np.isfinite(a[k]).all(),(kind,width,k)
            E=a['state'];assert E.shape==(334,145) and np.isfinite(E).all()
            q,r,c,d,e,w,p=[a[k] for k in ('q','r','c','d','emergency','spill','price')]
            n=(data['load'][31:365]-data['pv'][31:365])/6
            truth=data['price'][31:365] if kind.startswith('q4') else np.broadcast_to(data['day_price'],p.shape)
            lo,hi=6000-width/2,6000+width/2
            delta=np.diff(E,axis=1)
            checks={'capacity_low_violation':float(max(0,lo-E.min())),
                'capacity_high_violation':float(max(0,E.max()-hi)),
                'initial_error':float(abs(E[0,0]-6000)),'final_error':float(abs(E[-1,-1]-6000)),
                'midnight_error':float(np.max(abs(E[:-1,-1]-E[1:,0]))),
                'recurrence_error':float(np.max(abs(delta-.9*c+d/.9))),
                'bus_balance_error':float(np.max(abs(r+e+d-c-w-n))),
                'negative_energy':float(max(0,-min(x.min() for x in (q,r,c,d,e,w)))),
                'power_violation_kwh':float(max(0,max(c.max(),d.max())-5000/6)),
                'simultaneous_charge_discharge_kwh':float(np.minimum(c,d).max()),
                'canonical_charge_error':float(np.max(abs(c-np.maximum(delta,0)/.9))),
                'canonical_discharge_error':float(np.max(abs(d-.9*np.maximum(-delta,0)))),
                'emergency_minimality_error':float(np.max(abs(e-np.maximum(n+c-d-r,0)))),
                'spill_error':float(np.max(abs(w-np.maximum(r+d-c-n,0)))),
                'price_source_error':float(np.max(abs(p-truth)))}
            remaining=np.arange(48095,-1,-1).reshape(334,144)
            checks['remaining_terminal_reachability']=float(max(0,np.max(6000-remaining*.9*(5000/6)-E[:,1:]),np.max(E[:,1:]-6000-remaining*(5000/6)/.9)))
            assert a['releases'].shape==(334,4,144)
            checks['original_release_error']=float(np.max(abs(a['releases'][:,0]-q)))
            if kind in ('q2','q4_2'):
                checks['no_revision_error']=float(np.max(abs(r-q)))
                assert np.isnan(a['releases'][:,1:]).all()
            else:
                for block in range(4):
                    start=block*36;stop=start+36
                    assert np.isfinite(a['releases'][:,block,start:]).all()
                    if block:assert np.isnan(a['releases'][:,block,:start]).all()
                    checks[f'final_contract_block{block}_error']=float(np.max(abs(r[:,start:stop]-a['releases'][:,block,start:stop])))
            if width==0:
                checks['zero_capacity_inventory_error']=float(np.max(abs(E-6000)))
                checks['zero_capacity_action_error']=float(max(c.max(),d.max()))
            parts={'planned_cost':p*q,'increase_cost':1.5*p*np.maximum(r-q,0),
                'reduction_net_cost':-.5*p*np.maximum(q-r,0),'emergency_cost':5*p*e}
            cash=sum(parts.values());daily=cash.sum(1)
            checks['bill_formula_equivalence']=float(np.max(abs(cash-p*(r+.5*abs(r-q)+5*e))))
            checks['reported_total_error']=float(abs(daily.sum()-meta['totals']['total_cost']))
            for k,v in parts.items():
                if k in meta['totals']:checks[k+'_reported_error']=float(abs(v.sum()-meta['totals'][k]))
            if width!=9600:
                ex=meta['execution'];assert ex['source_hashes']==hashes['source_hashes']
                assert ex['input_hashes']==hashes['input_hashes'] and ex['script_sha256']==hashes['producer_sha256']
                ce=meta['capacity_experiment'];assert ce['usable_width_kwh']==width
                assert ce['emin_kwh']==lo and ce['emax_kwh']==hi
                assert ce['grid_nodes']==(width//30+1 if width else 1)
                assert meta['configuration']['horizon_days']==2 and meta['configuration']['final']==6000
                assert meta['configuration']['count']==7 and meta['configuration']['tail_scale']==1
                for rec in meta['decisions']:assert rec['latest_training_target_exclusive']<=rec['as_of']
            require_small(checks)
            summary={'kind':kind,'usable_width_kwh':width,'total_cost_yuan':float(daily.sum()),
                **{k+'_yuan':float(v.sum()) for k,v in parts.items()},
                'charge_kwh':float(c.sum()),'discharge_kwh':float(d.sum()),'emergency_kwh':float(e.sum()),'spill_kwh':float(w.sum()),
                'soc_min_kwh':float(E.min()),'soc_max_kwh':float(E.max()),'soc_mean_kwh':float(E[:,:-1].mean()),
                'initial_kwh':float(E[0,0]),'final_kwh':float(E[-1,-1]),'maximum_power_kw':float(6*max(c.max(),d.max())),
                'endpoint_sample_count':48096,'endpoint_hit_tolerance_kwh':1e-6,
                'lower_endpoint_hits':int(np.sum(abs(E[:,1:]-lo)<=1e-6)),
                'upper_endpoint_hits':int(np.sum(abs(E[:,1:]-hi)<=1e-6)),
                'lower_endpoint_hit_fraction':float(np.mean(abs(E[:,1:]-lo)<=1e-6)),
                'upper_endpoint_hit_fraction':float(np.mean(abs(E[:,1:]-hi)<=1e-6))}
            rows.append(summary)
            for ix,date in enumerate(a['dates']):dailyrows.append({'kind':kind,'usable_width_kwh':width,'date':str(date),'total_cost_yuan':float(daily[ix]),**{k+'_yuan':float(v[ix].sum()) for k,v in parts.items()}})
            runs[kind][str(width)]={'summary':summary,'checks':checks,'daily_cost_yuan':daily.tolist(),
                'trajectory_path':str(path),'trajectory_sha256':sha(path),'metrics_sha256':sha(path.with_suffix('.json'))}
    if baseline_only:
        dump(HERE/'baseline-schema-audit.json',{'status':'PASS','completed_utc':now(),
             'scope':'Four W9600 full trajectories and four exact eight-variable suffix identities only; new widths still pending',
             'runs':runs,'suffix_identity':suffix_checks,'verifier_sha256':sha(Path(__file__))})
        print('BASELINE SCHEMA AND SUFFIX PASS',flush=True)
        return
    for ki,kind in enumerate(KINDS):
        pairs[kind]={}
        for pi,(small,large) in enumerate(((0,4800),(0,9600),(4800,9600))):
            old=runs[kind][str(small)];new=runs[kind][str(large)]
            delta=np.array(old['daily_cost_yuan'])-np.array(new['daily_cost_yuan'])
            monthly={f'2025-{month:02}':float(sum(delta[i] for i,date in enumerate(data['dates'][31:365]) if str(date).startswith(f'2025-{month:02}'))) for month in range(2,13)}
            info={'smaller_width_kwh':small,'larger_width_kwh':large,'saving_yuan':float(delta.sum()),
                'saving_percent':float(100*delta.sum()/old['summary']['total_cost_yuan']),
                'daily_mean_saving_yuan':float(delta.mean()),'positive_days':int(np.sum(delta>1e-6)),
                'negative_days':int(np.sum(delta < -1e-6)),'zero_days':int(np.sum(abs(delta)<=1e-6)),
                'monthly_saving_yuan':monthly,'positive_months':sum(x>1e-6 for x in monthly.values())}
            if large==9600:info['bootstrap']=bootstrap(delta,ki,pi)
            pairs[kind][f'{small}_to_{large}']=info
        for row in rows:
            if row['kind']==kind:
                for target in (0,4800,9600):row[f'saving_vs_W{target}_yuan']=runs[kind][str(target)]['summary']['total_cost_yuan']-row['total_cost_yuan']
    assert current_hashes()==hashes,'Inputs changed during audit'
    result={'status':'PASS','completed_utc':now(),'tolerance':TOL,'monotonic_cost_assertion':False,
        'scope':'Usable-window closed-loop ablation of original two-midnight main model; no change of hardware rating, no exact-policy savings theorem',
        'hash_observation_snapshot':snapshot,'current_hashes':hashes,'verifier_sha256':sha(Path(__file__)),
        'baseline_input_sha256':sha(REFERENCE/'data.npz'),
        'suffix_identity':suffix_checks,
        'runs':runs,'comparisons':pairs}
    dump(HERE/'capacity-audit.json',result)
    for name,records in (('summary.csv',rows),('daily-costs.csv',dailyrows)):
        with (HERE/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    print(json.dumps({'status':'PASS','rows':len(rows),'summary':[r for r in rows]},ensure_ascii=False),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wait',action='store_true');parser.add_argument('--snapshot-only',action='store_true');parser.add_argument('--baseline-only',action='store_true');args=parser.parse_args()
    sp=HERE/'verifier-observation-snapshot.json'
    if not sp.exists():dump(sp,{'observed_utc':now(),'scope':'Observed after annual launch; compared to producer-recorded hashes and completion state; not claimed to be launch-time instrumentation','hashes':current_hashes()})
    snapshot=json.loads(sp.read_text());assert current_hashes()==snapshot['hashes']
    if args.snapshot_only:print('snapshot saved');return
    if args.baseline_only:run(snapshot,baseline_only=True);return
    while True:
        missing=[str(path_for(k,w)) for k in KINDS for w in (0,4800,9600) if not path_for(k,w).exists() or not path_for(k,w).with_suffix('.json').exists()]
        if not missing:break
        dump(HERE/'capacity-audit-status.json',{'status':'WAITING_FOR_RESULTS','checked_utc':now(),'missing':missing})
        if not args.wait:
            print(json.dumps({'status':'WAITING_FOR_RESULTS','missing':missing},ensure_ascii=False))
            sys.exit(2)
        time.sleep(30)
    run(snapshot)
    dump(HERE/'capacity-audit-status.json',{'status':'PASS','checked_utc':now()})
if __name__=='__main__':main()
