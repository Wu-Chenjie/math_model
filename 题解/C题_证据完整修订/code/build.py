from pathlib import Path
import shutil,json,numpy as np,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parents[1]; W=R.parents[1]; S=W/'题解/C题_跨日随机控制'; T=W/'论文/最新双篇/01_跨日随机控制'
for d in ['tables','figures','evidence','src','review','artifacts','paper']: (R/d).mkdir(exist_ok=True)
for p in (T/'tables').glob('*.tex'): shutil.copy2(p,R/'tables'/p.name)
shutil.copy2(T/'figures/mechanism.pdf',R/'figures/mechanism.pdf')
for p in (S/'src').glob('*'):
 if p.is_file(): shutil.copy2(p,R/'src'/p.name)
for p in (S/'review').glob('*.py'): shutil.copy2(p,R/'review'/p.name)
for f in ['summary.json','handoff-tables.json','result-registry.json','data-audit.json','q1.json','q2.json','q3.json','q4_2.json','q4_3.json','global-terminal.json','forecast-selection.json','warmup.json']:
 if (S/'artifacts'/f).exists(): shutil.copy2(S/'artifacts'/f,R/'artifacts'/f)
shutil.copy2(S/'requirements-model.txt',R/'requirements-model.txt')
font='/System/Library/Fonts/STHeiti Medium.ttc'; font_manager.fontManager.addfont(font)
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
C=['#269c9b','#de795d','#7484b5','#b398bd']; derived={}; checks={}
def save(fig,n):
 fig.savefig(R/f'figures/{n}.pdf',bbox_inches='tight');plt.close(fig)
# physical region
fig,ax=plt.subplots(figsize=(6.8,3.4)); x=np.linspace(1.2,10.8,400);lo=np.maximum(1.2,x-5/6/.9);hi=np.minimum(10.8,x+.9*5/6)
ax.fill_between(x,lo,hi,color=C[0],alpha=.22);ax.plot(x,lo,color=C[0]);ax.plot(x,hi,color=C[0]);ax.plot(x,x,'--',color='gray',lw=1)
ax.set(xlabel='时段初库存 E / MWh',ylabel='下一库存 x / MWh',xlim=(1,11),ylim=(1,11));ax.text(2.0,7.5,'容量边界与功率边界共同限定\n每10分钟可达库存',linespacing=1.7);save(fig,'feasible')
# Q1
z=np.load(S/'artifacts/q1.npz');data=np.load(S/'artifacts/data.npz');print('data keys',data.files)
fig,ax=plt.subplots(figsize=(7,3));ax.plot(np.arange(145)/6,z['state']/1000,color=C[0],lw=1.8);ax.axhline(6,color='gray',ls='--',lw=.8);ax.set(xlabel='时刻 / h',ylabel='库存 / MWh',xlim=(0,24),xticks=range(0,25,4));save(fig,'q1state')
# savings composition and uncertainty
boots=[]
fig,axes=plt.subplots(1,2,figsize=(9,3.3));rng=np.random.default_rng(20260911)
for i,k in enumerate(['q2','q3','q4_2','q4_3']):
 a=json.loads((S/f'artifacts/{k}.json').read_text());b=json.loads((S/f'artifacts/annual/{k}_closed_baseline.json').read_text());az=np.load(S/f'artifacts/{k}.npz')
 dates=[v['date'] for v in a['daily']];assert dates==[v['date'] for v in b['daily']]
 diff=np.array([v['total_cost'] for v in b['daily']])-np.array([v['total_cost'] for v in a['daily']]);N=len(diff)
 # moving-block bootstrap, non-circular, blocks of 7 then trim to 334
 starts=rng.integers(0,N-7+1,size=(10000,int(np.ceil(N/7))));idx=(starts[:,:,None]+np.arange(7)).reshape(10000,-1)[:,:N]
 reps=diff[idx].mean(1);ci=np.quantile(reps,[.025,.975]);boots.append({'setting':k,'mean':float(diff.mean()),'low':float(ci[0]),'high':float(ci[1]),'days':N})
 total=float(np.sum(az['price']*(az['q']+1.5*np.maximum(az['r']-az['q'],0)-.5*np.maximum(az['q']-az['r'],0)+5*az['emergency'])))
 checks[k]={'bill_recompute_error':abs(total-a['totals']['total_cost']),'stock_recurrence':float(abs(np.diff(az['state'],axis=1)-.9*az['c']+az['d']/.9).max()),'midnight':float(abs(az['state'][1:,0]-az['state'][:-1,-1]).max())}
 axes[0].barh(i,diff.sum()/10000,color=C[i]);axes[0].text(diff.sum()/10000+.3,i,f'{diff.sum()/10000:.2f}',va='center')
 axes[1].errorbar(diff.mean(),i,xerr=[[diff.mean()-ci[0]],[ci[1]-diff.mean()]],fmt='o',color=C[i],capsize=4)
