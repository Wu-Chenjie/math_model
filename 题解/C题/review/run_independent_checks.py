"""Read-only checks of frozen producer code and artifacts. Writes only review/ outputs."""
from pathlib import Path
import sys, json, hashlib, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dispatch import solve, execute_slot, settlement
from forecasting import make_forecasts, scenario_data
from run_models import simulate

def main():
    started=time.perf_counter()
    out={'reviewer':'independent_review','checks':{},'source_hashes':{}}
    for name in ['dispatch.py','forecasting.py','run_models.py']:
        out['source_hashes'][name]=hashlib.sha256((ROOT/'src'/name).read_bytes()).hexdigest()
    # Exact one-slot newsvendor checks, including correlated price/demand.
    values=np.arange(0.,100.,10.)[:,None]
    check=[]
    for prices in [np.ones_like(values),np.arange(1.,11.)[:,None]]:
        s=solve(values,prices,initial=6000,terminal=6000,power=0)
        candidates=values.ravel()
        objective=np.array([float(prices.mean()*q+5*np.mean(prices[:,0]*np.maximum(values[:,0]-q,0))) for q in candidates])
        error=abs(s['expected_cost']-objective.min())
        assert error<1e-7
        check.append({'q':float(s['q'][0]),'objective':s['expected_cost'],'grid_min':float(objective.min()),'error':error})
    out['checks']['one_slot_exact_newsvendor']=check
    # Settlement independently specified, and no-refund downward domination.
    cost_cases=[]
    for refund,expected in [(True,[90.,130.]),(False,[110.,130.])]:
        for r,amount in zip([80.,120.],expected):
            c=settlement(np.array([100.]),np.array([r]),np.array([0.]),np.array([1.]),refund)
            assert c['total_cost']==amount
            cost_cases.append({'refund':refund,'r':r,'total_cost':amount})
    for net in [-100.,0.,50.,100.,150.]:
        sol=solve(np.array([[net]]),np.ones((1,1)),power=0,base=np.array([100.]),refund=False)
        assert sol['q'][0]>=100-1e-8
    out['checks']['settlement_exact_cases']=cost_cases
    out['checks']['no_refund_no_downward_adjustment']='pass'
    # Extreme deterministic paths challenge the one-step reachable terminal set.
    maxpower=maxterminal=maxrecurrence=0.
    for eta in [.85,.9,.95]:
        for power in [4000.,5000.,6000.]:
            for target in [4800.,6000.,7200.]:
                for kind in range(5):
                    E=target
                    for t in range(144):
                        balance=[10000.,-10000.,10000.*(-1)**t,10000. if t<100 else -10000.,-10000. if t<100 else 10000.][kind]
                        q=max(balance,0.); net=max(-balance,0.)
                        c,d,nextE,e,spill=execute_slot(q,net,E,0.,0.,t,'greedy',eta,power,terminal=target)
                        assert 1200-1e-7<=nextE<=10800+1e-7
                        assert 0<=min(c,d)<=1e-8 and max(c,d)*6<=power+1e-7
                        assert abs(q+d+e-c-spill-net)<1e-7
                        maxpower=max(maxpower,max(c,d)*6)
                        maxrecurrence=max(maxrecurrence,abs(nextE-E-eta*c+d/eta))
                        E=nextE
                    maxterminal=max(maxterminal,abs(E-target))
    out['checks']['terminal_reachability']={'paths':135,'steps':19440,'max_power_kw':maxpower,'terminal_error':maxterminal,'soc_recurrence_error':maxrecurrence}
    data=dict(np.load(ROOT/'artifacts/data.npz'))
    fc,selection=make_forecasts(data)
    # Future information is made absurd; prior-release forecasts/scenarios must stay identical.
    cause=[]
    for release in [0,1,2,3]:
        day=100;t=release*36
        changed={k:v.copy() for k,v in data.items()}
        for name in ['load','pv','price']:
            changed[name][day,t:]+=100000
            changed[name][day+1:]+=200000
        changed['forecast'][day,release+1:]+=300000
        changed['forecast'][day+1:]+=300000
        cf,_=make_forecasts(changed)
        for official in [False,True]:
            a=scenario_data(data,fc,day,release,official,True)
            b=scenario_data(changed,cf,day,release,official,True)
            differences=[float(np.max(np.abs(a[k]-b[k]))) for k in [0,1]]
            assert max(differences)==0
            cause.append({'release':release,'official_pv':official,'net_scenario_max_delta':differences[0],'price_scenario_max_delta':differences[1]})
    out['checks']['future_perturbation']=cause
    # Recompute all saved main trajectory identities without using producer validation functions.
    products={}
    for name in ['q2','q3','q4_2','q4_3']:
        a=dict(np.load(ROOT/f'artifacts/{name}.npz'))
        summary=json.loads((ROOT/f'artifacts/{name}.json').read_text())
        cfg=summary['configuration'];eta=cfg['eta'];days=a['days'];p=a['price']
        residual=a['r']+a['emergency']+a['d']-a['c']-a['spill']-(data['load'][days]-data['pv'][days])/6
        eq=np.diff(a['state'],axis=1)-eta*a['c']+a['d']/eta
        total=float(np.sum(p*(a['q']+1.5*np.maximum(a['r']-a['q'],0)-.5*np.maximum(a['q']-a['r'],0)+5*a['emergency'])))
        delta=abs(total-summary['totals']['total_cost'])
        assert max(abs(residual).max(),abs(eq).max(),delta)<1e-6
        assert np.all(a['days']==np.arange(31,365))
        assert np.max(abs(a['state'][:,[0,-1]]-6000))<1e-6
        assert np.min(a['state'])>=1200-1e-6 and np.max(a['state'])<=10800+1e-6
        assert np.max(a['c'])*6<=5000+1e-6 and np.max(a['d'])*6<=5000+1e-6
        assert np.min(np.stack([a[k] for k in ['q','r','c','d','emergency','spill']]))>=-1e-6
        # Final executed ordinary purchases equal the most recent available decision for that slot.
        resolved=a['q'].copy()
        for release in cfg['updates']:
            start=release*36
            resolved[:,start:]=a['releases'][:,release,start:]
        assert np.max(abs(resolved-a['r']))<1e-8
        assert np.max(abs(a['releases'][:,0,:]-a['q']))<1e-8
        products[name]={'energy_max_abs':float(abs(residual).max()),'soc_recurrence_max_abs':float(abs(eq).max()),'cost_recomputed':total,'cost_difference':delta,'release_snapshot_consistency':'pass','dates':len(days)}
    out['checks']['saved_main_products']=products
    out['pv_forecast_attribution_note']='Producer is independently running stale-PV/full-replanning control; omitted here to avoid duplicate annual computation.'
    out['runtime_seconds']=time.perf_counter()-started
    out['status']='pass'
    (ROOT/'review/independent-checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':main()
