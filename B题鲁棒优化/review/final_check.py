import csv,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1];total=0;res=0
for name,count,methods in [('iid.csv',2400,{0,1,2,3,4,5}),('stratified.csv',6480,{0,5})]:
 rows=list(csv.DictReader((ROOT/'results'/name).open()));assert len(rows)==count;total+=len(rows);groups=defaultdict(dict)
 for r in rows:
  assert r['n']==r['cleared'];key=(r['problem'],r['seed']);m=int(r['method']);assert m not in groups[key];groups[key][m]=r
  calc=float(r['move_m'])/5+float(r['switches'])+5*float(r['measures'])+3*float(r['miss'])+5*float(r['cleared']);res=max(res,abs(calc-float(r['time_s'])));assert res<.001
  if name=='iid.csv':
   assert int(r['exact_plans'])<=int(r['plans'])and int(r['nonlocal_plans'])==0
   if int(r['n'])<16:assert int(r['skipped'])==0
 for group in groups.values():assert set(group)==methods and len({r['n']for r in group.values()})==1
 if name=='iid.csv':
  for p in ['3','4']:assert sorted(int(k[1])for k in groups if k[0]==p)==list(range(510001,510201))
 else:assert sorted(int(k[1])for k in groups)==list(range(710001,713241))
h=list(csv.DictReader((ROOT/'results/hardware.csv').open()));assert len(h)==320
aware=[r for r in h if r['aware']=='1'];assert len(aware)==160 and all(r['status']=='ok'and r['total']==r['cleared']for r in aware)
assert Counter(r['reason']for r in h if r['aware']=='0')=={'truth excluded from conservative polygon':156,'empty feasible region':4}
mock=json.loads((ROOT/'results/original_mock_validation.json').read_text(encoding='utf-8'));assert len(mock)==66
arc=json.loads((ROOT/'review/q4_area_arc_certificate.json').read_text(encoding='utf-8'));assert arc['N_integer_lower']==15 and len(arc['intervals'])==6
cover=json.loads((ROOT/'review/cover21_eta0.4_r999.6.json').read_text(encoding='utf-8'));assert cover['status']=='CERTIFIED'and len(cover['leaves'])==21996
text=(ROOT/'B题鲁棒优化_论文交接.md').read_text(encoding='utf-8');assert '{{'not in text and '最终论文说明正在'not in text
for value in ['97/100','110','246640.32','0.4','21996','11.80','13.78','1.96','4.51']:assert value in text,value
assert chr(92)+'rm 'not in text
for folder in ['B题成果','B题优化','B题深化']:
 root=ROOT.parent/folder;m=json.loads((root/'manifest.json').read_text(encoding='utf-8'));assert all(hashlib.sha256((root/f).read_bytes()).hexdigest()==v for f,v in m['sha256'].items()),folder
out={'status':'passed','nominal_rows':total,'hardware_rows':len(h),'all_nominal_complete':True,'aware_hardware_complete':160,'nominal_diagnostic_truth_excluded':156,'nominal_empty_feasible_set':4,'max_cost_residual_s':res,'previous_three_frozen_versions_unchanged':True,'official_formal_cases':0}
(ROOT/'review/final_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
