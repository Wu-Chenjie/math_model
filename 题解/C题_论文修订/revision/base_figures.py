from pathlib import Path
import json,numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
O=Path(__file__).resolve().parents[1];R=O.parent/'C题_跨日随机控制'
font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family':'Heiti TC','axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160,'savefig.dpi':220})
C=json.loads((O/'revision/base-artifacts/result-claims.json').read_text());H=json.loads((O/'revision/base-artifacts/handoff-tables.json').read_text());K=list(C['models']);labels=['问题二','问题三','问题四日前','问题四日内'];colors=['#2b8c91','#cb655d','#7683b4','#d79a57']
def save(name):plt.savefig(O/f'figures/{name}.png',bbox_inches='tight');plt.close()
def table(name,caption,head,rows,spec=None):
 spec=spec or 'l'+'r'*(len(head)-1)
 lines=['\\begin{table}[htbp]\\centering\\small',r'\caption{'+caption+'}',r'\begin{tabular}{'+spec+'}',r'\toprule',' & '.join(head)+r' \\',r'\midrule']
 lines+=[' & '.join(str(x) for x in row)+r' \\' for row in rows];lines +=[r'\bottomrule\end{tabular}\end{table}']
 # Table reproduction is handled by revision/build_required_tables.py.
 pass
table('main','同真实初末库存下的334日账单与配对节省（C；费用单位：万元）',['机制','主策略','每日闭合基线','节省','降幅'],[[l,f"{C['models'][k]['main']['total_cost']/1e4:.2f}",f"{C['models'][k]['baseline_daily_greedy']['total_cost']/1e4:.2f}",f"{C['models'][k]['paired_vs_daily_greedy']['cumulative_yuan']/1e4:.2f}",f"{100*C['models'][k]['paired_vs_daily_greedy']['cumulative_yuan']/C['models'][k]['baseline_daily_greedy']['total_cost']:.2f}\\%"] for k,l in zip(K,labels)])
table('mechanisms','分别隔离跨日状态与库存价值反馈的闭环对照（C；万元）',['机制','每日闭合仿射','跨日仿射','跨日节省','反馈再节省'],[[l,f"{C['models'][k]['closed_affine']['total_cost']/1e4:.2f}",f"{C['models'][k]['cross_affine']['total_cost']/1e4:.2f}",f"{C['models'][k]['cross_saving_yuan']/1e4:.2f}",f"{C['models'][k]['feedback_saving_yuan']/1e4:.2f}"] for k,l in zip(K,labels)])
table('ablation','固定主策略框架下删减已提供预报的配对回放（C；万元）',['保留预报','总费用','相对完整预报增加'],[['全部',f"{C['models']['q3']['main']['total_cost']/1e4:.2f}",'0.00']]+[[{'0only':'只保留0时','without6':'删除6时','without12':'删除12时','without18':'删除18时'}[n],f"{v['full_fixed_totals']['total_cost']/1e4:.2f}",f"{v['extra_cost_yuan']/1e4:.2f}"] for n,v in C['ablation'].items()])
table('bootstrap','日均配对节省的移动块95\\%百分位区间（C；元/日）',['机制','日均节省','3日块','7日块','14日块'],[[l,f"{C['models'][k]['paired_vs_daily_greedy']['mean_yuan']:.1f}"]+['['+', '.join(f'{x:.1f}' for x in C['models'][k]['paired_vs_daily_greedy']['bootstrap'][str(b)]['mean_95_percentile_yuan'])+']' for b in [3,7,14]] for k,l in zip(K,labels)])
table('stability','同年度时间稳定性诊断（C）',['机制','正日数','负日数','正月数/11','一阶相关'],[[l,v['positive_days'],v['negative_days'],f"{v['positive_months']}/11",f"{v['lag1_correlation']:.3f}"] for k,l in zip(K,labels) for v in [C['models'][k]['paired_vs_daily_greedy']]])
table('monthly','逐月配对累计节省（C；万元）',['月份']+labels,[[m]+[f"{C['models'][k]['paired_vs_daily_greedy']['monthly_yuan'][m]/1e4:.3f}" for k in K] for m in C['models']['q2']['paired_vs_daily_greedy']['monthly_yuan']])
table('dev','固定终点开发期复核：2025年1月25日至31日（C；元）',['候选']+labels,[[c.replace('_',r'\_')]+[f"{C['development'][k]['costs_yuan'][c]:.2f}" for k in K] for c in C['development']['q2']['costs_yuan']])
table('sensitivity','既有七日敏感性实验：3月14日至20日，自由末端（C）',['配置','费用/元','末库存/kWh','相对参考/元'],[[n.replace('_',r'\_'),f"{v['totals']['total_cost']:.2f}",f"{v['validation']['final_inventory']:.2f}",f"{v['totals']['total_cost']-C['sensitivity']['reference']['totals']['total_cost']:.2f}"] for n,v in C['sensitivity'].items()])
table('q1buy','问题一指定时段购电量（C；kWh）',['时间段','购电量'],[[t,f'{v:.2f}'] for t,v in H['q1']['purchase']])
table('q1bat','问题一分块电池动作（C；母线侧kWh）',['时间段','充电量','放电量'],[[t,f'{c:.2f}',f'{d:.2f}'] for t,c,d in H['q1']['battery']])
for k,l in zip(K,labels):
 rows=[]
 for date,s in H['models'][k]['selected'].items():
  rows+=[[date,t,f'{q:.2f}',f'{r:.2f}'] for t,q,r in s['purchase']]
 table('specified-'+k,l+'指定日期、指定时段合同（C；kWh）',['日期','时段','原合同','最终合同'],rows,'llrr')
