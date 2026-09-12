"""Produce paper tables and capacity figure exclusively from independently audited runs."""
from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent
PAPER=HERE.parents[1]
KINDS=['q2','q3','q4_2','q4_3']
LABELS=['问题二','问题三','问题四日前','问题四日内']
def main():
    p=HERE/'capacity-audit.json';audit=json.loads(p.read_text());assert audit['status']=='PASS'
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    assert audit['verifier_sha256']==sha(HERE/'verify_capacity.py'), 'Audit verifier version changed'
    recorded=audit['current_hashes'];base=PAPER.parent/'C题_跨日随机控制'
    assert recorded['producer_sha256']==sha(HERE/'run_capacity.py')
    for name,digest in recorded['source_hashes'].items():assert sha(base/'src'/name)==digest
    for name,digest in recorded['input_hashes'].items():assert sha(base/'artifacts'/name)==digest
    for kind in KINDS:
        for width in [0,4800,9600]:
            entry=audit['runs'][kind][str(width)]
            expected=PAPER/f'revision/base-artifacts/{kind}.npz' if width==9600 else HERE/f'results/{kind}_W{width}.npz'
            assert Path(entry['trajectory_path']).resolve()==expected.resolve()
            assert sha(expected)==entry['trajectory_sha256'], (kind,width,'trajectory changed')
            assert sha(expected.with_suffix('.json'))==entry['metrics_sha256'], (kind,width,'metrics changed')
    font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
    plt.rcParams.update({'font.family':'Heiti TC','axes.unicode_minus':False,'font.size':14,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(10.4,4.5),layout='constrained')
    for ai,ax in enumerate(axes):
        for j,k in enumerate(KINDS[ai*2:ai*2+2]):
            y=np.array([audit['runs'][k][str(w)]['summary']['total_cost_yuan']/1e4 for w in [0,4800,9600]])
            ax.plot([0,4.8,9.6],y,'o-',color=['#299c99','#db8162'][j],lw=2,label=['日前机制','日内机制'][j])
            for x,v in zip([0,4.8,9.6],y):
                ax.annotate(f'{v:,.2f}',(x,v),xytext=(0,12 if j==0 else -19),textcoords='offset points',ha='center',fontsize=12,bbox={'facecolor':'white','edgecolor':'none','alpha':.9,'pad':.5})
        ax.set_xticks([0,4.8,9.6]);ax.set_xlim(-.9,10.5);ax.margins(y=.19)
        ax.set_xlabel('可用库存宽度 W / MWh');ax.set_ylabel('334日实际账单 / 万元')
        ax.set_title(['固定电价','变动电价'][ai]);ax.grid(axis='y',alpha=.18);ax.legend(fontsize=12)
    fig.suptitle('同初末库存、同功率：可用容量的闭环费用响应',fontsize=18)
    fig.savefig(PAPER/'figures/storage-capacity.png',dpi=220);plt.close(fig)
    rows=[];parts=[];cirows=[]
    for label,k in zip(LABELS,KINDS):
        costs=[audit['runs'][k][str(w)]['summary']['total_cost_yuan']/1e4 for w in [0,4800,9600]]
        full=audit['comparisons'][k]['0_to_9600'];half=audit['comparisons'][k]['4800_to_9600']
        rows.append(label+'&'+'&'.join(f'{v:,.2f}' for v in costs)+f"&{full['saving_yuan']/1e4:,.2f}&{full['saving_percent']:.2f}\\%&{half['saving_yuan']/1e4:,.2f}"+r'\\')
        for w in [0,4800,9600]:
            z=audit['runs'][k][str(w)]['summary'];parts.append(f'{label}&{w/1000:.1f}&'+'&'.join(f'{z[f]/1e4:,.2f}' for f in ['planned_cost_yuan','increase_cost_yuan','reduction_net_cost_yuan','emergency_cost_yuan','total_cost_yuan'])+r'\\')
        for pair,plabel in [('0_to_9600','停用至全窗口'),('4800_to_9600','半窗口至全窗口')]:
            z=audit['comparisons'][k][pair];lo,hi=z['bootstrap']['daily_mean_ci95_yuan'];cirows.append(f"{label}&{plabel}&{z['daily_mean_saving_yuan']:,.2f}&[{lo:,.2f}, {hi:,.2f}]&{z['positive_days']}/{z['negative_days']}/{z['zero_days']}"+r'\\')
    table=r'''\begin{table}[H]\centering\small
\caption{三档可用容量的完整运行期账单}\label{tab:capacitycost}
\begin{tabular}{lrrrrrr}\toprule
机制& $W=0$ & $W=4.8$ & $W=9.6$ & 全对零节省 & 降幅 & 全对半节省\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}
\par\footnotesize $W$单位MWh，费用单位万元。全对零节省为$C(0)-C(9.6)$，降幅除以$C(0)$；全对半节省为$C(4.8)-C(9.6)$。
\end{table}
'''
    (PAPER/'tables/storage-capacity.tex').write_text(table)
    tab=r'''\begin{table}[H]\centering\small
\caption{容量消融费用分解（万元）}\label{tab:capacityparts}
\begin{tabular}{lrrrrrr}\toprule
机制& $W$/MWh & 原计划 & 增购 & 退购净额 & 紧急费 & 合计\\\midrule
'''+ '\n'.join(parts)+r'''
\bottomrule\end{tabular}
\par\footnotesize 分项按未舍入数值相加；退购净额为退款扣除退购手续费后的负支出。
\end{table}
'''
    (PAPER/'tables/storage-capacity-parts.tex').write_text(tab)
    tab=r'''\begin{table}[H]\centering\small
\caption{容量配对日差的7日块重采样（元/日）}\label{tab:capacityci}
\begin{tabular}{llrrr}\toprule
机制&比较&日均节省&95\%区间&节省/增支/持平日\\\midrule
'''+ '\n'.join(cirows)+r'''
\bottomrule\end{tabular}
\par\footnotesize 正差为较大窗口降低费用。块长7日，10,000次，种子序列$[20260912,k,p]$；当前单年度时间稳定性诊断。
\end{table}
'''
    (PAPER/'tables/storage-capacity-ci.tex').write_text(tab)
    def saving_phrase(v):
        return ('节省' if v>=0 else '增加')+f'{abs(v)/1e4:,.2f}万元'
    full=[audit['comparisons'][k]['0_to_9600'] for k in KINDS]
    half=[audit['comparisons'][k]['4800_to_9600'] for k in KINDS]
    text=r'\textbf{容量作用：}在问题二、问题三、问题四日前和日内机制中，完整9.60 MWh窗口相对停用储能，费用依次'+ '、'.join(saving_phrase(z['saving_yuan']) for z in full)+'。'
    text+='将可用窗口从4.80 MWh扩大到9.60 MWh，费用依次'+ '、'.join(saving_phrase(z['saving_yuan']) for z in half)+'。完整费用、分项账目及配对日差区间见附录表'+r'\ref{tab:capacitycost}至表\ref{tab:capacityci}'+'。容量对照量化储能可用空间的费用作用；主表固定9.60 MWh窗口的跨日贪心对照，则量化控制策略的改进。\n'
    (PAPER/'tables/storage-capacity-results-text.tex').write_text(text)
    text='12组轨迹的库存区间、初末条件、跨午夜衔接、充放电功率、单向动作、紧急电量和供需平衡均通过独立逐段检查。电量项容差为$10^{-5}$ kWh，功率按每段$5000/6$ kWh约束核验。现金费用同时按分项账单和逐段$p_t\\{r_t+0.5|r_t-q_t|+5e_t\\}$重算，年度总费与保存结果的绝对差小于$10^{-5}$元。实际价格逐段与题目数据对应，日前机制无日内改约，日内机制的每次发布只覆盖当前及后续区间。所有新容量运行的源码、输入和实验入口哈希均与审计观察快照相符；主结果五份工作簿保持原对应轨迹。\n'
    (PAPER/'tables/storage-capacity-validation-text.tex').write_text(text)
    evidence={'audit_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'figure_roles':{'figures/storage-capacity.png':'actual closed-loop cost response at three usable inventory widths','figures/annual-inventory-heatmap.png':'ten-minute end-state pattern over the calendar year','figures/annual-inventory-envelope.png':'daily envelope and all366 midnight states including true endpoint'},'capacity_text_metrics':{k:{'costs_yuan':[audit['runs'][k][str(w)]['summary']['total_cost_yuan'] for w in [0,4800,9600]],'full_vs_zero_saving_yuan':audit['comparisons'][k]['0_to_9600']['saving_yuan'],'full_vs_zero_saving_percent':audit['comparisons'][k]['0_to_9600']['saving_percent'],'full_vs_half_saving_yuan':audit['comparisons'][k]['4800_to_9600']['saving_yuan']} for k in KINDS}}
    (HERE/'paper-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
