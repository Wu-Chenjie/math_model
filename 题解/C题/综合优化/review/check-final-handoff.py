"""Independent selector, derived result, handoff-table, and input snapshot audit."""
from pathlib import Path
import json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent
KINDS=['q2','q3','q4_2','q4_3']
NAMES=['baseline','common_mpc','affine_feedback','affine_mpc','affine_saa_mpc','affine_sdp']
EXTRA=['common_saa_mpc','common_sdp']
cache={}
def read(p):
    p=str(p)
    if p not in cache:cache[p]=json.loads((ROOT/p).read_text())
    return cache[p]
def close(a,b,tol=1e-5):
    assert np.allclose(a,b,rtol=0,atol=tol,equal_nan=True),(np.asarray(a).shape,np.asarray(b).shape)
def interval(t,end=None):
    fmt=lambda x:f'{x//6:02d}:{x%6*10:02d}'
    return fmt(t)+'-'+fmt(t+1 if end is None else end)
def table_check(t,a,main=False):
    for date,info in t.items():
        i=a['dates'].tolist().index(date)
        for row,slot in zip(info['purchase'],[60,72,84,96,108,120]):
            assert row[0]==interval(slot);close(row[1:],[a['q'][i,slot],a['r'][i,slot]])
        for row,slot in zip(info['battery'],range(0,144,24)):
            index=1 if main else 0
            assert row[index]==interval(slot,slot+24)
            close(row[index+1:index+3],[a['c'][i,slot:slot+24].sum(),a['d'][i,slot:slot+24].sum()])
        em=[];start=None
        for slot in range(145):
            active=slot<144 and a['emergency'][i,slot]>1e-6
            if active and start is None:start=slot
            if not active and start is not None:
                em.append([interval(start,slot),float(a['emergency'][i,start:slot].sum())]);start=None
        actual=[r[1:] for r in info['emergency']] if main else info['emergency']
        if main and actual==[['无',0.0]]:actual=[]
        assert len(actual)==len(em)
        for row,want in zip(actual,em):assert row[0]==want[0];close(row[1],want[1])
        q,r,p,e=[a[k][i] for k in ['q','r','price','emergency']]
        contract=np.sum(p*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0)))
        d=info['daily'];close(d['total_cost'],contract+5*p@e)
        if not main:
            close(d['planned_purchase_energy'],q.sum());close(d['final_contract_energy'],r.sum())
            close(d['actual_purchase_energy'],r.sum()+e.sum())

