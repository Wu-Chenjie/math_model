from pathlib import Path
import json, hashlib, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
R=Path(__file__).resolve().parents[2]
BASE=R.parent/'C题_跨日随机控制'
font=FontProperties(fname='/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220})
KS=['q2','q3','q4_2','q4_3'];labels=['问题二','问题三','问题四日前','问题四日内']
result={};ledger={}
def parts(a):
 q,r,p,e=[a[k] for k in ['q','r','price','emergency']]
 return np.array([(p*q).sum(1),(1.5*p*np.maximum(r-q,0)).sum(1),(-.5*p*np.maximum(q-r,0)).sum(1),(5*p*e).sum(1)])
for k in KS:
 mpath=BASE/f'artifacts/global-terminal/{k}_markov_mpc.npz';bpath=R/f'revision/results/{k}_cross_baseline_fixed.npz'
 a=np.load(mpath);b=np.load(bpath);pm=parts(a);pb=parts(b);diff=(pb-pm).sum(0);dates=a['dates'];months=np.array([str(d)[:7] for d in dates]);n=len(diff)
 st={'baseline_cost':float(pb.sum()),'main_cost':float(pm.sum()),'saving':float(diff.sum()),'mean':float(diff.mean()),'positive_days':int((diff>1e-6).sum()),'negative_days':int((diff< -1e-6).sum()),'zero_days':int((abs(diff)<=1e-6).sum()),'monthly':{x:float(diff[months==x].sum()) for x in np.unique(months)},'lag1':float(np.corrcoef(diff[:-1],diff[1:])[0,1]),'bootstrap':{},'component_delta_yuan':(pm-pb).sum(1).tolist(),'main_path':str(mpath.resolve()),'baseline_path':str(bpath.resolve()),'main_sha256':hashlib.sha256(mpath.read_bytes()).hexdigest(),'baseline_sha256':hashlib.sha256(bpath.read_bytes()).hexdigest()}
 for block in [3,7,14]:
  rng=np.random.default_rng(20260911);starts=rng.integers(0,n-block+1,size=(10000,int(np.ceil(n/block))));ix=(starts[:,:,None]+np.arange(block)).reshape(10000,-1)[:,:n]
  st['bootstrap'][str(block)]=np.quantile(diff[ix].mean(1),[.025,.975]).tolist()
 st['positive_months']=sum(v>1e-6 for v in st['monthly'].values());result[k]=st
result['_method']={'replicates':10000,'seed':20260911,'blocks':[3,7,14],'method':'overlapping noncircular moving blocks; independent default_rng reset for each mechanism and block; 334 truncation','scope':'2025-02-01 through 2025-12-31; same initial/final 6000 kWh; single-year time stability'}
(R/'revision/restore/primary-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
def table(file,caption,cols,head,rows):
 s='\\begin{table}[H]\\centering\\small\n\\caption{'+caption+'}\n\\begin{tabular}{'+cols+'}\\toprule\n'+head+r' \\ \midrule'+'\n'+'\n'.join(r+r' \\' for r in rows)+'\n\\bottomrule\\end{tabular}\\end{table}\n';(R/'tables'/file).write_text(s)
table('bootstrap-primary.tex','相对跨日贪心的日均节省与移动块95\\%区间（元/日）','lrrrr','机制 & 日均节省 & 3日块 & 7日块 & 14日块',[labels[i]+f' & {result[k]["mean"]:.1f}'+''.join(' & ['+', '.join(f'{v:.1f}' for v in result[k]['bootstrap'][str(b)])+']' for b in [3,7,14]) for i,k in enumerate(KS)])
table('stability-primary.tex','相对跨日贪心的日、月稳定性','lrrrr','机制 & 正日数 & 负日数 & 正月数/11 & 一阶相关',[f'{labels[i]} & {result[k]["positive_days"]} & {result[k]["negative_days"]} & {result[k]["positive_months"]}/11 & {result[k]["lag1"]:.3f}' for i,k in enumerate(KS)])
table('monthly-primary.tex','主策略相对跨日贪心的逐月累计节省（万元）','lrrrr','月份 & 问题二 & 问题三 & 问题四日前 & 问题四日内',[m+''.join(f' & {result[k]["monthly"][m]/10000:.2f}' for k in KS) for m in result['q2']['monthly']])
fig,ax=plt.subplots(figsize=(7,3.0));colors=['#36a9ad','#ed8581','#36a9ad','#e6a072']
for i,k in enumerate(KS):
 st=result[k];lo,hi=st['bootstrap']['7'];ax.errorbar(st['mean'],3-i,xerr=[[st['mean']-lo],[hi-st['mean']]],fmt='o',color=colors[i],capsize=4,linewidth=2)
 ax.text(870,3-i,f'{st["mean"]:.0f}  [{lo:.0f}, {hi:.0f}]',va='center',fontsize=10)
ax.axvline(0,color='#aaa',ls='--',lw=1);ax.set_yticks(range(4),labels[::-1]);ax.set_xlim(-30,1180);ax.set_ylim(-.6,3.7);ax.set_xlabel('日均节省 / 元（七日移动块95%区间）');ax.text(870,3.55,'均值及区间',fontsize=10);ax.grid(axis='x',alpha=.15);fig.tight_layout();fig.savefig(R/'figures/bootstrap-primary.png');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(9,3.6))
for ax,k in zip(axs,['q3','q4_3']):
 st=result[k];vals=np.array(st['component_delta_yuan'])/10000;start=st['baseline_cost']/10000;end=st['main_cost']/10000
 ax.bar(0,start,color='#92cdd0',width=.65);running=start
 for j,v in enumerate(vals):
  ax.bar(j+1,abs(v),bottom=min(running,running+v),width=.65,color='#e88885' if v>0 else '#42afb2');ax.plot([j+.34,j+.66],[running,running],c='#999',lw=.8)
  ax.text(j+1,running+v+(1 if v>=0 else -1),f'{v:+.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=9);running+=v
 ax.bar(5,end,color='#369d9f',width=.65);ax.plot([4.34,4.66],[end,end],c='#999',lw=.8)
 ax.text(0,start+1,f'{start:.2f}',ha='center',fontsize=9);ax.text(5,end+1,f'{end:.2f}',ha='center',fontsize=9)
 ax.set_ylim(min(start,end,np.min(start+np.cumsum(vals)))-12,max(start,end,np.max(start+np.cumsum(vals)))+13);ax.set_xticks(range(6),['跨日\n贪心','原合同','增购','退购\n净额','紧急电','主策略']);ax.set_ylabel('费用 / 万元');ax.set_title(labels[KS.index(k)]+f'：净节省 {st["saving"]/10000:.2f} 万元');ax.grid(axis='y',alpha=.15)
fig.tight_layout();fig.savefig(R/'figures/decomposition-primary.png');plt.close(fig)
print(json.dumps({k:{x:result[k][x] for x in ['saving','mean','positive_days','negative_days','positive_months','bootstrap','component_delta_yuan']} for k in KS},ensure_ascii=False,indent=2))
# The horizon increment has its own baseline and seed; never use primary CIs here.
nxt=json.loads((R/'review/restoration-control-diagnostics.json').read_text())
dlt=np.array(nxt['annual']['q2']['runs']['midnight']['daily_cost_yuan'])-np.array(nxt['annual']['q2']['runs']['fixed72']['daily_cost_yuan'])
diag={'saving':float(dlt.sum()),'mean':float(dlt.mean()),'positive_days':int((dlt>1e-6).sum()),'negative_days':int((dlt< -1e-6).sum()),'zero_days':int((abs(dlt)<=1e-6).sum()),'bootstrap':{},'seed':20260912,'replicates':10000}
for block in [3,7,14]:
 rng=np.random.default_rng(20260912);starts=rng.integers(0,335-block,size=(10000,int(np.ceil(334/block))));ids=(starts[:,:,None]+np.arange(block)).reshape(10000,-1)[:,:334]
 diag['bootstrap'][str(block)]=np.quantile(dlt[ids].mean(1),[.025,.975]).tolist()
(R/'revision/restore/q2-horizon-increment.json').write_text(json.dumps(diag,indent=2)+'\n')
