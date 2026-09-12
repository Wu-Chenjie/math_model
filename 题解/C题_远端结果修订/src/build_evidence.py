"""Recompute paper evidence; reported remote summaries and replay checks stay distinct."""
from pathlib import Path
import hashlib, json, shutil, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT=Path(__file__).resolve().parents[1]
NEXT=ROOT.parent/'C题_下一代随机控制'
REF=ROOT.parent/'C题_论文修订'
for name in ['artifacts','figures','tables','output/pdf','tmp/pdfs','model-source','inputs']:
    (ROOT/name).mkdir(parents=True,exist_ok=True)
font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family':'Heiti TC','axes.unicode_minus':False,'font.size':11,
 'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160,'savefig.bbox':'tight'})
teal='#36aaa6'; coral='#ec9b85'; grey='#647378'
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def figsave(name):
    for ext in ['png','pdf']:plt.savefig(ROOT/'figures'/f'{name}.{ext}')
    plt.close()
sources={}
def record(p):
    sources[str(p.relative_to(ROOT.parent))]=hashlib.sha256(p.read_bytes()).hexdigest()
summary=NEXT/'results/remote-formal-20260912/remote_formal_summary.json'
record(summary);shutil.copy2(summary,ROOT/'artifacts/remote-reported-summary.json')
report=json.loads(summary.read_text())
for name in ['control.py','dispatch.py','forecasting.py','nextgen_scenarios.py','nextgen_control.py','nextgen_run.py','sddp.py']:
    p=NEXT/'src'/name;record(p);shutil.copy2(p,ROOT/'model-source'/name)
for name in ['q1buy.tex','q1bat.tex']:
    shutil.copy2(REF/'tables'/name,ROOT/'tables'/name)
for name in ['reachable.png','q1.png']:
    shutil.copy2(REF/'figures'/name,ROOT/'figures'/name)
shutil.copy2(REF/'fvextra.sty',ROOT/'fvextra.sty')
q1p=NEXT/'baseline_frozen/artifacts/q1.json';q1z=NEXT/'baseline_frozen/artifacts/q1.npz'
record(q1p);record(q1z)
q1=dict(np.load(q1z)); q1m=json.loads(q1p.read_text())
q1m.update(buy_kwh=float(q1['q'].sum()),charge_kwh=float(q1['c'].sum()),discharge_kwh=float(q1['d'].sum()))
q1m.update(specified_buy_kwh=q1['q'][[60,72,84,96,108,120]].tolist(),
 charge_4h_kwh=q1['c'].reshape(6,24).sum(1).tolist(),discharge_4h_kwh=q1['d'].reshape(6,24).sum(1).tolist(),
 initial_kwh=float(q1['state'][0]),terminal_kwh=float(q1['state'][-1]))
dump(ROOT/'artifacts/q1-evidence.json',q1m)
newp=NEXT/'artifacts/formal/q2_6cfbc0fe34fd0999.npz'
oldp=NEXT/'baseline_frozen/artifacts/global-terminal/q2_markov_mpc.npz'
for p in [newp,oldp,newp.with_suffix('.json')]:record(p)
new=dict(np.load(newp));old=dict(np.load(oldp)); data=dict(np.load(NEXT/'artifacts/data.npz'))
record(NEXT/'artifacts/data.npz')
assert np.array_equal(new['days'],old['days'])
assert np.array_equal(new['days'],np.arange(31,365))
assert str(new['dates'][0])=='2025-02-01' and str(new['dates'][-1])=='2025-12-31'
assert np.max(np.abs(new['r']-new['q']))<1e-6
assert min(new[k].min() for k in ['q','r','c','d','emergency','spill'])>=-1e-6
def bill(z):
    p=np.broadcast_to(data['day_price'],z['q'].shape)
    parts={'planned_cost':p*z['q'],'adjustment_cost':p*(1.5*np.maximum(z['r']-z['q'],0)-.5*np.maximum(z['q']-z['r'],0)),
           'emergency_cost':5*p*z['emergency']}
    return sum(parts.values()).sum(1),{k:float(v.sum()) for k,v in parts.items()}
