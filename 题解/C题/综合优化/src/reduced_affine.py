"""Exact economic elimination of battery flows from the causal affine LP."""
import numpy as np
from scipy.sparse import eye,diags,kron,hstack,vstack,csr_matrix,coo_matrix
from controllers import ETA,EMIN,EMAX,TARGET,M,affine_features,highslp

def affine_plan(net,prices,initial=TARGET,base=None,start=0,alpha=.2,solver='choose'):
    S,T=net.shape;ST=S*T;G=8
    center,err,ema=affine_features(net,alpha)
    row=np.arange(ST);times=np.tile(np.arange(T),S);block=(start+times)//36
    v0=err.ravel().copy();v1=ema.ravel().copy();v0[times==T-1]=0;v1[times==T-1]=0
    F=coo_matrix((np.r_[v0,v1],(np.r_[row,row],np.r_[2*block,2*block+1])),shape=(ST,G)).tocsr()
    R=kron(np.ones((S,1)),eye(T),format='csr');Z=csr_matrix((ST,T));I=eye(ST,format='csr')
    H=hstack([Z,R,F,csr_matrix((ST,ST))],format='csr') # q,a,g,e -> E[s,t+1]
    D=kron(eye(S),eye(T)-diags(np.ones(T-1),-1),format='csr')
    J=D@H;init=np.zeros(ST);init[np.arange(S)*T]=initial
    NE=hstack([-R,csr_matrix((ST,T+G)),-I],format='csr')
    A=vstack([H,-H,J,-J,ETA*J+NE,J/ETA+NE],format='csr')
    b=np.r_[np.full(ST,EMAX),np.full(ST,-EMIN),ETA*M+init,M/ETA-init,
            -net.ravel()+ETA*init,-net.ravel()+init/ETA]
    p=prices.mean(0);obj=np.r_[np.zeros(T) if base is not None else p,np.zeros(T+G),5*prices.ravel()/S]
    bounds=[(0,None)]*T+[(EMIN,EMAX)]*T+[(-10,10)]*G+[(0,None)]*ST
    bounds[2*T-1]=(TARGET,TARGET)
    eq=csr_matrix((0,len(obj)));rhs=np.zeros(0)
    if base is not None:
        n=len(obj);A=hstack([A,csr_matrix((len(b),2*T))],format='csr')
        eq=hstack([eye(T),csr_matrix((T,n-T)),-eye(T),eye(T)],format='csr');rhs=base
        obj=np.r_[obj,1.5*p,-.5*p];bounds +=[(0,None)]*(2*T)
    res=highslp(obj,A,b,eq,rhs,bounds,solver=solver)
    if not res.success:raise RuntimeError(res.message)
    x=res.x;q=x[:T];a=x[T:2*T];g=x[2*T:2*T+G].reshape(4,2)
    states=(R@a+F@g.ravel()).reshape(S,T);prev=np.c_[np.full(S,initial),states[:,:-1]]
    c=np.maximum(states-prev,0)/ETA;d=np.maximum(prev-states,0)*ETA
    em=np.maximum(net+c-d-q,0)
    cost=float(p@q if base is None else np.sum(1.5*p*np.maximum(q-base,0)-.5*p*np.maximum(base-q,0)))
    cost+=float(np.mean(np.sum(5*prices*em,axis=1)))
    return dict(q=q,a=a,g=g,center=center,alpha=alpha,expected_cost=cost,
                eq_residual=float(np.max(abs(eq@x-rhs))) if len(rhs) else 0.,
                ineq_violation=float(max(0,np.max(A@x-b))),objective_after_cancellation_gap=float(abs(cost-res.fun)))
