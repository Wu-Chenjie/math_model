"""Final independent warmup/Q1, development, handoff and workbook checks.

python3 review/check-final-supplement.py
bundled-python review/check-final-supplement.py --workbooks
Reuses the reviewer's explicit-spill LP and NumPy ledger modules, not production
settlement, forecasting, or controller functions.
"""
from pathlib import Path
import importlib.util, hashlib, json, sys, time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'review/final-supplement.json'
DATA=dict(np.load(ROOT/'artifacts/data.npz'))
def load(name):return json.loads((ROOT/name).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def near(a,b,tol=1e-6):
    e=float(np.max(abs(np.asarray(a)-np.asarray(b))))
    assert np.isfinite(e) and e<=tol,e
    return e
def clock(t):return f'{t//6:02d}:{10*(t%6):02d}'
def interval(a,b=None):return clock(a)+'-'+clock(a+1 if b is None else b)

def warmup():
    a=dict(np.load(ROOT/'artifacts/january-warmup.npz'));m=load('artifacts/warmup.json')
    assert a['state'].shape==(31,145)
    for k in ['q','r','c','d']:near(a[k],0,0)
    near(a['state'],6000,0);n=(DATA['load'][:31]-DATA['pv'][:31])/6
    near(a['emergency'],np.maximum(n,0),0);near(a['spill'],np.maximum(-n,0),0)
    near(a['r']+a['emergency']+a['d']-a['c']-a['spill'],n)
    near(np.diff(a['state'],axis=1),.9*a['c']-a['d']/.9)
    near(a['state'][1:,0],a['state'][:-1,-1],0)
    fees={'fixed_price_cost':float(np.sum(5*DATA['day_price']*a['emergency'])),
          'variable_price_cost':float(np.sum(5*DATA['price'][:31]*a['emergency']))}
    for k,v in fees.items():near(m[k],v)
    assert m['days']==31 and m['initial_energy']==6000 and m['february_initial_energy']==6000
    for k in ['q2','q3','q4_2','q4_3']:
        a2=np.load(ROOT/f'artifacts/{k}.npz');near(a['state'][-1,-1],a2['state'][0,0],0)
    return {'passed':True,'days':31,'fees_yuan':fees,'emergency_kwh':float(a['emergency'].sum()),
            'spill_kwh':float(a['spill'].sum()),'initial_and_february_inventory':6000.,
            'files':{f:sha(ROOT/f) for f in ['artifacts/january-warmup.npz','artifacts/warmup.json']}}

def q1():
    oracle=module('review_oracle','review/check-global-oracle.py')
    n=(DATA['day_load']-DATA['day_pv'])/6;p=DATA['day_price']
    exact,_=oracle.one_case(oracle.matrices(144),n,p,6000,'q1_final_independent')
    a=dict(np.load(ROOT/'artifacts/q1.npz'));m=load('artifacts/q1.json');c,d,E=a['c'],a['d'],a['state']
    near(p@a['q'],exact['objective_cost_yuan']);near(m['expected_cost'],exact['objective_cost_yuan']);near(m['lp_objective'],exact['objective_cost_yuan'])
    near(np.diff(E),.9*c-d/.9);near(np.minimum(c,d),0);near(E[[0,-1]],6000)
    assert E.min()>=1200-1e-6 and E.max()<=10800+1e-6 and max(c.max(),d.max())<=5000/6+1e-6
    assert max(0,float(np.max(n+c-d-a['q'])))<1e-6
    return {'passed':True,'economic_cost_yuan':exact['objective_cost_yuan'],'energy_kwh':float(a['q'].sum()),
            'duality_gap':exact['checks']['primal_minus_repaired_dual'],
            'normalization_simultaneous_max':float(np.minimum(c,d).max()),
            'files':{f:sha(ROOT/f) for f in ['artifacts/q1.json','artifacts/q1.npz']}}

def development_and_short():
    aud=module('review_production','review/check-production.py');sel=load('artifacts/selection.json');checked=[]
    for kind in ['q2','q3','q4_2','q4_3']:
        costs={}
        for cand in ['cross_baseline','affine_mpc','markov_mpc','sddp_mpc','sddp_markov']:
            folder='calibrate_sddp_v2' if cand.startswith('sddp') else 'calibrate'
            f=f'artifacts/{folder}/{kind}_{cand}';a,m,h=aud.read_pair(f)
            near(a['days'],np.arange(24,31),0)
            aud.physical(a,kind,6000);aud.releases(a,kind);l=aud.daily_ledger(a)
            e=aud.compare_reported_ledger(l,m['daily'],m['totals'],a['dates'],a['state'])
            costs[cand]=float(l['total_cost'].sum());near(costs[cand],sel['development_costs'][kind][cand])
            for node in m['decisions']:
                assert node['latest_training_target_exclusive']<=node['as_of']
                if node['tail_cut_count']:
                    assert node['tail_model_cutoff']==14 and node['tail_model_days']==min(3,(31*144-node['end'])//144)
                if node['end']==31*144:assert node['tail_cut_count']==0 and node['tail_price']==0
            checked.append({'case':f,'ledger_error':e,'files':h})
        chosen=min(costs,key=costs.get)
        if costs['markov_mpc']<=min(costs.values())*(1+sel['relative_tie_tolerance']):chosen='markov_mpc'
        assert sel['selected'][kind]==chosen
    for p in sorted((ROOT/'artifacts/experiments').glob('*.json')):
        if p.stem.startswith('annual_'):continue
        f=str(p.relative_to(ROOT))[:-5];a,m,h=aud.read_pair(f);cfg=m['configuration'];design=m['validation_design']
        changed={k:v.copy() for k,v in DATA.items()}
        if design.get('stress'):
            changed['load'][72:79]*=1.1;changed['pv'][72:79]*=.8
        aud.DATA=changed
        aud.physical(a,m['kind'],6000,terminal=cfg['final']);aud.releases(a,m['kind']);l=aud.daily_ledger(a)
        e=aud.compare_reported_ledger(l,m['daily'],m['totals'],a['dates'],a['state'])
        near(a['days'],np.arange(72,79),0)
        for node in m['decisions']:assert node['latest_training_target_exclusive']<=node['as_of']
        checked.append({'case':f,'ledger_error':e,'files':h})
    return {'passed':True,'development_cases':20,'short_experiments':15,'checked':checked,
            'scope':'Independent numerical ledger/physics for January counterfactual development and March sensitivity; January choice reconstructed with declared tie rule. No out-of-sample claim for development scores.'}

def tables():
    tab=load('artifacts/handoff-tables.json');selected=load('artifacts/selection.json')['selected'];errs=[]
    for kind in ['q2','q3','q4_2','q4_3']:
        a=dict(np.load(ROOT/f'artifacts/{kind}.npz'));source=np.load(ROOT/f'artifacts/annual/{kind}_{selected[kind]}.npz')
        for k in a:
            if np.issubdtype(a[k].dtype,np.number):assert np.array_equal(a[k],source[k],equal_nan=True)
            else:assert np.array_equal(a[k],source[k])
        dates=tab['models'][kind]['selected'];assert set(dates)=={'2025-03-20','2025-06-21','2025-09-23','2025-12-21'}
        for date,v in dates.items():
            i=a['dates'].tolist().index(date)
            for row,t in zip(v['purchase'],[60,72,84,96,108,120]):
                assert row[0]==interval(t);errs.append(near(row[1:],[a['q'][i,t],a['r'][i,t]]))
            for j,row in enumerate(v['battery']):
                assert row[0]==date and row[1]==interval(j*24,(j+1)*24)
                errs.append(near(row[2:4],[a['c'][i,j*24:(j+1)*24].sum(),a['d'][i,j*24:(j+1)*24].sum()]))
                expectedtime='00:00' if j==0 else '24:00' if j==1 else None
                assert row[4]==expectedtime
                if j<2:errs.append(near(row[5],a['state'][i,0 if j==0 else -1]))
                else:assert row[5] is None
            mask=a['emergency'][i]>1e-6;starts=np.flatnonzero(mask&~np.r_[False,mask[:-1]]);ends=np.flatnonzero(mask&~np.r_[mask[1:],False])+1
            ev=[[date,interval(int(s),int(e)),float(a['emergency'][i,s:e].sum())] for s,e in zip(starts,ends)] or [[date,'无',0.]]
            assert len(ev)==len(v['emergency'])
            for r,s in zip(ev,v['emergency']):assert r[:2]==s[:2];errs.append(near(r[2],s[2]))
    return {'passed':True,'selected_dates':16,'max_numeric_error':max(errs),'source':sha(ROOT/'artifacts/handoff-tables.json'),
            'meaning':'Four-hour blocks may contain both charging and discharging at different ten-minute intervals; this does not violate instantaneous mutual exclusion.'}

def workbooks():
    import openpyxl
    cases=[]
    for name,kind in [('result1',None),('result2','q2'),('result3','q3'),('result4-2','q4_2'),('result4-3','q4_3')]:
        p=ROOT/'计算结果'/f'{name}.xlsx';w=openpyxl.load_workbook(p,read_only=True,data_only=True)
        a=dict(np.load(ROOT/f'artifacts/{kind or "q1"}.npz'));r=list(w['计划购电量'].values)
        if kind:
            assert list(r[0][1:145])==[interval(t) for t in range(144)]
            near(np.array([z[1:145] for z in r[1:335]],float),a['q'])
            b=list(w['充放电量'].values)[1:]
            for j,row in enumerate(b):
                i=j//6;t=j%6
                assert row[1]==interval(t*24,(t+1)*24)
                near(row[2:4],[a['c'][i,t*24:(t+1)*24].sum(),a['d'][i,t*24:(t+1)*24].sum()])
                if t==0:assert row[0].strftime('%Y-%m-%d')==a['dates'][i]
                else:assert row[0] is None
                if t<2:assert row[4]==('00:00' if t==0 else '24:00');near(row[5],a['state'][i,0 if t==0 else -1])
                else:assert row[4] is None and row[5] is None
        else:
            assert [row[0] for row in r[1:145]]==[interval(t) for t in range(144)]
            near([row[1] for row in r[1:145]],a['q'])
            b=list(w['充放电量'].values)
            near(b[1][4],6000);near(b[2][4],6000)
        # The phrase SOC/kWh is a workbook convention for E, not a ratio.
        cases.append({'file':str(p.relative_to(ROOT)),'sha256':sha(p),'sheet_count':len(w.sheetnames),'status':'pass'})
        w.close()
    return {'passed':True,'files':cases,'scope':'Independent workbook headers, full q and four-hour battery sums/inventory directly versus raw NPZ. Other workbook cells are covered by producer readback plus independently reconciled handoff/production ledgers; no claim to have rerendered all cells.'}

def main():
    start=time.perf_counter();only='--workbooks' in sys.argv
    report=load('review/final-supplement.json') if only else {'scope':'final_independent_supplement','reviewer_id':'/root/independent_review','independent':True,'checks':{}}
    todo=[('workbooks',workbooks)] if only else [('warmup',warmup),('q1',q1),('development_and_short',development_and_short),('specified_day_tables',tables)]
    for key,fn in todo:print(key,flush=True);report['checks'][key]=fn()
    report['passed']=all(v['passed'] for v in report['checks'].values())
    report.setdefault('executions',[]).append({'command':('bundled-python' if only else 'python3')+' review/check-final-supplement.py'+(' --workbooks' if only else ''),'exit_code':0,'runtime_seconds':time.perf_counter()-start})
    report['review_script_sha256']=sha(__file__)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':report['passed'],'seconds':time.perf_counter()-start}))
if __name__=='__main__':main()
