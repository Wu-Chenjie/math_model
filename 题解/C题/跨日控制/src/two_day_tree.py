"""Synthetic causal cross-day scenario tree and exact-tail Benders verification.

Two compressed 'days', each containing two 10-minute slots, are NOT the contest
dataset. Day-2 forecast is observed at its midnight; its two actual innovations
are then revealed sequentially. This is a finite-tree demonstration, not a
general SDDP implementation or an annual performance experiment.
"""
from pathlib import Path
import itertools,json,time,sys,platform,hashlib
import numpy as np
import scipy
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'inputs/toy.json').read_text())
ETA=CONFIG['eta'];M=CONFIG['power_limit_kw']*CONFIG['step_hours']
LOW,HIGH=CONFIG['energy_bounds_kwh'];INITIAL=CONFIG['initial_and_final_energy_kwh']
PATHS=list(itertools.product([0,1],CONFIG['independent_innovation_support_kwh'],CONFIG['independent_innovation_support_kwh']))

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def observations(path,t):
    z,u,v=path
    return () if t<2 else (z,u) if t==2 else (z,u,v)

def net(path,t):return CONFIG['first_block_net_kwh'][t] if t<2 else CONFIG['second_block_forecast_levels_kwh'][path[0]]+path[t-1]
def price(t):return CONFIG['prices_yuan_per_kwh'][t]

def solve(start=0,stop=4,initial=INITIAL,daily_closed=False,cuts=None,paths=None):
    paths=PATHS if paths is None else paths;prob=1/len(paths)
    names=[];index={};bounds=[];obj=[];eq=[];rhs=[];ub=[];bub=[]
    def var(key,b=(0,None)):
        if key not in index:index[key]=len(names);names.append(key);bounds.append(b);obj.append(0.)
        return index[key]
    def con(terms,b,equal=False):
        (eq if equal else ub).append(terms);(rhs if equal else bub).append(b)
    e0=var(('E_initial',),(LOW,HIGH));con({e0:1.},initial,True)
    trajectories=[];ends=set();mids=set()
    for path in paths:
        prev=e0;rows=[]
        for t in range(start,stop):
            hist=observations(path,t)
            # Contract at day-2 midnight knows the forecast z, NOT actual u/v.
            q=var(('q',t) if t<2 else ('q',path[0],t))
            en=var(('E_next',t,*hist),(LOW,HIGH));em=var(('emergency',t,*hist))
            obj[q]+=prob*price(t);obj[em]+=prob*5*price(t)
            for slope in [ETA,1/ETA]:
                con({en:slope,prev:-slope,q:-1.,em:-1.},-net(path,t))
            con({en:1.,prev:-1.},ETA*M);con({en:-1.,prev:1.},M/ETA)
            rows.append((t,q,prev,en,em));prev=en
            if t==1:mids.add(en)
        ends.add(prev);trajectories.append(rows)
    if stop==4:
        for en in ends:con({en:1.},INITIAL,True)
    if daily_closed:
        for en in mids:con({en:1.},INITIAL,True)
    if cuts is not None:
        assert stop==2 and len(ends)==1
        last=next(iter(ends))
        # This is reachability of the single final experiment endpoint, not a
        # daily reset. Two remaining slots can add at most 2*ETA*M.
        bounds[last]=(max(LOW,INITIAL-2*ETA*M),min(HIGH,INITIAL+2*M/ETA))
        theta=var(('future_cost',));obj[theta]=1.
        for alpha,beta in cuts:con({last:beta,theta:-1.},-alpha)
    def matrix(rows):
        a=np.zeros((len(rows),len(names)))
        for i,row in enumerate(rows):
            for j,value in row.items():a[i,j]=value
        return a
    A=matrix(ub);B=matrix(eq)
    r=linprog(obj,A_ub=A,b_ub=bub,A_eq=B,b_eq=rhs,bounds=bounds,method='highs')
    if not r.success:raise RuntimeError(r.message)
    eqgap=float(abs(B@r.x-rhs).max());ineq=float(max(0,np.max(A@r.x-bub)))
    assert max(eqgap,ineq)<1e-6
    costs=[];replay=[]
    for path,rows in zip(paths,trajectories):
        series=[];cost=0.
        for t,q,old,new,em in rows:
            delta=r.x[new]-r.x[old];c=max(delta,0)/ETA;d=ETA*max(-delta,0)
            emergency=max(0,net(path,t)-r.x[q]+c-d)
            spill=max(0,r.x[q]+d-c-net(path,t))
            assert abs(emergency-r.x[em])<1e-6
            cost+=price(t)*(r.x[q]+5*emergency)
            series.append({'slot':t,'q':float(r.x[q]),'initial_energy':float(r.x[old]),
                'end_energy':float(r.x[new]),'charge':c,'discharge':d,'emergency':emergency,'spill':spill,'net':net(path,t)})
        costs.append(cost);replay.append({'forecast':path[0],'innovations':list(path[1:]),'probability':prob,'cost':cost,'slots':series})
    out={'economic_cost':float(np.mean(costs)),'lp_objective':float(r.fun),
         'initial_energy_dual':float(r.eqlin.marginals[0]),'eq_residual':eqgap,'ineq_violation':ineq,
         'midnight_energy':None if not mids else float(r.x[next(iter(mids))]),
         'paths':replay,'variables':{str(k):float(r.x[i]) for k,i in index.items()}}
    if cuts is None:assert abs(out['economic_cost']-r.fun)<1e-6
    return out

