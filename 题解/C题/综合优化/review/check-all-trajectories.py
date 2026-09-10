"""Independent reconciliation of all 32 annual controller runs; read-only inputs."""
from pathlib import Path
import json,hashlib
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
MAIN={'baseline':('common','greedy'),'common_mpc':('common','mpc'),
      'affine_feedback':('affine','affine'),'affine_mpc':('affine','mpc'),
      'affine_saa_mpc':('affine','saa_mpc'),'affine_sdp':('affine','sdp')}
EXTRA={'common_saa_mpc':('common','saa_mpc'),'common_sdp':('common','sdp')}
KINDS=['q2','q3','q4_2','q4_3']

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def close(a,b,tol=1e-6):
    gap=float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
    assert gap<tol,(gap,tol)
    return gap

def main():
    data=dict(np.load(BASE/'artifacts/data.npz'));days=np.arange(31,365)
    net=(data['load'][days]-data['pv'][days])/6
    reports=[];hashes={};log_checks={};original_gaps={}
    for phase,pool in [('annual',MAIN),('diagnostic',EXTRA)]:
        ep=ROOT/f'artifacts/execution-{phase}.json';ex=json.loads(ep.read_text())
        assert ex['exit_code']==0 and ex['runtime_seconds']>0
        logged={(x['kind'],x['candidate']):x for x in ex['results']}
        assert len(logged)==len(ex['results'])==4*len(pool)
        assert set(logged)=={(k,c) for k in KINDS for c in pool}
        hashes[ep.relative_to(ROOT).as_posix()]=digest(ep)
        for kind in KINDS:
            price=data['price'][days] if kind.startswith('q4') else np.broadcast_to(data['day_price'],net.shape)
            revised=kind in ['q3','q4_3']
            for candidate,configuration in pool.items():
                stem=ROOT/f'artifacts/{phase}/{kind}_{candidate}'
                a=dict(np.load(stem.with_suffix('.npz')));m=json.loads(stem.with_suffix('.json').read_text())
                for ext in ['.json','.npz']:
                    path=stem.with_suffix(ext);hashes[path.relative_to(ROOT).as_posix()]=digest(path)
                assert m['kind']==kind and m['candidate']==candidate
                cfg=m['configuration'];assert (cfg['upper'],cfg['lower'])==configuration
                assert cfg['window']==28 and cfg['alpha']==.2 and cfg['grid_size']==321
                assert cfg['start_day']==31 and cfg['end_day']==364
                assert np.array_equal(a['days'],days) and np.array_equal(a['dates'],data['dates'][days])
                assert [r['date'] for r in m['daily']]==a['dates'].tolist()
                for key in ['q','r','c','d','emergency','spill','projection','price']:
                    assert a[key].shape==(334,144) and np.isfinite(a[key]).all(),(kind,candidate,key)
                    assert a[key].min()>=-1e-8
                assert price.min()>0 and np.array_equal(a['price'],price)
                E=a['state'];assert E.shape==(334,145) and np.isfinite(E).all()
                assert E.min()>=1200-1e-6 and E.max()<=10800+1e-6
                terminal=close(E[:,[0,-1]],6000)
                # Derive both bus flows from stored energy changes, independently
                # enforcing the physical one-direction battery implementation.
                change=np.diff(E,axis=1)
                c=np.maximum(change,0)/.9;d=np.maximum(-change,0)*.9
                flow_gap=max(close(c,a['c']),close(d,a['d']))
                assert max(c.max(),d.max())*6<=5000+1e-6
                nrem=net-a['r']+c-d
                emergency=np.maximum(nrem,0);spill=np.maximum(-nrem,0)
                balance=max(close(emergency,a['emergency']),close(spill,a['spill']))
                # Stronger than checking only reconstruction: illegal publications
                # must be absent, and every legal publication must be complete.
                releases=a['releases'];assert releases.shape==(334,4,144)
                mask=np.ones((4,144),dtype=bool)
                for k in range(4 if revised else 1):mask[k,k*36:]=False
                assert np.array_equal(np.isnan(releases),np.broadcast_to(mask,releases.shape))
                assert np.isfinite(releases[:,~mask]).all() and releases[:,~mask].min()>=-1e-8
                release_gap=close(releases[:,0],a['q'])
                actual_contract=np.empty_like(a['r'])
                for t in range(144):actual_contract[:,t]=releases[:,t//36 if revised else 0,t]
                release_gap=max(release_gap,close(actual_contract,a['r']))
                q,r=a['q'],actual_contract
                components={
                    'planned_cost':np.sum(price*q,axis=1),
                    'increase_cost':np.sum(price*1.5*np.maximum(r-q,0),axis=1),
                    'reduction_net_cost':np.sum(price*(-.5)*np.maximum(q-r,0),axis=1),
                    'emergency_cost':np.sum(5*price*emergency,axis=1)}
                fee=sum(components.values());components['total_cost']=fee
                components.update(emergency_energy=emergency.sum(1),planned_energy=q.sum(1),
                                  adjusted_energy=r.sum(1),spill_energy=spill.sum(1))
                component_gap=0.;total_gap=0.
                for key,values in components.items():
                    component_gap=max(component_gap,close(values,[x[key] for x in m['daily']]))
                    total_gap=max(total_gap,close(values.sum(),m['totals'][key],1e-4))
                close(np.quantile(fee,.95),m['totals']['daily_cost_p95'])
                close(fee.max(),m['totals']['worst_day_cost'])
                close(fee.sum(),logged[(kind,candidate)]['total_cost'],1e-4)
                assert m['validation']['lp_eq_max_abs']<1e-5 and m['validation']['lp_ineq_max']<1e-5
                if candidate=='baseline':
                    old=dict(np.load(BASE/f'artifacts/{kind}.npz'))
                    original_gaps[kind]={key:close(a[key],old[key]) for key in ['q','r','c','d','emergency','spill','state']}
                reports.append({'name':kind+'_'+candidate,'phase':phase,'status':'pass','days':334,
                                'total_cost_recomputed':float(fee.sum()),'daily_metric_max_abs':component_gap,
                                'annual_metric_max_abs':total_gap,'battery_flow_max_abs':flow_gap,
                                'emergency_spill_max_abs':balance,'initial_terminal_max_abs':terminal,
                                'legal_release_mask':True,'final_contract_reconstruction_max_abs':release_gap})
        log_checks[phase]={'exit_code':0,'unique_complete_runs':len(logged)}
    for relative in ['src/run_comparison.py','src/run_diagnostics.py','src/controllers.py',
                     'src/validate_extension.py','artifacts/falsification.json']:
        hashes[relative]=digest(ROOT/relative)
    report={'status':'pass_for_32_completed_trajectories','scope':'32 complete annual candidates; no project acceptance or causal proof from arrays alone',
            'checks':reports,'execution_log_checks':log_checks,'baseline_reproduction':original_gaps,
            'causality_evidence':'Exact publication permissions verified from all arrays; controller information flow audited in source and recorded future-mutation checks. Current actual prices are scoring-only by the declared restricted information class.',
            'comparison_scope':'All eight candidates within each setting share dates, forecasts, residual window, physical/terminal policies and settlement. Q3/Q4-3 comparisons include subsequent contract feedback from each own SOC; added diagnostics are excluded from original six-candidate selector.',
            'reviewed_artifact_hashes':hashes}
    (ROOT/'review/all-trajectories-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'runs':len(reports),'slots':32*334*144,
                      'maximum_metric_error':max(x['annual_metric_max_abs'] for x in reports),
                      'maximum_flow_error':max(x['battery_flow_max_abs'] for x in reports),
                      'maximum_contract_error':max(x['final_contract_reconstruction_max_abs'] for x in reports)},ensure_ascii=False))

if __name__=='__main__':main()
