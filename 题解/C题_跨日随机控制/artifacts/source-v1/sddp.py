"""Finite-horizon, risk-neutral SDDP for general convex linear stage models.

The engine only requires solve(state, noise, next_cuts) -> objective, outgoing
state, realized stage cost, input-state dual. BatteryStage is one application.
Stagewise-independent noises are observed at stage entry. Here-and-now
contracts have their own preceding deterministic stages.
"""
from pathlib import Path
from dataclasses import dataclass
import sys,json,time,hashlib,argparse
import numpy as np
from scipy.sparse import coo_matrix,vstack,csr_matrix
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor'))
import highspy

@dataclass
class StageResult:
    objective:float
    state:np.ndarray
    stage_cost:float
    gradient:np.ndarray

class LinearStage:
    """General LP stage with explicit incoming-state fixing equalities.

    Variables start with x_in, x_out, then stage controls, final theta.
    The user supplies base matrix/bounds/cost for each finite noise outcome.
    Costs must exclude theta, which the engine adds with coefficient one.
    """
    def __init__(self,dimension,outcomes):
        self.dimension=dimension;self.outcomes=outcomes
        self.probabilities=np.array([o['probability'] for o in outcomes])
        assert np.isclose(self.probabilities.sum(),1)
    def solve(self,state,noise,next_cuts):
        o=self.outcomes[noise];D=self.dimension;N=len(o['cost']);theta=N-1
        fix=coo_matrix((np.ones(D),(np.arange(D),np.arange(D))),shape=(D,N)).tocsr()
        mats=[fix,o['matrix']];lower=[state,o['row_lower']];upper=[state,o['row_upper']]
        if next_cuts:
            coeff=np.array([c[1] for c in next_cuts]);rows,cols=np.nonzero(coeff)
            mat=coo_matrix((np.r_[coeff[rows,cols],-np.ones(len(next_cuts))],(np.r_[rows,np.arange(len(next_cuts))],np.r_[D+cols,np.full(len(next_cuts),theta)])),shape=(len(next_cuts),N)).tocsr()
            mats.append(mat);lower.append(np.full(len(next_cuts),-np.inf));upper.append(-np.array([c[0] for c in next_cuts]))
        A=vstack(mats,format='csr');lo=np.concatenate(lower);hi=np.concatenate(upper)
        p=highspy.HighsLp();p.num_col_=N;p.num_row_=len(lo);p.col_cost_=o['cost'].copy();p.col_cost_[theta]=1.
        p.col_lower_=o['lower'];p.col_upper_=o['upper'];p.row_lower_=lo;p.row_upper_=hi
        p.a_matrix_.format_=highspy.MatrixFormat.kRowwise;p.a_matrix_.start_=A.indptr;p.a_matrix_.index_=A.indices;p.a_matrix_.value_=A.data
        h=highspy.Highs();h.setOptionValue('output_flag',False);h.setOptionValue('threads',1);h.passModel(p);h.run()
        if h.getModelStatus()!=highspy.HighsModelStatus.kOptimal:raise RuntimeError(h.modelStatusToString(h.getModelStatus()))
        sol=h.getSolution();x=np.array(sol.col_value)
        return StageResult(h.getObjectiveValue(),x[D:2*D],float(o['cost']@x),np.array(sol.row_dual[:D]))

