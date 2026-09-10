"""Causal affine-policy SAA MPC and one-dimensional convex Markov DP."""
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
from scipy.sparse import coo_matrix,csr_matrix,vstack,eye
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor'))
import highspy

ETA=.9; M=5000/6; EMIN=1200.; EMAX=10800.; INITIAL=6000.

def lp_solve(obj,A,b,bounds,solver='ipm'):
    A=A.tocsr();p=highspy.HighsLp();p.num_col_=len(obj);p.num_row_=len(b)
    p.col_cost_=np.asarray(obj);p.col_lower_=np.array([a if a is not None else -np.inf for a,z in bounds]);p.col_upper_=np.array([z if z is not None else np.inf for a,z in bounds])
    p.row_lower_=np.full(len(b),-np.inf);p.row_upper_=np.asarray(b)
    p.a_matrix_.format_=highspy.MatrixFormat.kRowwise;p.a_matrix_.start_=A.indptr;p.a_matrix_.index_=A.indices;p.a_matrix_.value_=A.data
    h=highspy.Highs();h.setOptionValue('output_flag',False);h.setOptionValue('threads',1);h.setOptionValue('solver',solver);h.passModel(p);h.run()
    if h.getModelStatus()!=highspy.HighsModelStatus.kOptimal:raise RuntimeError(h.modelStatusToString(h.getModelStatus()))
    x=np.array(h.getSolution().col_value)
    return SimpleNamespace(x=x,fun=h.getObjectiveValue(),violation=float(max(0,np.max(A@x-b))))

def features(net):
    err=net-net.mean(0);ema=np.zeros_like(err);avg=np.zeros_like(err);z=np.zeros(len(net))
    for t in range(net.shape[1]):
        z=.8*z+.2*err[:,t];ema[:,t]=z;avg[:,t]=err[:,max(0,t-35):t+1].mean(1)
    return err,ema,avg