nc,np_=bill(new);oc,op=bill(old);delta=oc-nc
assert abs(nc.sum()-report['comparison']['q2']['candidate_cost_yuan'])<1e-5
net=(data['load'][new['days']]-data['pv'][new['days']])/6
validation={'balance_max':float(np.abs(new['r']+new['emergency']+new['d']-new['c']-new['spill']-net).max()),
 'state_residual':float(np.abs(np.diff(new['state'],axis=1)-.9*new['c']+new['d']/.9).max()),
 'midnight_jump':float(np.abs(new['state'][1:,0]-new['state'][:-1,-1]).max()),
 'soc_min':float(new['state'].min()),'soc_max':float(new['state'].max()),
 'power_max_kw':float(6*max(new['c'].max(),new['d'].max())),
 'simultaneous_kwh':float(np.minimum(new['c'],new['d']).max()),
 'initial':float(new['state'][0,0]),'final':float(new['state'][-1,-1])}
assert max(validation[k] for k in ['balance_max','state_residual','midnight_jump','simultaneous_kwh'])<1e-5
assert abs(validation['initial']-6000)<1e-5 and abs(validation['final']-6000)<1e-5
assert validation['soc_min']>=1200-1e-5 and validation['soc_max']<=10800+1e-5 and validation['power_max_kw']<=5000+1e-5
months=np.array([str(x)[:7] for x in new['dates']])
monthly={m:float(delta[months==m].sum()) for m in sorted(set(months))}
boot={}
for b in [3,7,14]:
    rng=np.random.default_rng(20260912)
    starts=rng.integers(0,len(delta)-b+1,(10000,int(np.ceil(len(delta)/b))))
    indexes=(starts[:,:,None]+np.arange(b)).reshape(10000,-1)[:,:len(delta)]
    samples=delta[indexes].mean(1)
    lo,hi=np.quantile(samples,[.025,.975])
    boot[str(b)]={'mean_ci95':[float(lo),float(hi)],'total_ci95':[float(lo*len(delta)),float(hi*len(delta))]}
q2={'comparison':'candidate 6cf vs old fixed-end Markov, matched 334 days',
 'new_total':float(nc.sum()),'old_total':float(oc.sum()),'saving':float(delta.sum()),
 'mean_saving':float(delta.mean()),'new_parts':np_,'old_parts':op,'validation':validation,
 'positive_days':int((delta>1e-6).sum()),'negative_days':int((delta< -1e-6).sum()),'tie_days':int((abs(delta)<=1e-6).sum()),
 'positive_months':sum(v>0 for v in monthly.values()),'monthly':monthly,'daily_delta':delta.tolist(),
 'bootstrap':boot,'bootstrap_seed':20260912,'bootstrap_repetitions':10000}
dump(ROOT/'artifacts/q2-new-analysis.json',q2)
rows=[];comparison={}
for kind,row in report['comparison'].items():
    oldc=row['previous_paper_cost_yuan'];newc=row['candidate_cost_yuan'];diff=oldc-newc
    comparison[kind]={'old':oldc,'new':newc,'difference':diff,'percent':100*diff/oldc,
                     'source_evidence':'locally_recomputed' if kind=='q2' else 'remote_reported_summary'}
    rows.append(f"{row['label']} & {oldc/1e4:,.2f} & {newc/1e4:,.2f} & {diff/1e4:.2f} & {100*diff/oldc:.3f}\\% \\\\")
