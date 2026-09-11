#!/usr/bin/env python3
"""Independent short LP/Bellman and observation-order falsification tests."""
from pathlib import Path
import hashlib,json,sys,time,traceback
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nextgen_scenarios import Config,state_paths,ScenarioFactory
from nextgen_control import affine_plan,EnhancedMarkovDP,WeightedMarkovDP,nonnegative_kernel,minimize_action
from control import execute


def bundle_for(net,prices,weights,seed=None):
    seed=np.zeros(4) if seed is None else np.array(seed)
    net=np.asarray(net,float);prices=np.asarray(prices,float);weights=np.asarray(weights,float)
    center=weights@net;fp=weights@prices;rn=net-center;rp=prices-fp
    return {'net':net,'prices':prices,'weights':weights,'seed':seed,'forecast':{'net':center,'price':fp},
        'states':state_paths(rn,rp,seed,.2,True),'history_states':state_paths(rn,rp,np.tile(seed,(len(net),1)),.2,True),
        'history_net_error':rn,'history_price_error':rp,'origins':np.arange(len(net))*144}


def explicit_lp(net,prices,weights,initial,terminal,base=None):
    # Shared deterministic physical controls, with scenario emergency recourse.
    # r,c,d,E,e and contractfee; explicit bus inequality permits free surplus spill.
    S,T=net.shape;r=0;c=T;d=2*T;E=3*T;e=4*T;fee=e+S*T;N=fee+T
    objective=np.zeros(N);objective[e:fee]=(5*prices*weights[:,None]).ravel();objective[fee:]=weights@prices
    eq=[];beq=[];ub=[];bub=[]
    for j in range(T):
        row=np.zeros(N);row[E+j]=1;row[c+j]=-.9;row[d+j]=1/.9
        if j:row[E+j-1]=-1
        eq.append(row);beq.append(initial if j==0 else 0)
        for s in range(S):
            row=np.zeros(N);row[r+j]=-1;row[c+j]=1;row[d+j]=-1;row[e+s*T+j]=-1
            ub.append(row);bub.append(-net[s,j])
        if base is None:
            row=np.zeros(N);row[r+j]=1;row[fee+j]=-1;ub.append(row);bub.append(0)
        else:
            for rate,constant in ((1.5,-.5*base[j]),(.5,.5*base[j])):
                row=np.zeros(N);row[r+j]=rate;row[fee+j]=-1;ub.append(row);bub.append(-constant)
    bounds=[(0,None)]*T+[(0,5000/6)]*(2*T)+[(1200,10800)]*T+[(0,None)]*(S*T+T)
    bounds[E+T-1]=(terminal,terminal)
    result=linprog(objective,A_ub=ub,b_ub=bub,A_eq=eq,b_eq=beq,bounds=bounds,method='highs')
    assert result.success,result.message
    return float(result.fun)


