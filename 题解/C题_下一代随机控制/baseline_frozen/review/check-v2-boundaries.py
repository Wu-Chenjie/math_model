"""Independent limited audit of v2 terminal handling and economic-only Q1.

python3 review/check-v2-boundaries.py
python3 review/check-v2-boundaries.py --month-only
The latter completes the actual cross-month test when its D1 model is ready.
"""
from pathlib import Path
import hashlib, importlib.util, json, sys, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import run as rr
import control as cc
import dispatch

DATA=dict(np.load(ROOT/'artifacts/data.npz'))
SEL=json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
OUT=ROOT/'review/v2-boundary-review.json'
FILES=['src/run.py','src/control.py','src/dispatch.py','src/check_terminal.py','src/sddp.py']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def hashes():return {p:sha(ROOT/p) for p in FILES}
def error(a,b):return float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
def check(a,b,tol=1e-6):
    v=error(a,b);assert v<=tol,v;return v

def q1_check():
    spec=importlib.util.spec_from_file_location('independent_oracle',ROOT/'review/check-global-oracle.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    net=(DATA['day_load']-DATA['day_pv'])/6;p=DATA['day_price']
    solved,arrays=oracle.one_case(oracle.matrices(144),net,p,6000.,'q1_independent')
    producer=dispatch.solve(net[None,:],p[None,:],hard=True)
    saved=json.loads((ROOT/'artifacts/q1.json').read_text());a=dict(np.load(ROOT/'artifacts/q1.npz'))
    values=[producer['expected_cost'],producer['lp_objective'],saved['expected_cost'],saved['lp_objective'],float(p@a['q'])]
    for value in values:check(value,solved['objective_cost_yuan'],1e-6)
    c,d,q,E=[a[k] for k in ['c','d','q','state']]
    checks={'max_simultaneous':check(np.minimum(c,d),0),
            'soc_recurrence':check(np.diff(E),.9*c-d/.9),
            'initial':check(E[0],6000),'terminal':check(E[-1],6000),
            'max_shortage_without_emergency':float(max(0,(net+c-d-q).max())),
            'max_economic_objective_difference':max(abs(v-solved['objective_cost_yuan']) for v in values)}
    assert checks['max_shortage_without_emergency']<1e-6
    assert E.min()>=1200-1e-6 and E.max()<=10800+1e-6
    assert min(q.min(),c.min(),d.min())>=-1e-6 and max(c.max(),d.max())<=5000/6+1e-6
    # Algebraic normalization on deliberately simultaneous random flows.
    rng=np.random.default_rng(250611);c=rng.uniform(0,5000/6,1000);d=rng.uniform(0,5000/6,1000)
    rem=np.minimum(c,d/.9**2);c1=c-rem;d1=d-.9**2*rem
    checks['normalization_delta_error']=check(.9*c-d/.9,.9*c1-d1/.9)
    checks['normalization_net_supply_error']=check(d1-c1-(d-c),(1-.9**2)*rem)
    checks['normalization_simultaneous']=check(np.minimum(c1,d1),0)
    assert (c1>=-1e-10).all() and (d1>=-1e-10).all()
    return {'passed':True,'cost_yuan':solved['objective_cost_yuan'],'independent_duality_gap':solved['checks']['primal_minus_repaired_dual'],
            'checks':checks,'q1_artifact_sha256':{'json':sha(ROOT/'artifacts/q1.json'),'npz':sha(ROOT/'artifacts/q1.npz')},
            'scope':'Explicit-spill independent LP agrees with economic-only producer and regenerated artifact; normalization preserves SOC and permits extra free spill.'}

def route_check():
    class Intercept(Exception):pass
    original=rr.tail_file;rows=[]
    def record(kind,cutoff,days=3):
        rows.append({'kind':kind,'cutoff':cutoff,'days':days});raise Intercept()
    rr.tail_file=record
    try:
        for length,expected in [(3,1),(4,2),(5,3),(8,3)]:
            try:rr.simulate(DATA,SEL,list(range(58,58+length)),'q2','sddp_mpc',count=3)
            except Intercept:pass
            else:raise AssertionError('Expected a tail request')
            assert rows[-1]=={'kind':'q2','cutoff':31,'days':expected}
        # H=T: there must be no tail request; nonstandard initial proves it is
        # inherited even when this standalone replay starts inside the year.
        a,m=rr.simulate(DATA,SEL,[363,364],'q2','sddp_mpc',count=3,initial=7123.)
        check(a['state'][0,0],7123)
        assert all(z['tail_model_days'] is None and z['tail_cut_count']==0 and z['tail_price']==0 for z in m['decisions'])
    finally:rr.tail_file=original
    # Numeric reachable-set proof for every prefix action, independent of state.
    prefix_last_day=362;T=365*144
    remaining=T-(np.arange(31*144,(prefix_last_day+1)*144))-1
    lower=6000-remaining*.9*(5000/6);upper=6000+remaining*(5000/6)/.9
    assert lower.max()<=1200 and upper.min()>=10800
    return {'passed':True,'intercepted_requests':rows,'actual_zero_tail_decisions':len(m['decisions']),
            'optional_initial_kwh':7123.,'prefix_last_date':str(DATA['dates'][prefix_last_day]),
            'minimum_remaining_steps_in_prefix':int(remaining.min()),
            'steps_sufficient_for_entire_SOC_range':7,
            'minimum_prefix_reachability_slack_kwh':float(min(1200-lower.max(),upper.min()-10800)),
            'scope':'Intercepted file requests test routing only. The zero-tail case executes actual original data.'}

def suffix_check():
    rows=[]
    for candidate in ['affine_mpc','markov_mpc']:
        path=ROOT/f'artifacts/annual/q2_{candidate}.npz'
        a=dict(np.load(path));m=json.loads(path.with_suffix('.json').read_text())
        check(a['days'],np.arange(31,365),0)
        config=m['configuration'];assert config['horizon_days']==2 and config['final'] is None
        kw={k:config[k] for k in ['count','horizon_days','tail_scale','grid']}
        ix=len(a['days'])-4;init=float(a['state'][ix,0]);days=a['days'][ix:].tolist()
        free,fm=rr.simulate(DATA,SEL,days,'q2',candidate,initial=init,**kw)
        fixed,xm=rr.simulate(DATA,SEL,days,'q2',candidate,initial=init,final=6000.,**kw)
        two,tm=rr.simulate(DATA,SEL,days[-2:],'q2',candidate,initial=float(a['state'][-2,0]),final=6000.,**kw)
        full_error={};prefix_error={};suffix_error={}
        for key in ['q','r','c','d','emergency','spill','state']:
            full_error[key]=check(free[key],a[key][ix:],1e-5)
            prefix_error[key]=check(fixed[key][:2],free[key][:2],1e-5)
            suffix_error[key]=check(fixed[key][2:],two[key],1e-5)
        check(fixed['state'][-1,-1],6000)
        check(two['state'][0,0],a['state'][-2,0])
        check(fixed['state'][1:,0],fixed['state'][:-1,-1])
        rows.append({'candidate':candidate,'source_sha256':sha(path),'initial_four_day_inventory':init,
                     'suffix_initial_inventory':float(a['state'][-2,0]),
                     'free_replay_max_differences':full_error,'fixed_prefix_max_differences':prefix_error,
                     'two_day_vs_four_day_fixed_suffix_differences':suffix_error,
                     'free_final_inventory':fm['validation']['final_inventory'],'fixed_final_inventory':xm['validation']['final_inventory']})
    return {'passed':True,'cases':rows,
            'scope':'Two Q2 linear-tail policies only; four-day replay, same two-day prefix under free/fixed global end, and exact match to inherited two-day suffix. This does not establish reuse across changed SDDP tail model versions.'}

def month_check():
    path=rr.tail_file('q2',31,1)
    if not path.exists():return {'passed':False,'status':'pending_input','required_file':str(path.relative_to(ROOT))}
    model=json.loads(path.read_text());meta=model['configuration']
    assert meta['cutoff_day_exclusive']==31 and meta['horizon_days']==1 and max(meta['history_days'])<31
    a,m=rr.simulate(DATA,SEL,[58,59,60],'q2','sddp_mpc',count=3,initial=6432.)
    check(a['state'][0,0],6432)
    check(a['state'][1:,0],a['state'][:-1,-1])
    for z in m['decisions']:
        if z['end']<61*144:
            assert z['tail_model_cutoff']==31 and z['tail_model_days']==1 and z['tail_cut_count']>0
        else:assert z['tail_model_days'] is None and z['tail_cut_count']==0
    return {'passed':True,'status':'executed','model_sha256':sha(path),'decisions':m['decisions'],
            'midnight_inventories':a['state'][:,-1].tolist(),'validation':m['validation'],
            'scope':'Actual February 28 root horizon reaches March; uses known February cutoff with only one remaining auxiliary day, then no tail at H=T.'}

def main():
    start=time.perf_counter();before=hashes();month_only='--month-only' in sys.argv
    if month_only:
        report=json.loads(OUT.read_text())
        # Only check_terminal may receive added guards without affecting earlier
        # runtime tests; production numerical modules must still match.
        for key in ['src/run.py','src/control.py','src/dispatch.py','src/sddp.py']:
            assert report['source_hashes'][key]==before[key],key
        report['checks']['actual_cross_month_D1']=month_check()
    else:
        report={'schema_version':1,'reviewer_id':'/root/independent_review','independent':True,
                'scope':'v2_boundary_and_q1_only','annual_final_review':'pending','checks':{}}
        for name,fn in [('q1_economic_and_normalization',q1_check),('tail_routing_and_reachable_prefix',route_check),
                        ('inherited_suffix_replay',suffix_check),('actual_cross_month_D1',month_check)]:
            print(name,flush=True);report['checks'][name]=fn()
    after=hashes()
    for key in ['src/run.py','src/control.py','src/dispatch.py','src/sddp.py']:assert before[key]==after[key],key
    report['source_hashes']=after
    report['passed']=all(v['passed'] for v in report['checks'].values())
    report['status']='pass_within_scope' if report['passed'] else 'pending_actual_D1_model_test'
    report.setdefault('executions',[]).append({'command':'python3 review/check-v2-boundaries.py'+(' --month-only' if month_only else ''),
                                              'exit_code':0,'runtime_seconds':time.perf_counter()-start})
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':report['status'],'seconds':time.perf_counter()-start}),flush=True)

if __name__=='__main__':main()
