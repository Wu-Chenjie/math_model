"""Independently reconcile continuous inventory and plot full-year physical states."""
from pathlib import Path
import hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
KINDS=['q2','q3','q4_2','q4_3'];LABELS=['问题二｜固定价日前','问题三｜固定价日内','问题四｜变动价日前','问题四｜变动价日内']
font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
plt.rcParams.update({'font.family':'Heiti TC','axes.unicode_minus':False,'font.size':16,'axes.labelsize':16,'xtick.labelsize':16,'ytick.labelsize':16,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':200})
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(a,net):
 e=a['state'];res={'balance_max_abs_kwh':float(abs(a['r']+a['emergency']+a['d']-a['c']-a['spill']-net).max()),'state_recurrence_max_abs_kwh':float(abs(np.diff(e,axis=1)-.9*a['c']+a['d']/.9).max()),'midnight_jump_max_abs_kwh':float(abs(e[1:,0]-e[:-1,-1]).max()),'state_min_kwh':float(e.min()),'state_max_kwh':float(e.max()),'power_max_kw':float(6*max(a['c'].max(),a['d'].max())),'simultaneous_charge_discharge_max_kwh':float(np.minimum(a['c'],a['d']).max()),'negative_energy_violation_kwh':float(max(0,-min(a[k].min() for k in ['q','r','c','d','emergency','spill'])))}
 assert max(res[k] for k in ['balance_max_abs_kwh','state_recurrence_max_abs_kwh','midnight_jump_max_abs_kwh','simultaneous_charge_discharge_max_kwh','negative_energy_violation_kwh'])<1e-5
 assert res['state_min_kwh']>=1200-1e-5 and res['state_max_kwh']<=10800+1e-5 and res['power_max_kw']<=5000+1e-5
 return res

def main():
 jp=ROOT/'revision/prediction-control/january-causal-greedy.npz';jan=dict(np.load(jp));dp=ROOT/'artifacts/data.npz';data=dict(np.load(dp));net=(data['load']-data['pv'])/6
 assert jan['state'].shape==(31,145) and abs(jan['state'][-1,-1]-6000)<1e-6
 dates=np.arange(np.datetime64('2025-01-01'),np.datetime64('2026-01-01'));states=[];report={'schema_version':1,'evidence_role':'Show physical continuity across midnight and seasonal use of the same bounded battery; this is not an additional cost-saving experiment.','initialization':'January is a shared causal-greedy initialization, excluded from the formal February–December 334-day bill.','definitions':{'heatmap':'Each cell represents a ten-minute interval (start,end] and displays its end inventory, rather than a point at its pixel center; kWh arrays and MWh axes.','envelope':'Daily minimum/maximum across 145 boundary states shown over the entire day as a post-step band; line connects 366 midnight inventories including 2026-01-01 00:00 true terminal.','boundary_hits':'Formal-period end states only, abs(E-bound)<=1e-6 kWh; count/48096 is sampled-endpoint frequency, not continuous time at a bound.','daily_range':'max minus min over 145 boundary states in each formal day.','midnight_change':'E[d,144]-E[d,0], signed daily change between midnight inventories.','formal_days':334,'formal_end_samples':48096},'source_hashes':{str(jp.relative_to(ROOT)):digest(jp),str(dp.relative_to(ROOT)):digest(dp)},'january_validation':check(jan,net[:31]),'models':{}}
 for k in KINDS:
  p=ROOT/f'revision/base-artifacts/{k}.npz';a=dict(np.load(p));assert a['state'].shape==(334,145) and np.array_equal(a['days'],np.arange(31,365));assert abs(a['state'][0,0]-6000)<1e-6
  assert abs(jan['state'][0,0]-6000)<1e-6 and abs(a['state'][-1,-1]-6000)<1e-6
  all_a={f:np.concatenate([jan[f],a[f]]) for f in jan};e=all_a['state'];states.append(e);validation=check(all_a,net);formal=a['state'];ends=formal[:,1:];lo=int((abs(ends-1200)<=1e-6).sum());hi=int((abs(ends-10800)<=1e-6).sum());ranges=np.ptp(formal,axis=1);change=formal[:,-1]-formal[:,0]
  report['source_hashes'][str(p.relative_to(ROOT))]=digest(p)
  report['models'][k]={'full_year_validation':validation,'january_to_february_jump_kwh':float(a['state'][0,0]-jan['state'][-1,-1]),'year_initial_kwh':float(e[0,0]),'year_final_kwh':float(e[-1,-1]),'formal_lower_endpoint_hits':lo,'formal_upper_endpoint_hits':hi,'formal_lower_endpoint_fraction':lo/48096,'formal_upper_endpoint_fraction':hi/48096,'formal_daily_range_mean_kwh':float(ranges.mean()),'formal_daily_range_median_kwh':float(np.median(ranges)),'formal_daily_range_max_kwh':float(ranges.max()),'formal_midnight_change_mean_abs_kwh':float(abs(change).mean()),'formal_midnight_change_max_abs_kwh':float(abs(change).max()),'formal_midnight_change_sum_kwh':float(change.sum())}
 states=np.array(states);midnight_dates=np.arange(np.datetime64('2025-01-01'),np.datetime64('2026-01-02'));midnight_state=np.concatenate([states[:,:,0],states[:,-1,-1,None]],axis=1)
 assert midnight_state.shape==(4,366) and np.allclose(midnight_state[:,[0,31,365]],6000,atol=1e-6,rtol=0)
 report['jan1_feb1_true_end_6000_passed']=True
 np.savez_compressed(OUT/'annual-inventory.npz',dates=dates,kinds=np.array(KINDS),state_kwh=states,end_state_kwh=states[:,:,1:],daily_min_kwh=states.min(2),daily_max_kwh=states.max(2),midnight_start_kwh=states[:,:,0],midnight_change_kwh=states[:,:,-1]-states[:,:,0],formal_mask=np.arange(365)>=31,midnight_dates=midnight_dates,midnight_state_kwh=midnight_state)
 (OUT/'annual-inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 x0=mdates.date2num(dates[0]);x1=mdates.date2num(np.datetime64('2026-01-01'));feb=mdates.date2num(np.datetime64('2025-02-01'))
 fig,axes=plt.subplots(4,1,figsize=(12.2,9.2),sharex=True,layout='constrained')
 for i,ax in enumerate(axes):
  im=ax.imshow(states[i,:,1:].T/1000,origin='lower',aspect='auto',extent=[x0,x1,0,24],vmin=1.2,vmax=10.8,cmap='viridis',interpolation='nearest',rasterized=True)
  ax.axvline(feb,color='white',lw=1.6,ls='--');ax.set_yticks([0,6,12,18,24]);ax.set_ylabel('时刻 / h');ax.set_title(LABELS[i],loc='left',fontsize=17);ax.text(x0+2,1,'共同初始化',color='white',fontsize=14,bbox={'facecolor':'#333333','alpha':.5,'edgecolor':'none','pad':2});ax.xaxis.set_major_locator(mdates.MonthLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%m月'))
 axes[-1].set_xticks([mdates.date2num(np.datetime64(f'2025-{m:02d}-01')) for m in range(1,13)], [f'{m}月' for m in range(1,13)])
 axes[-1].set_xlabel('2025年日期；每格为十分钟区间的段末库存')
 cb=fig.colorbar(im,ax=axes,shrink=.85,pad=.012);cb.set_label('每个十分钟段末库存 / MWh');cb.set_ticks([1.2,3.6,6,8.4,10.8])
 fig.suptitle('全年段末库存：午夜连续传递，容量约束逐段保持\n1月为共同初始化，不计入334日比较账单',fontsize=20)
 fig.savefig(ROOT/'figures/annual-inventory-heatmap.png');plt.close(fig)
 fig,axes=plt.subplots(4,1,figsize=(12.2,9.2),sharex=True,layout='constrained')
 for i,ax in enumerate(axes):
  ax.axvspan(dates[0],np.datetime64('2025-02-01'),facecolor='#e8e8e8',alpha=.85,label='共同初始化（1月）')
  ax.fill_between(midnight_dates,np.r_[states[i].min(1),states[i,-1].min()]/1000,np.r_[states[i].max(1),states[i,-1].max()]/1000,step='post',color='#36aaa6',alpha=.3,label='日内最小—最大库存')
  ax.plot(midnight_dates,midnight_state[i]/1000,color='#287d79',lw=.75,marker='.',ms=2,label='每日00:00库存（按日连接）')
  ax.scatter(midnight_dates[-1],6,color='#cb655d',s=25,zorder=6,clip_on=False)
  ax.annotate('年末6.0',(mdates.date2num(midnight_dates[-1]),6),xytext=(-8,10),textcoords='offset points',ha='right',fontsize=14,color='#a3443e',bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1})
  ax.axhline(1.2,color='#777777',ls=':',lw=.7);ax.axhline(10.8,color='#777777',ls=':',lw=.7);ax.axvline(np.datetime64('2025-02-01'),color='#777777',ls='--',lw=.9)
  ax.set_ylim(.8,11.2);ax.set_yticks([1.2,6,10.8]);ax.set_ylabel('库存 / MWh');ax.set_title(LABELS[i],loc='left',fontsize=17);ax.xaxis.set_major_locator(mdates.MonthLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%m月'));ax.set_xlim(dates[0],np.datetime64('2026-01-01'))
 axes[-1].set_xticks([mdates.date2num(np.datetime64(f'2025-{m:02d}-01')) for m in range(1,13)], [f'{m}月' for m in range(1,13)])
 handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=3,fontsize=14,frameon=False);axes[-1].set_xlabel('2025年日期；含真实年末的366个午夜状态')
 fig.suptitle('日内调节幅度与午夜继承库存\n阶梯色带汇总每日145个边界状态，1月初始化不计入正式比较账单',fontsize=20)
 fig.savefig(ROOT/'figures/annual-inventory-envelope.png');plt.close(fig)
 print(json.dumps({k:{f:v for f,v in z.items() if not isinstance(v,dict)} for k,z in report['models'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
