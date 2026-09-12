from pathlib import Path
import json,csv,hashlib,datetime
import numpy as np
from openpyxl import load_workbook
R=Path(__file__).resolve().parents[2]/'C题_论文修订';O=Path(__file__).resolve().parent
out={'source':'C题_论文修订','main_path':'revision/base-artifacts/q*.npz','cases':{}};strong={'source':'same 334-day fixed6000-end main vs fixed6000-end cross-day greedy','tolerance_yuan':1e-6,'blocks':[3,7,14],'replicates':10000,'seed_each_block':20260911,'cases':{}}
def bill(a):return np.sum(a['price']*(a['r']+.5*abs(a['r']-a['q'])+5*a['emergency']),axis=1)
data=dict(np.load(R/'artifacts/data.npz'))
for k,f in [('q2','result2'),('q3','result3'),('q4_2','result4-2'),('q4_3','result4-3')]:
 p=R/f'revision/base-artifacts/{k}.npz';a=dict(np.load(p));assert a['q'].shape==(334,144) and a['state'][0,0]==a['state'][-1,-1]==6000
 bal=a['r']+a['emergency']+a['d']-a['c']-a['spill']-(data['load'][a['days']]-data['pv'][a['days']])/6
 rec=np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9;assert max(abs(bal).max(),abs(rec).max())<1e-5
 rows=list(csv.DictReader(open(R/f'计算结果/{k}_逐时完整策略.csv',encoding='utf-8-sig')));assert len(rows)==48096
 csv_error={}
 for col,field in [('计划购电_kWh','q'),('最终合同购电_kWh','r'),('充电_kWh','c'),('放电_kWh','d'),('紧急购电_kWh','emergency'),('弃电_kWh','spill'),('电价_元每kWh','price')]:
  err=float(np.max(abs(np.array([float(row[col]) for row in rows])-a[field].ravel())));assert err<1e-8;csv_error[field]=err
 for col,vals in [('时段初SOC_kWh',a['state'][:,:-1]),('时段末SOC_kWh',a['state'][:,1:])]:assert np.max(abs(np.array([float(row[col]) for row in rows])-vals.ravel()))<1e-8
 cost=bill(a);w=load_workbook(R/f'计算结果/{f}.xlsx',read_only=True,data_only=True);fees=list(w['费用汇总'].values);daily=[row for row in fees if isinstance(row[0],datetime.datetime)];assert len(daily)==334
 daily_error=float(abs(np.array([row[5] for row in daily])-cost).max());total=next(row for row in fees if row[0]=='合计')[5];assert daily_error<1e-6 and abs(total-cost.sum())<1e-6
 bat=[row for row in w['充放电量'].values if len(row)>3 and isinstance(row[1],str) and '-' in row[1] and isinstance(row[2],(float,int))];assert len(bat)==2004
 baterr=max(float(abs(np.array([row[2] for row in bat])-a['c'].reshape(-1,24).sum(1)).max()),float(abs(np.array([row[3] for row in bat])-a['d'].reshape(-1,24).sum(1)).max()));assert baterr<1e-7
 text=(R/f'tables/specified-{k}.tex').read_text();datechecks=[]
 for date in ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']:
  i=list(a['dates'].astype(str)).index(date);chunk=text[text.index(date):];end=chunk.find('\\subsubsection*',20);chunk=chunk if end<0 else chunk[:end]
  for t in [60,72,84,96,108,120]:assert f"{a['r'][i,t]:,.2f}" in chunk,(k,date,t)
  for v in np.r_[a['c'][i].reshape(6,24).sum(1),a['d'][i].reshape(6,24).sum(1),a['state'][i,[0,-1]],cost[i]]:assert f'{v:,.2f}' in chunk,(k,date,v)
  datechecks.append(date)
 out['cases'][k]={'cost':float(cost.sum()),'days':334,'initial':6000,'final':6000,'csv_fields_max_error':csv_error,'xlsx_daily_error':daily_error,'xlsx_total_error':float(abs(total-cost.sum())),'xlsx_battery_error':baterr,'specified_dates_checked':datechecks,'main_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 b=dict(np.load(R/f'revision/results/{k}_cross_baseline_fixed.npz'));assert np.array_equal(a['days'],b['days']) and b['state'][0,0]==b['state'][-1,-1]==6000
 delta=bill(b)-cost;monthly={m:float(delta[np.array([str(d)[:7] for d in a['dates']])==m].sum()) for m in sorted(set(str(d)[:7] for d in a['dates']))};z={'baseline_total':float(bill(b).sum()),'main_total':float(cost.sum()),'saving':float(delta.sum()),'mean_saving':float(delta.mean()),'positive_days':int((delta>1e-6).sum()),'negative_days':int((delta< -1e-6).sum()),'ties':int((abs(delta)<=1e-6).sum()),'monthly_yuan':monthly,'positive_months':sum(v>0 for v in monthly.values()),'bootstrap':{},'daily_delta':delta.tolist()}
 for length in [3,7,14]:
  rng=np.random.default_rng(20260911);starts=rng.integers(0,335-length,(10000,(334+length-1)//length));ix=(starts[:,:,None]+np.arange(length)).reshape(10000,-1)[:,:334];means=delta[ix].mean(1);ci=np.quantile(means,[.025,.975]);z['bootstrap'][str(length)]={'mean_ci95_yuan':ci.tolist(),'total_ci95_yuan':(ci*334).tolist()}
 previous=json.load(open(R/f'revision/results/{k}_strong_baseline.json'));assert abs(z['saving']-previous['saving'])<1e-6 and np.max(abs(np.array(z['bootstrap']['7']['total_ci95_yuan'])-previous['saving_95ci']))<1e-6
 strong['cases'][k]=z
out['passed']=True
(O/'restoration-evidence-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(O/'strong-baseline-three-blocks.json').write_text(json.dumps(strong,ensure_ascii=False,indent=2));print(json.dumps({k:{x:v[x] for x in ['saving','positive_days','negative_days','positive_months','bootstrap']} for k,v in strong['cases'].items()},ensure_ascii=False,indent=2))