def main():
    selection=read('artifacts/selection.json');comp=read('artifacts/comparisons.json')
    tables=read('artifacts/handoff-tables.json');aggregates=read('artifacts/aggregate-handoff-tables.json')
    payload=read('artifacts/workbook-payload.json');assert payload['labels']==[interval(t) for t in range(144)]
    selected={};choices={};table_count=0
    for kind in KINDS:
        cal={c:read(f'artifacts/calibrate/{kind}_{c}.json') for c in NAMES}
        ann={c:read(f'artifacts/annual/{kind}_{c}.json') for c in NAMES}
        score=[sum(d['total_cost'] for d in cal[c]['daily']) for c in NAMES]
        jan=NAMES[int(np.argmin(score))];selected[kind]=jan
        assert selection[kind]['january_selected']==jan
        for j,c in enumerate(NAMES):close(selection[kind]['january_costs'][c],score[j])
        arrays={c:dict(np.load(ROOT/f'artifacts/annual/{kind}_{c}.npz')) for c in NAMES}
        saved=dict(np.load(ROOT/f'artifacts/{kind}.npz'))
        for key in arrays[jan]:
            if arrays[jan][key].dtype.kind in 'SU':assert np.array_equal(saved[key],arrays[jan][key])
            else:close(saved[key],arrays[jan][key],0)
        past_daily=np.array([[x['total_cost'] for x in cal[c]['daily']+ann[c]['daily']] for c in NAMES]).T
        dates=np.array([x['date'] for x in cal[jan]['daily']+ann[jan]['daily']],dtype='datetime64[D]')
        chosen=[];adaptive=dict(np.load(ROOT/f'artifacts/{kind}_adaptive.npz'))
        for j in range(334):
            day=dates[j+10];past=np.flatnonzero((dates<day)&(dates>=day-np.timedelta64(28,'D')))
            sums=past_daily[past].sum(0);chosen.append(NAMES[int(np.argmin(sums))])
            close(sums,selection[kind]['adaptive_history_scores'][j])
            for key,value in arrays[chosen[j]].items():
                if value.dtype.kind in 'SU':assert np.array_equal(adaptive[key][j],value[j])
                else:close(adaptive[key][j],value[j],0)
        assert chosen==selection[kind]['adaptive_choices'];choices[kind]={c:chosen.count(c) for c in NAMES}
        assert choices[kind]==selection[kind]['adaptive_counts']
        all_daily={c:ann[c]['daily'] for c in NAMES}
        all_daily.update({c:read(f'artifacts/diagnostic/{kind}_{c}.json')['daily'] for c in EXTRA})
        all_daily['january_selected']=ann[jan]['daily']
        all_daily['adaptive28']=[ann[chosen[j]]['daily'][j] for j in range(334)]
        all_daily['convex28']=read(f'artifacts/{kind}_convex.json')['daily']
        base=sum(x['total_cost'] for x in ann['baseline']['daily'])
        for c,daily in all_daily.items():
            values=np.array([x['total_cost'] for x in daily]);total=values.sum()
            stated=comp[kind]['comparisons'][c]
            close(total,stated['total_cost']);close(base-total,stated['saving_vs_baseline_yuan'])
            close(100*(base-total)/base,stated['saving_vs_baseline_percent'])
            close(np.quantile(values,.95),stated['daily_cost_p95'])
            monthly=[sum(x['total_cost'] for x in daily if int(x['date'][5:7])==m) for m in range(2,13)]
            close(monthly,comp[kind]['monthly_cost_yuan'][c])
        assert selection[kind]['retrospective_best_candidate']==min(NAMES,key=lambda c:sum(x['total_cost'] for x in all_daily[c]))
        assert selection[kind]['retrospective_best_including_diagnostics']==min(NAMES+EXTRA,key=lambda c:sum(x['total_cost'] for x in all_daily[c]))
        table_check(tables['models'][kind]['selected'],saved,True);table_count+=4
        for policy in ['adaptive','convex']:
            a=dict(np.load(ROOT/f'artifacts/{kind}_{policy}.npz'))
            table_check(aggregates[policy][kind]['selected'],a);table_count+=4
        grid=read('artifacts/grid-sensitivity.json')[kind]
        dense=read(f'artifacts/grid641/{kind}_affine_sdp.json')
        assert grid['dates']==[x['date'] for x in dense['daily']]
        sparse=sum(x['total_cost'] for x in ann['affine_sdp']['daily'] if x['date'] in grid['dates'])
        fine=sum(x['total_cost'] for x in dense['daily'])
        close(sparse,grid['grid321_cost']);close(fine,grid['grid641_cost'])
        close(100*(fine-sparse)/sparse,grid['difference_percent'])
    registry=read('artifacts/result-registry.json')['results'];ids=set()
    for row in registry:
        assert row['id'] not in ids;ids.add(row['id'])
        v=read(row['source_artifact'])
        for part in row['source_path'].strip('/').split('/'):
            part=part.replace('~1','/').replace('~0','~');v=v[int(part)] if isinstance(v,list) else v[part]
        assert v==row['value'] and row['status']=='verified'
    manifest=read('modeling-manifest.json');inputs=manifest['source']['input_hashes']
    for path,sha in inputs.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
    for file in ['data.npz','forecasts.npz']:
        assert (ROOT/'inputs/prepared'/file).read_bytes()==(BASE/'artifacts'/file).read_bytes()
    for file in ['dispatch.py','forecasting.py','prepare_data.py']:
        assert (ROOT/'inputs/baseline-code'/file).read_bytes()==(BASE/'src'/file).read_bytes()
    report={'status':'pass_for_current_handoff','january_selected':selected,'adaptive_day_counts':choices,
            'independent_history_windows_checked':4*334,'specified_date_tables_checked':table_count,
            'registry_values_resolved':len(registry),'input_hashes_verified':len(inputs),
            'checks':['January-only main selection','whole-day past-only adaptive choice','all adaptive fields including publication snapshots',
                      '32 candidates plus aggregators cost/monthly/percentile metrics','same-date grid comparison','all 144 corrected period labels',
                      'specified-date purchase/battery/emergency/energy tables','registry pointers and inherited input snapshots'],
            'scope':'Current modeling/calculation handoff; final manifest and reproducibility output hashes are finalized by the author after independent findings.'}
    (ROOT/'review/final-handoff-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
