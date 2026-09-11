"""Independent extensive-form LP and exhaustive policy audit of finite SDDP."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import sddp

K=4;ETA=.9;M=5000*24/K;D=1+2*K
NET=[[0.,2000.],[1000.,3000.],[-500.,1000.],[800.,2500.]]
PRICES=[.2,1.3,.4,1.8]
INITIAL=np.r_[6000.,np.zeros(2*K)]

def specification(adjust):
    spec=[('sign',0)]
    for k in range(K):
        if adjust and k:spec.append(('revise',k))
        spec.append(('deliver',k))
    return spec

def extensive(spec,state,start=0,clairvoyant=False):
    """Separate bus c/d variables and direct tree recursion, no producer matrices.

    A variable is a dict {index:1}; scalar constants represent fixed state.
    Signing/revision controls are created BEFORE the next outcome branches.
    """
    bounds=[];cost=[];equal=[];rhs=[];upper=[];ub=[]
    def var(bound=(0,None),weight=0.):
        j=len(bounds);bounds.append(bound);cost.append(weight);return {j:1.}
    def constraint(terms,right,equality=False):
        row={};constant=0.
        for weight,expr in terms:
            if isinstance(expr,dict):
                for j,v in expr.items():row[j]=row.get(j,0.)+weight*v
            else:constant+=weight*float(expr)
        (equal if equality else upper).append(row);(rhs if equality else ub).append(right-constant)
    def visit(t,E,q,r,prob):
        if t==len(spec):return
        kind,hour=spec[t]
        if kind=='sign':
            newq=[var() for _ in range(K)]
            visit(t+1,E,newq,newq.copy(),prob)
        elif kind=='revise':
            newr=[r[k] if k<hour else var() for k in range(K)]
            visit(t+1,E,q,newr,prob)
        else:
            for demand in NET[hour]:
                node_prob=prob/2;price=PRICES[hour]
                c=var((0,M));d=var((0,M));em=var(weight=node_prob*5*price)
                bill=var(weight=node_prob*price);end=var((1200,10800))
                constraint([(1,end),(-1,E),(-ETA,c),(1/ETA,d)],0,True)
                constraint([(-1,r[hour]),(-1,d),(-1,em),(1,c)],-demand)
                constraint([(1.5,r[hour]),(-.5,q[hour]),(-1,bill)],0)
                constraint([(.5,r[hour]),(.5,q[hour]),(-1,bill)],0)
                qq=q.copy();rr=r.copy();qq[hour]=0.;rr[hour]=0.
                visit(t+1,end,qq,rr,node_prob)
    visit(start,float(state[0]),list(map(float,state[1:1+K])),list(map(float,state[1+K:])),1.)
    def matrix(rows):
        a=np.zeros((len(rows),len(bounds)))
        for i,row in enumerate(rows):
            for j,v in row.items():a[i,j]=v
        return a
    res=linprog(cost,A_ub=matrix(upper),b_ub=ub,A_eq=matrix(equal),b_eq=rhs,bounds=bounds,method='highs')
    assert res.success,res.message
    return float(res.fun)

def policy_value(model,state,t=0):
    if t==len(model.stages):return 0.
    stage=model.stages[t];total=0.
    for k,prob in enumerate(stage.probabilities):
        sol=stage.solve(state,k,model.cuts[t+1])
        total+=prob*(sol.stage_cost+policy_value(model,sol.state,t+1))
    return float(total)

def one_case(adjust):
    spec=specification(adjust)
    stages=[sddp.battery_stage(K,kind,h,NET[h],[PRICES[h]]*2,[.5,.5]) for kind,h in spec]
    exact=extensive(spec,INITIAL);model=sddp.SDDP(stages,seed=2121+int(adjust))
    def explore(i,x):x[0]=[1200.,3600.,6000.,8400.,10800.][i%5];return x
    batches=[]
    for batch in range(5):
        model.train(INITIAL,iterations=100,exploration=explore)
        lower=model.bound(INITIAL);policy=policy_value(model,INITIAL)
        assert lower<=exact+1e-5 and policy>=exact-1e-5
        batches.append({'iterations':(batch+1)*100,'lower_bound':lower,'exact_tree_cost':exact,'exact_policy_cost':policy})
        if policy-lower<1e-5:break
    assert policy-lower<1e-5,('SDDP not converged on toy',adjust,batches)
    # Check every cut at independently valued state probes at every stage.
    probes=[[] for _ in stages]
    for E in [1200.,3600.,6000.,8400.,10800.]:
        x=INITIAL.copy();x[0]=E;inputs,_=model.forward(x)
        for t,state in enumerate(inputs):probes[t].append(state.copy())
    # Include nonzero q/r states so both refund and increase branches are tested.
    for t,(kind,h) in enumerate(spec):
        if kind=='sign':continue
        for qval,rval in [(600.,300.),(600.,900.)]:
            x=INITIAL.copy();x[1+h:1+K]=qval;x[1+K+h:]=rval;probes[t].append(x)
    cut_max=-np.inf;probe_count=0;upper_max=-np.inf
    for t,states in enumerate(probes):
        for x in states:
            truth=extensive(spec,x,t);cuts=model.cuts[t]
            cut_max=max(cut_max,max(a+b@x-truth for a,b in cuts));probe_count+=1
            assert max(a+b@x for a,b in cuts)<=truth+1e-5
    # Root signing discards fully delivered contracts, so root gradients vanish.
    root_qr=max(np.abs(b[1:]).max() for _,b in model.cuts[0]);assert root_qr<1e-7
    # Deterministic one-delivery accounting: q100,r80 ->90; q100,r120 ->130.
    fee_checks=[]
    delivery=sddp.battery_stage(K,'deliver',0,[0.],[1.],[1.])
    for qval,rval,want in [(100.,80.,90.),(100.,120.,130.)]:
        x=INITIAL.copy();x[1]=qval;x[1+K]=rval
        sol=delivery.solve(x,0,[]);assert abs(sol.stage_cost-want)<1e-7
        assert abs(sol.state[1])+abs(sol.state[1+K])<1e-8
        fee_checks.append({'q':qval,'r':rval,'expected':want,'actual':sol.stage_cost})
    return {'adjustments':adjust,'stages':len(stages),'full_path_count':16,'status':'pass',
            'independent_extensive_cost':exact,'sddp_lower_bound':lower,'enumerated_policy_cost':policy,
            'bound_policy_gap':policy-lower,'training_batches':batches,'cut_state_probes':probe_count,
            'all_cut_max_lower_bound_violation':cut_max,'root_unused_contract_gradient_max_abs':root_qr,
            'one_delivery_fee_checks':fee_checks}

def main():
    before=hashlib.sha256((ROOT/'src/sddp.py').read_bytes()).hexdigest()
    cases=[one_case(False),one_case(True)]
    after=hashlib.sha256((ROOT/'src/sddp.py').read_bytes()).hexdigest();assert before==after,'Source changed during review run'
    result={'status':'pass_for_finite_battery_sddp','scope':'Independent K4 one-day finite-tree tests, with/without pre-noise revisions; exact extensive LP and all-path policy values. Not validation of original-data MPC terminal quality or universal negative-cost models.',
            'cases':cases,'reviewed_source_sha256':before,
            'input':{'K':K,'days':1,'net_support_kwh':NET,'prices_yuan_per_kwh':PRICES,'probabilities':[.5,.5],'initial_state':INITIAL.tolist()},
            'initial_bound_condition':'Every supplied theta lower bound must be a valid remaining-value lower bound. BatteryStage uses zero because all remaining costs are nonnegative.'}
    (ROOT/'review/sddp-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
