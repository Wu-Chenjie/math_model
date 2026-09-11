#!/usr/bin/env python3
"""Falsification tests for conditional scenarios. No annual optimization."""
from pathlib import Path
import hashlib,json,sys,time,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nextgen_scenarios import Config,ScenarioFactory,state_paths,reduce_measure


def run():
    data=dict(np.load(ROOT/'baseline_frozen/artifacts/data.npz'))
    selection=json.loads((ROOT/'baseline_frozen/artifacts/forecast-selection.json').read_text())
    cases=[];t0=time.perf_counter()
    def check(name,fn):
        try:details=fn();cases.append({'name':name,'status':'PASS','details':details})
        except Exception as e:cases.append({'name':name,'status':'FAIL','error':str(e),'traceback':traceback.format_exc()})
    for official,variable,fusion,correction in ((False,False,1.,0.),(True,False,1.,0.),(False,True,1.,0.),(True,True,1.,0.),(True,False,.65,.35),(True,True,.65,.35)):
        def perturb(official=official,variable=variable,fusion=fusion,correction=correction):
            count=0
            for phase in (0,36,72,108):
                now=31*144+phase;end=now+288;cfg=Config(scenario_method='conditional',fusion_weight=fusion,official_correction=correction)
                baseline=ScenarioFactory(data,selection,official,variable,fusion_weight=fusion,official_correction=correction).build(now,end,cfg)
                changed={k:v.copy() for k,v in data.items()}
                for key,shift in [('load',8000),('pv',12000),('price',20)]:changed[key].ravel()[now:]+=shift
                changed['forecast'].reshape(-1,24)[now//36+1:]+=50000
                other=ScenarioFactory(changed,selection,official,variable,fusion_weight=fusion,official_correction=correction).build(now,end,cfg)
                for key in ('net','prices','weights','states','history_states','mass','seed','origins'):
                    assert np.array_equal(baseline[key],other[key]),key
                assert baseline['meta']==other['meta'],'metadata changed'
                count+=1
            return {'origins_tested':count,'modified':'current/future actuals, later official releases; all pre-contract outputs exact equal'}
        check(f'future_actuals_and_unreleased_forecasts:{official}:{variable}:{fusion}:{correction}',perturb)
    def maturity():
        factory=ScenarioFactory(data,selection,True,True)
        factory.block(20*144,288,22*144)
        try:factory.block(20*144,288,22*144-1)
        except AssertionError:return {'exact_boundary_accepted':True,'one_slot_unripe_rejected':True}
        raise AssertionError('unripe cached block accepted')
    check('maturity_guard_before_cache',maturity)
    def state_math():
        rn=np.array([[2.,-3.,8.],[5.,1.,-2.]])
        rp=np.array([[.1,.4,-.2],[.5,-.1,.2]])
        seed=np.array([7.,10.,.7,1.2]);alpha=.3
        actual=state_paths(rn,rp,seed,alpha,True);expected=np.empty((2,3,4))
        for s in range(2):
            zn,zp,ep=10.,1.2,.7
            for j in range(3):
                zn=.7*zn+.3*rn[s,j];expected[s,j]=rn[s,j],zn,ep,zp
                ep=rp[s,j];zp=.7*zp+.3*ep
        assert np.allclose(actual,expected,rtol=0,atol=1e-14)
        return {'max_abs_error':float(np.abs(actual-expected).max())}
    check('lagged_price_and_EMA_identity',state_math)
    def reduction():
        points=np.array([[0.],[1.],[3.],[10.]])
        distance=np.abs(points-points.T);mass=np.array([.1,.2,.3,.4])
        ids,weights,meta=reduce_measure(distance,mass,2)
        assignment=np.argmin(distance[:,ids],axis=1)
        expected=np.bincount(assignment,weights=mass,minlength=len(ids))
        assert np.allclose(weights,expected)
        assert abs(meta['transport_distance']-float(mass@distance[:,ids].min(1)))<1e-14
        ids_all,weights_all,meta_all=reduce_measure(distance,mass,4)
        assert np.array_equal(ids_all,np.arange(4)) and np.allclose(weights_all,mass)
        assert meta_all['transport_distance']==0
        objectives=[]
        from itertools import combinations
        for pair in combinations(range(4),2):objectives.append(float(mass@distance[:,pair].min(1)))
        assert abs(meta['transport_distance']-min(objectives))<1e-14
        return {'fixture_exhaustive_optimum':min(objectives),'returned_transport':meta['transport_distance'],'mass_preserved':True}
    check('weighted_PAM_mass_and_small_exact_case',reduction)
    def singleton():
        cfg=Config(window=1,scenarios=7,scenario_method='conditional')
        obj=ScenarioFactory(data,selection,True,True).build(31*144,33*144,cfg)
        assert np.isfinite(obj['weights']).all() and np.isfinite(obj['mass']).all(),'single-block weights nonfinite'
        assert len(obj['weights'])==1 and obj['weights'][0]==1
        return {'single_mature_candidate_probability':float(obj['weights'][0])}
    check('single_candidate_statistical_fallback',singleton)
    source=ROOT/'src/nextgen_scenarios.py'
    report={'reviewer_id':'/root/upgrade_code_review','independent':True,'status':'PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
            'scope':'Scenario algebra, weight transport, mature-cache access and contract-origin information perturbations only. No upper LP, battery policy or annual performance claim.',
            'cases':cases,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'execution':{'command':sys.argv,'runtime_seconds':time.perf_counter()-t0}}
    output=ROOT/'review/nextgen-scenario-checks.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'cases':[(c['name'],c['status']) for c in cases]},ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':sys.exit(run())
