"""Causal affine contract planning, economic MPC, finite-state stochastic DP.

All energies are bus-side kWh except E (internal stored kWh). No actual future
price is exposed to a controller. Historical joint scenarios are read-only.
"""
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye, diags, hstack, vstack, kron, csr_matrix, coo_matrix
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor'))
import highspy

ETA=.9
EMIN=1200.
EMAX=10800.
TARGET=6000.
M=5000/6

def highslp(obj,A,b,eq,rhs,bounds,solver='choose'):
    """Same LP, native single-thread solver to avoid process oversubscription."""
    mat=vstack([A,eq],format='csr'); n=len(obj)
    lp=highspy.HighsLp();lp.num_col_=n;lp.num_row_=len(b)+len(rhs)
    lp.col_cost_=obj;lp.col_lower_=np.array([x[0] if x[0] is not None else -np.inf for x in bounds])
    lp.col_upper_=np.array([x[1] if x[1] is not None else np.inf for x in bounds])
    lp.row_lower_=np.r_[np.full(len(b),-np.inf),rhs];lp.row_upper_=np.r_[b,rhs]
    lp.a_matrix_.format_=highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_=mat.indptr;lp.a_matrix_.index_=mat.indices;lp.a_matrix_.value_=mat.data
    h=highspy.Highs();h.setOptionValue('output_flag',False);h.setOptionValue('threads',1)
    h.setOptionValue('solver',solver);h.passModel(lp);h.run()
    status=h.getModelStatus()
    return SimpleNamespace(success=status==highspy.HighsModelStatus.kOptimal,
         message=h.modelStatusToString(status),x=np.asarray(h.getSolution().col_value),fun=h.getObjectiveValue())

def feasible(E,t):
    R=143-t
    return (max(EMIN,E-M/ETA,TARGET-R*ETA*M),
            min(EMAX,E+ETA*M,TARGET+R*M/ETA))

def execute_target(E,target,q,net,t):
    lo,hi=feasible(E,t)
    x=float(np.clip(target,lo,hi))
    c=max(0.,(x-E)/ETA); d=max(0.,(E-x)*ETA)
    balance=q+d-c-net
    return c,d,x,max(-balance,0.),max(balance,0.),abs(target-x)

def affine_features(net,alpha=.2):
    center=net.mean(0); errors=net-center
    ema=np.zeros_like(errors)
    z=np.zeros(len(net))
    for t in range(net.shape[1]):
        z=(1-alpha)*z+alpha*errors[:,t]
        ema[:,t]=z
    return center,errors,ema

