"""Independent final numerical/artifact gates using only local recorded evidence."""
import csv,json,math
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
summary=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
rows_checked=0;max_residual=0.
for p in list((ROOT/'results').glob('test*.csv'))+list((ROOT/'results').glob('stress*.csv')):
 rows=list(csv.DictReader(p.open()));rows_checked+=len(rows)
 for r in rows:
  assert int(r['cleared'])==int(r['total'])
  cost=float(r['move_m'])/5+float(r['switches'])+5*float(r['measures'])+3*float(r['miss'])+5*float(r['cleared'])
  residual=abs(cost-float(r['time_s']));max_residual=max(max_residual,residual);assert residual<.001
  assert r['certificate']in ['upper_bound_16','seven_point_per_channel','convex_mesh_per_channel']
assert rows_checked==3400
for p in ['3','4']:
 rows=[r for r in csv.DictReader((ROOT/'results/test_final.csv').open())if r['problem']==p]
 actual=sum(float(r['time_s'])for r in rows)/200
 assert abs(actual-summary['configs']['最终方案'][p]['time_s']['mean'])<1e-8
cert=json.loads((ROOT/'review/q2_rational_certificate.json').read_text(encoding='utf-8'))
upper=Fraction(cert['continuous_and_quantized_upper']['upper_m'])
lower=Fraction(cert['continuous_model_lower']['certified_floor_m'])
quant=Fraction(cert['physical_quantized_lower']['certified_floor_m'])
assert upper-lower==Fraction('0.00071')and upper-quant==Fraction('0.08831')
leaves=cert['continuous_and_quantized_upper']['leaves']
assert Fraction(leaves[0]['lo'])==-182 and Fraction(leaves[-1]['hi'])==2
assert all(Fraction(a['hi'])==Fraction(b['lo'])for a,b in zip(leaves,leaves[1:]))
layout=json.loads((ROOT/'review/layout_exact_certificate.json').read_text(encoding='utf-8'))
assert layout['points']==25 and layout['triangles']==33
doc=(ROOT/'B题优化_论文交接.md').read_bytes().replace(bytes([13,10]),bytes([10]))
assert not any(x<32 and x not in (10,)for x in doc),'control character in manuscript'
text=doc.decode('utf-8');assert '{{'not in text
for num in ['0.00071','0.08831','285.28','646.76','17.08','23.63','87.396']:assert num in text
mock=json.loads((ROOT/'results/original_mock_validation.json').read_text(encoding='utf-8'))
assert len(mock)==66
for r in mock:
 if r['layer']=='local_HTTP':assert r['cleared']==r['total']and f"{r['runtime_s']:.2f}"in text
out={'status':'passed','checked_rows':rows_checked,'max_cost_residual_s':max_residual,'q2_nodes':cert['continuous_and_quantized_upper']['nodes'],'layout_points':25,'mock_cases':66,'official_formal_cases':0}
(ROOT/'review/final_data_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
