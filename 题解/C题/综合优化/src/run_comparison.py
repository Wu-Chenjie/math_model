"""Frozen candidate pool, January development, February-December causal replay."""
from pathlib import Path
import sys,json,time,argparse,platform,hashlib
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import scipy

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
sys.path.insert(0,str(BASE/'src'))
from forecasting import scenario_data
from dispatch import solve,execute_slot,settlement
from controllers import affine_plan,execute_target,mpc_action,MarkovDP

CANDIDATES={
    'baseline':('common','greedy'),
    'common_mpc':('common','mpc'),
    'affine_feedback':('affine','affine'),
    'affine_mpc':('affine','mpc'),
    'affine_saa_mpc':('affine','saa_mpc'),
    'affine_sdp':('affine','sdp'),
}
KINDS={'q2':(False,False,()),'q3':(True,False,(1,2,3)),
       'q4_2':(False,True,()),'q4_3':(True,True,(1,2,3))}

def dump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def simulate(data,fc,days,kind,candidate,grid_size=321,alpha=.2):
    official,variable,updates=KINDS[kind];upper,lower=CANDIDATES[candidate]
    N=len(days);a={k:np.zeros((N,144)) for k in ['q','r','c','d','emergency','spill','price','projection']}
    a['state']=np.zeros((N,145));a['releases']=np.full((N,4,144),np.nan)
    logs=[];eq=ineq=cancelgap=0.;solve_count=0
    for i,day in enumerate(days):
        E=6000.;a['state'][i,0]=E
        actual=(data['load'][day]-data['pv'][day])/6
        price=data['price'][day] if variable else data['day_price'];a['price'][i]=price
        active=0;ema=0.;dp=None
        for t in range(144):
            k=t//36
            if t==0 or (t%36==0 and k in updates):
                net,prices,hist=scenario_data(data,fc,day,k,official,variable)
                active=t;ema=0.
                base=a['q'][i,t:] if t else None
                sol=(affine_plan(net,prices,E,base,start=t,alpha=alpha) if upper=='affine'
                     else solve(net,prices,E,base=base))
                solve_count+=1;eq=max(eq,sol['eq_residual']);ineq=max(ineq,sol['ineq_violation'])
                cancelgap=max(cancelgap,sol.get('objective_after_cancellation_gap',0))
                if t==0:a['q'][i]=sol['q']
                a['r'][i,t:]=sol['q'];a['releases'][i,k,t:]=sol['q']
                if lower=='sdp':dp=MarkovDP(net,prices,sol['q'],start=t,grid_size=grid_size)
            j=t-active
            if lower=='greedy':
                c,d,E,em,sp=execute_slot(a['r'][i,t],actual[t],E,0,0,t,controller='greedy')
                proj=0.
            else:
                if lower=='affine':
                    error=actual[t]-sol['center'][j];ema=(1-alpha)*ema+alpha*error
                    target=sol['a'][j]+sol['g'][k]@np.array([error,ema]) if t<143 else 6000.
                elif lower in ['mpc','saa_mpc']:
                    target=mpc_action(net,prices,a['r'][i,active:],E,actual[active:t+1],j,lower=='saa_mpc')
                    solve_count+=1
                elif lower=='sdp':target=dp.action(j,actual[t],E,a['r'][i,t])
                else:raise ValueError(lower)
                c,d,E,em,sp,proj=execute_target(E,target,a['r'][i,t],actual[t],t)
            for key,v in [('c',c),('d',d),('emergency',em),('spill',sp),('projection',proj)]:a[key][i,t]=v
            a['state'][i,t+1]=E
        cost=settlement(a['q'][i],a['r'][i],a['emergency'][i],price)
        logs.append({'date':str(data['dates'][day]),**cost,
                     'emergency_energy':float(a['emergency'][i].sum()),
                     'planned_energy':float(a['q'][i].sum()),'adjusted_energy':float(a['r'][i].sum()),
                     'spill_energy':float(a['spill'][i].sum()),
                     'projection_count':int(np.sum(a['projection'][i]>1e-5)),
                     'projection_total_kwh':float(a['projection'][i].sum()),
                     'projection_max_kwh':float(a['projection'][i].max())})
    a['days']=np.array(days);a['dates']=data['dates'][days]
    balance=a['r']+a['emergency']+a['d']-a['c']-a['spill']-(data['load'][days]-data['pv'][days])/6
    val={'energy_balance_max_abs':float(abs(balance).max()),
         'soc_recurrence_max_abs':float(abs(np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9).max()),
         'soc_min':float(a['state'].min()),'soc_max':float(a['state'].max()),
         'terminal_max_abs':float(abs(a['state'][:,-1]-6000).max()),
         'power_max_kw':float(max(a['c'].max(),a['d'].max())*6),
         'simultaneous_max':float(np.minimum(a['c'],a['d']).max()),'lp_eq_max_abs':eq,'lp_ineq_max':ineq,
         'max_lp_tie_break_and_cancellation_gap_yuan':cancelgap,
         'negative_energy_violation':float(max(0,-min(a[z].min() for z in ['q','r','c','d','emergency','spill'])))}
    assert val['energy_balance_max_abs']<1e-6 and val['soc_recurrence_max_abs']<1e-6
    assert val['soc_min']>=1200-1e-5 and val['soc_max']<=10800+1e-5
    assert val['terminal_max_abs']<1e-5 and val['power_max_kw']<=5000+1e-5 and val['simultaneous_max']<1e-5
    totals={k:float(sum(r[k] for r in logs)) for k in logs[0] if k not in ['date','projection_max_kwh']}
    totals['projection_max_kwh']=max(r['projection_max_kwh'] for r in logs)
    dailycost=np.array([r['total_cost'] for r in logs])
    totals['daily_cost_p95']=float(np.quantile(dailycost,.95))
    totals['worst_day_cost']=float(dailycost.max())
    return a,{'kind':kind,'candidate':candidate,'configuration':{'upper':upper,'lower':lower,'grid_size':grid_size,
               'alpha':alpha,'window':28,'start_day':int(days[0]),'end_day':int(days[-1])},
               'totals':totals,'daily':logs,'validation':val,'lp_solve_count':solve_count}