def affine_plan(net,prices,initial=TARGET,base=None,start=0,alpha=.2):
    """SAA LP in a finite-dimensional causal affine next-SOC policy class.

    E[s,t+1]=a[t]+g[block,0]*error[s,t]+g[block,1]*EMA(error)[s,t].
    The last row's features vanish, imposing the fixed terminal state only.
    Gains are restricted to [-10,10], a declared policy-class constraint.
    """
    S,T=net.shape; ST=S*T; B=4; G=2*B
    center,err,ema=affine_features(net,alpha)
    row=np.arange(ST); times=np.tile(np.arange(T),S)
    block=(start+times)//36
    vals0=err.ravel().copy();vals1=ema.ravel().copy()
    vals0[times==T-1]=0;vals1[times==T-1]=0
    F=coo_matrix((np.r_[vals0,vals1],(np.r_[row,row],np.r_[2*block,2*block+1])),shape=(ST,G)).tocsr()
    I=eye(ST,format='csr');Z=csr_matrix((ST,ST));R=kron(np.ones((S,1)),eye(T),format='csr')
    D=kron(eye(S),eye(T)-diags(np.ones(T-1),-1),format='csr')
    # q,c,d,e,E,a,g, optionally plus/minus contract amendments.
    A=hstack([-R,I,-I,-I,Z,csr_matrix((ST,T+G))],format='csr')
    dyn=hstack([csr_matrix((ST,T)),-ETA*I,I/ETA,Z,D,csr_matrix((ST,T+G))],format='csr')
    pol=hstack([csr_matrix((ST,T+3*ST)),I,-R,-F],format='csr')
    eq=vstack([dyn,pol],format='csr')
    rhs=np.zeros(2*ST);rhs[np.arange(S)*T]=initial
    p=prices.mean(0)
    obj=np.r_[np.zeros(T) if base is not None else p,np.full(2*ST,1e-7),5*prices.ravel()/S,
              np.zeros(ST+T+G)]
    bounds=[(0,None)]*T+[(0,M)]*(2*ST)+[(0,None)]*ST+[(EMIN,EMAX)]*(ST+T)+[(-10,10)]*G
    bounds[T+4*ST+T-1]=(TARGET,TARGET)
    if base is not None:
        n=eq.shape[1]
        A=hstack([A,csr_matrix((ST,2*T))],format='csr')
        eq=hstack([eq,csr_matrix((2*ST,2*T))],format='csr')
        amend=hstack([eye(T),csr_matrix((T,n-T)),-eye(T),eye(T)],format='csr')
        eq=vstack([eq,amend],format='csr');rhs=np.r_[rhs,base]
        obj=np.r_[obj,1.5*p,-.5*p];bounds +=[(0,None)]*(2*T)
    res=highslp(obj,A,-net.ravel(),eq,rhs,bounds,solver='ipm')
    if not res.success:raise RuntimeError(res.message)
    x=res.x;q=x[:T];a=x[T+4*ST:T+4*ST+T];g=x[T+4*ST+T:T+4*ST+T+G].reshape(B,2)
    states=x[T+3*ST:T+4*ST].reshape(S,T)
    prev=np.c_[np.full(S,initial),states[:,:-1]]
    c=np.maximum(states-prev,0)/ETA;d=np.maximum(prev-states,0)*ETA
    emerg=np.maximum(net+c-d-q,0)
    economic=(p@q if base is None else np.sum(1.5*p*np.maximum(q-base,0)-.5*p*np.maximum(base-q,0)))
    economic+=float(np.mean(np.sum(5*prices*emerg,axis=1)))
    return dict(q=q,a=a,g=g,center=center,alpha=alpha,expected_cost=float(economic),
                eq_residual=float(np.max(abs(eq@x-rhs))),
                ineq_violation=float(max(0,np.max(A@x+net.ravel()))),
                objective_after_cancellation_gap=float(abs(economic-res.fun)))

def posterior(net,observed,t,window=6):
    """Soft match only the latest already observed net loads; uniform shrinkage."""
    beg=max(0,t-window+1)
    hist=net[:,beg:t+1]
    scale=np.maximum(hist.std(0),10.)
    distance=np.mean(((hist-observed[None,beg:t+1])/scale)**2,axis=1)
    z=-.5*distance;z-=z.max();w=np.exp(z);w/=w.sum()
    return .8*w+.2/len(w)

@lru_cache(maxsize=512)
def fixed_matrices(T,S):
    I=eye(T,format='csr');Z=csr_matrix((T,T));R=kron(np.ones((S,1)),I,format='csr')
    A=hstack([R,-R,csr_matrix((S*T,T)),-eye(S*T)],format='csr')
    D=eye(T)-diags(np.ones(T-1),-1,shape=(T,T))
    eq=hstack([-ETA*I,I/ETA,D,csr_matrix((T,S*T))],format='csr')
    return A,eq

