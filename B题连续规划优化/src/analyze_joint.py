import csv,json,math
from pathlib import Path
import numpy as np
from scipy.stats import t
ROOT=Path(__file__).resolve().parents[1]
def interval(a):
    mean=float(a.mean());half=float(t.ppf(.975,len(a)-1)*a.std(ddof=1)/math.sqrt(len(a)))
    return [mean-half,mean+half]
def paired(basefile,newfile,start,count,final_method=38):
    groups=[]
    for filename,method in [(basefile,0),(newfile,final_method)]:
        rows=list(csv.DictReader((ROOT/'results'/filename).open(encoding='utf-8-sig')))
        assert len(rows)==2*count
        data={}
        for r in rows:
            p,seed=int(r['problem']),int(r['seed']);assert int(r['method'])==method
            assert int(r['n'])==int(r['cleared']) and r['certificate']!='incomplete'
            assert int(r['dp_actions'])<=6*int(r['n']) and int(r['aux_calls'])<=4*int(r['n'])
            cost=float(r['move_m'])/5+float(r['switches'])+5*float(r['measures'])+3*float(r['miss'])+5*float(r['cleared'])
            assert abs(cost-float(r['time_s']))<.001
            assert abs(float(r['avg_s'])-float(r['time_s'])/int(r['n']))<1e-6
            assert (p,seed) not in data;data[p,seed]=r
        assert set(data)=={(p,s) for p in [3,4] for s in range(start,start+count)}
        groups.append(data)
    result={}
    for p in [3,4]:
        arr=lambda g,key:np.array([float(groups[g][p,s][key]) for s in range(start,start+count)])
        assert np.array_equal(arr(0,'n'),arr(1,'n'))
        b,n=arr(0,'time_s'),arr(1,'time_s');d=b-n;over=.9*b-n;idx=int(np.argmin(d))
        result[p]={'cases':count,'all_cleared':True,'baseline_total_s':float(b.mean()),'new_total_s':float(n.mean()),'baseline_single_s':float(arr(0,'avg_s').mean()),'new_single_s':float(arr(1,'avg_s').mean()),
            'saving_percent':float(100*d.mean()/b.mean()),'saving_mean_s':float(d.mean()),'paired_ci95_s':interval(d),'excess_over_10pct_s':float(over.mean()),'excess_over_10pct_ci95_s':interval(over),
            'wins':int(sum(d>1e-6)),'losses':int(sum(d< -1e-6)),'ties':int(sum(abs(d)<=1e-6)),'max_slowdown_s':float(max(0,-min(d))),'worst_seed':start+idx,
            'baseline_p95_s':float(np.quantile(b,.95)),'new_p95_s':float(np.quantile(n,.95)),
            'baseline_cpu_mean_s':float(arr(0,'runtime_s').mean()),'new_cpu_mean_s':float(arr(1,'runtime_s').mean()),'new_cpu_max_s':float(arr(1,'runtime_s').max()),'budget_hits':int(arr(1,'dp_budget_hits').sum()),
            'dp_calls_mean':float(arr(1,'dp_calls').mean()),'aux_calls_mean':float(arr(1,'aux_calls').mean()),
            'cost_savings_s':{'move':float((arr(0,'move_m')-arr(1,'move_m')).mean()/5),'measure':float((arr(0,'measures')-arr(1,'measures')).mean()*5),'switch':float((arr(0,'switches')-arr(1,'switches')).mean()),'failed_clear':float((arr(0,'miss')-arr(1,'miss')).mean()*3)}}
    return result
def main():
    report={'baseline':'previous round default two-step DP','iid':paired('iid_baseline.csv','iid_final.csv',1510001,200),'stress':{}}
    for k,start in enumerate([1520001,1530001,1540001,1550001,1560001],1):report['stress'][k]=paired(f'stress{k}_0.csv',f'stress{k}_38.csv',start,40)
    (ROOT/'results/summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