class SDDP:
    def __init__(self,stages,seed=20260911):
        self.stages=stages;self.dimension=stages[0].dimension;self.rng=np.random.default_rng(seed);self.seed=seed
        self.cuts=[[] for _ in range(len(stages)+1)];self.trace=[]
    def forward(self,initial):
        state=np.array(initial,dtype=float);inputs=[];cost=0.
        for t,stage in enumerate(self.stages):
            inputs.append(state.copy());k=int(self.rng.choice(len(stage.outcomes),p=stage.probabilities))
            sol=stage.solve(state,k,self.cuts[t+1]);state=sol.state;cost+=sol.stage_cost
        return inputs,cost
    def backward(self,inputs):
        for t in range(len(self.stages)-1,-1,-1):
            x=inputs[t];stage=self.stages[t]
            vals=[stage.solve(x,k,self.cuts[t+1]) for k in range(len(stage.outcomes))]
            value=sum(p*v.objective for p,v in zip(stage.probabilities,vals))
            beta=sum(p*v.gradient for p,v in zip(stage.probabilities,vals));alpha=float(value-beta@x)
            self.cuts[t].append((alpha,beta))
    def bound(self,initial):
        stage=self.stages[0]
        return float(sum(p*stage.solve(np.array(initial),k,self.cuts[1]).objective for k,p in enumerate(stage.probabilities)))
    def train(self,initial,iterations=50,exploration=None):
        for it in range(iterations):
            x=np.array(initial,dtype=float)
            if exploration is not None:x=exploration(it,x)
            path,cost=self.forward(x);self.backward(path)
            if it==0 or (it+1)%10==0 or it==iterations-1:self.trace.append({'iteration':it+1,'root_lower_bound':self.bound(initial),'forward_sample_cost':cost})
        return self
    def evaluate(self,initial,count=128,seed=9182):
        old=self.rng;self.rng=np.random.default_rng(seed)
        costs=np.array([self.forward(initial)[1] for _ in range(count)]);self.rng=old
        se=float(costs.std(ddof=1)/np.sqrt(count))
        return {'samples':count,'seed':seed,'mean_policy_cost':float(costs.mean()),'standard_error':se,
                'normal_approximation_95_interval':[float(costs.mean()-1.96*se),float(costs.mean()+1.96*se)],
                'root_lower_bound':self.bound(initial),'note':'Monte Carlo estimate, not a deterministic upper bound.'}

def battery_stage(K,kind,hour,net_values=None,prices=None,probabilities=None):
    D=1+2*K;N=2*D+3;em=2*D;bill=em+1;theta=bill+1
    # Contract states contain all K deliveries; delivered entries are set to zero.
    rows=[];cols=[];vs=[];rl=[];ru=[]
    def row(items,lo,hi):
        r=len(rl)
        for c,v in items.items():rows.append(r);cols.append(c);vs.append(v)
        rl.append(lo);ru.append(hi)
    def copy(i):row({D+i:1,i:-1},0,0)
    q=lambda h:1+h
    r=lambda h:1+K+h
    if kind=='sign':
        copy(0)
        for h in range(K):row({D+r(h):1,D+q(h):-1},0,0)
    elif kind=='revise':
        copy(0)
        for h in range(K):
            copy(q(h))
            if h<hour:copy(r(h))
    else:
        dt=24/K;max_bus=5000*dt
        row({D:1,0:-1},-max_bus/.9,.9*max_bus)
        for h in range(K):
            if h==hour:
                row({D+q(h):1},0,0);row({D+r(h):1},0,0)
            else:copy(q(h));copy(r(h))
        row({bill:1,r(hour):-1.5,q(hour):.5},0,np.inf)
        row({bill:1,r(hour):-.5,q(hour):-.5},0,np.inf)
        row({em:1,r(hour):1,D:-.9,0:.9},0,np.inf)
        row({em:1,r(hour):1,D:-1/.9,0:1/.9},0,np.inf)
    matrix=coo_matrix((vs,(rows,cols)),shape=(len(rl),N)).tocsr()
    lower=np.zeros(N);upper=np.full(N,np.inf);lower[0]=lower[D]=1200;upper[0]=upper[D]=10800
    outcomes=[]
    if kind!='deliver':net_values=[0];prices=[0];probabilities=[1]
    for net,p,prob in zip(net_values,prices,probabilities):
        cost=np.zeros(N);cost[em]=5*p;cost[bill]=p
        lowers=np.array(rl,dtype=float)
        if kind=='deliver':lowers[-2:]=net
        outcomes.append({'probability':float(prob),'matrix':matrix,'row_lower':lowers,'row_upper':np.array(ru,dtype=float),
                         'lower':lower,'upper':upper,'cost':cost})
    return LinearStage(D,outcomes)