def affine_plan(net,prices,asof,E,base=None,adjust=False,affine=True,tail_price=0.,terminal=None,tail_cuts=None,daily_closed=False,solver='ipm'):
    """Node-time affine recourse. Future contracts use ONLY pre-release errors.

    Scenario states are feasible in-sample; unseen paths are projected physically.
    Future official forecast innovations are omitted from this restricted policy
    class, while actual current releases are used by the scenario producer.
    """
    S,T=net.shape;K=S*T;clock=np.arange(asof,asof+T); day0=asof//144
    blocks=clock//36-clock[0]//36;B=int(blocks.max()+1);days=clock//144-day0;D=int(days.max()+1)
    err,ema,avg=features(net)
    # a_q, a_r, a_E, g_q, g_r, g_E, emergency, delivered contract charge.
    aq=0; ar=T; ae=2*T;gq=3*T;gr=gq+2*D;ge=gr+2*B;em=ge+2*B;bill=em+K;theta=bill+K;N=theta+(S if tail_cuts else 0)
    def expr(which):
        rows=[];cols=[];vals=[];constant=np.zeros(K)
        for s in range(S):
            for j,ts in enumerate(clock):
                row=s*T+j;di=days[j];bi=blocks[j]
                if which=='Q' and di==0 and base is not None:
                    constant[row]=base[j];continue
                if which=='Q': a=aq+j;g=gq+2*di;reveal=(ts//144)*144-asof
                elif which=='R': a=ar+j;g=gr+2*bi;reveal=(ts//36)*36-asof
                else:a=ae+j;g=ge+2*bi;reveal=j+1
                rows.append(row);cols.append(a);vals.append(1.)
                if affine and reveal>0:
                    values=(err[s,j],ema[s,j]) if which=='E' else (avg[s,reveal-1],ema[s,reveal-1])
                    for k,val in enumerate(values):rows.append(row);cols.append(g+k);vals.append(val)
        return coo_matrix((vals,(rows,cols)),shape=(K,N)).tocsr(),constant
    Q,q0=expr('Q'); R,r0=expr('R') if adjust else (Q,q0);X,x0=expr('E')
    if adjust:
        firstblock=np.tile(clock%144<36,S).astype(float)
        from scipy.sparse import diags
        keep=diags(firstblock);R=keep@Q+(eye(K)-keep)@R;r0=firstblock*q0+(1-firstblock)*r0
    shift=coo_matrix((np.ones(S*(T-1)),(np.concatenate([np.arange(s*T+1,(s+1)*T) for s in range(S)]),np.concatenate([np.arange(s*T,(s+1)*T-1) for s in range(S)]))),shape=(K,K)).tocsr()
    Delta=X-shift@X; delta0=np.zeros(K);delta0[np.arange(S)*T]=-E
    U=coo_matrix((np.ones(K),(np.arange(K),em+np.arange(K))),shape=(K,N)).tocsr()
    F=coo_matrix((np.ones(K),(np.arange(K),bill+np.arange(K))),shape=(K,N)).tocsr()
    mats=[-Q,-R,X,-X,Delta,-Delta,ETA*Delta-R-U,Delta/ETA-R-U,1.5*R-.5*Q-F,.5*R+.5*Q-F]
    rhs=[q0,r0,np.full(K,EMAX),np.full(K,-EMIN),np.full(K,ETA*M)-delta0,np.full(K,M/ETA)+delta0,
         r0-net.ravel()-ETA*delta0,r0-net.ravel()-delta0/ETA,.5*q0-1.5*r0,-.5*q0-.5*r0]
    last=np.arange(S)*T+T-1
    if terminal is not None:
        mats +=[X[last],-X[last]];rhs +=[np.full(S,terminal),np.full(S,-terminal)]
    if daily_closed:
        mids=np.flatnonzero(np.tile((clock+1)%144==0,S))
        mats +=[X[mids],-X[mids]];rhs +=[np.full(len(mids),6000.),np.full(len(mids),-6000.)]
    if tail_cuts:
        Theta=coo_matrix((np.ones(S),(np.arange(S),theta+np.arange(S))),shape=(S,N)).tocsr()
        for alpha,beta in tail_cuts:mats.append(beta*X[last]-Theta);rhs.append(np.full(S,-alpha))
    obj=np.zeros(N);obj[em:bill]=(5*prices/S).ravel();obj[bill:theta]=(prices/S).ravel()
    if tail_cuts:obj[theta:]=1/S
    obj-=tail_price*np.asarray(X[last].mean(0)).ravel()
    bounds=[(None,None)]*(3*T)+[(-10,10) if affine else (0,0)]*(2*D+4*B)+[(0,None)]*(2*K+(S if tail_cuts else 0))
    sol=lp_solve(obj,vstack(mats),np.concatenate(rhs),bounds,solver);x=sol.x
    qs=(Q@x+q0).reshape(S,T);rs=(R@x+r0).reshape(S,T);xs=(X@x).reshape(S,T)
    prev=np.c_[np.full(S,E),xs[:,:-1]];delta=xs-prev
    emer=np.maximum(net-rs+np.maximum(ETA*delta,delta/ETA),0)
    true=float(np.mean(np.sum(prices*(np.maximum(1.5*rs-.5*qs,.5*rs+.5*qs)+5*emer),axis=1))-tail_price*xs[:,-1].mean())
    if tail_cuts:true+=float(np.maximum(0,np.max([a+b*xs[:,-1] for a,b in tail_cuts],axis=0)).mean())
    return {'q':qs.mean(0),'r':rs.mean(0),'a':x[ae:ae+T],'g':x[ge:ge+2*B].reshape(B,2),
            'center':net.mean(0),'asof':asof,'lp_violation':sol.violation,'objective_gap':abs(true-sol.fun),
            'scenario_q':qs,'scenario_r':rs,'scenario_state':xs,'forecast_contract_gain':x[gq:gr]}

def prune_cuts(cuts):
    """Remove globally inactive lines on [EMIN, EMAX], preserving the envelope."""
    by_slope={}
    for a,b in [[0.,0.]]+list(cuts):by_slope[b]=max(a,by_slope.get(b,-np.inf))
    hull=[];starts=[]
    for b,a in sorted(by_slope.items()):
        start=-np.inf
        while hull:
            pa,pb=hull[-1];start=(pa-a)/(b-pb)
            if start>starts[-1]:break
            hull.pop();starts.pop()
        if not hull:start=-np.inf
        hull.append([a,b]);starts.append(start)
    keep=[line for i,line in enumerate(hull) if starts[i]<=EMAX and (i==len(hull)-1 or starts[i+1]>=EMIN)]
    probes=np.linspace(EMIN,EMAX,301)
    assert np.max(np.abs(np.max([a+b*probes for a,b in [[0.,0.]]+list(cuts)],axis=0)-np.max([a+b*probes for a,b in keep],axis=0)))<1e-6
    return keep

def execute(E,target,q,net,remaining,closed=False,t=0,final=6000.):
    lo=max(EMIN,E-M/ETA);hi=min(EMAX,E+ETA*M)
    if closed: remaining=143-t
    if final is not None:
        lo=max(lo,final-remaining*ETA*M);hi=min(hi,final+remaining*M/ETA)
    if lo>hi+1e-6:raise RuntimeError('Unreachable terminal inventory')
    nex=float(np.clip(target,lo,hi));delta=nex-E;c=max(delta,0)/ETA;d=max(-delta,0)*ETA
    balance=q+d-c-net
    return nex,c,d,max(-balance,0),max(balance,0),abs(nex-target)

def inf_convolution(grid,V,net_minus_q,price):
    """Exact convex PL infimal convolution, then interpolate on the state grid.

    min_x V(x)+5p max(0,n-q+g(x-E)). Slopes of two convex PL
    functions are merged. Interpolation is an upper chord approximation.
    """
    a=net_minus_q;ys=np.array(sorted(set([-ETA*M,M/ETA,0.,float(np.clip(a/ETA,-ETA*M,M/ETA)),float(np.clip(a*ETA,-ETA*M,M/ETA))])))
    cost=5*price*np.maximum(0,a+np.maximum(-ETA*ys,-ys/ETA))
    lengths=np.r_[np.diff(grid),np.diff(ys)];slopes=np.r_[np.diff(V)/np.diff(grid),np.diff(cost)/np.diff(ys)]
    order=np.argsort(slopes,kind='stable');knots=np.r_[grid[0]+ys[0],grid[0]+ys[0]+np.cumsum(lengths[order])]
    values=np.r_[V[0]+cost[0],V[0]+cost[0]+np.cumsum(lengths[order]*slopes[order])]
    return np.interp(grid,knots,values)

class MarkovDP:
    """Observable net-load bins, conditional price means, continuous actions.

    Future provisional contracts use the planner's common nominal quantities.
    Grid value interpolation approximates convex Bellman functions; it is not
    advertised as SDDP or a global lower bound.
    """
    def __init__(self,net,prices,q,tail_price,grid_size=321,terminal=None,tail_cuts=None):
        S,T=net.shape;self.grid=np.linspace(EMIN,EMAX,grid_size);self.T=T
        cuts=np.quantile(net,[1/3,2/3],axis=0).T;self.cuts=cuts
        labels=(net>cuts[:,0]).astype(int)+(net>cuts[:,1]).astype(int)
        self.future=np.zeros((T,3,grid_size));self.price=np.zeros((T,3))
        # Convex exact terminal penalty ensures true-end target in the model;
        # physical reachability is separately enforced in execution.
        v=np.repeat((-tail_price*self.grid)[None,:],3,axis=0)
        if tail_cuts:v=np.repeat(np.maximum(0,np.max([a+b*self.grid for a,b in tail_cuts],axis=0))[None,:],3,axis=0)
        if terminal is not None:v=np.repeat((1000*np.abs(self.grid-terminal))[None,:],3,axis=0)
        for j in range(T-1,-1,-1):
            counts=np.zeros((3,3))
            if j<T-1:np.add.at(counts,(labels[:,j],labels[:,j+1]),1.)
            P=(counts+1/3)/(counts.sum(1,keepdims=True)+1)
            nxt=P@v;self.future[j]=nxt;cur=np.empty_like(v)
            for k in range(3):
                ids=np.flatnonzero(labels[:,j]==k)
                if not len(ids):ids=np.arange(S)
                price=float(prices[ids,j].mean());self.price[j,k]=price
                cur[k]=np.mean([inf_convolution(self.grid,nxt[k],net[s,j]-q[j],price) for s in ids],axis=0)
            v=cur
        self.initial_values=v

    def action(self,j,E,net,q):
        k=int(net>self.cuts[j,0])+int(net>self.cuts[j,1]);a=net-q
        lo=max(EMIN,E-M/ETA);hi=min(EMAX,E+ETA*M)
        # A convex PL minimum occurs at a value knot or an immediate-cost kink.
        candidates=np.unique(np.r_[self.grid[(self.grid>=lo)&(self.grid<=hi)],lo,hi,np.clip([E,E-a/ETA,E-a*ETA],lo,hi)])
        delta=candidates-E;cost=5*self.price[j,k]*np.maximum(0,a+np.maximum(ETA*delta,delta/ETA))+np.interp(candidates,self.grid,self.future[j,k])
        return float(candidates[np.argmin(cost)])
