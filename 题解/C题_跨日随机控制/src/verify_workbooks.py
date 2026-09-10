"""Read exported workbooks and reconcile them with executed numerical artifacts."""
from pathlib import Path
import json,hashlib,time
import openpyxl
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
begin=time.perf_counter();checks=[]
payload=json.loads((ROOT/'artifacts/workbook-payload.json').read_text())
for name,key in [('result1',None),('result2','q2'),('result3','q3'),('result4-2','q4_2'),('result4-3','q4_3')]:
    path=ROOT/'计算结果'/(name+'.xlsx');w=openpyxl.load_workbook(path,data_only=True,read_only=True)
    rows=list(w['计划购电量'].values)
    if key:
        a=np.load(ROOT/f'artifacts/{key}.npz');m=payload['models'][key]
        assert np.max(abs(np.array([r[1:145] for r in rows[1:335]],float)-a['q']))<1e-7
        assert rows[0][1:145]==tuple(payload['labels'])
        assert len(rows)==335
        assert [r[0].strftime('%Y-%m-%d') for r in rows[1:335]]==m['dates']
        assert all(abs(rows[i+1][145]-a['q'][i].sum())<1e-6 for i in range(334))
        assert all(abs(rows[i+1][146]-m['daily'][i]['planned_cost'])<1e-6 for i in range(334))
        if key.endswith('3'):
            adjusted=list(w['调整购电量'].values)
            assert np.max(abs(np.array([r[1:145] for r in adjusted[1:335]],float)-a['r']))<1e-7
            for i,row in enumerate(adjusted[1:335]):
                assert abs(row[145]-a['r'][i].sum())<1e-6
                d=m['daily'][i];assert abs(row[146]-d['planned_cost']-d['increase_cost']-d['reduction_net_cost'])<1e-6
        battery=list(w['充放电量'].values)
        assert len(battery)==2005
        for j,(row,expected) in enumerate(zip(battery[1:],m['battery'])):
            if j%6==0:assert row[0].strftime('%Y-%m-%d')==expected[0]
            else:assert row[0] is None
            assert row[1]==expected[1] and np.max(abs(np.array(row[2:4])-expected[2:4]))<1e-7
            assert row[4]==expected[4]
            if expected[5] is not None:assert abs(row[5]-expected[5])<1e-7
        emergency=list(w['紧急购电量'].values)[1:]
        assert len(emergency)==len(m['emergency'])
        for row,expected in zip(emergency,m['emergency']):
            assert row[0].strftime('%Y-%m-%d')==expected[0] and row[1]==expected[1] and abs(row[2]-expected[2])<1e-7
        fees=list(w['费用汇总'].values);total=sum(r[5] for r in fees[1:335])
        fields=['planned_cost','increase_cost','reduction_net_cost','emergency_cost','total_cost','planned_energy','adjusted_energy','emergency_energy','spill_energy']
        assert np.max(abs(np.array([r[1:10] for r in fees[1:335]],float)-np.array([[d[f] for f in fields] for d in m['daily']])))<1e-6
        expected=json.loads((ROOT/f'artifacts/{key}.json').read_text())['totals']['total_cost']
        assert abs(total-expected)<1e-6 and abs(fees[335][5]-expected)<1e-6
    else:
        q=payload['q1'];assert abs(rows[145][1]-q['daily_energy'])<1e-6
        assert abs(rows[146][1]-q['daily_cost'])<1e-6
        assert np.max(abs(np.array([r[1] for r in rows[1:145]])-q['q']))<1e-7
        battery=list(w['充放电量'].values)
        expected=[[sum(q['c'][24*b:24*b+24]),sum(q['d'][24*b:24*b+24])] for b in range(6)]
        assert np.max(abs(np.array([r[1:3] for r in battery[1:7]],float)-expected))<1e-7
        assert abs(battery[1][4]-q['state'][0])<1e-7 and abs(battery[2][4]-q['state'][-1])<1e-7
    for sheet in w:
        for row in sheet.values:
            assert not any(isinstance(v,str) and v.startswith(('#REF!','#DIV/0!','#VALUE!','#NAME?','#N/A','#NUM!','#NULL!','#SPILL!','#CALC!')) for v in row)
    checks.append({'file':str(path.relative_to(ROOT)),'status':'pass','sheet_count':len(w.sheetnames),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});w.close()
(ROOT/'artifacts/workbook-validation.json').write_text(json.dumps({'checks':checks,'execution':{'command':'bundled-python src/verify_workbooks.py','exit_code':0,'runtime_seconds':time.perf_counter()-begin}},ensure_ascii=False,indent=2)+'\n')
print(checks)