def main():
    tic=time.perf_counter()
    closed=solve(daily_closed=True);continuous=solve()
    cuts=[];trace=[];best=np.inf
    for iteration in range(30):
        master=solve(stop=2,cuts=cuts);E=master['midnight_energy'];tail=solve(start=2,initial=E)
        upper=master['economic_cost']+tail['economic_cost'];best=min(best,upper)
        lower=master['lp_objective'];beta=tail['initial_energy_dual'];alpha=tail['economic_cost']-beta*E
        cuts.append((alpha,beta));trace.append({'iteration':iteration+1,'midnight_energy':E,'lower_bound':lower,
             'feasible_policy_cost':upper,'best_upper_bound':float(best),'cut_alpha':alpha,'cut_beta':beta})
        if best-lower<1e-7:break
    else:raise AssertionError('Finite toy Benders failed to converge')
    assert abs(best-continuous['economic_cost'])<1e-6
    # Rolling resolve at day-2 forecast, preserving actual midnight SOC.
    rolling_tails=[solve(start=2,initial=E,paths=[p for p in PATHS if p[0]==z]) for z in [0,1]]
    rolling=master['economic_cost']+np.mean([r['economic_cost'] for r in rolling_tails])
    assert abs(rolling-continuous['economic_cost'])<1e-6
    assert continuous['economic_cost']<=closed['economic_cost']+1e-6
    probes=np.linspace(INITIAL-2*ETA*M,INITIAL+2*ETA*M,31)
    tails=[solve(start=2,initial=float(e))['economic_cost'] for e in probes]
    maxcut=max(float(a+b*e-v) for a,b in cuts for e,v in zip(probes,tails))
    assert maxcut<1e-6
    result={'scope':'Synthetic compressed two-day, eight-path causal example; NOT contest-data annual results or full SDDP',
        'daily_closed':closed,'continuous_tree':continuous,'benders_trace':trace,'tail_cuts':cuts,
        'rolling_expected_cost':float(rolling),'saving_yuan':closed['economic_cost']-continuous['economic_cost'],
        'checks':{'status':'pass','full_tree_benders_gap':float(abs(best-continuous['economic_cost'])),
                  'rolling_full_tree_gap':float(abs(rolling-continuous['economic_cost'])),
                  'cut_max_lower_bound_violation_on_31_probes':maxcut,
                  'same_final_energy':INITIAL,'cross_day_energy_jump':0.},
        'tail_probe_energies':probes.tolist(),'tail_probe_costs':tails}
    dump(ROOT/'artifacts/prototype-results.json',result)
    source=Path(__file__)
    dump(ROOT/'artifacts/prototype-execution.json',{'command':'python3 '+' '.join(sys.argv),'exit_code':0,
        'runtime_seconds':time.perf_counter()-tic,'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
        'platform':platform.platform(),'seed':None,'deterministic_reason':'All eight synthetic paths enumerated; deterministic LP solver',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'input_sha256':hashlib.sha256((ROOT/'inputs/toy.json').read_bytes()).hexdigest()})
    print(json.dumps({'daily_closed':closed['economic_cost'],'cross_day':continuous['economic_cost'],
        'midnight_energy':continuous['midnight_energy'],'iterations':len(trace),'checks':result['checks']}))

if __name__=='__main__':main()