def run():
    started=time.perf_counter();cases=[]
    source_paths=[ROOT/'src'/n for n in ('nextgen_scenarios.py','nextgen_control.py','nextgen_run.py','control.py','dispatch.py')]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    def check(name,fn):
        try:details=fn();cases.append({'name':name,'status':'PASS','details':details})
        except Exception as e:cases.append({'name':name,'status':'FAIL','error':str(e),'traceback':traceback.format_exc()})
    def smalllp():
        maximum=0.;details=[]
        for w in ([1.],[.2,.8],[.8,.2]):
            n=np.array([[700.,-100.,500.,1200.],[300.,600.,900.,100.]])[:len(w)]
            p=np.array([[.2,.8,1.2,.3],[1.3,.4,.1,.7]])[:len(w)]
            for base in (None,np.array([400.,500.,300.,200.])):
                # Begin at a legitimate06h revision; no future release in this toy.
                config=Config(upper='state',gain_bound=0.)
                bundle=bundle_for(n,p,w)
                result=affine_plan(bundle,36,6000.,config,base=base,adjust=base is not None,terminal=6000.)
                expected=explicit_lp(n,p,np.array(w),6000.,6000.,base)
                gap=abs(result['objective']-expected);maximum=max(maximum,gap)
                assert gap<1e-5,(w,base,gap)
                assert result['objective_gap']<1e-5
                details.append({'weights':w,'adjustment':base is not None,'objective':result['objective'],'independent_explicit_lp':expected})
        return {'max_objective_gap':maximum,'cases':details}
    check('weighted_affine_vs_independent_explicit_LP',smalllp)
    def futurecutoff():
        T=80;weights=np.array([.2,.3,.5]);net=np.tile(np.linspace(250,600,T),(3,1));prices=np.tile(np.linspace(.4,.9,T),(3,1))
        net[1,36:]+=400;net[2,36:]-=300;prices[1,36:]+=.3;prices[2,36:]-=.2
        b=bundle_for(net,prices,weights,seed=[3,2,.1,.03]);cfg=Config(upper='state')
        p=affine_plan(b,108,6000,cfg,base=np.full(T,400.),adjust=True)
        # All histories strictly before next midnight coincide; its entire q must share.
        q=p['scenario_q'];r=p['scenario_r'];assert np.ptp(q[:,36:],axis=0).max()<1e-8
        assert np.ptp(r[:,:36],axis=0).max()<1e-8
        assert np.max(np.abs(r[:,36:72]-q[:,36:72]))<1e-8
        assert p['contract_information_cutoffs']['original'][36]==144
        assert p['objective_gap']<1e-5
        return {'shared_midnight_q_max_spread':float(np.ptp(q[:,36:],axis=0).max()),'root_revision_max_spread':float(np.ptp(r[:,:36],axis=0).max()),'future_midnight_information_cutoff':144}
    check('future_contract_shared_prefix_and_cutoff',futurecutoff)
    def m1algebra():
        rng=np.random.default_rng(8168);T=12;net=300+rng.normal(0,80,(5,T));prices=.5+rng.uniform(-.4,.5,(5,T));w=np.array([.1,.15,.2,.25,.3])
        b=bundle_for(net,prices,w);cfg=Config(lower='M1',grid=41,innovation_count=4)
        dp=EnhancedMarkovDP(b,np.full(T,400.),0,cfg,.3)
        maxerr=0.;minslope=0.
        for phase,model in enumerate(dp.models):
            A=model['A'];intercept=model['b'];e=np.zeros(4);e[1]=.8
            maxerr=max(maxerr,float(abs(A[1]-(.2*A[0]+e)).max()),abs(intercept[1]-.2*intercept[0]))
            e=np.zeros(4);e[3]=.8
            maxerr=max(maxerr,float(abs(A[3]-(.2*A[2]+e)).max()),abs(intercept[3]-.2*intercept[2]))
            x=b['states'][:,2];nxt,mean=dp.transition(x,phase,.05)
            maxerr=max(maxerr,float(abs(nxt[:,:,1]-(.8*x[:,None,1]+.2*nxt[:,:,0])).max()),float(abs(nxt[:,:,3]-(.8*x[:,None,3]+.2*nxt[:,:,2])).max()))
            expected=np.maximum(.001,.05+(x@A.T+intercept)[:,None,2]+model['innovations'][None,:,1])@model['mass']
            assert np.max(abs(mean-expected))<1e-12
        slopes=np.diff(dp.future,axis=2)/np.diff(dp.grid)
        minslope=float(np.diff(slopes,axis=2).min())
        assert maxerr<1e-10 and minslope>-1e-8,(maxerr,minslope)
        weights=nonnegative_kernel(dp.support[:,0],b['states'][0,0],dp.scales,dp.weights)
        assert np.all(weights>=0) and abs(weights.sum()-1)<1e-12
        return {'EMA_max_abs_error':maxerr,'min_slope_increment':minslope,'nonnegative_inventory_independent_kernel':True}
    check('M1_EMA_matrix_clipped_price_expectation_convexity',m1algebra)
    def hiddenprice():
        # Construct a declared finite-support last-stage kernel directly. Hidden prices
        #0.1 and1.0 with equal probability are integrated before choosing inventory.
        # A -2E continuation creates distinct informed actions: discharging at p1.0,
        # retaining/charging at p0.1. Averaging branch optima must be strictly optimistic.
        dp=object.__new__(EnhancedMarkovDP);dp.grid=np.array([1200.,2000.,3000.,4000.,5000.,6000.,7000.,8000.,9000.,10800.])
        dp.support=np.zeros((2,1,2));dp.weights=np.array([.5,.5]);dp.scales=np.ones(2)
        dp.future=np.tile(-2*dp.grid,(1,2,1));dp.price=np.array([[.1,1.]])
        E=6000.;net=1000.;q=0.;action=dp.action(0,E,net,q,np.zeros(2))
        grid=dp.grid;V=-2*grid
        candidates=np.unique(np.r_[grid[(grid>=E-5000/6/.9)&(grid<=E+.9*5000/6)],E-5000/6/.9,E+.9*5000/6,E,np.clip([E-net/.9,E-net*.9],E-5000/6/.9,E+.9*5000/6)])
        def value(y,p):
            delta=y-E;return 5*p*max(0,net+max(.9*delta,delta/.9))-2*y
        expected_values=np.array([value(y,.55) for y in candidates]);independent=candidates[np.argmin(expected_values)]
        assert abs(value(action,.55)-expected_values.min())<1e-10
        causal=.5*value(action,.1)+.5*value(action,1.)
        informed=.5*min(value(y,.1) for y in candidates)+.5*min(value(y,1.) for y in candidates)
        assert causal>informed+1
        return {'causal_action':action,'causal_value':causal,'hidden_price_branchwise_value':informed,'invalid_information_advantage':causal-informed}
    check('action_before_hidden_price_not_branchwise_min',hiddenprice)
    def terminal():
        errors=[]
        for initial in (1200.,6000.,10800.):
            # Start far enough from target to retain reachability; extreme target
            #requests are clipped by the same frozen physical executor.
            E=initial
            for left in range(23,-1,-1):
                request=1e9 if left%2 else -1e9
                new,c,d,em,sp,projection=execute(E,request,200.,300.,left,final=6000.)
                assert 1200-1e-6<=new<=10800+1e-6 and max(c,d)<=5000/6+1e-6
                assert abs(new-E-.9*c+d/.9)<1e-8;E=new
            errors.append(abs(E-6000.))
        assert max(errors)<1e-8
        return {'three_initial_states_endpoint_max_error':max(errors)}
    check('true_endpoint_reachable_projection',terminal)
    def actual_hidden_price():
        import nextgen_run
        data=dict(np.load(ROOT/'baseline_frozen/artifacts/data.npz'))
        selection=json.loads((ROOT/'baseline_frozen/artifacts/forecast-selection.json').read_text())
        cfg=Config(lower='M1',upper='state',scenario_method='conditional',grid=81,innovation_count=4,fusion_weight=.65,official_correction=.35)
        class StopAfterAction(Exception):pass
        original=nextgen_run.execute
        def first_action(d):
            captured={}
            def trap(*args,**kwargs):
                result=original(*args,**kwargs)
                captured['target']=args[1];captured['physical_result']=list(result)
                raise StopAfterAction
            nextgen_run.execute=trap
            try:nextgen_run.simulate(d,selection,[24],'q4_3',cfg)
            except StopAfterAction:pass
            finally:nextgen_run.execute=original
            assert captured
            return captured
        baseline=first_action(data);changed={k:v.copy() for k,v in data.items()};now=24*144
        changed['price'].ravel()[now:]+=11
        changed['load'].ravel()[now+1:]+=7000;changed['pv'].ravel()[now+1:]+=12000
        changed['forecast'].reshape(-1,24)[now//36+1:]+=13000
        other=first_action(changed)
        assert baseline==other,(baseline,other)
        return {'origin':now,'current_net_preserved':True,'current_price_and_future_realizations_mutated':True,'first_action':baseline,'scope':'First executed action only; replay intentionally stopped after committing that action.'}
    check('actual_replay_first_action_hides_current_price_with_fusion',actual_hidden_price)

    after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    if before!=after:cases.append({'name':'source_stability_during_tests','status':'FAIL','error':'source changed during audit'})
    report={'reviewer_id':'/root/upgrade_code_review','independent':True,'status':'PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
        'scope':'Independent small LP, stored-state metadata, EMA/convexity, hidden-price fixture and frozen executor boundary tests. Not full policy optimality, annual performance or full rollout perturbation acceptance.',
        'cases':cases,'source_hashes':before,'execution':{'command':sys.argv,'runtime_seconds':time.perf_counter()-started}}
    (ROOT/'review/nextgen-control-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'cases':[(c['name'],c['status']) for c in cases]}));return 0 if report['status']=='PASS' else 1
if __name__=='__main__':sys.exit(run())
