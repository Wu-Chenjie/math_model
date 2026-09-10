"""Causal daily convex aggregation of full hierarchical shadow policies.

Weights are optimized exclusively on prior-day trajectories. Equal daily
initial/terminal SOC and exogenous observations make convex state aggregation
implementable. Exact cancellation recovers a single physical battery action.
"""
import argparse,json,time,sys,hashlib,csv
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from scipy.sparse import csr_matrix,hstack,vstack,eye
from run_comparison import ROOT,BASE,CANDIDATES,KINDS,dump
from controllers import highslp,ETA,M

def fit_weights(q,r,delta,net,price):
    """Arrays days x slots x experts. Solve convex empirical combination cost."""
    K=q.shape[-1];Q=q.reshape(-1,K);R=r.reshape(-1,K);D=delta.reshape(-1,K)
    n=net.ravel();p=price.ravel();N=len(n);I=eye(N,format='csr');Z=csr_matrix((N,N))
    # Variables w, billed-energy epigraph h, emergency energy e.
    A=vstack([hstack([csr_matrix(1.5*R-.5*Q),-I,Z]),
              hstack([csr_matrix(.5*R+.5*Q),-I,Z]),
              hstack([csr_matrix(-R+ETA*D),Z,-I]),
              hstack([csr_matrix(-R+D/ETA),Z,-I])],format='csr')
    b=np.r_[np.zeros(2*N),-n,-n]
    eq=csr_matrix(np.r_[np.ones(K),np.zeros(2*N)][None,:]);rhs=np.ones(1)
    obj=np.r_[np.zeros(K),p,5*p]
    res=highslp(obj,A,b,eq,rhs,[(0,1)]*K+[(0,None)]*(2*N),solver='ipm')
    if not res.success:raise RuntimeError(res.message)
    w=np.maximum(res.x[:K],0);w/=w.sum()
    billing=np.maximum(1.5*(R@w)-.5*(Q@w),.5*(R@w)+.5*(Q@w))
    e=np.maximum.reduce([n-R@w+ETA*(D@w),n-R@w+(D@w)/ETA,np.zeros(N)])
    cost=float(p@(billing+5*e))
    vertices=np.sum(p[:,None]*(np.maximum(1.5*R-.5*Q,.5*R+.5*Q)+
              5*np.maximum.reduce([n[:,None]-R+ETA*D,n[:,None]-R+D/ETA,np.zeros_like(R)])),axis=0)
    assert cost<=vertices.min()+1e-4,(cost,vertices.min())
    assert abs(cost-res.fun)<1e-4,(cost,res.fun)
    return w,{'objective':cost,'best_vertex_cost':float(vertices.min()),
              'reconstructed_objective_gap':float(abs(cost-res.fun)),
              'max_constraint_violation':float(max(0,np.max(A@res.x-b)))}

