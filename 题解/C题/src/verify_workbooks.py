"""Reopen exported XLSX and reconcile values and cached formulas against executed arrays."""
from pathlib import Path
import openpyxl,numpy as np,json
ROOT=Path(__file__).resolve().parents[1]
checks=[]
for name,key in [('result1',None),('result2','q2'),('result3','q3'),('result4-2','q4_2'),('result4-3','q4_3')]:
    p=ROOT/'计算结果'/(name+'.xlsx');w=openpyxl.load_workbook(p,data_only=True,read_only=True)
    rows=list(w['计划购电量'].values)
    if key:
        a=np.load(ROOT/f'artifacts/{key}.npz');v=np.array([r[1:145] for r in rows[1:335]],float)
        assert np.max(abs(v-a['q']))<1e-7
        assert rows[0][1]=='00:00-00:10' and rows[0][144]=='23:50-24:00'
        assert len(rows)==335 and len(list(w['充放电量'].values))==2005
        ss=list(w['费用汇总'].values);total=sum(r[5] for r in ss[1:335]);tot=json.loads((ROOT/f'artifacts/{key}.json').read_text())['totals']['total_cost']
        assert abs(total-tot)<1e-6 and abs(ss[335][5]-tot)<1e-6
        assert all(abs(rows[i+1][145]-a['q'][i].sum())<1e-6 for i in range(334))
        if key.endswith('3'):
            r=np.array([r[1:145] for r in list(w['调整购电量'].values)[1:335]],float)
            assert np.max(abs(r-a['r']))<1e-7
    else:
        q=json.loads((ROOT/'artifacts/q1.json').read_text());assert abs(rows[145][1]-q['daily_energy'])<1e-6
    for sheet in w:
        for row in sheet.values:
            assert not any(isinstance(v,str) and v.startswith(('#REF!','#DIV/0!','#VALUE!','#NAME?')) for v in row)
    checks.append({'file':str(p.relative_to(ROOT)),'status':'pass','sheet_count':len(w.sheetnames)})
    w.close()
(ROOT/'artifacts/workbook-validation.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2))
print(checks)