axes[0].set(xlabel='334日费用节省 / 万元',yticks=range(4),yticklabels=['问题2','问题3','问题4-2','问题4-3'],xlim=(0,49));axes[1].set(xlabel='日均节省及95%区间 / 元',yticks=range(4),yticklabels=[]);axes[1].axvline(0,color='gray',ls='--');fig.tight_layout();save(fig,'savings')
derived['bootstrap']={'seed':20260911,'replicates':10000,'method':'non-circular moving blocks, length 7, sampled to 334 days','comparison':'free terminal main vs daily closed baseline','results':boots}
# actual q3 waterfall compared to daily closed baseline
main=json.loads((S/'artifacts/q3.json').read_text())['totals'];base=json.loads((S/'artifacts/annual/q3_closed_baseline.json').read_text())['totals'];fields=['planned_cost','increase_cost','reduction_net_cost','emergency_cost'];deltas=[main[f]-base[f] for f in fields]
fig,ax=plt.subplots(figsize=(7.2,3.3));cur=base['total_cost']/10000; ax.bar(0,cur,bottom=0,color=C[2],width=.55);ax.text(0,cur+1,f'{cur:.2f}',ha='center',fontsize=9)
for i,v in enumerate(deltas,1):
 v/=10000;ax.bar(i,abs(v),bottom=min(cur,cur+v),color=C[0] if v<0 else C[1],width=.55);ax.plot([i-1+.275,i-.275],[cur,cur],color='gray',lw=.8);ax.text(i,max(cur,cur+v)+1,f'{v:+.2f}',ha='center',fontsize=9);cur+=v
ax.bar(5,cur,color=C[2],width=.55);ax.text(5,cur+1,f'{cur:.2f}',ha='center',fontsize=9);ax.set(xticks=range(6),xticklabels=['闭合基线','原计划费','增购费','退购净费','紧急费','跨日主方案'],ylabel='费用 / 万元',ylim=(min(base['total_cost']/10000,cur)-70,max(base['total_cost']/10000,cur)+20));save(fig,'waterfall');derived['q3_cost_deltas']=dict(zip(fields,deltas))
(R/'artifacts/paper-derived.json').write_text(json.dumps(derived,ensure_ascii=False,indent=2));(R/'evidence/trajectory-check.json').write_text(json.dumps(checks,indent=2))
# mirror published registry and add computed results
reg=json.loads((R/'artifacts/result-registry.json').read_text());reg['scope']='Paper results inherited from executed cross-day project, plus reproduced descriptive bootstrap.'
reg['results'].append({'id':'paper.bootstrap','source_artifact':'artifacts/paper-derived.json','source_path':'/bootstrap','value':derived['bootstrap'],'status':'verified'})
(R/'artifacts/result-registry.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
(R/'paper/result-claims.json').write_text(json.dumps({'claims':[{'result_id':v['id'],'value':v['value']} for v in reg['results']]},ensure_ascii=False,indent=2))
tex=(T/'main.tex').read_text(); (R/'main.tex').write_text(tex)
print('bootstrap',boots);print('checks',checks)
