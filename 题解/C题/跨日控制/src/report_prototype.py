"""Export traceable synthetic results and a plot of the continuation-value cuts."""
from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]

def main():
    m=json.loads((ROOT/'artifacts/prototype-results.json').read_text());e=np.array(m['tail_probe_energies']);v=np.array(m['tail_probe_costs'])
    envelope=np.maximum(0,np.max([a+b*e for a,b in m['tail_cuts']],axis=0))
    plt.rcParams.update({'font.family':'Songti SC','font.size':11,'axes.unicode_minus':False,'svg.fonttype':'none'})
    fig,axs=plt.subplots(1,2,figsize=(9,3.8),constrained_layout=True)
    axs[0].plot(e,v,color='#24798D',label='精确继续费用（网格核验）')
    axs[0].plot(e,envelope,'--',color='#BE6D3B',label='当前割下界')
    axs[0].axvline(6000,color='#888888',lw=.8,ls=':');axs[0].axvline(m['continuous_tree']['midnight_energy'],color='#73599C',lw=.8,ls=':')
    axs[0].set(xlabel='两块之间的库存 / kWh',ylabel='第二块条件期望费用 / 元',title='未来电量价值代替每日固定库存')
    trace=m['benders_trace'];it=[r['iteration'] for r in trace]
    axs[1].plot(it,[r['lower_bound'] for r in trace],'o-',label='根问题下界',color='#24798D')
    axs[1].plot(it,[r['best_upper_bound'] for r in trace],'s--',label='已知可行策略期望费用',color='#BE6D3B')
    axs[1].set(xlabel='Benders迭代',ylabel='两块总期望费用 / 元',title='完整有限树下的上下界核对',xticks=it)
    for ax in axs:ax.legend(fontsize=8);ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('人工压缩跨日算例：不是原附件年度结果',fontsize=12)
    for suffix in ['png','svg']:fig.savefig(ROOT/f'figures/跨日价值函数机制.{suffix}',dpi=300,bbox_inches='tight',facecolor='white')
    plt.close(fig)
    text=f'''# 人工跨日机制验证结果

本文件数值由src/two_day_tree.py计算。两个压缩块各含两个10分钟时段，不是两个自然日或原附件结果。价格确定，第二块预测状态和随后负荷创新按既定人工概率揭示；无日内调约。

| 对照 | 期望总费用/元 | 中间库存/kWh | 真正整段末库存/kWh |
|---|---:|---:|---:|
| 两块各自闭合 | {m['daily_closed']['economic_cost']:.6f} | {m['daily_closed']['midnight_energy']:.6f} | 6000 |
| 仅整段末闭合的因果树LP | {m['continuous_tree']['economic_cost']:.6f} | {m['continuous_tree']['midnight_energy']:.6f} | 6000 |
| 午夜保留库存、按新预测条件重解 | {m['rolling_expected_cost']:.6f} | {m['continuous_tree']['midnight_energy']:.6f} | 6000 |

本例费用差为{m['saving_yuan']:.6f}元。其作用是证明跨块携带能量可能有价值，而非预测赛题的节省幅度。

Benders以第二块完整因果树LP的边界库存固定约束对偶乘子构造割，经过{len(trace)}轮得到根上下界一致，和完整树LP的差为{m['checks']['full_tree_benders_gap']:.3g}元。31个状态探针上的最大割超界量为{m['checks']['cut_max_lower_bound_violation_on_31_probes']:.3g}元，属于浮点误差。对偶支撑在精确LP理论下是全可行域下界；有限探针只是实现核验，不能单独证明全域正确。

根最优值收敛不等于整个继续价值函数都已被精确重建。边界处LP可能有多个合法对偶斜率，不必等于内部右导数。实现是两块精确尾值Benders分解，不是通用SDDP训练器。

原始路径、合同、库存、充放电、紧急购电、割系数和迭代轨迹见artifacts/prototype-results.json；输入见inputs/toy.json。图见figures/跨日价值函数机制.png与SVG。
'''
    (ROOT/'机制验证结果.md').write_text(text)
    entries=[]
    def walk(x,p=''):
        if isinstance(x,dict):
            for k,v in x.items():walk(v,p+'/'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,p+'/'+str(i))
        elif isinstance(x,(int,float)) and not isinstance(x,bool):entries.append({'id':'toy'+p.replace('/','.'),'value':x,'source_artifact':'artifacts/prototype-results.json','source_path':p,'status':'verified','scope':'synthetic example only'})
    walk(m)
    (ROOT/'artifacts/result-registry.json').write_text(json.dumps({'results':entries},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'generated','registered_values':len(entries),'scope':'synthetic example only'}))

if __name__=='__main__':main()
