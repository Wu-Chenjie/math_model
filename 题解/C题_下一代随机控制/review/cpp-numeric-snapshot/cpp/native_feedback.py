# Reference summation and tie ordering; native PL convolution.
import numpy as np
from control import EMIN, EMAX, ETA, M
from nextgen_scenarios import weighted_quantile
from nextgen_control import terminal_values, minimize_action
from native import inf_convolution
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
        # A finite convex terminal penalty approximates the target in this DP;
        # hard true-end reachability is enforced separately in execution.
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

class WeightedMarkovDP:
    def __init__(self, net, prices, q, weights, tail_price, grid_size=321, bins=3, terminal=None, tail_cuts=None):
        self.legacy = None
        if bins == 3 and np.allclose(weights, 1/len(weights), rtol=0, atol=1e-15):
            self.legacy = MarkovDP(net, prices, q, tail_price, grid_size, terminal, tail_cuts)
            return
        S, T = net.shape; self.grid = np.linspace(EMIN, EMAX, grid_size)
        self.cuts = np.array([weighted_quantile(net[:, j], np.arange(1, bins)/bins, weights) for j in range(T)])
        labels = np.sum(net[:, :, None] > self.cuts[None], axis=2)
        self.future = np.empty((T, bins, grid_size)); self.price = np.empty((T, bins))
        v = np.tile(terminal_values(self.grid, tail_price, terminal, tail_cuts), (bins, 1))
        for j in range(T-1, -1, -1):
            counts = np.zeros((bins, bins))
            if j < T-1:
                np.add.at(counts, (labels[:, j], labels[:, j+1]), S*weights)
            P = (counts+1/bins)/(counts.sum(1, keepdims=True)+1)
            nxt = P@v; self.future[j] = nxt; cur = np.empty_like(v)
            for k in range(bins):
                ids = np.flatnonzero(labels[:, j] == k)
                if not len(ids): ids = np.arange(S)
                w = weights[ids]/weights[ids].sum(); price = float(w@prices[ids, j]); self.price[j, k] = price
                cur[k] = w@np.array([inf_convolution(self.grid, nxt[k], net[s, j]-q[j], price) for s in ids])
            v = cur
        self.initial_values = v

    def action(self, j, E, net, q, state=None):
        if self.legacy is not None:
            return self.legacy.action(j, E, net, q)
        k = int(np.sum(net > self.cuts[j]))
        return minimize_action(self.grid, self.future[j, k], E, net-q, self.price[j, k])