dump(ROOT/'artifacts/annual-comparison.json',comparison)
(ROOT/'tables/new-main.tex').write_text(r'''\begin{table}[htbp]\centering\small
\caption{统一候选与上一版同任务费用比较（万元）}\label{tab:main}
\begin{tabular}{lrrrr}\toprule
机制&上一版&72小时融合候选&节省&降幅\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}\par\vspace{2mm}
\begin{minipage}{.95\linewidth}\footnotesize
2025年2月至12月334日，报告口径均为初末库存6000 kWh。问题二经本地完整轨迹重算；其余三项按远端复核汇总报告。统一候选属于年度候选比较，对照为上一版跨日Markov策略。
\end{minipage}\end{table}
''')
fig,axs=plt.subplots(1,2,figsize=(9.1,3.5),gridspec_kw={'width_ratios':[1.65,1]})
labels=['问题二','问题三','问题四日前','问题四日内']
for i,(kind,c) in enumerate(comparison.items()):
    y=3-i;ax=axs[0]
    ax.plot([c['new']/1e4,c['old']/1e4],[y,y],color=grey,lw=2)
    ax.scatter(c['old']/1e4,y,color=coral,s=48,label='上一版' if i==0 else None,zorder=3)
    ax.scatter(c['new']/1e4,y,color=teal,s=48,label='72小时融合候选' if i==0 else None,zorder=4)
    ax.annotate(f"{c['new']/1e4:.2f}",(c['new']/1e4,y),xytext=(-4,-17),textcoords='offset points',ha='right',fontsize=9)
    ax.annotate(f"{c['old']/1e4:.2f}",(c['old']/1e4,y),xytext=(4,7),textcoords='offset points',fontsize=9)
    axs[1].barh(y,c['difference']/1e4,color=teal,height=.45)
    axs[1].text(c['difference']/1e4+.25,y,f"{c['difference']/1e4:.2f}（{c['percent']:.3f}%）",va='center',fontsize=9)
axs[0].set_yticks(range(4),labels[::-1]);axs[0].set_xlabel('334日费用 / 万元');axs[0].set_xlim(1320,1480)
axs[0].legend(loc='upper center',bbox_to_anchor=(.5,1.2),frameon=False,ncol=2,fontsize=9)
axs[1].set_yticks([]);axs[1].set_xlabel('相对上一版节省 / 万元');axs[1].set_xlim(0,21)
for ax in axs:ax.set_ylim(-.6,3.7)
fig.tight_layout();figsave('annual-comparison')
fig,axs=plt.subplots(1,2,figsize=(9,3.1))
xx=np.arange(11);vals=np.array(list(monthly.values()))/1e4
axs[0].bar(xx,vals,color=[teal if v>=0 else coral for v in vals]);axs[0].axhline(0,color=grey,lw=.8)
axs[0].set_xticks(xx,range(2,13));axs[0].set_xlabel('月份');axs[0].set_ylabel('问题二月度节省 / 万元')
for i,b in enumerate([3,7,14]):
    lo,hi=boot[str(b)]['mean_ci95'];mu=delta.mean()
    axs[1].plot([lo,hi],[2-i]*2,color=teal,lw=3);axs[1].scatter(mu,2-i,s=45,color=teal,zorder=3)
    axs[1].text(hi+8,2-i,f'[{lo:.1f}, {hi:.1f}]',va='center',fontsize=9)
axs[1].axvline(0,color=coral,ls='--');axs[1].set_yticks([0,1,2],['14日块','7日块','3日块']);axs[1].set_xlabel('日均节省及95%区间 / 元')
allci=[v for k in boot.values() for v in k['mean_ci95']]
axs[1].set_xlim(min(allci)-30,max(allci)+210);axs[1].set_ylim(-.6,2.6)
fig.tight_layout();figsave('q2-stability')
fig,ax=plt.subplots(figsize=(7.5,3.5));levels=[oc.sum()/1e4]
changes=[(np_[k]-op[k])/1e4 for k in ['planned_cost','emergency_cost']]
ax.bar(0,levels[0],color=coral,width=.5)
for i,change in enumerate(changes,1):
    nxt=levels[-1]+change;ax.bar(i,abs(change),bottom=min(levels[-1],nxt),color=teal if change<0 else coral,width=.5)
    ax.plot([i-1+.25,i-.25],[levels[-1]]*2,color=grey,lw=1)
    ax.text(i,max(levels[-1],nxt)+.18,f'{change:+.2f}',ha='center');levels.append(nxt)
