"""Bounded independent state/contract and M1 operator checks; no annual replay."""
from pathlib import Path
import sys, json, hashlib, time
sys.dont_write_bytecode = True
import numpy as np
from scipy.optimize import linprog
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nextgen_scenarios import Config, state_paths
from nextgen_control import EnhancedMarkovDP, affine_plan

def digest(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def make_bundle(net, price, weights, alpha=.2):
    net=np.asarray(net);price=np.asarray(price);weights=np.asarray(weights)
    center=weights@net;fp=weights@price;rn=net-center;rp=price-fp
    seed=np.array([20.,-15.,.07,-.02])
    hs=np.array([seed+np.array([8*i,-3*i,.01*i,-.02*i]) for i in range(len(net))])
    return {'net':net,'prices':price,'weights':weights,'seed':seed,
            'forecast':{'net':center,'price':fp},'origins':np.arange(len(net))*144,
            'states':state_paths(rn,rp,seed,alpha,True),
            'history_states':state_paths(rn,rp,hs,alpha,True),
            'history_net_error':rn,'history_price_error':rp,'history_seeds':hs}

def explicit_action(E, n, q, price, grid, future):
    # c,d,E_next,e,theta. Independent explicit charge/discharge LP, with
    # every convex chord represented by a supporting affine epigraph row.
    slope=np.diff(future)/np.diff(grid)
    assert np.min(np.diff(slope),initial=0)>-1e-7
    intercept=future[:-1]-slope*grid[:-1]
    A=[[1.,-1.,0.,-1.,0.]];rhs=[q-n]
    for m,b in zip(slope,intercept):A.append([0,0,m,0,-1]);rhs.append(-b)
    result=linprog([0,0,0,5*price,1],A_ub=A,b_ub=rhs,
        A_eq=[[-.9,1/.9,1,0,0]],b_eq=[E],
        bounds=[(0,5000/6),(0,5000/6),(1200,10800),(0,None),(None,None)],method='highs')
    assert result.success,result.message
    return float(result.fun),float(result.x[2])

def action_value(y,E,n,q,p,grid,future):
    d=y-E
    return 5*p*max(0,n-q+max(.9*d,d/.9))+float(np.interp(y,grid,future))

def independent_kernel(points,queries,scale,weights):
    distance=np.sum(((np.atleast_2d(queries)[:,None,:]-points[None,:,:])/scale)**2,axis=2)
    log=-.5*distance+np.log(weights)[None,:]
    out=np.exp(log-log.max(axis=1,keepdims=True));return out/out.sum(axis=1,keepdims=True)

def verify_complete_bellman(dp,b,q,alpha,tail_price):
    """Rebuild all short stages, including both support projections and LP minima.

    Reads fitted A/innovation parameters, but does not call production transition,
    kernel, convolution, action selection, or Bellman recursion to form values.
    """
    net=b['net'];states=b['states'];weights=b['weights'];S,T=net.shape;D=states.shape[-1]
    v=np.tile(-tail_price*dp.grid,(S,1));values=[None]*T
    raw_gap=price_gap=rowsum_gap=0.
    for j in range(T-1,-1,-1):
        model=dp.models[(j%144)//36];x=states[:,j];proposal=x@model['A'].T+model['b']
        u=model['innovations'];mass=model['mass'];ns=np.repeat(proposal[:,None,:],len(u),axis=1)
        ns[:,:,0]+=u[None,:,0];ns[:,:,1]=(1-alpha)*x[:,None,1]+alpha*ns[:,:,0]
        price=np.maximum(.001,b['forecast']['price'][j]+proposal[:,None,2]+u[None,:,1])
        ns[:,:,2]=price-b['forecast']['price'][j]
        ns[:,:,3]=(1-alpha)*x[:,None,3]+alpha*ns[:,:,2]
        mean=price@mass
        if j==T-1:raw=np.tile(v[0],(S,1))
        else:
            k=independent_kernel(states[:,j+1],ns.reshape(-1,D),dp.scales,weights).reshape(S,-1,S)
            P=np.sum(k*mass[None,:,None],axis=1)
            rowsum_gap=max(rowsum_gap,float(np.max(abs(P.sum(1)-1))))
            raw=P@v
        raw_gap=max(raw_gap,float(np.max(abs(raw-dp.future[j]))))
        price_gap=max(price_gap,float(np.max(abs(mean-dp.price[j]))))
        W=independent_kernel(x,x,dp.scales,weights);future=W@raw;mean=W@mean
        v=np.array([[explicit_action(float(E),net[s,j],q[j],mean[s],dp.grid,future[s])[0]
                     for E in dp.grid] for s in range(S)])
        values[j]=v
    initial_gap=float(np.max(abs(v-dp.initial_values)))
    assert max(raw_gap,price_gap,initial_gap)<1e-6,(raw_gap,price_gap,initial_gap)
    probe={'j':4,'support':2,'inventory':6000.}
    j,s,E=probe.values();s=int(s);j=int(j)
    x=states[s,j];W=independent_kernel(states[:,j],x,dp.scales,weights)[0]
    actual=dp.action(j,E,net[s,j],q[j],x)
    online=action_value(actual,E,net[s,j],q[j],float(W@dp.price[j]),dp.grid,W@dp.future[j])
    pos=int(np.flatnonzero(abs(dp.grid-E)<1e-8)[0]);gap=abs(online-values[j][s,pos])
    assert gap<1e-6,gap
    return {'passed':True,'raw_continuation_gap':raw_gap,'conditional_price_gap':price_gap,
            'initial_value_gap':initial_gap,'row_stochastic_gap':rowsum_gap,
            'support_operator_objective_gap':gap,'support_operator_probe':probe,
            'explicit_LP_states':S*T*len(dp.grid)}

def run():
    start=time.perf_counter()
    paths=['src/nextgen_scenarios.py','src/nextgen_control.py','src/nextgen_run.py']
    hashes={p:digest(p) for p in paths};rng=np.random.default_rng(140926)
    S,T=5,7;w=np.array([.1,.15,.2,.25,.3])
    n=rng.uniform(-900,1900,(S,T));p=rng.uniform(.03,1.6,(S,T));q=np.full(T,300.)
    alpha_results=[];counter=None;max_lp_gap=0.;largest_coefficient_gap=0.;bellman=[]
    for alpha in [.1,.2,.5]:
        b=make_bundle(n,p,w,alpha);cfg=Config(lower='M1',upper='state',alpha=alpha,grid=41,innovation_count=4)
        dp=EnhancedMarkovDP(b,q,0,cfg,.7)
        bellman.append({'alpha':alpha,**verify_complete_bellman(dp,b,q,alpha,.7)})
        manual=[];zn,zp,ep=b['seed'][1],b['seed'][3],b['seed'][2]
        for j in range(T):
            zn=(1-alpha)*zn+alpha*(n[0,j]-b['forecast']['net'][j])
            manual.append([n[0,j]-b['forecast']['net'][j],zn,ep,zp])
            ep=p[0,j]-b['forecast']['price'][j];zp=(1-alpha)*zp+alpha*ep
        err=float(np.max(np.abs(np.asarray(manual)-b['states'][0])))
        assert err<1e-10
        altered=(p-b['forecast']['price']).copy();altered[:,2]+=3
        states2=state_paths(n-b['forecast']['net'],altered,b['seed'],alpha,True)
        assert np.array_equal(states2[:,:3],b['states'][:,:3])
        assert not np.array_equal(states2[:,3],b['states'][:,3])
        alpha_results.append({'alpha':alpha,'manual_state_error':err,'hidden_current_price_state_unchanged':True})
        # Reconstruct the online kernel without calling its production helper.
        for j in range(T):
            for s in range(S):
                x=b['states'][s,j];distance=np.sum(((b['states'][:,j]-x)/dp.scales)**2,axis=1)
                logits=-.5*distance+np.log(w);kw=np.exp(logits-logits.max());kw/=kw.sum()
                online_future=kw@dp.future[j];online_price=float(kw@dp.price[j])
                coefficient_gap=float(np.max(np.abs(online_future-dp.future[j,s])))
                largest_coefficient_gap=max(largest_coefficient_gap,coefficient_gap)
                for E in [3000.,6000.,9000.]:
                    expected,y=explicit_action(E,n[s,j],q[j],online_price,dp.grid,online_future)
                    actual=dp.action(j,E,n[s,j],q[j],x)
                    gap=abs(action_value(actual,E,n[s,j],q[j],online_price,dp.grid,online_future)-expected)
                    max_lp_gap=max(max_lp_gap,gap);assert gap<1e-6
                    # Compare the online action to the *unsmoothed support* update
                    # actually used in backward recursion; a gap is an approximation
                    # finding, not a physical-feasibility or LP-solving failure.
                    support_value,support_y=explicit_action(E,n[s,j],q[j],dp.price[j,s],dp.grid,dp.future[j,s])
                    regret=action_value(actual,E,n[s,j],q[j],dp.price[j,s],dp.grid,dp.future[j,s])-support_value
                    if counter is None or regret>counter['support_operator_regret']:
                        counter={'alpha':alpha,'j':j,'support':s,'inventory':E,
                                 'kernel_self_weight':float(kw[s]),'support_price':float(dp.price[j,s]),
                                 'online_smoothed_price':online_price,'online_action':actual,
                                 'support_greedy_action':support_y,'support_operator_regret':float(regret)}
    # The unprojected VAR support is intentionally different after the fix.
    # Consistency is checked against the fully declared projected operator above.
    # Full-gain planning: paired histories agree before the future midnight and
    # before06h; disagreement begins only at that06h delivery.
    T=82;clock=np.arange(T);net=np.tile(400+80*np.sin(clock/7),(4,1));price=np.tile(.5+.2*np.cos(clock/9),(4,1))
    net[1,72:]+=500;price[1,72:]+=.4
    price[2:,:36]+=.2;net[3,72:]-=200;price[3,72:]-=.2
    bundle=make_bundle(net,price,np.array([.1,.2,.3,.4]));cfg=Config(upper='state',gain_bound=10.)
    plan=affine_plan(bundle,108,6000,cfg,base=np.full(T,500.),adjust=True)
    spread=0.
    for i,k in [(0,1),(2,3)]:
        spread=max(spread,float(np.max(abs(plan['scenario_q'][i,36:]-plan['scenario_q'][k,36:]))),
                   float(np.max(abs(plan['scenario_r'][i,72:]-plan['scenario_r'][k,72:]))))
    root_spread=float(np.ptp(plan['scenario_r'][:,:36],axis=0).max())
    assert max(spread,root_spread)<1e-7 and plan['objective_gap']<1e-5
    assert hashes=={p:digest(p) for p in paths},'Production sources changed during audit'
    report={'reviewer_id':'/root/independent_review','independent':True,'status':'PASS',
            'scope':'bounded_static_and_small_mathematical_checks_no_annual_replay',
            'checks':{'origin_state_recursion':alpha_results,
                      'online_M1_action_vs_independent_explicit_LP':{'passed':True,'max_objective_gap':max_lp_gap,'cases':3*7*5*3},
                      'complete_short_projected_Bellman_vs_explicit_LPs':bellman,
                      'paired_future_contract_nonanticipation':{'passed':True,'max_paired_spread':spread,'root_revision_spread':root_spread}},
            'finding':{'id':'NM-1','status':'resolved_by_operator_correction',
                       'description':'Backward support updates now use the same current-state probability projection as online actions.',
                       'previous_evidence':'review/history/origin-math-checks-before-NM1-fix.json',
                       'previous_evidence_sha256':digest('review/history/origin-math-checks-before-NM1-fix.json'),
                       'diagnostic_raw_VAR_vs_projected_operator':counter,
                       'max_raw_VAR_vs_projected_continuation_gap':largest_coefficient_gap},
            'source_hashes':hashes,'audit_source_sha256':digest('review/check_origin_math.py'),
            'runtime_seconds':time.perf_counter()-start}
    (ROOT/'review/origin-math-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks_passed':True,'finding':'NM-1 resolved','max_lp_gap':max_lp_gap,'bellman':bellman},ensure_ascii=False))

if __name__=='__main__':run()
