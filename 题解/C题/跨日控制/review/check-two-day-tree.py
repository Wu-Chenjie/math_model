"""Independent full-path c/d LP, explicit nonanticipativity, and cut audit."""
from pathlib import Path
import itertools,json,hashlib
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parents[1]
PATHS=list(itertools.product([0,1],[-500.,500.],[-500.,500.]))
ETA=.9;M=5000/6

def independent_lp(initial=6000.,start=0,closed=False,oracle=False,forecast=None):
    paths=[p for p in PATHS if forecast is None or p[0]==forecast]
    slots=list(range(start,4));S=len(paths);T=len(slots);N=5*S*T
    index=lambda s,j,k:5*(s*T+j)+k # q, charge, discharge, emergency, next energy
    obj=np.zeros(N);bounds=[];eq=[];rhs=[];ub=[];bub=[]
    def row(terms):
        x=np.zeros(N)
        for i,v in terms.items():x[i]=v
        return x
    for s,p in enumerate(paths):
        for j,t in enumerate(slots):
            q,c,d,e,E=[index(s,j,k) for k in range(5)]
            n=-600. if t<2 else [1000.,2000.][p[0]]+p[t-1]
            price=.2 if t<2 else 1.
            obj[q]=price/S;obj[e]=5*price/S
            bounds +=[(0,None),(0,M),(0,M),(0,None),(1200,10800)]
            ub.append(row({q:-1,c:1,d:-1,e:-1}));bub.append(-n)
            terms={E:1,c:-ETA,d:1/ETA}
            if j:terms[index(s,j-1,4)]=-1
            eq.append(row(terms));rhs.append(initial if j==0 else 0.)
            if t==3 or (closed and t==1):eq.append(row({E:1}));rhs.append(6000.)
    if not oracle:
        # All paths keep separate variables; equality rows encode information.
        for j,t in enumerate(slots):
            contract_groups={};action_groups={}
            for s,p in enumerate(paths):
                contract_key=() if t<2 else (p[0],)
                action_key=() if t<2 else p[:t-0]  # t=2:(z,u); t=3:(z,u,v)
                for groups,key,components in [(contract_groups,contract_key,[0]),(action_groups,action_key,[1,2,3,4])]:
                    if key not in groups:groups[key]=s
                    else:
                        first=groups[key]
                        for k in components:eq.append(row({index(s,j,k):1,index(first,j,k):-1}));rhs.append(0.)
    res=linprog(obj,A_ub=np.array(ub),b_ub=bub,A_eq=np.array(eq),b_eq=rhs,bounds=bounds,method='highs')
    assert res.success,res.message
    return float(res.fun)

