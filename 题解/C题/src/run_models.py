"""Reproduce all models and prequential evaluations. NumPy/SciPy; deterministic HiGHS."""
from pathlib import Path
import json, time, platform, sys, argparse
import numpy as np
import scipy
from forecasting import make_forecasts,scenario_data,predict
from dispatch import solve,execute_slot,settlement

ROOT=Path(__file__).resolve().parents[1]
def dump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def simulate(data,fc,days,official=False,variable_price=False,updates=(),controller='fixed',
             deterministic=False,window=28,refund=True,eta=.9,terminal=6000.,power=5000.,label=''):
    N=len(days)
    a={key:np.zeros((N,144)) for key in ['q','r','c','d','emergency','spill','price']}
    a['state']=np.zeros((N,145));a['releases']=np.full((N,4,144),np.nan)
    logs=[];maxeq=maxineq=maxgap=0.
    for i,day in enumerate(days):
        E=terminal;a['state'][i,0]=E
        net_actual=(data['load'][day]-data['pv'][day])/6
        p=data['price'][day] if variable_price else data['day_price'];a['price'][i]=p
        for k in range(4):
            start=k*36
            if k==0 or k in updates:
                net,prices,hist=scenario_data(data,fc,day,k,official,variable_price,window,deterministic)
                sol=solve(net,prices,E,terminal,base=(a['q'][i,start:] if k else None),refund=refund,eta=eta,power=power)
                if k==0:a['q'][i]=sol['q']
                a['r'][i,start:]=sol['q'];a['c'][i,start:]=sol['c'];a['d'][i,start:]=sol['d']
                a['releases'][i,k,start:]=sol['q']
                maxeq=max(maxeq,sol['eq_residual']);maxineq=max(maxineq,sol['ineq_violation']);maxgap=max(maxgap,sol['duality_gap'])
            for t in range(start,start+36):
                c,d,E,em,sp=execute_slot(a['r'][i,t],net_actual[t],E,a['c'][i,t],a['d'][i,t],t,controller,eta,power,terminal=terminal)
                for key,value in [('c',c),('d',d),('emergency',em),('spill',sp)]:a[key][i,t]=value
                a['state'][i,t+1]=E
        cost=settlement(a['q'][i],a['r'][i],a['emergency'][i],p,refund)
        logs.append({'date':str(data['dates'][day]),**cost,'planned_energy':float(a['q'][i].sum()),
                     'adjusted_energy':float(a['r'][i].sum()),'emergency_energy':float(a['emergency'][i].sum()),
                     'spill_energy':float(a['spill'][i].sum()),
                     'emergency_while_charging':float(np.minimum(a['emergency'][i],a['c'][i]).sum())})
    a['days']=np.array(days);a['dates']=data['dates'][days]
    totals={key:float(sum(row[key] for row in logs)) for key in logs[0] if key!='date'}
    balance=a['r']+a['emergency']+a['d']-a['c']-a['spill']-(data['load'][days]-data['pv'][days])/6
    valid={'energy_balance_max_abs':float(abs(balance).max()),
           'soc_recurrence_max_abs':float(abs(np.diff(a['state'],axis=1)-eta*a['c']+a['d']/eta).max()),
           'soc_min':float(a['state'].min()),'soc_max':float(a['state'].max()),
           'terminal_max_abs':float(abs(a['state'][:,-1]-terminal).max()),
           'power_max_kw':float(max(a['c'].max(),a['d'].max())*6),
           'simultaneous_charge_discharge_max':float(np.minimum(a['c'],a['d']).max()),
           'lp_eq_max_abs':maxeq,'lp_ineq_violation':maxineq,'lp_duality_gap_max':maxgap,
           'negative_energy_violation':float(max(0,-min(a[z].min() for z in ['q','r','c','d','emergency','spill'])))}
    assert valid['energy_balance_max_abs']<1e-6 and valid['soc_recurrence_max_abs']<1e-6
    assert valid['terminal_max_abs']<1e-5 and valid['soc_min']>=1200-1e-5 and valid['soc_max']<=10800+1e-5
    assert valid['power_max_kw']<=power+1e-5 and valid['simultaneous_charge_discharge_max']<1e-5
    return a,{'totals':totals,'daily':logs,'validation':valid,'configuration':{'official':official,
         'variable_price':variable_price,'updates':list(updates),'controller':controller,'window':window,
         'refund':refund,'eta':eta,'terminal':terminal,'power':power,'deterministic':deterministic}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['calibrate','main','extras'],default='main')
    args=parser.parse_args();start=time.perf_counter()
    data=dict(np.load(ROOT/'artifacts/data.npz'))
    fc,selection=make_forecasts(data)
    np.savez_compressed(ROOT/'artifacts/forecasts.npz',**fc)
    dump(ROOT/'artifacts/forecast-selection.json',selection)
    print('FORECAST_SELECTION',json.dumps(selection),flush=True)
    if args.phase=='calibrate':
        results={}
        # Use Jan22-31 as a small policy development window; forecast family selection also Jan only.
        for controller in ['fixed','greedy']:
            total=0
            for kind in ['q2','q3']:
                _,m=simulate(data,fc,list(range(21,31)),official=kind=='q3',updates=(1,2,3) if kind=='q3' else (),controller=controller)
                results[f'{kind}_{controller}']=m['totals'];total+=m['totals']['total_cost']
            results[controller+'_sum']=total
        chosen=min(['fixed','greedy'],key=lambda z:results[z+'_sum'])
        dump(ROOT/'artifacts/controller-selection.json',{'selected':chosen,'results':results,
             'caveat':'January development only; family selection and controller selection share January, no out-of-sample claim for January.'})
        dump(ROOT/'artifacts/execution-calibrate.json',{'command':'python3 src/run_models.py --phase calibrate',
             'exit_code':0,'runtime_seconds':time.perf_counter()-start,
             'deterministic_reason':'January-only fixed candidate comparison; no random sampling.'})
        print('CONTROLLER',chosen,results,flush=True);return
    controller=json.loads((ROOT/'artifacts/controller-selection.json').read_text())['selected']
    days=list(range(31,365));metrics={}
    if args.phase=='main':
        net=(data['day_load']-data['day_pv'])[None,:]/6;p=data['day_price'][None,:]
        q1=solve(net,p,hard=True)
        q1['no_storage_cost']=float(p[0]@np.maximum(net[0],0));q1['daily_energy']=float(q1['q'].sum())
        q1['daily_cost']=float(p[0]@q1['q'])
        dump(ROOT/'artifacts/q1.json',{k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in q1.items()})
        configs={'q2':{},'q3':{'official':True,'updates':(1,2,3)},
                 'q4_2':{'variable_price':True},'q4_3':{'official':True,'variable_price':True,'updates':(1,2,3)}}
        for key,kw in configs.items():
            tick=time.perf_counter();a,m=simulate(data,fc,days,controller=controller,**kw)
            m['runtime_seconds']=time.perf_counter()-tick
            np.savez_compressed(ROOT/f'artifacts/{key}.npz',**a);dump(ROOT/f'artifacts/{key}.json',m);metrics[key]=m['totals']
            print(key,json.dumps(m['totals']),f"seconds {m['runtime_seconds']:.2f}",flush=True)
        metrics['q1']={k:q1[k] for k in ['daily_energy','daily_cost','no_storage_cost']}
        metrics['runtime_seconds']=time.perf_counter()-start
        metrics['environment']={'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'platform':platform.platform()}
        dump(ROOT/'artifacts/metrics.json',metrics)
    else:
        # Controlled ablations: same forecast system and real-time controller, change one policy feature.
        configs={'q2_deterministic':{'deterministic':True},
                 'q3_0only':{'official':True},
                 'q3_6only':{'official':True,'updates':(1,)},
                 'q3_12only':{'official':True,'updates':(2,)},
                 'q3_18only':{'official':True,'updates':(3,)},
                 'q3_no_refund':{'official':True,'updates':(1,2,3),'refund':False},
                 'q4_3_0only':{'official':True,'variable_price':True},
                 'q2_fixed':{'controller':'fixed'}}
        for key,kw in configs.items():
            tick=time.perf_counter();ctl=kw.pop('controller',controller)
            a,m=simulate(data,fc,days,controller=ctl,**kw)
            m['runtime_seconds']=time.perf_counter()-tick
            dump(ROOT/f'artifacts/{key}.json',m);metrics[key]=m['totals']
            print(key,json.dumps(m['totals']),f"seconds {m['runtime_seconds']:.2f}",flush=True)
        sensitivity={}
        # Representative predeclared first day of every month in evaluation period.
        sample=[d for d in days if str(data['dates'][d]).endswith('-01')]
        configs={'reference':{},'window14':{'window':14},'window56':{'window':56},
                 'eta085':{'eta':.85},'eta095':{'eta':.95},'terminal4800':{'terminal':4800.},
                 'terminal7200':{'terminal':7200.},'power4000':{'power':4000.},'power6000':{'power':6000.}}
        for key,kw in configs.items():
            _,m=simulate(data,fc,sample,official=True,variable_price=True,updates=(1,2,3),controller=controller,**kw)
            sensitivity[key]=m
        dump(ROOT/'artifacts/sensitivity.json',sensitivity)
        # Perfect information daily cyclic LP is an optimistic cost reference, NOT an executable forecast policy.
        oracle={}
        for variable in [False,True]:
            costs=[];energies=[]
            for day in days:
                p=(data['price'][day] if variable else data['day_price'])[None,:]
                sol=solve((data['load'][day]-data['pv'][day])[None,:]/6,p,hard=True)
                costs.append(float(p[0]@sol['q']));energies.append(float(sol['q'].sum()))
            oracle['variable' if variable else 'fixed']={'daily_cost':costs,'total_cost':sum(costs),'total_energy':sum(energies)}
        dump(ROOT/'artifacts/oracle.json',oracle)
        dump(ROOT/'artifacts/ablations.json',metrics)
        dump(ROOT/'artifacts/baseline-metrics.json',{'q2':metrics['q2_deterministic']})
    dump(ROOT/f'artifacts/execution-{args.phase}.json',{'command':'python3 src/run_models.py --phase '+args.phase,
         'exit_code':0,'runtime_seconds':time.perf_counter()-start,'deterministic_reason':'No random sampling; chronological residual windows and deterministic HiGHS.'})

if __name__=='__main__':main()
