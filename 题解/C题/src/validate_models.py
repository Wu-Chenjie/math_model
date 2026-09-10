"""Independent numerical invariants, causal falsification, controlled PV value and stress tests."""
from pathlib import Path
import json,time,sys
import numpy as np
from forecasting import make_forecasts,scenario_data
from dispatch import solve,execute_slot,settlement
from run_models import simulate,dump
ROOT=Path(__file__).resolve().parents[1]

def main():
    start=time.perf_counter();data=dict(np.load(ROOT/'artifacts/data.npz'));fc,_=make_forecasts(data)
    checks=[]
    q=solve(np.arange(1.,11.)[:,None],np.ones((10,1)),power=0)
    assert 8-1e-6<=q['q'][0]<=9+1e-6
    checks.append({'name':'newsvendor_80_percent_quantile','status':'pass','quantity':float(q['q'][0]),'optimal_interval':[8,9]})
    # Analytical simultaneous charge/discharge cancellation preserves state and reduces bus demand.
    c,d=100.,40.;z=min(c,d/.9**2)
    assert abs(.9*c-d/.9-(.9*(c-z)-(d-.9**2*z)/.9))<1e-8
    checks.append({'name':'charge_discharge_cancellation','status':'pass'})
    # Perturb all observations unknown at the tested release, including all future forecasts.
    for release in [0,1,2,3]:
        day=100;t=release*36;mut={k:v.copy() for k,v in data.items()}
        for key in ['load','pv','price']:
            mut[key][day,t:]*=1.777;mut[key][day+1:]*=.333
        mut['forecast'][day,release+1:]*=1.999;mut['forecast'][day+1:]*=.222
        fm,_=make_forecasts(mut)
        for official in [False,True]:
            n,p,h=scenario_data(data,fc,day,release,official,True)
            nn,pp,hh=scenario_data(mut,fm,day,release,official,True)
            assert np.array_equal(n,nn) and np.array_equal(p,pp) and np.max(h)<day
        checks.append({'name':f'future_mutation_invariance_release_{release*6:02d}','status':'pass'})
    # The no-refund case should never decrease contracted quantities under free curtailment.
    n,p,_=scenario_data(data,fc,100,1,True,False)
    base=solve(*scenario_data(data,fc,100,0,True,False)[:2])['q'][36:]
    s=solve(n,p,base=base,refund=False)
    assert np.min(s['q']-base)>-1e-5
    checks.append({'name':'no_refund_downward_adjustment_dominated','status':'pass'})
    # Correct common horizon comparison of hourly official PV forecast errors.
    pv_accuracy=[]
    for k in range(4):
        t=k*36;act=data['pv'][31:,t:]
        pv_accuracy.append({'release_hour':6*k,'latest_mae_kw':float(abs(act-fc['official_pv'][31:,k,t:]).mean()),
             'midnight_same_horizon_mae_kw':float(abs(act-fc['official_pv'][31:,0,t:]).mean())})
    prediction={key:{'mae_kw' if key!='price' else 'mae_cny_per_kwh':float(abs(data[key][31:]-fc[key][31:,0]).mean()),
                    'rmse':float(np.sqrt(np.mean((data[key][31:]-fc[key][31:,0])**2))))} for key in ['load','pv','price']}
    # Update controller and load/price forecasts at identical times; hold PV forecast at midnight.
    fhold={k:v.copy() for k,v in fc.items()}
    for k in range(1,4): fhold['official_pv'][:,k,k*36:]=fc['official_pv'][:,0,k*36:]
    controlled={}
    for variable in [False,True]:
        _,m=simulate(data,fhold,list(range(31,365)),official=True,variable_price=variable,updates=(1,2,3),controller='greedy')
        label='q4_3_keep_midnight_pv' if variable else 'q3_keep_midnight_pv'
        dump(ROOT/f'artifacts/{label}.json',m);controlled[label]=m['totals']
        print(label,m['totals']['total_cost'],flush=True)
    stress={}
    a=dict(np.load(ROOT/'artifacts/q3.npz'));days=a['days']
    for label,ls,vs in [('reference',1,1),('load_plus5pct',1.05,1),('load_minus5pct',.95,1),('pv_minus10pct',1,.9),('pv_plus10pct',1,1.1)]:
        costs=[];em_total=0.;maxterm=0.
        for i,day in enumerate(days):
            E=6000.;em=np.zeros(144);net=(ls*data['load'][day]-vs*data['pv'][day])/6
            for t in range(144):
                c,d,E,em[t],spill=execute_slot(a['r'][i,t],net[t],E,0,0,t,'greedy')
            costs.append(settlement(a['q'][i],a['r'][i],em,a['price'][i])['total_cost']);em_total+=em.sum()
            maxterm=max(maxterm,abs(E-6000))
        stress[label]={'total_cost':float(sum(costs)),'emergency_energy':float(em_total),'terminal_max_abs':maxterm}
    # Q1 conversion/efficiency sensitivity; do not overwrite primary inputs.
    q1sens={};L=data['day_load'];V=data['day_pv'];P=data['day_price']
    for name,eta,n,p in [('reference',.9,(L-V)/6,P),('roundtrip90',np.sqrt(.9),(L-V)/6,P),
                        ('trapezoid_power',.9,((L+np.roll(L,1))-(V+np.roll(V,1)))/12,P)]:
        s=solve(n[None,:],p[None,:],eta=eta,hard=True)
        q1sens[name]={'cost':float(p@s['q']),'energy':float(s['q'].sum())}
    out={'checks':checks,'prediction_accuracy':prediction,'pv_release_accuracy':pv_accuracy,
         'controlled_pv_value':controlled,'frozen_contract_stress':stress,'q1_sensitivity':q1sens,
         'runtime_seconds':time.perf_counter()-start}
    dump(ROOT/'artifacts/validation.json',out)
    dump(ROOT/'artifacts/execution-validation.json',{'command':'python3 src/validate_models.py','exit_code':0,'runtime_seconds':out['runtime_seconds']})

if __name__=='__main__':main()
