"""Convex sample-average planning and causal battery execution; all energy in kWh."""
from functools import lru_cache
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye, hstack, vstack, kron, csr_matrix, diags

@lru_cache(maxsize=256)
def matrices(T,S,adjust,eta):
    I=eye(T,format='csr'); Z=csr_matrix((T,T)); R=kron(np.ones((S,1)),I,format='csr')
    # -q + c - d - emergency <= -net demand
    Aub=hstack([-R,R,-R,csr_matrix((S*T,T)),-eye(S*T)],format='csr')
    D=eye(T)-diags(np.ones(T-1),-1,shape=(T,T))
    Aeq=hstack([Z,-eta*I,I/eta,D,csr_matrix((T,S*T))],format='csr')
    if adjust:
        Aub=hstack([Aub,csr_matrix((S*T,2*T))],format='csr')
        Aeq=hstack([Aeq,csr_matrix((T,2*T))],format='csr')
        Aeq=vstack([Aeq,hstack([I,Z,Z,Z,csr_matrix((T,S*T)),-I,I])],format='csr')
    return Aub,Aeq

def solve(net,prices,initial=6000.,terminal=6000.,base=None,refund=True,eta=.9,
          power=5000.,emin=1200.,emax=10800.,penalty=5.,hard=False):
    S,T=net.shape; adjust=base is not None; p=prices.mean(0)
    Aub,Aeq=matrices(T,S,adjust,eta)
    obj=np.r_[np.zeros(T) if adjust else p,np.full(2*T,1e-7),np.zeros(T),penalty*prices.ravel()/S]
    if adjust: obj=np.r_[obj,1.5*p,(-.5 if refund else .5)*p]
    rhs=np.zeros(T);rhs[0]=initial
    if adjust:rhs=np.r_[rhs,base]
    bounds=[(0,None)]*T+[(0,power/6)]*(2*T)+[(emin,emax)]*T+[(0,0 if hard else None)]*(S*T)
    bounds[4*T-1]=(terminal,terminal)
    if adjust: bounds += [(0,None)]*(2*T)
    res=linprog(obj,A_ub=Aub,b_ub=-net.ravel(),A_eq=Aeq,b_eq=rhs,bounds=bounds,method='highs',
                options={'dual_feasibility_tolerance':1e-8,'primal_feasibility_tolerance':1e-8})
    if not res.success: raise RuntimeError(f'LP failed: {res.message}')
    x=res.x; q=x[:T];c=x[T:2*T];d=x[2*T:3*T]
    # Analytic removal of any numerical simultaneous charge/discharge, preserving SOC.
    remove=np.minimum(c,d/eta**2);c=c-remove;d=d-eta**2*remove
    state=np.r_[initial,initial+np.cumsum(eta*c-d/eta)]
    em=np.maximum(net+c-d-q,0)
    if adjust:
        cost=float(np.sum(1.5*p*np.maximum(q-base,0)+(-.5 if refund else .5)*p*np.maximum(base-q,0))+
                   penalty*np.mean(np.sum(prices*em,axis=1)))
    else: cost=float(p@q+penalty*np.mean(np.sum(prices*em,axis=1)))
    return {'q':q,'c':c,'d':d,'state':state,'expected_cost':cost,'lp_objective':float(res.fun),
            'eq_residual':float(np.max(np.abs(Aeq@x-rhs))),
            'ineq_violation':float(max(0,np.max(Aub@x+net.ravel()))),
            'duality_gap':float(abs(res.fun-(np.dot(rhs,res.eqlin.marginals)+np.dot(-net.ravel(),res.ineqlin.marginals)+
                sum(lo*m for (lo,hi),m in zip(bounds,res.lower.marginals) if lo is not None)+
                sum(hi*m for (lo,hi),m in zip(bounds,res.upper.marginals) if hi is not None))))}

def execute_slot(q,net,E,c_plan,d_plan,t,controller='fixed',eta=.9,power=5000.,emin=1200.,emax=10800.,terminal=6000.):
    if controller=='fixed': c,d=c_plan,d_plan
    elif controller=='greedy':
        balance=q-net
        nextE=E+eta*min(max(balance,0),power/6,(emax-E)/eta)-min(max(-balance,0),power/6,eta*(E-emin))/eta
        # Backward reachable terminal set prevents last-day battery depletion borrowing.
        left=143-t
        lower=max(emin,terminal-left*eta*power/6)
        upper=min(emax,terminal+left*power/(6*eta))
        nextE=np.clip(nextE,lower,upper)
        c=max(0,(nextE-E)/eta);d=max(0,(E-nextE)*eta)
    else: raise ValueError(controller)
    nextE=E+eta*c-d/eta
    balance=q+d-c-net
    emergency=max(-balance,0);spill=max(balance,0)
    return c,d,nextE,emergency,spill

def settlement(q,r,emergency,price,refund=True,penalty=5.):
    planned=price*q
    increase=1.5*price*np.maximum(r-q,0)
    reduction=(-.5 if refund else .5)*price*np.maximum(q-r,0)
    emerg=penalty*price*emergency
    return {'planned_cost':float(planned.sum()),'increase_cost':float(increase.sum()),
            'reduction_net_cost':float(reduction.sum()),'emergency_cost':float(emerg.sum()),
            'total_cost':float((planned+increase+reduction+emerg).sum())}
