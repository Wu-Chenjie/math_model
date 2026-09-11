#!/usr/bin/env python3
"""Independent full-replay physical and bill validator; imports no producer code.

NPZ: q,r,c,d,emergency,spill,price,projection (optional),state,releases,days,dates.
JSON: kind,configuration,totals,daily,decisions. Fixed year end is mandatory
unless --allow-free-end; --development permits only Jan development subsets.
PASS is limited to numerical physics/billing, not forecast-information causality.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,sys,time
import numpy as np

PHYS=1e-5;MONEY=1e-4
KINDS={'q2':(False,False),'q3':(True,False),'q4_2':(False,True),'q4_3':(True,True)}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def audit_arrays(data,a,m,allow_free_end=False,development=False):
    errors=[];checks={};scope=[]
    def check(name,x,tol=PHYS):
        x=float(x);checks[name]={'value':x,'tolerance':tol,'passed':bool(np.isfinite(x) and x<=tol)}
        if not checks[name]['passed']:errors.append(name)
    def require(name,ok):
        checks[name]={'passed':bool(ok)}
        if not ok:errors.append(name)
    try:
        kind=m['kind'];official,variable=KINDS[kind];cfg=m['configuration']
        days=np.asarray(a['days']);N=len(days);E=np.asarray(a['state']);releases=np.asarray(a['releases'])
        expected=range(int(days[0]),int(days[-1])+1) if development else range(31,365)
        require('evaluation_day_indices',np.array_equal(days,np.array(list(expected))))
        if development:require('January_development_only',bool(N>0 and days.min()>=0 and days.max()<=30))
        require('dates_align_input',np.array_equal(a['dates'],data['dates'][days]))
        require('state_shape',E.shape==(N,145));require('release_shape',releases.shape==(N,4,144))
        for key in ('q','r','c','d','emergency','spill','price'):
            require('shape:'+key,a[key].shape==(N,144));require('finite:'+key,np.isfinite(a[key]).all())
        require('finite:state',np.isfinite(E).all())
        q,r,c,b,e,spill,p=[a[k] for k in ('q','r','c','d','emergency','spill','price')]
        net=(data['load'][days]-data['pv'][days])/6
        require('official_physics_only',not m.get('validation_design',{}).get('stress') and not cfg.get('degradation_cost'))
        check('bus_balance_max_abs',np.abs(r+e+b-c-spill-net).max())
        check('soc_recurrence_max_abs',np.abs(np.diff(E,axis=1)-.9*c+b/.9).max())
        check('inventory_bound_violation',max(0.,1200-E.min(),E.max()-10800))
        check('charge_power_excess_kw',max(0.,6*c.max()-5000));check('discharge_power_excess_kw',max(0.,6*b.max()-5000))
        check('simultaneous_energy_max',np.minimum(c,b).max())
        check('negative_energy_max',max(0.,-min(x.min() for x in (q,r,c,b,e,spill))))
        check('midnight_jump_max_abs',np.abs(E[1:,0]-E[:-1,-1]).max(initial=0))
        require('initial_inventory_declared','initial' in cfg)
        check('initial_inventory_agreement',abs(E[0,0]-cfg.get('initial',6000)))
        if not development:check('matched_initial6000',abs(E[0,0]-6000))
        target=cfg.get('final')
        if not allow_free_end:
            require('hard_terminal_declared',target==6000);check('true_terminal6000',abs(E[-1,-1]-6000))
        elif target is not None:check('declared_terminal',abs(E[-1,-1]-target))
        if cfg.get('closed_daily'):check('declared_daily_closure',np.abs(E[:,-1]-6000).max())
        check('unaltered_actual_scoring_price',np.abs(p-(data['price'][days] if variable else data['day_price'])).max(),1e-12)
        require('root_original_contract_finite',np.isfinite(releases[:,0]).all())
        check('original_q_release',np.abs(releases[:,0]-q).max())
        if official:
            effective=q.copy()
            for k in range(1,4):
                require(f'release{k}_past_delivery_unset',np.isnan(releases[:,k,:36*k]).all())
                future=releases[:,k,36*k:]
                require(f'release{k}_future_finite',np.isfinite(future).all())
                effective[:,36*k:]=future
            check('effective_r_reconstructed',np.abs(effective-r).max())
            check('first_six_hours_unchanged',np.abs(q[:,:36]-r[:,:36]).max())
        else:
            check('Q2_no_adjustment',np.abs(q-r).max())
            require('forbidden_releases_unset',np.isnan(releases[:,1:]).all())
        parts={'planned_cost':p*q,'increase_cost':1.5*p*np.maximum(r-q,0),
               'reduction_net_cost':-.5*p*np.maximum(q-r,0),'emergency_cost':5*p*e}
        parts['total_cost']=sum(parts.values());totals=m['totals'];daily=m['daily']
        require('daily_log_count',len(daily)==N)
        require('daily_log_dates',[x['date'] for x in daily]==a['dates'].tolist())
        independent_totals={k:float(v.sum()) for k,v in parts.items()}
        for key,values in parts.items():
            check('aggregate:'+key,abs(values.sum()-totals[key]),MONEY)
            check('daily:'+key,np.abs(values.sum(1)-[x[key] for x in daily]).max(),MONEY)
        for key,values in [('emergency_energy',e),('spill_energy',spill)]:
            independent_totals[key]=float(values.sum())
            check('aggregate:'+key,abs(values.sum()-totals[key]),MONEY)
            check('daily:'+key,np.abs(values.sum(1)-[x[key] for x in daily]).max(),MONEY)
        check('daily_ending_inventory',np.abs(E[:,-1]-[x['ending_inventory'] for x in daily]).max())
        # Metadata catches illegal recorded dates, not producer behavior under mutation.
        decisions=m.get('decisions',[])
        require('decision_log_complete',len(decisions)==N*4)
        expected_asofs=[int(d*144+k*36) for d in days for k in range(4)]
        require('decision_clock', [z['as_of'] for z in decisions]==expected_asofs)
        for z in decisions:
            now,end=z['as_of'],z['end']
            if 'horizon_hours' in cfg:
                mode=cfg.get('horizon_mode','fixed')
                require(f'known_horizon_mode:{now}',mode in ('fixed','legacy'))
                expected_end=now+6*cfg['horizon_hours'] if mode=='fixed' else (now//144+cfg['horizon_hours']//24)*144
                require(f'{mode}_horizon:{now}',end==min(expected_end,144*(int(days[-1])+1)))
            origins=z.get('history_origins')
            if origins is None and 'history_days' in z:origins=[144*d+now%144 for d in z['history_days']]
            if origins is not None:require(f'mature_whole_blocks:{now}',all(h+end-now<=now for h in origins))
            else:scope.append(f'maturity metadata missing at {now}; separate information gate required')
            if z.get('latest_training_target_exclusive') is not None:require(f'recorded_maturity:{now}',z['latest_training_target_exclusive']<=now)
        return {'passed':not errors,'checks':checks,'errors':errors,'independent_totals':independent_totals,
                'independent_daily_total_cost':parts['total_cost'].sum(1).tolist(),'scope_notes':sorted(set(scope))}
    except Exception as exc:
        return {'passed':False,'checks':checks,'errors':errors+[f'{type(exc).__name__}: {exc}'],'scope_notes':scope}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trajectory',type=Path,required=True);parser.add_argument('--metrics',type=Path,required=True)
    parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-free-end',action='store_true');parser.add_argument('--development',action='store_true')
    args=parser.parse_args();started=time.perf_counter()
    paths={'trajectory':args.trajectory,'metrics':args.metrics,'data':args.data}
    missing=[str(p) for p in paths.values() if not p.is_file()]
    if missing:report={'passed':False,'status':'PENDING','missing':missing};code=2
    else:
        report=audit_arrays(dict(np.load(args.data,allow_pickle=False)),dict(np.load(args.trajectory,allow_pickle=False)),json.loads(args.metrics.read_text()),args.allow_free_end,args.development)
        report['status']='PASS' if report['passed'] else 'FAIL';code=0 if report['passed'] else 1
        report['input_hashes']={k:sha(v) for k,v in paths.items()}
    report.update(reviewer_id='/root/upgrade_code_review',independent=True,
        scope='Numerical physics, billing, release reconstruction and recorded metadata only. Separate executable information-mutation and model-formula gates mandatory.',
        execution={'command':sys.argv,'exit_code':code,'runtime_seconds':time.perf_counter()-started,'created_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(__file__)})
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':report['status'],'errors':report.get('errors',[]),'output':str(args.output)},ensure_ascii=False));sys.exit(code)

if __name__=='__main__':main()