def mpc_action(net,prices,q,E,observed,t,stochastic=False):
    """Common-open-loop SAA MPC or conditional-mean MPC, rest of current day.

    First net load is observed; current price is conditional predicted price.
    Scenario future prices may affect costs, but future battery actions are
    common across scenarios. No scenario-specific clairvoyant recourse.
    """
    weights=posterior(net,observed,t)
    n=net[:,t:].copy();p=prices[:,t:].copy();n[:,0]=observed[t]
    if not stochastic:
        n=(weights@n)[None,:];p=(weights@p)[None,:];weights=np.ones(1)
    S,T=n.shape
    A,eq=fixed_matrices(T,S)
    obj=np.r_[np.full(2*T,1e-7),np.zeros(T),(5*weights[:,None]*p).ravel()]
    rhs=np.zeros(T);rhs[0]=E
    bounds=[(0,M)]*(2*T)+[(EMIN,EMAX)]*T+[(0,None)]*(S*T)
    bounds[3*T-1]=(TARGET,TARGET)
    res=highslp(obj,A,(q[None,t:]-n).ravel(),eq,rhs,bounds)
    if not res.success:raise RuntimeError(res.message)
    return float(res.x[2*T])

class MarkovDP:
    """Discretized finite-horizon stochastic DP, three net-load regimes.

    Historical adjacent regime counts determine transitions with one uniform
    pseudo-observation. Net-load emissions remain empirical within each regime;
    stage price is conditional regime mean, so price is never revealed early.
    This is an approximate Markov model, not an exact model of historical paths.
    """
    def __init__(self,net,prices,q,start=0,grid_size=321):
        S,T=net.shape;self.start=start;self.grid=np.linspace(EMIN,EMAX,grid_size)
        self.cuts=np.quantile(net,[1/3,2/3],axis=0).T
        labels=(net>self.cuts[:,0]).astype(int)+(net>self.cuts[:,1]).astype(int)
        self.meanprice=np.zeros((T,3));self.W=np.zeros((T,3,grid_size))
        step=self.grid[1]-self.grid[0]
        offsets=np.arange(-int(np.floor(M/ETA/step+1e-10)),int(np.floor(ETA*M/step+1e-10))+1)
        inds=np.arange(grid_size)[:,None]+offsets[None,:]
        mask=(inds<0)|(inds>=grid_size);ids=np.clip(inds,0,grid_size-1)
        delta=self.grid[ids]-self.grid[:,None]
        action=np.maximum(delta,0)/ETA-np.maximum(-delta,0)*ETA
        vnext=np.full((3,grid_size),np.inf)
        target=int(np.argmin(abs(self.grid-TARGET)));assert abs(self.grid[target]-TARGET)<1e-9
        vnext[:,target]=0
        self.max_bellman_residual=0.
        for t in range(T-1,-1,-1):
            cur=np.empty_like(vnext)
            counts=np.zeros((3,3))
            if t<T-1:np.add.at(counts,(labels[:,t],labels[:,t+1]),1)
            P=(counts+1/3)/(counts.sum(1,keepdims=True)+1)
            future=P@vnext
            self.W[t]=future
            for k in range(3):
                emission=net[labels[:,t]==k,t]
                price=prices[labels[:,t]==k,t]
                if not len(emission):emission=net[:,t];price=prices[:,t]
                self.meanprice[t,k]=price.mean()
                costs=5*price.mean()*np.maximum(emission[:,None,None]-q[t]+action[None,:,:],0)
                costs+=future[k,ids][None,:,:]
                costs[:,mask]=np.inf
                cur[k]=np.min(costs,axis=2).mean(0)
            vnext=cur
        self.V0=vnext

    def action(self,t,net,E,q):
        k=int(net>self.cuts[t,0])+int(net>self.cuts[t,1])
        lo,hi=feasible(E,self.start+t)
        ids=np.flatnonzero((self.grid>=lo-1e-8)&(self.grid<=hi+1e-8))
        if not len(ids):raise RuntimeError('DP grid has no feasible action')
        x=self.grid[ids];delta=x-E
        action=np.maximum(delta,0)/ETA-np.maximum(-delta,0)*ETA
        obj=5*self.meanprice[t,k]*np.maximum(net-q+action,0)+self.W[t,k,ids]
        if not np.isfinite(obj).any():raise RuntimeError('DP cannot reach terminal')
        return float(x[np.argmin(obj)])
