"""Independent, non-annual audit; writes only this review directory.

Run: python3 review/check-controllers.py
Uses separate SciPy LPs with bus charge/discharge variables for Bellman checks.
"""
from pathlib import Path
import hashlib, json, sys, time
import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import forecasting as fc
import control as ct
import run as replay

DATA = dict(np.load(ROOT/'artifacts/data.npz'))
SEL = json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
REPORT = {'scope': 'controller_implementation_and_development_trajectories_only',
          'reviewer_id': '/root/independent_review', 'independent': True,
          'annual_execution_review': 'pending', 'checks': {}}
SOURCE = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in [ROOT/'src/forecasting.py', ROOT/'src/control.py', ROOT/'src/run.py']}

def eq(a, b, tol=1e-7):
    error = float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
    assert error <= tol, error
    return error

def forecast_checks():
    evidence = []; root_checks = []
    for day in [31, 59, 60, 150, 333]:
        for offset in [0, 36, 72, 108, 120]:
            now = day*144+offset; end = min((day+3)*144, 365*144)
            targets = np.arange(now, end)
            changed = {k: v.copy() for k, v in DATA.items()}
            for k in ['load', 'pv', 'price']:
                changed[k].ravel()[now:] = 100000+np.arange(changed[k].size-now)
            release_index = now//36
            changed['forecast'].reshape(-1,24)[release_index+1:] += 100000
            for official, variable in [(False,False),(True,False),(False,True),(True,True)]:
                original = fc.forecast_as_of(DATA, SEL, now, targets, official, variable)
                mutant = fc.forecast_as_of(changed, SEL, now, targets, official, variable)
                for k in ['load','pv','price','net']: eq(original[k], mutant[k], 0)
                net, prices, meta = fc.scenarios(DATA, SEL, now, end, official, variable, count=3)
                nn, pp, mm = fc.scenarios(changed, SEL, now, end, official, variable, count=3)
                eq(net,nn,0); eq(prices,pp,0); assert meta == mm
                assert meta['latest_training_target_exclusive'] <= now
                mature = [h*144+offset+end-now for h in meta['history_days']]
                assert max(mature) <= now
                if official:
                    issue = now//36*36
                    assert meta['official_covered_slots'] == issue+144-now
                    d,k = divmod(issue//36,4)
                    for hour in range(1,25):
                        target = issue+hour*6-1
                        if target >= now: eq(original['pv'][target-now], DATA['forecast'][d,k,hour-1], 1e-10)
                evidence.append({'asof':now,'official':official,'variable':variable,
                                 'maturity_slack':now-max(mature),
                                 'official_covered_slots':meta['official_covered_slots']})
                if day == 60 and offset in [0,108] and official and variable:
                    # Same root empirical problem after mutation, independently solved twice.
                    base = None if offset == 0 else np.full(end-now,150.)
                    p1=ct.affine_plan(net,prices,now,6000.,base,True,True,.25)
                    p2=ct.affine_plan(nn,pp,now,6000.,base,True,True,.25)
                    root_checks.append({'asof':now,'q_error':eq(p1['q'],p2['q'],1e-5),
                                        'r_error':eq(p1['r'],p2['r'],1e-5)})
    REPORT['checks']['future_actual_and_release_mutation'] = {'passed':True,'cases':len(evidence),'cases_detail':evidence,'root_lp_checks':root_checks}

def node_checks():
    net=np.array([[100,150,800,1200,50,250], [100,150,50,200,1500,300],
                  [300,400,1000,50,1200,50], [300,400,200,1500,10,800]],float)
    prices=np.array([[.2,.2,.8,1.2,.8,.3]]*4)
    findings=[]
    for asof in [34,142,144]:
        base=None if asof==144 else np.array([125.,130.,0,0,0,0])
        plan=ct.affine_plan(net,prices,asof,6000.,base,True,True,.6)
        q,r,x=map(plan.get,['scenario_q','scenario_r','scenario_state'])
        if asof==144:
            eq(q,np.repeat(q[:1],4,axis=0));eq(r,q)
        else:
            eq(q[:,:2],np.repeat(base[None,:2],4,axis=0))
            if asof==34:
                eq(q,np.repeat(base[None,:],4,axis=0))
            for a,b in [(0,1),(2,3)]:
                eq(q[a,2:],q[b,2:]);eq(r[a,2:],r[b,2:]);eq(x[a,:2],x[b,:2])
        # Root 06:00 adjustment is shared despite distinct first-slot observations.
        findings.append({'asof':asof,'lp_violation':plan['lp_violation'],'objective_gap':plan['objective_gap']})
    p=ct.affine_plan(net,prices,36,6000.,np.full(6,100.),True,True,.6)
    eq(p['scenario_r'],np.repeat(p['scenario_r'][:1],4,axis=0))
    REPORT['checks']['pre_release_nonanticipation']={'passed':True,'cases':findings,
        'test':'Identical pre-release prefixes with different current/future observations have identical node contracts; current battery actions share identical observed prefixes.'}

def separate_lp(grid, values, E, net_minus_q, price):
    # Variables x,c,d,e,v; independent physical bus formulation.
    objective=[0.,0.,0.,5*price,1.]
    A=[[0.,1.,-1.,-1.,0.]]; b=[-net_minus_q]
    slopes=np.diff(values)/np.diff(grid)
    for i,slope in enumerate(slopes):
        A.append([slope,0,0,0,-1]);b.append(-(values[i]-slope*grid[i]))
    sol=linprog(objective,A_ub=A,b_ub=b,
                A_eq=[[1.,-ct.ETA,1/ct.ETA,0,0]],b_eq=[E],
                bounds=[(grid[0],grid[-1]),(0,ct.M),(0,ct.M),(0,None),(None,None)],method='highs')
    assert sol.success,sol.message
    return float(sol.fun),float(sol.x[0])

def dp_checks():
    rng=np.random.default_rng(742031); error=0.; tests=0
    for case in range(12):
        grid=np.linspace(1200,10800,13)
        slopes=np.sort(rng.uniform(-3,5,len(grid)-1))
        values=np.r_[0,np.cumsum(slopes*np.diff(grid))]
        a=float(rng.uniform(-2000,3000));price=float(rng.uniform(.01,2))
        got=ct.inf_convolution(grid,values,a,price)
        for j,E in enumerate(grid):
            exact,_=separate_lp(grid,values,E,a,price)
            error=max(error,eq(got[j],exact,1e-6));tests+=1
    net=np.array([[-100,200,1200],[200,900,-100],[700,400,600],[1400,1600,900]],float)
    prices=np.array([[.3,.8,.5],[.2,.7,.6],[.4,.9,.4],[.5,1.1,.7]])
    q=np.array([500.,600.,500.]);dp=ct.MarkovDP(net,prices,q,.35,grid_size=13)
    edges=np.quantile(net,[1/3,2/3],axis=0).T
    labels=np.sum(net[:,:,None]>edges[None,:,:],axis=2)
    val=np.tile(-.35*dp.grid,(3,1));rec_error=0.;action_error=0.
    for j in range(2,-1,-1):
        P=np.empty((3,3))
        for k in range(3):
            count=np.array([sum((labels[:,j]==k)&(labels[:,j+1]==kk)) if j<2 else 0 for kk in range(3)])
            P[k]=(count+1/3)/(count.sum()+1)
        nxt=P@val;rec_error=max(rec_error,eq(nxt,dp.future[j],1e-6));current=np.empty_like(val)
        for k in range(3):
            ids=np.flatnonzero(labels[:,j]==k)
            if len(ids)==0:ids=np.arange(len(net))
            p=float(prices[ids,j].mean())
            for z,E in enumerate(dp.grid):
                current[k,z]=np.mean([separate_lp(dp.grid,nxt[k],E,net[s,j]-q[j],p)[0] for s in ids])
            for s in ids[:1]:
                if labels[s,j]!=k:continue
                E=5831.;target=dp.action(j,E,net[s,j],q[j]);delta=target-E
                cost=5*p*max(0,net[s,j]-q[j]+max(ct.ETA*delta,delta/ct.ETA))+np.interp(target,dp.grid,nxt[k])
                exact,_=separate_lp(dp.grid,nxt[k],E,net[s,j]-q[j],p)
                action_error=max(action_error,eq(cost,exact,1e-6))
        val=current
    rec_error=max(rec_error,eq(val,dp.initial_values,1e-6))
    REPORT['checks']['convex_dp_independent_bus_lp']={'passed':True,'inf_convolution_cases':tests,
        'max_inf_convolution_error':error,'max_bellman_recursion_error':rec_error,
        'max_action_objective_error':action_error,
        'scope':'Exact subproblem comparison for the implemented convex PL grid model; not an exact original stochastic control result.'}

def cut_checks():
    rng=np.random.default_rng(6201);maxerr=0.;n=0
    for case in range(30):
        lines=np.c_[rng.uniform(-1e4,1e5,30),rng.uniform(-10,10,30)]
        original=np.r_[[[0,0]],lines];pruned=np.array(ct.prune_cuts(lines.tolist()))
        xs=[ct.EMIN,ct.EMAX]
        for i in range(len(original)):
            for j in range(i):
                if original[i,1] == original[j,1]:continue
                x=(original[j,0]-original[i,0])/(original[i,1]-original[j,1])
                if ct.EMIN<=x<=ct.EMAX:xs.append(x)
        xs=np.sort(xs);xs=np.r_[xs,(xs[1:]+xs[:-1])/2]
        e=eq(np.max(original[:,0,None]+original[:,1,None]*xs,axis=0),
             np.max(pruned[:,0,None]+pruned[:,1,None]*xs,axis=0),1e-6)
        maxerr=max(maxerr,e);n+=len(xs)
    REPORT['checks']['tail_cut_envelope_all_breakpoints']={'passed':True,'line_sets':30,'probes':n,'max_error':maxerr}

def trajectory_check(path):
    a=dict(np.load(path));metrics=json.loads(path.with_suffix('.json').read_text());days=a['days']
    q,r,c,d,em,sp,st=[a[k] for k in ['q','r','c','d','emergency','spill','state']]
    net=(DATA['load'][days]-DATA['pv'][days])/6
    assert st.min()>=ct.EMIN-1e-5 and st.max()<=ct.EMAX+1e-5
    assert max(c.max(),d.max())<=ct.M+1e-5
    for v in [q,r,c,d,em,sp]:assert v.min()>=-1e-5
    eq(np.minimum(c,d),0);eq(np.diff(st,axis=1),.9*c-d/.9)
    eq(r+d+em-c-sp,net);eq(st[1:,0],st[:-1,-1]);eq(st[0,0],6000)
    eq(a['releases'][:,0],q)
    is_adjust=metrics['kind'] in ['q3','q4_3'];effective=q.copy()
    for k in [1,2,3]:
        assert np.isnan(a['releases'][:,k,:k*36]).all()
        if is_adjust:
            assert np.isfinite(a['releases'][:,k,k*36:]).all()
            effective[:,k*36:]=a['releases'][:,k,k*36:]
        else:assert np.isnan(a['releases'][:,k]).all()
    eq(effective,r)
    expected_price=DATA['price'][days] if metrics['kind'].startswith('q4') else np.broadcast_to(DATA['day_price'],q.shape)
    eq(a['price'],expected_price,0)
    charges=expected_price*(np.maximum(1.5*r-.5*q,.5*r+.5*q)+5*em)
    err=eq(charges.sum(),metrics['totals']['total_cost'],1e-5)
    if metrics['configuration']['closed_daily']:eq(st[:,-1],6000)
    if metrics['configuration']['final'] is not None:eq(st[-1,-1],metrics['configuration']['final'])
    for row in metrics['decisions']:
        assert row['latest_training_target_exclusive']<=row['as_of']
        if row['tail_model_cutoff'] is not None:
            date=str(DATA['dates'][row['as_of']//144]);day=row['as_of']//144
            expected=14 if day<31 else day-int(date[8:10])+1
            assert row['tail_model_cutoff']==expected and expected*144<=row['as_of']
            model_days=row.get('tail_model_days') or 3
            model=json.loads(replay.tail_file(metrics['kind'],expected,model_days).read_text())
            # Numeric cutoff in training metadata, not merely the filename.
            assert model['configuration']['cutoff_day_exclusive']==expected
            assert model['configuration']['horizon_days']==model_days
            assert max(model['configuration']['history_days']) < expected
    return {'file':str(path.relative_to(ROOT)),'days':len(days),'cost_error':err,
            'midnight_final':st[:,-1].tolist(),'closed':metrics['configuration']['closed_daily'],
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def execution_checks():
    outcomes=[]
    # Development runs are evidence of mechanics, not annual performance.
    for folder in ['calibrate','calibrate_closed','calibrate_sddp']:
        for path in sorted((ROOT/'artifacts'/folder).glob('*.npz')):
            outcomes.append(trajectory_check(path))
    assert outcomes
    # Actual execute function with deliberately aggressive targets over two days.
    result=[]
    for closed,final in [(False,None),(False,6000.),(True,6000.)]:
        E=6000.;states=[E]
        for t in range(288):
            target=ct.EMAX if t<200 else ct.EMIN
            E,c,d,em,sp,_=ct.execute(E,target,200.,400.,287-t,closed,t%144,final)
            eq(E-states[-1],.9*c-d/.9);eq(200+d+em-c-sp,400)
            assert max(c,d)<=ct.M+1e-6 and min(c,d)==0
            states.append(E)
        if final is not None:eq(E,final)
        if closed:eq(states[144],6000)
        if not closed and final is None:eq(E,ct.EMIN)
        result.append({'daily_closed':closed,'global_final':final,'midnight':states[144],'end':E})
    REPORT['checks']['development_replay_and_contract_reconstruction']={'passed':True,'trajectories':outcomes}
    REPORT['checks']['physical_cross_day_free_fixed_terminal']={'passed':True,'synthetic_execution':result}

def real_month_boundary_checks():
    # The first horizon reaches March, but the decision is still on February 28.
    path=replay.tail_file('q2',31,1)
    tail_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    runs=[]
    for final in [None,6000.]:
        arrays,metrics=replay.simulate(DATA,SEL,[58,59,60],'q2','sddp_mpc',count=3,horizon_days=2,final=final)
        prefix='short-free' if final is None else 'short-fixed'
        output=ROOT/'review'/f'{prefix}.npz'
        np.savez_compressed(output,**arrays)
        output.with_suffix('.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        checked=trajectory_check(output)
        first=metrics['decisions'][0]
        assert first['end']//144 == 60 and first['tail_model_cutoff']==31 and first['tail_model_days']==1
        assert first['as_of']//144 == 58
        checked['first_decision']=first;checked['final_requested']=final
        runs.append(checked)
    assert tail_hash==hashlib.sha256(path.read_bytes()).hexdigest()
    REPORT['checks']['actual_three_day_free_fixed_and_month_version']={
        'passed':True,'runs':runs,'tail_model':str(path.relative_to(ROOT)),'tail_model_sha256':tail_hash,
        'scope':'February 28 to March 2, original data, 3-scenario mechanism check; not annual performance evidence.'}

def main():
    start=time.perf_counter()
    for fn in [forecast_checks,node_checks,dp_checks,cut_checks,execution_checks,real_month_boundary_checks]:
        print(fn.__name__,flush=True);fn()
    after={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE}
    assert after==SOURCE,'Production sources changed during audit'
    REPORT['source_hashes']=SOURCE
    REPORT['execution']={'command':'python3 review/check-controllers.py','exit_code':0,
                         'runtime_seconds':time.perf_counter()-start,'seed':742031}
    REPORT['passed']=True
    (ROOT/'review/controller-checks.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':True,'checks':len(REPORT['checks']),'seconds':REPORT['execution']['runtime_seconds']}))

if __name__=='__main__':main()
