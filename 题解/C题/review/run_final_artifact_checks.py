"""Read-only independent workbook, table, registry, CSV and hash reconciliation."""
from pathlib import Path
import json, hashlib, csv
import numpy as np
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/name).read_text())
def time(t):return f'{t//6:02d}:{t%6*10:02d}'
def span(t,end=None):return time(t)+'-'+time(t+1 if end is None else end)
def expected_events(values,date):
    active=np.flatnonzero(values>1e-6)
    out=[]
    if len(active):
        cuts=np.flatnonzero(np.diff(active)>1)+1
        for g in np.split(active,cuts):out.append((date,span(int(g[0]),int(g[-1]+1)),float(values[g].sum())))
    return out or [(date,'无',0.)]
def main():
    out={'reviewer_id':'/root/independent_review','checks':{}}
    rep=read('artifacts/reproducibility.json')
    for kind in ['input_hashes','output_hashes']:
        mismatches=[s for s,h in rep[kind].items() if not (ROOT/s).is_file() or hashlib.sha256((ROOT/s).read_bytes()).hexdigest()!=h]
        # Lead will refresh the final mutable handoff/source hashes after review-requested edits.
        out['checks'][kind]={'count':len(rep[kind]),'mismatches':mismatches}
    originals=ROOT.parents[1]/'C题'
    original_mismatch=[]
    for s,h in rep['input_hashes'].items():
        p=originals/Path(s).relative_to('inputs')
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:original_mismatch.append(str(p))
    assert not original_mismatch
    out['checks']['original_inputs_unchanged']={'files':len(rep['input_hashes']),'mismatches':original_mismatch}
    registry=read('artifacts/result-registry.json')['results']
    for row in registry:
        actual=read(row['source_artifact'])
        for p in row['source_path'].split('/')[1:]:
            p=p.replace('~1','/').replace('~0','~')
            actual=actual[int(p)] if isinstance(actual,list) else actual[p]
        assert actual==row['value'],row['id']
    lookup={r['id']:r for r in registry}
    claims=read('artifacts/handoff-claims.json')['claims']
    assert all(c['value']==lookup[c['result_id']]['value'] for c in claims)
    out['checks']['registry_and_claims']={'registered_results':len(registry),'claims':len(claims),'status':'pass'}
    labels=[span(t) for t in range(144)]
    tables=read('artifacts/handoff-tables.json')
    q1=read('artifacts/q1.json')
    workbooks=[];csvs=[]
    for name,key in [('result1',None),('result2','q2'),('result3','q3'),('result4-2','q4_2'),('result4-3','q4_3')]:
        w=load_workbook(ROOT/f'计算结果/{name}.xlsx',data_only=True,read_only=True)
        purchase=list(w['计划购电量'].values)
        if key is None:
            assert [row[0] for row in purchase[1:145]]==labels
            assert np.max(abs(np.array([row[1] for row in purchase[1:145]])-q1['q']))<1e-7
            assert abs(purchase[145][1]-sum(q1['q']))<1e-6
            assert abs(purchase[146][1]-q1['daily_cost'])<1e-7
            bat=list(w['充放电量'].values)
            for i in range(6):
                assert abs(bat[i+1][1]-sum(q1['c'][i*24:(i+1)*24]))<1e-7
                assert abs(bat[i+1][2]-sum(q1['d'][i*24:(i+1)*24]))<1e-7
            assert abs(bat[1][4]-6000)<1e-7 and abs(bat[2][4]-6000)<1e-7
            workbooks.append({'name':name,'purchase_values':144,'battery_values':12,'status':'pass'})
        else:
            a=dict(np.load(ROOT/f'artifacts/{key}.npz'));m=read(f'artifacts/{key}.json');dates=a['dates'].tolist()
            assert len(purchase)==335
            assert list(purchase[0][1:145])==labels
            assert [r[0].date().isoformat() for r in purchase[1:]]==dates
            assert np.max(abs(np.array([r[1:145] for r in purchase[1:]])-a['q']))<1e-7
            assert np.max(abs(np.array([r[145] for r in purchase[1:]])-a['q'].sum(1)))<1e-6
            assert np.max(abs(np.array([r[146] for r in purchase[1:]])-(a['q']*a['price']).sum(1)))<1e-6
            if key.endswith('3'):
                adjustment=list(w['调整购电量'].values)
                assert list(adjustment[0][1:145])==labels
                assert np.max(abs(np.array([r[1:145] for r in adjustment[1:]])-a['r']))<1e-7
                fees=(a['price']*(a['q']+1.5*np.maximum(a['r']-a['q'],0)-.5*np.maximum(a['q']-a['r'],0))).sum(1)
                assert np.max(abs(np.array([r[146] for r in adjustment[1:]])-fees))<1e-6
            bat=list(w['充放电量'].values)
            assert len(bat)==2005
            for i,date in enumerate(dates):
                for b in range(6):
                    row=bat[1+i*6+b]
                    assert (row[0].date().isoformat()==date if b==0 else row[0] is None)
                    assert row[1]==span(b*24,(b+1)*24)
                    assert abs(row[2]-sum(a['c'][i,b*24:(b+1)*24]))<1e-7
                    assert abs(row[3]-sum(a['d'][i,b*24:(b+1)*24]))<1e-7
                    if b<2:assert row[4]==['00:00','24:00'][b] and abs(row[5]-6000)<1e-7
            em=list(w['紧急购电量'].values)[1:]
            expected=[r for i,date in enumerate(dates) for r in expected_events(a['emergency'][i],date)]
            assert len(em)==len(expected)
            for row,want in zip(em,expected):
                assert row[0].date().isoformat()==want[0] and row[1]==want[1]
                assert abs(row[2]-want[2])<1e-7
            summary=list(w['费用汇总'].values)
            assert len(summary)==336
            for i,row in enumerate(summary[1:335]):
                assert row[0].date().isoformat()==dates[i]
                assert abs(row[5]-m['daily'][i]['total_cost'])<1e-7
            assert abs(summary[-1][5]-m['totals']['total_cost'])<1e-6
            selected=tables['models'][key]['selected']
            assert set(selected)=={'2025-03-20','2025-06-21','2025-09-23','2025-12-21'}
            for date,rows in selected.items():
                i=dates.index(date)
                for t,row in zip([60,72,84,96,108,120],rows['purchase']):
                    assert row==[labels[t],float(a['q'][i,t]),float(a['r'][i,t])]
                assert rows['daily']==m['daily'][i]
            with (ROOT/f'计算结果/{key}_逐时完整策略.csv').open(encoding='utf-8-sig',newline='') as f:
                reader=csv.reader(f);next(reader)
                count=0;maximum=0.
                for i,row in enumerate(reader):
                    day,t=divmod(i,144)
                    assert row[:2]==[dates[day],labels[t]]
                    expected_values=[a[z][day,t] for z in ['q','r','c','d','emergency','spill','price']]+[a['state'][day,t],a['state'][day,t+1]]
                    maximum=max(maximum,float(np.max(abs(np.array(row[2:],float)-expected_values))))
                    count+=1
                assert count==334*144 and maximum<1e-7
                csvs.append({'name':key,'rows':count,'numeric_max_abs':maximum,'status':'pass'})
            workbooks.append({'name':name,'days':334,'purchase_values':334*144,'battery_values':334*12,'emergency_rows':len(em),'status':'pass'})
        for s in w:
            for row in s:
                assert all(c.data_type!='e' for c in row)
        w.close()
    out['checks']['workbooks']=workbooks
    out['checks']['csvs']=csvs
    out['status']='pass_except_pending_hash_refresh' if any(out['checks'][k]['mismatches'] for k in ['input_hashes','output_hashes']) else 'pass'
    (ROOT/'review/final-artifact-checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
