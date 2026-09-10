"""Independently reconcile every completed q2 convex day; no producer outputs changed."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent
sys.path.insert(0,str(ROOT/'src'))
from convex_aggregation import fit_weights

def main():
    m=json.loads((ROOT/'artifacts/q2_convex.json').read_text())
    mixed=dict(np.load(ROOT/'artifacts/q2_convex.npz'))
    names=m['expert_names'];experts=[]
    for name in names:
        p=[dict(np.load(ROOT/f'artifacts/{phase}/q2_{name}.npz')) for phase in ['calibrate','annual']]
        experts.append({k:np.concatenate([s[k] for s in p]) for k in p[0]})
    for relative,digest in m['source_hashes'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest
    days=experts[0]['days'];dates=experts[0]['dates']
    assert np.array_equal(days,np.arange(21,365))
    assert np.array_equal(mixed['days'],np.arange(31,365))
    assert all(np.array_equal(x['days'],days) and np.array_equal(x['dates'],dates) for x in experts)
    assert [x['date'] for x in m['daily']]==mixed['dates'].tolist()==dates[10:].tolist()
    Q=np.stack([x['q'] for x in experts],-1);R=np.stack([x['r'] for x in experts],-1)
    E=np.stack([x['state'] for x in experts],-1);delta=np.diff(E,axis=1)
    data=dict(np.load(BASE/'artifacts/data.npz'))
    n=(data['load'][days]-data['pv'][days])/6
    p=np.broadcast_to(data['day_price'],n.shape)
    assert all(np.array_equal(x['price'],p) for x in experts)
    eta=.9;W=mixed['weights']
    assert W.shape==(334,6) and np.isfinite(W).all() and W.min()>=0
    assert np.max(abs(W.sum(1)-1))<1e-12
    assert np.max(abs(W-np.array(m['weights'])))==0
    q=np.einsum('dtk,dk->dt',Q[10:],W);r=np.einsum('dtk,dk->dt',R[10:],W)
    state=np.einsum('dtk,dk->dt',E[10:],W);dE=np.diff(state,axis=1)
    c=np.maximum(dE,0)/eta;d=eta*np.maximum(-dE,0)
    em=np.maximum(n[10:]+c-d-r,0);spill=np.maximum(r+d-c-n[10:],0)
    reconstructed={'q':q,'r':r,'state':state,'c':c,'d':d,'emergency':em,'spill':spill,'price':p[10:]}
    differences={k:float(np.max(abs(v-mixed[k]))) for k,v in reconstructed.items()}
    assert max(differences.values())<1e-7
    assert state.min()>=1200-1e-7 and state.max()<=10800+1e-7
    assert max(c.max(),d.max())*6<=5000+1e-7
    assert np.max(abs(state[:,[0,-1]]-6000))<1e-7
    assert np.min(np.stack([q,r,c,d,em,spill]))>=0
    balance=float(np.max(abs(r+d+em-c-spill-n[10:])))
    recurrence=float(np.max(abs(np.diff(state,axis=1)-eta*c+d/eta)))
    assert max(balance,recurrence)<1e-7
    fee=(p[10:]*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0)+5*em)).sum(1)
    daily=np.array([x['total_cost'] for x in m['daily']])
    assert np.max(abs(fee-daily))<1e-6 and abs(fee.sum()-m['totals']['total_cost'])<1e-5
    component={
        'planned_cost':(p[10:]*q).sum(1),
        'increase_cost':(1.5*p[10:]*np.maximum(r-q,0)).sum(1),
        'reduction_net_cost':(-.5*p[10:]*np.maximum(q-r,0)).sum(1),
        'emergency_cost':(5*p[10:]*em).sum(1)}
    component_gaps={k:float(max(np.max(abs(v-np.array([x[k] for x in m['daily']]))),abs(v.sum()-m['totals'][k]))) for k,v in component.items()}
    assert max(component_gaps.values())<1e-5
    individual=np.stack([(x['price']*(x['q']+1.5*np.maximum(x['r']-x['q'],0)-.5*np.maximum(x['q']-x['r'],0)+5*x['emergency'])).sum(1) for x in experts],axis=-1)
    weighted=np.sum(W*individual[10:],axis=1)
    dominance=float(np.max(fee-weighted))
    assert dominance<1e-5
    assert np.max(abs(weighted-np.array([x['weighted_expert_cost'] for x in m['daily']])))<1e-6
    snapshots=np.stack([x['releases'][10:] for x in experts],axis=-1)
    assert all(np.array_equal(np.isnan(snapshots[...,0]),np.isnan(snapshots[...,k])) for k in range(6))
    aggregated=np.sum(snapshots*W[:,None,None,:],axis=-1)
    assert np.array_equal(np.isnan(aggregated),np.isnan(mixed['releases']))
    release_diff=float(np.nanmax(abs(aggregated-mixed['releases'])))
    assert release_diff<1e-7 and np.nanmax(abs(aggregated[:,0]-q))<1e-7
    assert np.nanmax(abs(aggregated[:,0]-r))<1e-7
    assert np.isnan(aggregated[:,1:]).all()
    window_details=[];max_training_gap=0.;max_vertex_gap=0.
    for j in range(334):
        i=j+10;past=np.flatnonzero((days<days[i])&(days>=days[i]-28))
        assert np.array_equal(past,np.arange(max(0,i-28),i))
        w=W[j];qp=Q[past]@w;rp=R[past]@w;sp=E[past]@w
        de=np.diff(sp,axis=1);cp=np.maximum(de,0)/eta;dp=eta*np.maximum(-de,0)
        ep=np.maximum(n[past]+cp-dp-rp,0)
        training=float(np.sum(p[past]*(qp+1.5*np.maximum(rp-qp,0)-.5*np.maximum(qp-rp,0)+5*ep)))
        best=float(individual[past].sum(0).min());fit=m['training_log'][j]
        max_training_gap=max(max_training_gap,abs(training-fit['objective']))
        max_vertex_gap=max(max_vertex_gap,abs(best-fit['best_vertex_cost']))
        assert training<=best+1e-4
        assert abs(training-fit['objective'])<1e-5 and abs(best-fit['best_vertex_cost'])<1e-5
        if j in [0,28,170,333]:window_details.append({'date':str(dates[i]),'first_training_date':str(dates[past[0]]),'last_training_date':str(dates[past[-1]]),'count':len(past)})
    # Independent selected-window refits verify saved weights against the past-only solver interface.
    refits=[]
    for j in [0,28,170]:
        i=j+10;past=np.flatnonzero((days<days[i])&(days>=days[i]-28))
        w,fit=fit_weights(Q[past],R[past],delta[past],n[past],p[past])
        gap=float(np.max(abs(w-W[j])))
        assert gap<1e-8
        refits.append({'date':str(dates[i]),'weight_max_abs':gap,'objective_difference':abs(fit['objective']-m['training_log'][j]['objective'])})
    report={'scope':'Completed q2 convex aggregation only; other settings and project acceptance pending',
        'status':'pass_for_q2_annual','days':334,'slots':334*144,'experts':names,
        'expert_source_hashes_verified':len(m['source_hashes']),
        'aggregation_field_max_abs':differences,'weight_sum_max_abs':float(np.max(abs(W.sum(1)-1))),
        'balance_max_abs':balance,'soc_recurrence_max_abs':recurrence,'soc_min':float(state.min()),'soc_max':float(state.max()),
        'maximum_power_kw':float(6*max(c.max(),d.max())),'initial_terminal_max_abs':float(np.max(abs(state[:,[0,-1]]-6000))),
        'annual_cost_recomputed':float(fee.sum()),'annual_cost_difference':abs(float(fee.sum())-m['totals']['total_cost']),
        'daily_cost_max_abs':float(np.max(abs(fee-daily))),'component_max_abs':component_gaps,
        'convex_bound_max_difference':dominance,'convex_gain_recomputed':float((weighted-fee).sum()),
        'published_snapshot_max_abs':release_diff,'unpublished_masks':'all q2 later-release masks remain NaN',
        'all_history_windows':'all 334 windows exclude current and future dates',
        'training_objective_max_abs':max_training_gap,'training_best_vertex_max_abs':max_vertex_gap,
        'window_examples':window_details,'selected_window_refits':refits,
        'future_mutation_evidence':'review/convex-checks.json: current/future perturbations leave the three selected-window weights unchanged',
        'artifact_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in ['artifacts/q2_convex.json','artifacts/q2_convex.npz','src/convex_aggregation.py']}}
    (ROOT/'review/convex-q2-annual-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
