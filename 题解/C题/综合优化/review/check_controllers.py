"""Independent small checks of the new controllers; writes only this review folder."""
from pathlib import Path
from functools import lru_cache
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from controllers import MarkovDP,mpc_action,affine_plan,execute_target,ETA,M,TARGET

def main():
    result={'scope':'Independent finite examples, not final annual acceptance','checks':{}}
    result['source_hashes']={n:hashlib.sha256((ROOT/'src'/n).read_bytes()).hexdigest() for n in ['controllers.py','run_comparison.py']}
    # Explicit recursive enumeration, independently building action sets from physical distances.
    net=np.array([[50.,100.,-180.],[200.,300.,-100.],[400.,0.,-200.],[300.,500.,-400.]])
    prices=np.array([[.4,1.4,.4],[.5,1.2,.4],[.3,1.6,.5],[.5,1.5,.3]])
    q=np.array([100.,50.,100.]);dp=MarkovDP(net,prices,q,start=141,grid_size=33)
    grid=dp.grid
    cuts=np.quantile(net,[1/3,2/3],axis=0).T
    regimes=np.array([[int(x>cuts[t,0])+int(x>cuts[t,1]) for t,x in enumerate(row)] for row in net])
    transition=[]
    for t in range(3):
        counts=np.zeros((3,3))
        if t<2:
            for path in range(len(net)):counts[regimes[path,t],regimes[path,t+1]]+=1
        transition.append((counts+1/3)/(counts.sum(1)[:,None]+1))
    @lru_cache(None)
    def exhaustive(t,k,E_index):
        E=grid[E_index]
        if t==3:return 0. if abs(E-TARGET)<1e-8 else float('inf')
        sample=np.flatnonzero(regimes[:,t]==k)
        if len(sample)==0:sample=np.arange(len(net))
        meanprice=float(prices[sample,t].mean())
        candidates=[j for j,x in enumerate(grid) if -M/ETA-1e-8<=x-E<=ETA*M+1e-8]
        values=[]
        for path in sample:
            choices=[]
            for j in candidates:
                delta=grid[j]-E
                bus_change=max(delta,0)/ETA-max(-delta,0)*ETA
                stage=5*meanprice*max(net[path,t]-q[t]+bus_change,0)
                continuation=sum(transition[t][k,k2]*exhaustive(t+1,k2,j) for k2 in range(3))
                choices.append(stage+continuation)
            values.append(min(choices))
        return float(np.mean(values))
    truth=np.array([[exhaustive(0,k,j) for j in range(len(grid))] for k in range(3)])
    finite=np.isfinite(truth)
    assert np.array_equal(finite,np.isfinite(dp.V0))
    gap=float(np.max(abs(truth[finite]-dp.V0[finite])))
    assert gap<1e-8
    result['checks']['dp_vs_explicit_recursive_enumeration']={'grid_points':33,'horizon':3,'paths':4,'maximum_value_difference':gap}
    # Future-opportunity-cost toy: holding battery in cheap first interval is optimal.
    nt=np.array([[100.,100.,0.]]);pp=np.array([[.4,1.4,.4]]);contract=np.array([0.,0.,100/ETA**2])
    targets=[mpc_action(nt,pp,contract,6000.,np.array([100.]),0,stochastic=s) for s in [False,True]]
    assert max(abs(x-6000) for x in targets)<1e-7
    result['checks']['mpc_known_toy_first_target']={'deterministic':targets[0],'common_scenario':targets[1],'expected':6000.}
    # Scenario rollout of the affine policy must reproduce the LP's own cost without projection.
    affine_checks=[]
    for start in [0,36,72,108]:
        T=144-start;s=np.arange(7)[:,None];t=np.arange(T)[None,:]
        n=100+70*np.sin((t+start)/12)+(s-3)*(15+8*np.cos(t/9))
        p=np.broadcast_to(.3+.1*np.cos((t+start)/20),n.shape).copy()
        base=None if start==0 else np.full(T,110.)
        plan=affine_plan(n,p,initial=6000.,base=base,start=start)
        costs=[];projection=0.;terminal=0.
        for sample in range(len(n)):
            E=6000.;z=0.;em=[]
            for j in range(T):
                k=(start+j)//36;err=n[sample,j]-plan['center'][j]
                z=.8*z+.2*err
                target=plan['a'][j]+plan['g'][k]@np.array([err,z]) if j<T-1 else 6000.
                c,d,E,e,spill,proj=execute_target(E,target,plan['q'][j],n[sample,j],start+j)
                projection=max(projection,proj);em.append(e)
            terminal=max(terminal,abs(E-6000.))
            ordinary=p[sample]@plan['q'] if base is None else np.sum(p[sample]*(1.5*np.maximum(plan['q']-base,0)-.5*np.maximum(base-plan['q'],0)))
            costs.append(ordinary+5*p[sample]@np.array(em))
        gap=abs(np.mean(costs)-plan['expected_cost'])
        assert gap<1e-6 and projection<1e-6 and terminal<1e-7
        affine_checks.append({'release_hour':start/6,'cost_difference':float(gap),'maximum_projection':projection,'terminal_error':terminal,'lp_eq_residual':plan['eq_residual']})
    result['checks']['affine_scenario_rollout']=affine_checks
    result['status']='small_checks_pass'
    (ROOT/'review/controller-small-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
