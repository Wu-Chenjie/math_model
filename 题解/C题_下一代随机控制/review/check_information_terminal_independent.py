"""Read-only independent algebra/provenance audit; no controller/optimizer imported."""
from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT.parent/'C题_下一代基线复现'
TOL = 1e-6
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
def load(p):
    with np.load(p, allow_pickle=False) as z:
        return dict(z)
def same(a,b):
    if np.issubdtype(a.dtype, np.number):
        return bool(np.array_equal(a,b,equal_nan=True))
    return bool(np.array_equal(a,b))
def maximum(a):
    return float(np.max(np.abs(a),initial=0))
def require(condition, context):
    assert condition, context


def main():
    gate=read(ROOT/'artifacts/baseline-reproduction-check.json')
    require(gate['status']=='PASS' and gate['counts']=={'PASS':365}, 'reproduction gate')
    execution=read(ROOT/'artifacts/information-terminal-execution.json')
    require(execution['status']=='complete' and execution['execution']['exit_code']==0, 'execution')
    execution_rows={r['name']:r for r in execution['results']}
    evidence={}
    def bind(path):
        path=Path(path); key=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(Path('..')/path.relative_to(ROOT.parent))
        evidence[key]=sha(path)
        return evidence[key]
    def gate_bind(path):
        digest=bind(path)
        key=str(Path('..')/Path(path).relative_to(ROOT.parent))
        require(gate['evidence_hashes'].get(key)==digest, ('gate hash',key))
    gate_bind(REPLAY/'artifacts/data.npz')
    gate_bind(REPLAY/'artifacts/forecast-selection.json')
    for name in ['run.py','control.py','forecasting.py','dispatch.py','validate.py']:
        gate_bind(REPLAY/'src'/name)
        require(sha(REPLAY/'src'/name)==sha(ROOT/'baseline_frozen/src'/name),('frozen source',name))
    data=load(REPLAY/'artifacts/data.npz')
    results=[]
    for name, allowed in [('0only',[0]),('without6',[0,2,3]),('without12',[0,1,3]),('without18',[0,1,2])]:
        src=REPLAY/f'artifacts/experiments/annual_pv_{name}'
        out=ROOT/f'artifacts/information-terminal/q3_{name}'
        for suffix in ['.npz','.json']: gate_bind(src.with_suffix(suffix))
        a=load(out.with_suffix('.npz')); old=load(src.with_suffix('.npz'))
        m=read(out.with_suffix('.json')); om=read(src.with_suffix('.json'))
        require(m['kind']==om['kind']=='q3' and m['candidate']==om['candidate']=='markov_mpc','policy')
        require(m['validation_design']==om['validation_design'] and m['validation_design']['releases']==allowed,'release design')
        require(om['configuration']['final'] is None and om['configuration']['initial']==6000,'source endpoints')
        require(m['configuration']=={**om['configuration'],'initial':6000.,'final':6000.},'configuration')
        require(m['configuration']['horizon_days']==2 and not m['configuration']['closed_daily'],'prefix policy scope')
        pr=m['prefix_reuse']
        require(Path(pr['full_run_source'])==src and pr['source_npz_sha256']==sha(src.with_suffix('.npz')),'source binding')
        require(pr['reused_days']==332 and pr['replayed_days']==[363,364],'split')
        require(a.keys()==old.keys()==pr['free_suffix_max_errors'].keys(),'all arrays covered')
        for k in a:
            require(same(a[k][:332],old[k][:332]),('prefix exact',name,k))
            require(float(pr['free_suffix_max_errors'][k])==0.,('recorded free suffix',name,k))
        require(m['daily'][:332]==om['daily'][:332] and m['decisions'][:1328]==om['decisions'][:1328],'prefix metadata')
        require(np.array_equal(a['days'],np.arange(31,365)),'days')
        require(np.array_equal(a['dates'],data['dates'][31:]),'dates')
        q,r,c,d,e,s,p,E=(a[k] for k in ['q','r','c','d','emergency','spill','price','state'])
        n=(data['load'][31:]-data['pv'][31:])/6
        require(np.allclose(p,np.tile(data['day_price'],(334,1)),rtol=0,atol=0),'fixed price')
        checks={
            'balance_max_abs':maximum(r+e+d-c-s-n),
            'soc_recursion_max_abs':maximum(np.diff(E,axis=1)-.9*c+d/.9),
            'midnight_jump_max_abs':maximum(E[1:,0]-E[:-1,-1]),
            'simultaneous_max':float(np.minimum(c,d).max()),
            'energy_negative_max':max(0.,-float(min(v.min() for v in [q,r,c,d,e,s]))),
            'soc_bounds_violation':max(0.,1200-float(E.min()),float(E.max())-10800),
            'power_kwh_violation':max(0.,float(max(c.max(),d.max()))-5000/6),
            'initial_error':abs(float(E[0,0])-6000), 'final_error':abs(float(E[-1,-1])-6000),
        }
        require(max(checks.values())<TOL,('physical',name,checks))
        rel=a['releases']
        require(same(rel[:,0,:],q),'original q release')
        reconstructed=np.empty_like(r)
        for b in range(4):
            t=36*b
            require(np.isnan(rel[:,b,:t]).all() and np.isfinite(rel[:,b,t:]).all(),'release prefix mask')
            reconstructed[:,t:t+36]=rel[:,b,t:t+36]
        require(same(reconstructed,r) and same(r[:,:36],q[:,:36]),'final r latest release')
        require(len(m['decisions'])==1336,'all four contract opportunities retained')
        for i,z in enumerate(m['decisions']):
            day=31+i//4; phase=36*(i%4); now=day*144+phase; end=min((day+2)*144,365*144)
            require(z['as_of']==now and z['end']==end and z['release']==i%4,'decision clock')
            require(z['date']==a['dates'][i//4] and abs(z['inventory']-E[i//4,phase])<TOL,'decision state')
            maturity=max(z['history_days'])*144+phase+end-now
            require(z['latest_training_target_exclusive']==maturity and maturity<=now,'mature history')
            issue=max(t for t in range((day-1)*144,now+1,36) if (t%144)//36 in allowed)
            covered=max(0,min(end,issue+144)-now)
            require(z['official_covered_slots']==covered,'official allowed 24h coverage')
            require(z['tail_model_cutoff'] is None and z['tail_model_days'] is None and z['tail_cut_count']==0,'linear tail only')
            if i<1328: require(end<365*144,'true end outside prefix plans')
        daily={
            'planned_cost':np.sum(p*q,axis=1),
            'increase_cost':np.sum(1.5*p*np.maximum(r-q,0),axis=1),
            'reduction_net_cost':np.sum(-.5*p*np.maximum(q-r,0),axis=1),
            'emergency_cost':np.sum(5*p*e,axis=1),
            'total_cost':np.sum(p*(r+.5*np.abs(r-q)+5*e),axis=1),
            'emergency_energy':np.sum(e,axis=1),'spill_energy':np.sum(s,axis=1),
            'ending_inventory':E[:,-1],
        }
        errors={k:maximum(v-np.array([d[k] for d in m['daily']])) for k,v in daily.items()}
        require(max(errors.values())<TOL,('daily independent calculation',name,errors))
        totals={k:float(v.sum()) for k,v in daily.items() if k!='ending_inventory'}
        require(max(abs(v-m['totals'][k]) for k,v in totals.items())<1e-5,'totals')
        row=execution_rows[name]; checkpath=ROOT/row['validation']; prior=read(checkpath)
        require(prior['status']=='PASS' and prior['passed'] and prior['errors']==[],'producer independent validator')
        require(sha(checkpath)==row['validation_sha256'],'execution validator hash')
        require(sha(out.with_suffix('.npz'))==prior['input_npz_sha256'] and sha(out.with_suffix('.json'))==prior['input_json_sha256'],'validator inputs')
        require(abs(totals['total_cost']-row['total_cost_yuan'])<1e-5,'execution total')
        for path in [out.with_suffix('.npz'),out.with_suffix('.json'),checkpath]:bind(path)
        results.append({'name':name,'status':'PASS','independent_total_cost_yuan':totals['total_cost'],
            'physical_checks':checks,'daily_max_errors':errors,'prefix_arrays_exact':list(a),
            'recorded_free_suffix_max_abs':max(pr['free_suffix_max_errors'].values()),
            'free_suffix_evidence':'Producer rerun assertion and bound successful execution; free trajectories not separately retained, optimizer not rerun by this reviewer',
            'all_four_adjustment_opportunities_preserved':True})
    for path in ['artifacts/baseline-reproduction-check.json','artifacts/information-terminal-execution.json','tools/match_information_ablation_endpoints.py','review/check_information_terminal_independent.py']:bind(ROOT/path)
    report={'schema_version':1,'reviewer_id':'/root/independent_review','independent':True,
        'scope':'four_old_policy_information_ablations_with_matched_global_endpoints_only',
        'status':'PASS','decision':'bounded_information_ablation_audit_pass','unresolved':[],
        'independent_computation':'All physical, release, bill, daily, date, information timestamp and prefix-array equations recomputed with NumPy; no production numerical routines imported.',
        'reused_evidence':'Free-suffix replay zero errors and optimizer success are read from hash-bound producer artifacts; baseline 365-case PASS is a separately produced review, with relevant source/data/results hashes independently rechecked.',
        'optimization_executed':False,'results':results,
        'interpretation':'Old frozen two-midnight linear-tail Markov policy realization only; same initial/final 6000, information releases restricted but four adjustment opportunities retained. Neither optimal information value nor isolated new M1 benefit; not a proof for arbitrary long horizons.',
        'reviewed_artifact_hashes':evidence}
    (ROOT/'review/information-terminal-independent.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'costs':{r['name']:r['independent_total_cost_yuan'] for r in results}},ensure_ascii=False))
if __name__=='__main__':main()
