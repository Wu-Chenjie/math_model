"""Independent real-window, physical mixing and publication checks for q2 only."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent
sys.path.insert(0,str(ROOT/'src'))
from convex_aggregation import fit_weights
from run_comparison import CANDIDATES

ETA=.9;M=5000/6
def main():
    names=list(CANDIDATES);parts={};costs={}
    for c in names:
        raw=[dict(np.load(ROOT/f'artifacts/{phase}/q2_{c}.npz')) for phase in ['calibrate','annual']]
        parts[c]={k:np.concatenate([x[k] for x in raw],axis=0) for k in raw[0]}
        m=[json.loads((ROOT/f'artifacts/{phase}/q2_{c}.json').read_text()) for phase in ['calibrate','annual']]
        rows=m[0]['daily']+m[1]['daily'];costs[c]=np.array([x['total_cost'] for x in rows])
        assert [x['date'] for x in rows]==parts[c]['dates'].tolist()
    days=parts[names[0]]['days'];dates=parts[names[0]]['dates']
    assert np.array_equal(days,np.arange(21,365))
    assert all(np.array_equal(parts[c]['days'],days) for c in names)
    Q=np.stack([parts[c]['q'] for c in names],axis=-1)
    R=np.stack([parts[c]['r'] for c in names],axis=-1)
    E=np.stack([parts[c]['state'] for c in names],axis=-1)
    Delta=np.diff(E,axis=1)
    P=parts[names[0]]['price']
    assert all(np.array_equal(parts[c]['price'],P) for c in names)
    source=dict(np.load(BASE/'artifacts/data.npz'))
    N=(source['load'][days]-source['pv'][days])/6
    costs=np.stack([costs[c] for c in names],axis=-1)
    out={'scope':'q2 independent real-history windows and publication algebra; not other incomplete problem sets',
         'source_sha256':hashlib.sha256((ROOT/'src/convex_aggregation.py').read_bytes()).hexdigest(),
         'expert_names':names,'checks':{}}
    def evaluate(w,index):
        q=Q[index]@w;r=R[index]@w;state=E[index]@w;delta=np.diff(state,axis=-1)
        c=np.maximum(delta,0)/ETA;d=ETA*np.maximum(-delta,0)
        em=np.maximum(N[index]+c-d-r,0);spill=np.maximum(r+d-c-N[index],0)
        p=P[index]
        fee=p*q+1.5*p*np.maximum(r-q,0)-.5*p*np.maximum(q-r,0)+5*p*em
        assert max(abs((r+em+d-c-spill-N[index]).ravel()))<1e-7
        assert max(abs((np.diff(state,axis=-1)-ETA*c+d/ETA).ravel()))<1e-7
        assert state.min()>=1200-1e-6 and state.max()<=10800+1e-6
        assert max(c.max(),d.max())<=M+1e-6
        assert np.max(abs(state[...,0]-6000))<1e-6 and np.max(abs(state[...,-1]-6000))<1e-6
        return fee.sum(axis=-1)
    window_checks=[]
    for i in [10,38,180]:
        # Independent timestamp construction, rather than trusting producer's fixed index slice.
        take=np.flatnonzero((days<days[i])&(days>=days[i]-28))
        assert np.array_equal(take,np.arange(max(0,i-28),i))
        w,info=fit_weights(Q[take],R[take],Delta[take],N[take],P[take])
        actual=float(np.sum(evaluate(w,take)))
        assert abs(actual-info['objective'])<1e-5
        best=float(costs[take].sum(0).min())
        assert actual<=best+1e-4
        # Modify every current/future expert and physical observation; past-date weight remains unchanged.
        qm=Q.copy();rm=R.copy();dm=Delta.copy();nm=N.copy();pm=P.copy()
        qm[i:]+=10000;rm[i:]+=5000;dm[i:]+=1000;nm[i:]+=20000;pm[i:]*=4
        same,other=fit_weights(qm[take],rm[take],dm[take],nm[take],pm[take])
        diff=float(np.max(abs(same-w)))
        assert diff<1e-10 and abs(other['objective']-info['objective'])<1e-6
        realcost=float(evaluate(w,i));weighted=float(costs[i]@w)
        assert realcost<=weighted+1e-4
        window_checks.append({'date':str(dates[i]),'training_first_date':str(dates[take[0]]),'training_last_date':str(dates[take[-1]]),
            'training_days':len(take),'weight_sum':float(w.sum()),'minimum_weight':float(w.min()),
            'independent_training_cost':actual,'best_single_expert_training_cost':best,
            'training_objective_difference':abs(actual-info['objective']),
            'future_mutation_weight_max_abs':diff,'real_day_mixed_cost':realcost,'weighted_expert_cost':weighted})
    out['checks']['past_only_real_windows']=window_checks
    # Random and zero-weight examples challenge convex feasibility and the publication mask.
    rng=np.random.default_rng(2806)
    weights=[np.ones(6)/6,np.eye(6)[2]]+[rng.dirichlet(np.ones(6)) for _ in range(6)]
    maximum_violation=0.;release_error=0.;tested=0
    for i in [10,38,110,240,343]:
        snapshots=np.stack([parts[c]['releases'][i] for c in names],axis=-1)
        assert all(np.array_equal(np.isnan(snapshots[...,k]),np.isnan(snapshots[...,0])) for k in range(6))
        for w in weights:
            fee=float(evaluate(w,i));upper=float(costs[i]@w)
            maximum_violation=max(maximum_violation,fee-upper)
            assert fee<=upper+1e-4
            mixed=sum(w[k]*snapshots[...,k] for k in range(6))
            assert np.array_equal(np.isnan(mixed),np.isnan(snapshots[...,0]))
            error=max(float(np.max(abs(mixed[0]-Q[i]@w))),float(np.max(abs(mixed[0]-R[i]@w))))
            release_error=max(release_error,error)
            assert error<1e-7
            tested+=1
    out['checks']['random_weight_real_days']={'combinations':tested,'convex_upper_bound_violation':maximum_violation,'q2_publication_reconstruction_max_abs':release_error,'zero_weight_nan_mask':'pass'}
    # Four-release algebraic test, explicitly synthetic because q3 six-expert outputs are not yet complete.
    releases=np.full((4,144,6),np.nan)
    for k in range(4):releases[k,k*36:]=rng.uniform(0,1000,(144-k*36,6))
    final=np.empty((144,6))
    for k in range(4):final[k*36:(k+1)*36]=releases[k,k*36:(k+1)*36]
    w=weights[-1];mixed=sum(w[k]*releases[...,k] for k in range(6))
    reconstructed=np.concatenate([mixed[k,k*36:(k+1)*36] for k in range(4)])
    gap=float(np.max(abs(reconstructed-final@w)))
    altered=releases.copy();altered[3,108:]+=100000
    modified=sum(w[k]*altered[...,k] for k in range(6))
    assert gap<1e-9 and np.array_equal(mixed[:3],modified[:3],equal_nan=True)
    out['checks']['synthetic_four_release_test']={'final_contract_difference':gap,'future_publication_changes_prior_snapshots':False}
    out['status']='pass_for_reviewed_scope'
    (ROOT/'review/convex-checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