def fit_battery_model(data,cutoff,variable=False,adjust=False,K=12,days=3,window=28):
    """Coarse auxiliary future model, fitted only to complete past days.

    Per-stage net bins and conditional price means form a declared independent
    finite innovation model. This model is a terminal-value proxy, not a lower
    bound for the richer forecast-conditioned contest controller.
    """
    assert 144%K==0 and K%4==0 and cutoff>=7
    hist=np.arange(max(0,cutoff-window),cutoff);width=144//K
    net=((data['load'][hist]-data['pv'][hist])/6).reshape(len(hist),K,width).sum(2)
    p=(data['price'][hist] if variable else np.repeat(data['day_price'][None,:],len(hist),axis=0)).reshape(len(hist),K,width).mean(2)
    stages=[];emissions=[]
    for k in range(K):
        edges=np.quantile(net[:,k],[1/3,2/3]);labels=(net[:,k]>edges[0]).astype(int)+(net[:,k]>edges[1]).astype(int)
        vals=[];prices=[];weights=[]
        for b in range(3):
            ids=np.flatnonzero(labels==b)
            if len(ids):vals.append(float(net[ids,k].mean()));prices.append(float(p[ids,k].mean()));weights.append(len(ids)/len(hist))
        emissions.append((vals,prices,weights))
    for d in range(days):
        stages.append(battery_stage(K,'sign',0))
        for k in range(K):
            if adjust and k and k%(K//4)==0:stages.append(battery_stage(K,'revise',k))
            stages.append(battery_stage(K,'deliver',k,*emissions[k]))
    return stages,{'cutoff_day_exclusive':cutoff,'history_days':hist.tolist(),'steps_per_day':K,'horizon_days':days,
        'variable_price':variable,'adjustments':adjust,'noise_model':'Stagewise-independent net bins; conditional expected prices; hourly aggregation is an auxiliary-model approximation.'}

def train_tail(data,cutoff,variable=False,adjust=False,K=12,days=3,iterations=50,seed=20260911):
    start=time.perf_counter();stages,meta=fit_battery_model(data,cutoff,variable,adjust,K,days)
    model=SDDP(stages,seed);initial=np.r_[6000.,np.zeros(2*K)]
    def exploration(i,x):x[0]=np.linspace(1200,10800,9)[i%9];return x
    model.train(initial,iterations,exploration)
    ev=model.evaluate(initial,count=64)
    # Root signing resets contracts: its value depends on incoming inventory only.
    assert max(np.max(np.abs(b[1:])) for a,b in model.cuts[0])<1e-8
    rootcuts=[[a,float(b[0])] for a,b in model.cuts[0]]
    return {'configuration':meta,'seed':seed,'iterations':iterations,'trace':model.trace,'evaluation':ev,
        'root_cuts':rootcuts,'runtime_seconds':time.perf_counter()-start,
        'scope':'Valid lower cuts for this fixed coarse auxiliary model; approximate terminal values for the contest MPC.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--cutoff',type=int,default=31);p.add_argument('--iterations',type=int,default=50);p.add_argument('--steps',type=int,default=12);p.add_argument('--days',type=int,default=3);p.add_argument('--variable',action='store_true');p.add_argument('--adjust',action='store_true');p.add_argument('--output',default='sddp-pilot.json');args=p.parse_args()
    root=Path(__file__).resolve().parents[1];data=dict(np.load(root/'artifacts/data.npz'))
    out=train_tail(data,args.cutoff,args.variable,args.adjust,args.steps,args.days,args.iterations)
    out['execution']={'command':'python3 '+' '.join(sys.argv),'exit_code':0,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root/'artifacts'/args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out['evaluation']),flush=True)

if __name__=='__main__':main()
