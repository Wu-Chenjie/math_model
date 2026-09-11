"""Independent raw-data review for the second manuscript; does not change results."""
import csv
import json
import math
from pathlib import Path
from statistics import mean, stdev
from scipy.stats import t

ROOT=Path(__file__).resolve().parents[1]
RES=ROOT/'results'
summary=json.loads((RES/'summary.json').read_text(encoding='utf-8'))
configs={'旧最近邻':'test_baseline.csv','分层2-opt':'test_route.csv','联合31点':'test_joint31.csv',
         '25点最近邻':'test_mesh25_nn.csv','联合25点':'test_joint25.csv','最终方案':'test_final.csv'}
report={'configs':{},'stress':{}}
data={}
for name,file in configs.items():
    rows=list(csv.DictReader((RES/file).open()))
    assert len(rows)==400
    for p in (3,4):
        sub=[r for r in rows if int(r['problem'])==p]
        assert [int(r['seed']) for r in sub]==list(range(90001,90201))
        assert all(int(r['cleared'])==int(r['total']) and float(r['ratio'])==1 for r in sub)
        assert all(r['certificate'] in ('upper_bound_16','seven_point_per_channel','convex_mesh_per_channel') for r in sub)
    data[name]=rows
    worst=max(abs(float(r['time_s'])-float(r['move_m'])/5-int(r['switches'])-5*int(r['measures'])
                  -3*int(r['miss'])-5*int(r['cleared'])) for r in rows)
    assert worst<.001
    report['configs'][name]={'rows':400,'max_csv_accounting_residual_s':worst}
    for p in (3,4):
        sub=[r for r in rows if int(r['problem'])==p]
        base=[r for r in data['旧最近邻'] if int(r['problem'])==p]
        assert [(r['seed'],r['total']) for r in sub]==[(r['seed'],r['total']) for r in base]
        x=[float(r['time_s']) for r in sub]
        y=[float(r['time_s']) for r in base]
        delta=[a-b for a,b in zip(y,x)]
        half=t.ppf(.975,199)*stdev(delta)/math.sqrt(200)
        result={'mean_time_s':mean(x),'mean_avg_s':mean(float(r['avg_s']) for r in sub),
                'saving_percent':100*mean(delta)/mean(y),'saving_ci95':[mean(delta)-half,mean(delta)+half],
                'wins':sum(d>1e-6 for d in delta)}
        target=summary['configs'][name][str(p)]
        assert abs(result['mean_time_s']-target['time_s']['mean'])<1e-7
        assert abs(result['mean_avg_s']-target['avg_s']['mean'])<1e-7
        assert abs(result['saving_percent']-target['saving_percent'])<1e-8
        assert max(abs(a-b) for a,b in zip(result['saving_ci95'],target['saving_s']['ci95']))<1e-7
        assert result['wins']==target['wins']
        report['configs'][name][str(p)]=result
for idx,name in enumerate(['boundary','collinear','correlated','endpoint','degenerate']):
    rows=list(csv.DictReader((RES/f'stress_{name}.csv').open()))
    assert len(rows)==200
    for p in (3,4):
        sub=[r for r in rows if int(r['problem'])==p]
        assert [int(r['seed']) for r in sub]==list(range(110001+idx*10000,110101+idx*10000))
        assert all(int(r['cleared'])==int(r['total']) and float(r['ratio'])==1 for r in sub)
    report['stress'][name]={'rows':200,'all_cleared':True}
original=json.loads((RES/'original_mock_validation.json').read_text(encoding='utf-8'))
assert all(r.get('cleared_count',r.get('cleared'))==r.get('jammer_total',r.get('total')) for r in original)
report['original_mock']={key:sum(r['layer']==key for r in original) for key in {r['layer'] for r in original}}
report['lower_bound']={'outside_points':math.ceil(math.pi/math.atan(1000/1800)),
                       'fixed_points':math.ceil(3*(1800/1000)**2+7/2)}
report['q2_exact_rerun']=json.loads((ROOT/'review/scoring_q2_certificate.json').read_text())
report['q2_exact_rerun']['continuous_and_quantized_upper'].pop('leaves')
(ROOT/'review/second_scoring_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'final':report['configs']['最终方案'],'all_csv_rows':3400,'mock':report['original_mock'],
                  'lower_bound':report['lower_bound']},ensure_ascii=False,indent=2))