def main():
    config=json.loads((ROOT/'inputs/toy.json').read_text())
    assert config['eta']==ETA and abs(config['power_limit_kw']*config['step_hours']-M)<1e-10
    assert config['first_block_net_kwh']==[-600,-600] and config['second_block_forecast_levels_kwh']==[1000,2000]
    assert config['independent_innovation_support_kwh']==[-500,500] and config['prices_yuan_per_kwh']==[.2,.2,1.,1.]
    assert config['energy_bounds_kwh']==[1200,10800] and config['initial_and_final_energy_kwh']==6000
    execution=json.loads((ROOT/'artifacts/prototype-execution.json').read_text())
    assert execution['exit_code']==0
    assert execution['source_sha256']==hashlib.sha256((ROOT/'src/two_day_tree.py').read_bytes()).hexdigest()
    assert execution['input_sha256']==hashlib.sha256((ROOT/'inputs/toy.json').read_bytes()).hexdigest()
    saved=json.loads((ROOT/'artifacts/prototype-results.json').read_text())
    full=independent_lp();closed=independent_lp(closed=True);oracle=independent_lp(oracle=True)
    assert abs(full-saved['continuous_tree']['economic_cost'])<1e-7
    assert abs(closed-saved['daily_closed']['economic_cost'])<1e-7
    assert oracle<=full+1e-7<=closed+1e-7
    max_physical=max_cost=0.;group_checks=0
    for key in ['continuous_tree','daily_closed']:
        groups={};weighted=0.
        for branch in saved[key]['paths']:
            z=branch['forecast'];u,v=branch['innovations'];prev=6000.;cost=0.
            for j,row in enumerate(branch['slots']):
                n=-600. if j<2 else [1000.,2000.][z]+[u,v][j-2]
                assert abs(row['net']-n)<1e-12
                E=row['end_energy'];q=row['q'];c=row['charge'];d=row['discharge'];e=row['emergency'];spill=row['spill']
                errors=[abs(row['initial_energy']-prev),abs(E-prev-ETA*c+d/ETA),abs(q+d+e-c-spill-n)]
                max_physical=max(max_physical,*errors)
                assert 1200-1e-7<=E<=10800+1e-7 and min(q,c,d,e,spill)>=-1e-7
                assert max(c,d)<=M+1e-7 and min(c,d)<1e-7
                ck=(j,'q',() if j<2 else (z,));ak=(j,'action',() if j<2 else (z,u) if j==2 else (z,u,v))
                for k,vals in [(ck,[q]),(ak,[c,d,E,e])]:
                    if k in groups:assert np.allclose(groups[k],vals,atol=1e-7,rtol=0);group_checks+=1
                    else:groups[k]=vals
                cost+=(.2 if j<2 else 1.)*(q+5*e);prev=E
            assert abs(prev-6000)<1e-7
            max_cost=max(max_cost,abs(cost-branch['cost']));weighted+=branch['probability']*cost
        max_cost=max(max_cost,abs(weighted-saved[key]['economic_cost']))
    assert max(max_physical,max_cost)<1e-7
    cuts=saved['tail_cuts'];trace=saved['benders_trace']
    probes=sorted(set(np.linspace(4500.,7500.,61).tolist()+[r['midnight_energy'] for r in trace]))
    vals={E:independent_lp(initial=E,start=2) for E in probes}
    violations=[a+b*E-vals[E] for a,b in cuts for E in probes]
    assert max(violations)<1e-7
    tight=[]
    for cut,r in zip(cuts,trace):
        E=r['midnight_energy'];gap=abs(cut[0]+cut[1]*E-vals[E]);tight.append(gap);assert gap<1e-7
        assert r['lower_bound']<=full+1e-7 and r['best_upper_bound']>=full-1e-7
    E=saved['continuous_tree']['midnight_energy']
    first=sum(.2*(x['q']+5*x['emergency']) for x in saved['continuous_tree']['paths'][0]['slots'][:2])
    rolling=first+sum(independent_lp(initial=E,start=2,forecast=z) for z in [0,1])/2
    assert abs(rolling-full)<1e-7
    result={'status':'pass_for_synthetic_two_day_case','independent_formulation':'Full per-path q/c/d/e/E variables plus explicit nonanticipativity equalities; original uses shared-node variables and battery-flow elimination',
        'independent_closed_cost':closed,'independent_cross_day_cost':full,'independent_clairvoyant_reference_cost':oracle,
        'midnight_energy':E,'physical_max_abs':max_physical,'cost_max_abs':max_cost,'information_group_equalities_checked':group_checks,
        'cut_probe_count':len(probes),'cut_max_lower_bound_violation':max(violations),'cut_support_gaps':tight,
        'rolling_conditional_resolve_cost':rolling,'benders_iterations':len(trace),
        'scope':'Two compressed blocks, four ten-minute slots, eight specified equiprobable synthetic paths; exact second-block causal-tree Benders special case. No random-price, intraday-amendment, annual-data, or general SDDP validation.',
        'reviewed_artifact_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/two_day_tree.py','inputs/toy.json','artifacts/prototype-results.json','artifacts/prototype-execution.json','review/check-two-day-tree.py']}}
    (ROOT/'review/prototype-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
