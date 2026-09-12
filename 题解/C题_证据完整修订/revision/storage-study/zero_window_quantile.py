"""Independent analytic check of zero-window day-ahead contracts on identical scenarios."""
from pathlib import Path
import json,hashlib,sys,time
import numpy as np
P=Path(__file__).resolve().parents[2];S=P/'revision/storage-study';B=P.parent/'C题_跨日随机控制'
sys.path.insert(0,str(B/'src'))
from forecasting import scenarios

def main():
    start=time.perf_counter();data=dict(np.load(B/'artifacts/data.npz'));sel=json.loads((B/'artifacts/forecast-selection.json').read_text());out={}
    for kind in ['q2','q4_2']:
        a=dict(np.load(S/f'results/{kind}_W0.npz'));gaps=[];diff=[];small=[]
        for i,day in enumerate(range(31,365)):
            net,p,meta=scenarios(data,sel,day*144,min((day+2)*144,365*144),False,kind=='q4_2',count=7)
            net,p=net[:,:144],p[:,:144];assert np.all(p>0)
            order=np.argsort(net,axis=0,kind='stable');ns=np.take_along_axis(net,order,axis=0);ps=np.take_along_axis(p,order,axis=0)
            idx=np.argmax(np.cumsum(ps,axis=0)>=.8*ps.sum(0),axis=0)
            qstar=np.maximum(0,ns[idx,np.arange(144)]);q=a['q'][i]
            f=lambda x:np.mean(p*(x+5*np.maximum(net-x,0)),axis=0)
            gap=f(q)-f(qstar);gaps.extend(gap.tolist());diff.extend(abs(q-qstar).tolist());small.extend(qstar.tolist())
        g=np.array(gaps)
        assert np.max(abs(g))<1e-5
        out[kind]={'slots':len(g),'max_abs_scenario_objective_gap_yuan':float(abs(g).max()),'sum_scenario_objective_gap_yuan':float(g.sum()),'max_abs_contract_difference_kwh':float(max(diff)),'analytic_contract_min_kwh':float(min(small)),'trace_sha256':hashlib.sha256((S/f'results/{kind}_W0.npz').read_bytes()).hexdigest()}
    report={'status':'PASS','scope':'Only same-scenario zero-window day-ahead planning optimum; not real-distribution or annual causal optimality','quantile':.8,'derivation':'min_q>=0 mean_s p_s[q+5(n_s-q)+]; weights proportional to scenario prices','tolerance_yuan_per_slot':1e-5,'results':out,'runtime_seconds':time.perf_counter()-start,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    def sci(v):
        mant,exp=f'{v:.2e}'.split('e')
        return '$'+mant+r'\times10^{'+str(int(exp))+'}$'
    values=[sci(out[k]['max_abs_scenario_objective_gap_yuan']) for k in ['q2','q4_2']]
    text='针对两个日前机制各48,096段，在每日0时的相同场景下，保存合同与解析分位合同的单段目标最大绝对差分别约为'+values[0]+'元和'+values[1]+'元。该核验验证零窗口下当前有限场景规划的实现，比较对象是规划目标，而非未知真实分布下的最优费用。\n'
    (P/'tables/storage-zero-quantile-text.tex').write_text(text)
    (S/'zero-window-quantile.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
