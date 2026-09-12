import csv,json,math
from pathlib import Path
import numpy as np
from scipy.stats import t
ROOT=Path(__file__).resolve().parents[1]
def analyze(name,start,count):
    rows=list(csv.DictReader((ROOT/'results'/name).open(encoding='utf-8-sig')))
    assert len(rows)==2*count*4
    paired={}
    for r in rows:
        key=int(r['problem']),int(r['seed']);method=int(r['method'])
        assert int(r['cleared'])==int(r['n']) and r['certificate']!='incomplete'
        assert int(r['dp_actions'])<=6*int(r['n'])
        cost=float(r['move_m'])/5+float(r['switches'])+5*float(r['measures'])+3*float(r['miss'])+5*float(r['cleared'])
        assert abs(cost-float(r['time_s']))<.001
        assert abs(float(r['avg_s'])-float(r['time_s'])/int(r['n']))<1e-6
        if key not in paired:paired[key]={}
        assert method not in paired[key];paired[key][method]=r
    assert set(paired)=={(p,s) for p in [3,4] for s in range(start,start+count)}
    assert all(set(v)=={0,1,2,3} and len({r['n'] for r in v.values()})==1 for v in paired.values())
    result={}
    for p in [3,4]:
        env=[paired[p,s] for s in range(start,start+count)]
        arr=lambda m,k:np.array([float(e[m][k]) for e in env]);result[p]={}
        for m in range(4):
            x=arr(m,'time_s');v={'cases':count,'all_cleared':True,'total_mean_s':float(x.mean()),'single_mean_s':float(arr(m,'avg_s').mean()),'p95_s':float(np.quantile(x,.95)),
                'mean_cpu_s':float(arr(m,'runtime_s').mean()),'max_cpu_s':float(arr(m,'runtime_s').max()),'dp_calls_mean':float(arr(m,'dp_calls').mean()),'dp_actions_mean':float(arr(m,'dp_actions').mean()),
                'dp_fallbacks_mean':float(arr(m,'dp_fallbacks').mean()),'budget_hits':int(arr(m,'dp_budget_hits').sum()),'comparisons':{}}
            for base in [0,1,2]:
                d=arr(base,'time_s')-x;mean=float(d.mean());half=float(t.ppf(.975,count-1)*d.std(ddof=1)/math.sqrt(count));idx=int(np.argmin(d))
                v['comparisons'][base]={'saving_mean_s':mean,'saving_percent':100*mean/float(arr(base,'time_s').mean()),'ci95_s':[mean-half,mean+half],
                  'wins':int(sum(d>1e-6)),'losses':int(sum(d< -1e-6)),'ties':int(sum(abs(d)<=1e-6)),
                  'max_slowdown_s':float(max(0,-min(d))),'worst_seed':start+idx,
                  'cost_saving_s':{'move':float((arr(base,'move_m')-arr(m,'move_m')).mean()/5),'measure':float(5*(arr(base,'measures')-arr(m,'measures')).mean()),'switch':float((arr(base,'switches')-arr(m,'switches')).mean()),'failed_clear':float(3*(arr(base,'miss')-arr(m,'miss')).mean())}}
            result[p][m]=v
    return result
def main():
    report={'development':analyze('development.csv',1,40),'iid':analyze('iid.csv',1210001,200),'stress':{}}
    for k,start in enumerate([1220001,1230001,1240001,1250001,1260001],1):report['stress'][k]=analyze(f'stress{k}.csv',start,40)
    (ROOT/'results/summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'iid':report['iid'],'stress_selected':{k:{p:{'single':v[p][3]['single_mean_s'],'vs_previous':v[p][3]['comparisons'][1]} for p in [3,4]} for k,v in report['stress'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
