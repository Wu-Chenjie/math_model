"""Chronological contest replay; whole trajectories, never independent days."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,json,sys,time,platform,hashlib
import numpy as np
from forecasting import select_families,scenarios
from control import affine_plan,MarkovDP,execute,ETA,prune_cuts
from dispatch import settlement,solve
from sddp import train_tail

ROOT=Path(__file__).resolve().parents[1]
KINDS={'q2':(False,False),'q3':(True,False),'q4_2':(False,True),'q4_3':(True,True)}
CANDIDATES={'closed_baseline':(False,'greedy','linear',True),
            'closed_affine':(True,'affine','linear',True),
            'cross_baseline':(False,'greedy','linear',False),
            'affine_mpc':(True,'affine','linear',False),
            'markov_mpc':(True,'dp','linear',False),
            'sddp_mpc':(True,'affine','sddp',False),
            'sddp_markov':(True,'dp','sddp',False)}

def dump(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def warmup(data):
    net=(data['load'][:31]-data['pv'][:31])/6
    # No unearned February reset: hold the battery from the specified January initial state.
    a={'state':np.full((31,145),6000.),'q':np.zeros((31,144)),'r':np.zeros((31,144)),
       'c':np.zeros((31,144)),'d':np.zeros((31,144)),'emergency':np.maximum(net,0),'spill':np.maximum(-net,0)}
    np.savez_compressed(ROOT/'artifacts/january-warmup.npz',**a)
    return {'policy':'Zero planned purchase and no battery operation; current shortages covered by emergency purchase.',
            'initial_energy':6000.,'february_initial_energy':float(a['state'][-1,-1]),
            'days':31,'fixed_price_cost':float(np.sum(5*data['day_price']*a['emergency'])),
            'variable_price_cost':float(np.sum(5*data['price'][:31]*a['emergency'])),
            'note':'Same causal initialization for every candidate. January cost reported separately; no inventory transfer benefit hidden.'}

def tail_file(kind,cutoff,days=3):return ROOT/f"artifacts/tails/{kind}_{cutoff}{'' if days==3 else '_D'+str(days)}.json"

def train_job(job):
    kind,cutoff,iterations,steps,days=job;official,variable=KINDS[kind]
    data=dict(np.load(ROOT/'artifacts/data.npz'));res=train_tail(data,cutoff,variable,official,K=steps,days=days,iterations=iterations)
    res['execution']={'command':'python3 '+' '.join(sys.argv),'worker_job':list(job),'exit_code':0,'source_sha256':hashlib.sha256((ROOT/'src/sddp.py').read_bytes()).hexdigest()}
    dump(tail_file(kind,cutoff,days),res)
    return {'kind':kind,'cutoff':cutoff,'runtime_seconds':res['runtime_seconds'],'evaluation':res['evaluation']}

def simulate(data,selection,days,kind,candidate,count=7,horizon_days=2,tail_scale=1.,grid=321,final=None,initial=6000.):
    official,variable=KINDS[kind];affine,lower,tail,closed=CANDIDATES[candidate]
    N=len(days);arrays={k:np.zeros((N,144)) for k in ['q','r','c','d','emergency','spill','price','projection']}
    arrays['state']=np.zeros((N,145));arrays['releases']=np.full((N,4,144),np.nan)
    E=float(initial);logs=[];decisions=[];lpv=gap=0.;start=time.perf_counter();dp=None;cache={}
    evaluation_end=(days[-1]+1)*144
    for i,day in enumerate(days):
        arrays['state'][i,0]=E;actual=(data['load'][day]-data['pv'][day])/6
        price=data['price'][day] if variable else data['day_price'];arrays['price'][i]=price
        for t in range(144):
            now=day*144+t
            if t%36==0:
                end=min((day+horizon_days)*144,evaluation_end)
                net,prices,meta=scenarios(data,selection,now,end,official,variable,count=count)
                base=None if t==0 else np.r_[arrays['q'][i,t:],np.zeros(end-(day+1)*144)]
                terminal=6000. if closed else final if end==evaluation_end else None
                cuts=None
                lam=tail_scale*float(np.quantile(prices[:,-min(144,len(prices[0])):],.25))/ETA
                if end==evaluation_end or closed:lam=0.
                elif tail=='sddp':
                    # Monthly model version is fixed before the month begins.
                    cutoff=int(day)-(int(str(data['dates'][day])[8:10])-1)
                    if day<31:cutoff=14
                    tail_days=min(3,(evaluation_end-end)//144)
                    path=tail_file(kind,cutoff,tail_days)
                    if path not in cache:cache[path]=json.loads(path.read_text())
                    cuts=prune_cuts(cache[path]['root_cuts']);lam=0.
                plan=affine_plan(net,prices,now,E,base,official,affine,lam,terminal,cuts,daily_closed=closed)
                lpv=max(lpv,plan['lp_violation']);gap=max(gap,plan['objective_gap'])
                if t==0:
                    arrays['q'][i]=np.maximum(plan['q'][:144],0);arrays['r'][i]=arrays['q'][i]
                    arrays['releases'][i,0]=arrays['q'][i]
                elif official:
                    arrays['r'][i,t:]=np.maximum(plan['r'][:144-t],0)
                    arrays['releases'][i,t//36,t:]=arrays['r'][i,t:]
                effective=plan['r'].copy();until=36 if official else 144-t
                effective[:until]=arrays['r'][i,t:t+until]
                if lower=='dp':dp=MarkovDP(net,prices,effective,lam,grid,terminal,cuts)
                active=t;ema=0.
                decisions.append({**meta,'date':str(data['dates'][day]),'release':t//36,'inventory':E,'tail_price':lam,'tail_model_cutoff':cutoff if cuts else None,'tail_model_days':tail_days if cuts else None,'tail_cut_count':len(cuts) if cuts else 0})
            j=t-active
            if lower=='affine':
                error=actual[t]-plan['center'][j];ema=.8*ema+.2*error
                target=plan['a'][j]+plan['g'][0]@np.array([error,ema])
            elif lower=='dp':target=dp.action(j,E,actual[t],arrays['r'][i,t])
            else:
                balance=arrays['r'][i,t]-actual[t]
                target=E+ETA*max(balance,0)-max(-balance,0)/ETA
            remaining=evaluation_end-now-1
            E,c,d,em,sp,projection=execute(E,target,arrays['r'][i,t],actual[t],remaining,closed,t,6000. if closed else final)
            for k,v in [('c',c),('d',d),('emergency',em),('spill',sp),('projection',projection)]:arrays[k][i,t]=v
            arrays['state'][i,t+1]=E
        cost=settlement(arrays['q'][i],arrays['r'][i],arrays['emergency'][i],price)
        logs.append({'date':str(data['dates'][day]),**cost,'emergency_energy':float(arrays['emergency'][i].sum()),
          'spill_energy':float(arrays['spill'][i].sum()),'ending_inventory':E,'projection_count':int((arrays['projection'][i]>1e-6).sum())})
    balance=arrays['r']+arrays['emergency']+arrays['d']-arrays['c']-arrays['spill']-(data['load'][days]-data['pv'][days])/6
    val={'balance_max_abs':float(abs(balance).max()),'soc_recurrence_max_abs':float(abs(np.diff(arrays['state'],axis=1)-ETA*arrays['c']+arrays['d']/ETA).max()),
      'midnight_jump_max_abs':float(abs(arrays['state'][1:,0]-arrays['state'][:-1,-1]).max()) if N>1 else 0.,
      'soc_min':float(arrays['state'].min()),'soc_max':float(arrays['state'].max()),'power_max_kw':float(max(arrays['c'].max(),arrays['d'].max())*6),
      'simultaneous_max':float(np.minimum(arrays['c'],arrays['d']).max()),'lp_violation_max':lpv,'lp_objective_recompute_gap':gap,
      'initial_inventory':float(arrays['state'][0,0]),'final_inventory':float(E),
      'negative_energy_violation':float(max(0,-min(arrays[k].min() for k in ['q','r','c','d','emergency','spill'])))}
    assert val['balance_max_abs']<1e-5 and val['soc_recurrence_max_abs']<1e-5 and val['midnight_jump_max_abs']<1e-5
    assert val['soc_min']>=1200-1e-5 and val['soc_max']<=10800+1e-5 and val['power_max_kw']<=5000+1e-5
    if final is not None:assert abs(E-final)<1e-5
    totals={k:float(sum(z[k] for z in logs)) for k in ['planned_cost','increase_cost','reduction_net_cost','emergency_cost','total_cost','emergency_energy','spill_energy','projection_count']}
    arrays['days']=np.array(days);arrays['dates']=data['dates'][days]
    metrics={'kind':kind,'candidate':candidate,'configuration':{'count':count,'horizon_days':horizon_days,'tail_scale':tail_scale,'grid':grid,'final':final,'initial':initial,'closed_daily':closed,'start_day':days[0],'end_day':days[-1]},
       'totals':totals,'validation':val,'daily':logs,'decisions':decisions,'runtime_seconds':time.perf_counter()-start}
    return arrays,metrics

def replay_job(job):
    phase,kind,candidate,days,count,horizon,scale,grid,final=job
    data=dict(np.load(ROOT/'artifacts/data.npz'));selection=json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
    a,m=simulate(data,selection,days,kind,candidate,count,horizon,scale,grid,final)
    folder=ROOT/'artifacts'/phase;folder.mkdir(exist_ok=True)
    np.savez_compressed(folder/f'{kind}_{candidate}.npz',**a);dump(folder/f'{kind}_{candidate}.json',m)
    return {'kind':kind,'candidate':candidate,'total_cost':m['totals']['total_cost'],'runtime_seconds':m['runtime_seconds']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',default='pilot');p.add_argument('--workers',type=int,default=4);p.add_argument('--kinds',nargs='+',default=list(KINDS));p.add_argument('--candidates',nargs='+',default=list(CANDIDATES));p.add_argument('--count',type=int,default=7);p.add_argument('--horizon',type=int,default=2);p.add_argument('--tail-scale',type=float,default=1.);p.add_argument('--grid',type=int,default=321);p.add_argument('--final',type=float,default=None);p.add_argument('--iterations',type=int,default=100);p.add_argument('--steps',type=int,default=12);p.add_argument('--tail-days',type=int,default=3);p.add_argument('--cutoffs',nargs='+',type=int);p.add_argument('--start',type=int);p.add_argument('--stop',type=int);args=p.parse_args()
    data=dict(np.load(ROOT/'artifacts/data.npz'))
    if not (ROOT/'artifacts/forecast-selection.json').exists():dump(ROOT/'artifacts/forecast-selection.json',select_families(data))
    if args.phase=='initialize':
        dump(ROOT/'artifacts/warmup.json',warmup(data));n=(data['day_load']-data['day_pv'])/6
        q1=solve(n[None,:],data['day_price'][None,:],hard=True)
        np.savez_compressed(ROOT/'artifacts/q1.npz',**{k:v for k,v in q1.items() if isinstance(v,np.ndarray)})
        dump(ROOT/'artifacts/q1.json',{k:v for k,v in q1.items() if not isinstance(v,np.ndarray)});return
    if args.phase=='train':
        (ROOT/'artifacts/tails').mkdir(exist_ok=True)
        cutoffs=args.cutoffs or [14,31,59,90,120,151,181,212,243,273,304,334]
        jobs=[(k,d,args.iterations,args.steps,args.tail_days) for k in args.kinds for d in cutoffs];worker=train_job
    else:
        start=args.start if args.start is not None else {'pilot':31,'calibrate':24,'annual':31}.get(args.phase,31)
        stop=args.stop if args.stop is not None else {'pilot':32,'calibrate':31,'annual':365}.get(args.phase,32)
        days=list(range(start,stop));jobs=[(args.phase,k,c,days,args.count,args.horizon,args.tail_scale,args.grid,args.final) for k in args.kinds for c in args.candidates];worker=replay_job
    begin=time.perf_counter();results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(worker,j):j for j in jobs}
        for f in as_completed(futures):
            result=f.result();results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    log_phase=args.phase+(f'-D{args.tail_days}' if args.phase=='train' and args.tail_days!=3 else '')
    dump(ROOT/f'artifacts/execution-{log_phase}.json',{'command':'python3 '+' '.join(sys.argv),'exit_code':0,'runtime_seconds':time.perf_counter()-begin,
        'environment':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform()},'results':results,
        'seed':20260911 if args.phase=='train' else None,'deterministic_reason':None if args.phase=='train' else 'Deterministic chronological scenario selection, LP and convex DP.',
        'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').glob('*.py')}})

if __name__=='__main__':main()