def worker(job):
    phase,kind,candidate,days,grid_size=job
    data=dict(np.load(BASE/'artifacts/data.npz'));fc=dict(np.load(BASE/'artifacts/forecasts.npz'))
    start=time.perf_counter();a,m=simulate(data,fc,days,kind,candidate,grid_size)
    m['runtime_seconds']=time.perf_counter()-start
    output_phase=f'grid{grid_size}' if phase=='grid' else phase
    out=ROOT/'artifacts'/output_phase;out.mkdir(exist_ok=True)
    np.savez_compressed(out/f'{kind}_{candidate}.npz',**a);dump(out/f'{kind}_{candidate}.json',m)
    return {'kind':kind,'candidate':candidate,'total_cost':m['totals']['total_cost'],'runtime_seconds':m['runtime_seconds']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['pilot','calibrate','annual','grid'],default='pilot')
    p.add_argument('--workers',type=int,default=4);p.add_argument('--candidates',nargs='+',default=list(CANDIDATES))
    p.add_argument('--kinds',nargs='+',default=list(KINDS));p.add_argument('--grid-size',type=int,default=321)
    args=p.parse_args();days={'pilot':[30],'calibrate':list(range(21,31)),
                            'annual':list(range(31,365)),'grid':[31,59,90,120,151,181,212,243,273,304,334]}[args.phase]
    jobs=[(args.phase,k,c,days,args.grid_size) for k in args.kinds for c in args.candidates]
    start=time.perf_counter();results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending={pool.submit(worker,j):j for j in jobs}
        for f in as_completed(pending):
            result=f.result();results.append(result);print(json.dumps(result),flush=True)
    log_phase=f'grid{args.grid_size}' if args.phase=='grid' else args.phase
    dump(ROOT/f'artifacts/execution-{log_phase}.json',{'command':'python3 '+' '.join(sys.argv),
         'exit_code':0,'runtime_seconds':time.perf_counter()-start,'results':results,
         'environment':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform()},
         'deterministic_reason':'Fixed scenario windows, deterministic HiGHS, fixed quantile Markov bins; no random training.'})

if __name__=='__main__':main()