table('oracle','同路径、同真实终点的完美信息参照（B/C）',['机制','主策略/万元','乐观参照/万元','参照距离'],[[l,f"{C['models'][k]['main']['total_cost']/1e4:.2f}",f"{C['models'][k]['perfect_information_cost_yuan']/1e4:.2f}",f"{C['models'][k]['optimistic_distance_percent']:.2f}\\%"] for k,l in zip(K,labels)])
E=np.linspace(1.2,10.8,300);plt.figure(figsize=(5.7,3.5));plt.fill_between(E,np.maximum(1.2,E-(5/6)/.9),np.minimum(10.8,E+.9*5/6),color='#bfe6e4');plt.plot(E,E,'--',color='#555555',label='不动作');plt.plot(E,np.minimum(10.8,E+.9*5/6),color=colors[0],label='最大充电');plt.plot(E,np.maximum(1.2,E-(5/6)/.9),color=colors[1],label='最大放电');plt.xlabel('当前库存 E / MWh');plt.ylabel('下一库存 x / MWh');plt.legend(fontsize=9);save('reachable')
a=dict(np.load(R/'artifacts/q1.npz'));data=dict(np.load(R/'artifacts/data.npz'));fig,ax=plt.subplots(figsize=(7,2.8));ax.plot(np.arange(145)/6,a['state']/1000,color=colors[0],label='库存');ax.set(xlabel='时刻 / h',ylabel='库存 / MWh',xlim=(0,24));p=ax.twinx();p.step(np.arange(144)/6,data['day_price'],where='post',color=colors[1],alpha=.55,label='电价');p.set_ylabel('元/kWh');ax.legend(loc='upper left');p.legend(loc='upper right');save('q1')
fig,ax=plt.subplots(figsize=(7,2.8));
for i,(k,l) in enumerate(zip(K,labels)):
 v=C['models'][k]['paired_vs_daily_greedy'];ci=v['bootstrap']['7']['mean_95_percentile_yuan'];ax.errorbar(v['mean_yuan'],i,xerr=[[v['mean_yuan']-ci[0]],[ci[1]-v['mean_yuan']]],fmt='o',capsize=4,color=colors[i]);ax.text(ci[1]+20,i,f"{v['mean_yuan']:.0f} [{ci[0]:.0f}, {ci[1]:.0f}]",va='center',fontsize=9)
ax.set_yticks(range(4),labels);ax.set_xlim(0,2050);ax.axvline(0,color='#777777',ls='--');ax.set_xlabel('日均节省及7日块95%区间 / 元');save('bootstrap')
fig,axes=plt.subplots(1,2,figsize=(8,2.9));
for ax,k,title in zip(axes,['q3','q4_3'],['固定价日内机制','变动价日内机制']):
 v=C['models'][k];parts=['planned_cost','increase_cost','reduction_net_cost','emergency_cost'];delta=np.array([v['main'][p]-v['baseline_daily_greedy'][p] for p in parts])/1e4;ax.bar(range(4),delta,color=[colors[1] if x>0 else colors[0] for x in delta]);ax.axhline(0,color='#777777',lw=.6);ax.set_xticks(range(4),['原计划','增购','退购净额','紧急']);ax.set_title(title);ax.set_ylabel('相对基线的费用变化 / 万元');
 for j,x in enumerate(delta):ax.text(j,x+(1 if x>=0 else -1),f'{x:+.2f}',ha='center',va='bottom' if x>=0 else 'top',fontsize=9)
fig.tight_layout();save('decomposition')
fig,ax=plt.subplots(figsize=(7,2.8));a=dict(np.load(O/'artifacts/q3.npz'));i=list(a['dates']).index('2025-09-23');ax.step(np.arange(144)/6,a['q'][i]*6/1000,label='原合同',color=colors[0]);ax.step(np.arange(144)/6,a['r'][i]*6/1000,label='最终合同',color=colors[2]);ax.step(np.arange(144)/6,a['emergency'][i]*6/1000,label='紧急购电',color=colors[1]);ax.set(xlabel='9月23日时刻 / h',ylabel='功率 / MW',xlim=(0,24));ax.legend(ncol=3);save('contracts')
if all((O/f'artifacts/gain-{k}.json').exists() for k in K):
 table('gains','全年主策略规划LP增益触边诊断（C；容差$10^{-6}$）',['机制','规划次数','增益数','触边数','触边比例'],[[l,len(v['records']),v['gain_entries'],v['near_bound_entries'],f"{v['near_bound_fraction']*100:.2f}\\%"] for k,l in zip(K,labels) for v in [json.loads((O/f'artifacts/gain-{k}.json').read_text())]])
print('Generated registered tables and six argument-focused figures.')
