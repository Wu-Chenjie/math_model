"""Independent paper-score audit: raw rows and direct geometry, no reviewer imports."""
import csv
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'results'
summary = json.loads((RES / 'summary.json').read_text(encoding='utf-8'))
report = {}
for filename in ['test_main.csv', 'test_static.csv', 'test_square.csv', 'test_strict.csv',
                 'stress_boundary.csv', 'stress_collinear.csv', 'stress_correlated.csv',
                 'stress_endpoint.csv', 'stress_degenerate.csv']:
    rows = list(csv.DictReader((RES / filename).open()))
    assert all(int(r['total']) == int(r['cleared']) and float(r['ratio']) == 1 for r in rows)
    assert len({(r['problem'], r['seed']) for r in rows}) == len(rows)
    residual = max(abs(float(r['time_s']) - (float(r['move_m'])/5 + int(r['switches'])
                       + 5*int(r['measures']) + 3*int(r['miss']) + 5*int(r['cleared']))) for r in rows)
    # CSV uses 12 significant figures; long pressure-case times lose low digits.
    assert residual < 1e-3
    report[filename] = {'rows': len(rows), 'all_cleared': True, 'max_accounting_residual_s': residual}
    if filename == 'test_main.csv':
        for p in ('3', '4'):
            sub = [r for r in rows if r['problem'] == p]
            assert [int(r['seed']) for r in sub] == list(range(10001,10201))
            assert abs(mean(float(r['avg_s']) for r in sub)-summary['main'][p]['avg_s']['mean']) < 1e-8
            report[filename][p] = {'avg_s': mean(float(r['avg_s']) for r in sub),
                'pooled_s': sum(float(r['time_s']) for r in sub)/sum(int(r['cleared']) for r in sub)}
original = json.loads((RES/'original_mock_validation.json').read_text(encoding='utf-8'))
assert all(r.get('cleared_count',r.get('cleared')) == r.get('jammer_total',r.get('total')) for r in original)
report['original_mock_layers'] = {k: sum(r['layer']==k for r in original) for k in {r['layer'] for r in original}}

# Independently enumerate the six true cone boundaries of the paper's counterexample.
stations = [(-1000,0), (540,-500*math.sqrt(3)), (520,520*math.sqrt(3))]
constraints = []
for (x,y), angle in zip(stations,(1,121,241)):
    t=math.radians(angle); u=(math.cos(t),math.sin(t)); v=(-u[1],u[0])
    for sign in (-1,1):
        a=(sign*v[0]-math.tan(math.pi/180)*u[0],sign*v[1]-math.tan(math.pi/180)*u[1])
        constraints.append((a[0],a[1],a[0]*x+a[1]*y))
vertices=[]
for i,(a,b,c) in enumerate(constraints):
    for d,e,f in constraints[:i]:
        det=a*e-b*d
        if abs(det)<1e-12: continue
        x,y=(c*e-b*f)/det,(a*f-c*d)/det
        if all(g*x+h*y<=k+1e-8 for g,h,k in constraints):
            if all(math.hypot(x-xx,y-yy)>1e-6 for xx,yy in vertices): vertices.append((x,y))
assert len(vertices)==3
diam=max(math.dist(a,b) for a in vertices for b in vertices)
assert abs(diam-40)<1e-7
eps=math.radians(1.005)
q2=max(math.sqrt(r*r+a*a+b*b-2*r*(a*math.cos(ph)+b*math.sin(ph)))
       for r in (5,1500) for a in (650,850) for b in (-400,-200,200,400) for ph in (-eps,eps))
seven=math.sqrt(1800**2+1200**2-2*1800*1200*math.cos(math.pi/6))
report['geometry']={'triangle_vertices':vertices,'diameter_m':diam,'triangle_mec_radius_m':40/math.sqrt(3),
                    'q2_max_m':q2,'seven_point_cover_radius_m':seven,
                    'virtual_bound_s':(223*6644+16*107*28)/5+6*748+3*1776+2*16}
dest=ROOT/'review'/'scoring_checks.json'
dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