def run_kind(kind):
    start=time.perf_counter();names=list(CANDIDATES);K=len(names)
    data=dict(np.load(BASE/'artifacts/data.npz'));expert={};costs=[];source_hashes={}
    for c in names:
        parts=[];daily=[]
        for phase in ['calibrate','annual']:
            path=ROOT/f'artifacts/{phase}/{kind}_{c}.npz';parts.append(dict(np.load(path)))
            source_hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            m=json.loads(path.with_suffix('.json').read_text());daily += m['daily']
        expert[c]={key:np.concatenate([part[key] for part in parts],axis=0) for key in parts[0]}
        costs.append([r['total_cost'] for r in daily])
    first=expert[names[0]];days=first['days'];prices=first['price']
    for a in expert.values():assert np.max(abs(a['price']-prices))<1e-12 and np.array_equal(a['days'],days)
    Q=np.stack([expert[c]['q'] for c in names],axis=-1)
    R=np.stack([expert[c]['r'] for c in names],axis=-1)
    E=np.stack([expert[c]['state'] for c in names],axis=-1)
    D=np.diff(E,axis=1);net=(data['load'][days]-data['pv'][days])/6;costs=np.array(costs).T
    result={key:np.zeros((334,144)) for key in ['q','r','c','d','emergency','spill','price']}
    result['state']=np.zeros((334,145));result['releases']=np.full((334,4,144),np.nan)
    weights=[];logs=[];fitlog=[];max_dominance=0.;max_ineq=0.
    for i in range(10,len(days)):
        past=slice(max(0,i-28),i)
        w,fit=fit_weights(Q[past],R[past],D[past],net[past],prices[past]);fitlog.append(fit);weights.append(w.tolist())
        j=i-10;q=Q[i]@w;r=R[i]@w;state=E[i]@w;delta=np.diff(state)
        charge=np.maximum(delta,0)/ETA;discharge=ETA*np.maximum(-delta,0)
        balance=r+discharge-charge-net[i];em=np.maximum(-balance,0);spill=np.maximum(balance,0)
        bill=prices[i]*np.maximum(1.5*r-.5*q,.5*r+.5*q)
        planned=float(prices[i]@q);inc=float(np.sum(1.5*prices[i]*np.maximum(r-q,0)))
        reduction=float(np.sum(-.5*prices[i]*np.maximum(q-r,0)));ecost=float(5*prices[i]@em)
        cost=float(bill.sum()+ecost);weighted=float(costs[i]@w)
        max_dominance=max(max_dominance,cost-weighted)
        assert cost<=weighted+1e-4,(i,cost,weighted)
        assert abs(cost-planned-inc-reduction-ecost)<1e-6
        assert state.min()>=1200-1e-6 and state.max()<=10800+1e-6
        assert max(charge.max(),discharge.max())<=M+1e-6 and abs(state[-1]-6000)<1e-6
        for key,a in [('q',q),('r',r),('c',charge),('d',discharge),('emergency',em),('spill',spill),('price',prices[i])]:result[key][j]=a
        result['state'][j]=state
        result['releases'][j]=sum(w[k]*expert[c]['releases'][i] for k,c in enumerate(names))
        logs.append({'date':str(first['dates'][i]),'planned_cost':planned,'increase_cost':inc,
            'reduction_net_cost':reduction,'emergency_cost':ecost,'total_cost':cost,'weighted_expert_cost':weighted,
            'convex_combination_gain_yuan':weighted-cost,'planned_energy':float(q.sum()),'adjusted_energy':float(r.sum()),
            'emergency_energy':float(em.sum()),'spill_energy':float(spill.sum())})
    result['days']=days[10:];result['dates']=first['dates'][10:]
    result['weights']=np.array(weights)
    total={k:float(sum(r[k] for r in logs)) for k in logs[0] if k!='date'}
    total['daily_cost_p95']=float(np.quantile([r['total_cost'] for r in logs],.95))
    total['worst_day_cost']=max(r['total_cost'] for r in logs)
    validation={'energy_balance_max_abs':float(abs(result['r']+result['d']+result['emergency']-result['c']-result['spill']-net[10:]).max()),
                'soc_recurrence_max_abs':float(abs(np.diff(result['state'],axis=1)-ETA*result['c']+result['d']/ETA).max()),
                'soc_min':float(result['state'].min()),'soc_max':float(result['state'].max()),
                'power_max_kw':float(6*max(result['c'].max(),result['d'].max())),
                'terminal_max_abs':float(abs(result['state'][:,-1]-6000).max()),
                'convex_dominance_violation_yuan':max_dominance,
                'training_reconstruction_gap_yuan':max(x['reconstructed_objective_gap'] for x in fitlog),
                'training_constraint_violation':max(x['max_constraint_violation'] for x in fitlog)}
    m={'kind':kind,'candidate':'convex28','totals':total,'daily':logs,'weights':weights,'expert_names':names,
       'training_log':fitlog,'validation':validation,'source_hashes':source_hashes,
       'runtime_seconds':time.perf_counter()-start,
       'information_rule':'At day i, fit on indices max(0,i-28)..i-1 only; weights fixed for whole day; shadow controllers causal.',
       'scope':'Additional synthesis candidate designed during initial annual run. Not part of initially frozen selectors.'}
    np.savez_compressed(ROOT/f'artifacts/{kind}_convex.npz',**result);dump(ROOT/f'artifacts/{kind}_convex.json',m)
    out=ROOT/'计算结果';out.mkdir(exist_ok=True)
    with (out/f'{kind}_凸组合权重.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['日期',*names,'总费用_元','按当日权重计算的专家费用_元','凸组合节省_元'])
        writer.writerows([[row['date'],*weights[i],row['total_cost'],row['weighted_expert_cost'],row['convex_combination_gain_yuan']] for i,row in enumerate(logs)])
    return {'kind':kind,'total_cost':total['total_cost'],'runtime_seconds':m['runtime_seconds'],'validation':validation}

def main():
    p=argparse.ArgumentParser();p.add_argument('--kinds',nargs='+',default=list(KINDS));p.add_argument('--workers',type=int,default=1);args=p.parse_args()
    tic=time.perf_counter();results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run_kind,k) for k in args.kinds]):
            result=f.result();results.append(result);print(json.dumps(result),flush=True)
    dump(ROOT/'artifacts'/('execution-convex-'+'-'.join(args.kinds)+'.json'),{'command':'python3 '+' '.join(sys.argv),
         'exit_code':0,'runtime_seconds':time.perf_counter()-tic,'results':results,'deterministic_reason':'Native single-thread HiGHS, past-only fixed windows; no random sampling.'})

if __name__=='__main__':main()
