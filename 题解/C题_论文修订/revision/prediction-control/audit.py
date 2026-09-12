"""Read-only frozen-model audits; all generated evidence stays in revision/."""
from pathlib import Path
import sys,json,hashlib,time,argparse,csv
import numpy as np
HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1].parent/'C题_跨日随机控制'
sys.path[:0]=[str(BASE/'src'),str(BASE/'vendor')]
from forecasting import base_forecast,forecast_as_of,FAMILIES
from dispatch import solve,settlement
from control import execute

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,obj):(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def setup():return dict(np.load(BASE/'artifacts/data.npz')),json.loads((BASE/'artifacts/forecast-selection.json').read_text())
def score(y,p):
 e=np.asarray(p)-np.asarray(y)
 return {'n':int(e.size),'MAE':float(abs(e).mean()),'RMSE':float(np.sqrt(np.mean(e*e))),'bias':float(e.mean())}
def predict():
 data,selection=setup();out={'selection':selection,'units':{'load':'kW','pv':'kW','price':'yuan/kWh','net':'kW'},'development_note':'Retrospective January15-31 selection-window scores, not a prospectively frozen January deployment. February-December predictor is frozen before February1.','base_forecasts':[],'operational_forecasts':[]}
 for scope,days in [('development',range(14,31)),('formal',range(31,365))]:
  for key in ['load','pv','price']:
   actual=data[key][list(days)]
   for fam in FAMILIES:
    pred=np.array([base_forecast(data,key,d*144,np.arange(d*144,(d+1)*144),fam) for d in days])
    out['base_forecasts'].append({'scope':scope,'target':key,'family':fam,'selected':fam==selection[key]['selected'],**score(actual,pred)})
  # Every target is counted exactly once: release forecast for its next6 hours.
  for official in [False,True]:
   errors={k:[[],[]] for k in ['load','pv','price','net']}
   for d in days:
    for t in [0,36,72,108]:
     now=d*144+t;targets=np.arange(now,now+36)
     p=forecast_as_of(data,selection,now,targets,official,True)
     for key in errors:
      y=(data['load'].ravel()[targets]-data['pv'].ravel()[targets]) if key=='net' else data[key].ravel()[targets]
      pred=p[key]*6 if key=='net' else p[key]
      errors[key][0].extend(y);errors[key][1].extend(pred)
   for k,(y,p) in errors.items():out['operational_forecasts'].append({'scope':scope,'official_pv':official,'target':k,'horizon':'nonoverlapping next6h at0/6/12/18h','includes_observed_error_correction':True,**score(y,p)})
 # Deliberate perturbation of future actuals and unissued forecasts at4 release nodes.
 leaks=[]
 for t in [0,36,72,108]:
  now=170*144+t;targets=np.arange(now,now+144)
  a=forecast_as_of(data,selection,now,targets,True,True)
  changed={k:v.copy() for k,v in data.items()}
  for k in ['load','pv','price']:changed[k].ravel()[now:]+=12345
  changed['forecast'].reshape(-1,24)[now//36+1:]+=12345
  b=forecast_as_of(changed,selection,now,targets,True,True)
  gap=max(float(abs(a[k]-b[k]).max()) for k in ['net','load','pv','price']);assert gap==0
  leaks.append({'asof':now,'max_forecast_change':gap})
 out['future_information_perturbation']=leaks
 out['input_sha256']={str(BASE/f):sha(BASE/f) for f in ['artifacts/data.npz','artifacts/forecast-selection.json','src/forecasting.py']}
 dump('forecast-errors.json',out)
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 from matplotlib import font_manager
 font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
 plt.rcParams.update({'font.family':'Heiti TC','axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
 fig,axes=plt.subplots(3,2,figsize=(11,8),sharex=True)
 records=[]
 names={'load':'负荷 / kW','pv':'光伏 / kW','net':'净需求 / kW'}
 for col,date in enumerate(['2025-06-21','2025-09-23']):
  d=int(np.flatnonzero(data['dates']==date)[0]);history={k:[] for k in ['load','pv','net']};official={k:[] for k in history}
  for t in [0,36,72,108]:
   targets=np.arange(d*144+t,d*144+t+36)
   for flag,target in [(False,history),(True,official)]:
    pred=forecast_as_of(data,selection,d*144+t,targets,flag,True)
    for key in target:target[key].extend(pred[key]*6 if key=='net' else pred[key])
  for row,key in enumerate(history):
   y=data['load'][d]-data['pv'][d] if key=='net' else data[key][d]
   ax=axes[row,col];h=(np.arange(144)+.5)/6
   ax.plot(h,y,label='实测',color='black',lw=1.4)
   ax.plot(h,history[key],label='历史预测+在线误差修正',color='#4771b2',lw=1)
   if key!='load':ax.plot(h,official[key],label='官方光伏+历史负荷',color='#d66c32',lw=1)
   for edge in [6,12,18]:ax.axvline(edge,color='0.8',lw=.5,ls='--')
   ax.set_ylabel(names[key]);ax.grid(alpha=.18);ax.set_title(date if row==0 else '');ax.set_xlim(0,24)
   if row==2:ax.set_xlabel('时刻 / h（十分钟均值）')
  for t in range(144):records.append({'date':date,'slot':t,**{k+'_actual_kw':float(data['load'][d,t]-data['pv'][d,t]) if k=='net' else float(data[k][d,t]) for k in history},**{k+'_history_kw':history[k][t] for k in history},**{k+'_official_kw':official[k][t] for k in history}})
 axes[1,0].legend(loc='upper left',fontsize=8);fig.tight_layout();fig.savefig(HERE/'forecast-vs-actual.pdf');fig.savefig(HERE/'forecast-vs-actual.png',dpi=180);plt.close(fig)
 with (HERE/'forecast-vs-actual.csv').open('w') as f:w=csv.DictWriter(f,records[0]);w.writeheader();w.writerows(records)
 # Pairs seen in paper: verify both full-precision and 2decimal outputs.
 dup=[]
 for kind in ['q3','q4_3']:
  p=BASE/f'artifacts/global-terminal/{kind}_markov_mpc.npz';a=dict(np.load(p))
  for date,slots in [('2025-06-21',[108,120]),('2025-09-23',[72,84])]:
   i=int(np.flatnonzero(a['dates']==date)[0]);values=[float(a['q'][i,t]) for t in slots]
   dup.append({'kind':kind,'date':date,'slots':slots,'original_contract_kwh':values,'exactly_equal':values[0]==values[1],'absolute_difference_kwh':abs(values[0]-values[1]),'two_decimal_equal':f'{values[0]:.2f}'==f'{values[1]:.2f}','source_sha256':sha(p)})
 dump('duplicate-contract-audit.json',{'status':'VALUES_VERIFIED','records':dup,'interpretation':'The requested values are executed original contracts q, read directly from full-precision NPZ. Equality alone cannot prove zero intercept or affine degeneracy; current-day q is an independent intercept for each slot, because release<=asof prevents a current-day gain term.'})
 print('prediction and duplicate audits complete',flush=True)

def warmup():
 data,_=setup();a={k:np.zeros((31,144)) for k in ['q','r','c','d','emergency','spill']};a['state']=np.zeros((31,145));E=6000.;daily=[]
 for day in range(31):
  net=(data['load'][day]-data['pv'][day])/6;a['state'][day,0]=E
  # Jan1 no completed history: inherited no-action emergency policy.
  if day:
   p=(data['load'][day-1]-data['pv'][day-1])/6
   plan=solve(p[None,:],data['day_price'][None,:],initial=6000.,terminal=6000.)
   a['q'][day]=plan['q'];a['r'][day]=plan['q']
  for t in range(144):
   if day==0:target=E
   else:
    bal=a['r'][day,t]-net[t];target=E+.9*max(bal,0)-max(-bal,0)/.9
   E,c,d,em,sp,pr=execute(E,target,a['r'][day,t],net[t],143-t,True,t,6000.)
   for k,v in [('c',c),('d',d),('emergency',em),('spill',sp)]:a[k][day,t]=v
   a['state'][day,t+1]=E
  daily.append({'date':str(data['dates'][day]),'fixed':settlement(a['q'][day],a['r'][day],a['emergency'][day],data['day_price']),'variable':settlement(a['q'][day],a['r'][day],a['emergency'][day],data['price'][day])})
 net=(data['load'][:31]-data['pv'][:31])/6
 check={'bus':float(abs(a['r']+a['emergency']+a['d']-a['c']-a['spill']-net).max()),'soc':float(abs(np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9).max()),'midnight':float(abs(a['state'][1:,0]-a['state'][:-1,-1]).max()),'closure':float(abs(a['state'][:,[0,-1]]-6000).max()),'minimum':float(a['state'].min()),'maximum':float(a['state'].max()),'power_kw':float(max(a['c'].max(),a['d'].max())*6),'simultaneous':float(np.minimum(a['c'],a['d']).max())}
 assert max(check[k] for k in ['bus','soc','midnight','closure','simultaneous'])<1e-6 and check['power_kw']<=5000+1e-6 and check['minimum']>=1200-1e-6 and check['maximum']<=10800+1e-6
 np.savez_compressed(HERE/'january-causal-greedy.npz',**a)
 dump('january-causal-greedy.json',{'status':'PASS','policy':'January1 no battery use/no contract because no prior day exists; January2-31 one previous complete day forecast, deterministic daily-closed LP contract and physically projected greedy battery. Same contract schedule in all tasks; daily given tariff used as fixed planning price. No January15-31 selector or future data used.','daily':daily,'cost_fixed':sum(x['fixed']['total_cost'] for x in daily),'cost_variable':sum(x['variable']['total_cost'] for x in daily),'validation':check,'formal_evaluation_unchanged':True,'february1_inventory':E,'input_sha256':sha(BASE/'artifacts/data.npz')})
 print('causal January warmup complete',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['predict','warmup','all']);args=p.parse_args()
 if args.mode in ['predict','all']:predict()
 if args.mode in ['warmup','all']:warmup()