ax.bar(3,nc.sum()/1e4,color=teal,width=.5);ax.plot([2.25,2.75],[levels[-1]]*2,color=grey,lw=1)
ax.set_xticks(range(4),['上一版费用','普通购电费变化','紧急购电费变化','72小时费用'])
ax.text(0,levels[0]+.18,f'{levels[0]:.2f}',ha='center');ax.text(3,levels[-1]+.18,f'{levels[-1]:.2f}',ha='center')
ax.set_ylim(min(levels)-1.5,max(levels)+1.5);ax.set_ylabel('问题二费用 / 万元（局部纵轴）')
fig.tight_layout();figsave('q2-waterfall')
fig,ax=plt.subplots(figsize=(7.8,3.0))
hours=np.array([0,6,12,18]);oldh=np.array([48,42,36,30])
ax.plot(hours,oldh,'o-',color=coral,label='上一版：第二个午夜结束')
ax.plot(hours,[72]*4,'o-',color=teal,label='本候选：固定72小时')
ax.set_xticks(hours,['00:00','06:00','12:00','18:00']);ax.set_ylim(20,82);ax.set_ylabel('核心规划长度 / 小时');ax.set_xlabel('当前重规划时刻')
for h,y in zip(hours,oldh):ax.text(h,y-6,str(y),ha='center')
ax.legend(frameon=False,loc='center right');fig.tight_layout();figsave('horizon')
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
parts=[];specified={}
for dt in dates:
    i=list(new['dates'].astype(str)).index(dt);slots=[60,72,84,96,108,120]
    v={'buy':new['r'][i,slots].tolist(),'daily_contract':float(new['r'][i].sum()),'daily_cost':float(nc[i]),
       'charge_4h':new['c'][i].reshape(6,24).sum(1).tolist(),'discharge_4h':new['d'][i].reshape(6,24).sum(1).tolist(),
       'initial':float(new['state'][i,0]),'end':float(new['state'][i,-1]),'emergency_kwh':float(new['emergency'][i].sum())}
    specified[dt]=v
    parts.append(r'\begin{table}[H]\centering\small\setlength{\tabcolsep}{4pt}\caption{问题二 '+dt+r' 购电与电池动作（电量kWh，费用元）}\begin{tabular}{lrlrlr}\toprule')
    parts.append(r'时间段&合同电量&时间段&合同电量&时间段&合同电量\\\midrule')
    for ks in [[0,1,2],[3,4,5]]:
        parts.append(' & '.join(f'{[10,12,14,16,18,20][k]:02}:00--{[10,12,14,16,18,20][k]:02}:10 & {v["buy"][k]:,.2f}' for k in ks)+r'\\')
    parts.append(r'\midrule 四小时段&充电量&放电量&四小时段&充电量&放电量\\\midrule')
    for ks in [[0,1],[2,3],[4,5]]:
        parts.append(' & '.join(f'{k*4:02}:00--{(k+1)*4:02}:00 & {v["charge_4h"][k]:,.2f} & {v["discharge_4h"][k]:,.2f}' for k in ks)+r'\\')
    parts.append(r'\midrule '+f"日初库存 & \\multicolumn{{2}}{{r}}{{{v['initial']:,.2f}}} & 日末库存 & \\multicolumn{{2}}{{r}}{{{v['end']:,.2f}}}\\\\")
    parts.append(f"全天合同 & \\multicolumn{{2}}{{r}}{{{v['daily_contract']:,.2f}}} & 全天紧急购电 & \\multicolumn{{2}}{{r}}{{{v['emergency_kwh']:,.2f}}}\\\\")
    parts.append(f"全天实际费用 & \\multicolumn{{5}}{{r}}{{{v['daily_cost']:,.2f}}}\\\\"+r'\bottomrule\end{tabular}\end{table}')
(ROOT/'tables/q2-specified.tex').write_text('\n'.join(parts))
dump(ROOT/'artifacts/q2-specified.json',specified)
dump(ROOT/'artifacts/input-source-hashes.json',sources)
print(json.dumps({k:q2[k] for k in ['saving','mean_saving','positive_days','negative_days','positive_months','bootstrap','new_parts','old_parts']},ensure_ascii=False,indent=2))
