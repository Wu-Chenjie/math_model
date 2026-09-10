"""Independent workbook battery/event/fee/period audit against complete trajectories."""
from pathlib import Path
import json,hashlib
import numpy as np
import openpyxl
ROOT=Path(__file__).resolve().parents[1]
def close(x,y,tol=1e-6):assert np.allclose(x,y,rtol=0,atol=tol)
def interval(t,end=None):
    f=lambda v:f'{v//6:02d}:{v%6*10:02d}'
    return f(t)+'-'+f(t+1 if end is None else end)
def date(v):return v.strftime('%Y-%m-%d')
checks=[]
for kind,name in [('q2','result2'),('q3','result3'),('q4_2','result4-2'),('q4_3','result4-3')]:
    path=ROOT/'计算结果'/f'{name}.xlsx';w=openpyxl.load_workbook(path,read_only=True,data_only=True)
    a=dict(np.load(ROOT/f'artifacts/{kind}.npz'));m=json.loads((ROOT/f'artifacts/{kind}.json').read_text())
    for sheet,key in [('计划购电量','q')]+([('调整购电量','r')] if kind.endswith('3') else []):
        rows=list(w[sheet].values);assert len(rows)==335
        assert list(rows[0][1:145])==[interval(t) for t in range(144)]
        assert [date(row[0]) for row in rows[1:]]==a['dates'].tolist()
        close(np.array([row[1:145] for row in rows[1:]],float),a[key],1e-7)
        close([row[145] for row in rows[1:]],a[key].sum(1))
        if key=='q':bill=(a['price']*a['q']).sum(1)
        else:bill=(a['price']*(a['q']+1.5*np.maximum(a['r']-a['q'],0)-.5*np.maximum(a['q']-a['r'],0))).sum(1)
        close([row[146] for row in rows[1:]],bill)
    rows=list(w['充放电量'].values);assert len(rows)==2005
    for i in range(334):
        for j,t in enumerate(range(0,144,24)):
            row=rows[1+6*i+j]
            assert (date(row[0])==a['dates'][i]) if j==0 else row[0] is None
            assert row[1]==interval(t,t+24)
            close(row[2:4],[a['c'][i,t:t+24].sum(),a['d'][i,t:t+24].sum()])
            if j in [0,1]:
                assert row[4]==('00:00' if j==0 else '24:00')
                close(row[5],a['state'][i,0 if j==0 else -1])
            else:assert row[4] is None and row[5] is None
    wanted=[]
    for i,day in enumerate(a['dates']):
        events=[];start=None
        for t in range(145):
            active=t<144 and a['emergency'][i,t]>1e-6
            if active and start is None:start=t
            if not active and start is not None:
                events.append([str(day),interval(start,t),a['emergency'][i,start:t].sum()]);start=None
        wanted+=events or [[str(day),'无',0.]]
    rows=list(w['紧急购电量'].values)[1:];assert len(rows)==len(wanted)
    for row,v in zip(rows,wanted):assert date(row[0])==v[0] and row[1]==v[1];close(row[2],v[2])
    rows=list(w['费用汇总'].values);assert len(rows)==336
    fields=['planned_cost','increase_cost','reduction_net_cost','emergency_cost','total_cost','planned_energy','adjusted_energy','emergency_energy','spill_energy']
    for row,day in zip(rows[1:335],m['daily']):
        assert date(row[0])==day['date'];close(row[1:10],[day[k] for k in fields])
    close(rows[335][1:10],[m['totals'][k] for k in fields])
    checks.append({'file':path.relative_to(ROOT).as_posix(),'status':'pass','days':334,
                   'battery_rows':2004,'emergency_event_rows':len(wanted),
                   'scope':'all published purchase cells, all six battery windows/day, all emergency events, all fees and cached totals',
                   'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});w.close()
path=ROOT/'计算结果/result1.xlsx';w=openpyxl.load_workbook(path,read_only=True,data_only=True)
q=json.loads((ROOT/'artifacts/q1.json').read_text());rows=list(w['计划购电量'].values)
assert [r[0] for r in rows[1:145]]==[interval(t) for t in range(144)]
close([r[1] for r in rows[1:145]],q['q']);close(rows[145][1],q['daily_energy']);close(rows[146][1],q['daily_cost'])
rows=list(w['充放电量'].values)
for j in range(6):close(rows[j+1][1:3],[sum(q['c'][24*j:24*j+24]),sum(q['d'][24*j:24*j+24])])
close([rows[1][4],rows[2][4]],[q['state'][0],q['state'][-1]])
checks.append({'file':'计算结果/result1.xlsx','status':'pass','scope':'inherited Q1 numerical output and all corrected periods','sha256':hashlib.sha256(path.read_bytes()).hexdigest()});w.close()
report={'status':'pass','checks':checks}
(ROOT/'review/workbook-export-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
