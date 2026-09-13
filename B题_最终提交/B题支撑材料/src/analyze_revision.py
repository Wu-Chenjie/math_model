import csv,json,math,statistics as st
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def rows(name):
 p=R/'results'/name
 return list(csv.DictReader(p.open()))
def paired(a,b,q):
 a={int(x['seed']):x for x in a if int(x['problem'])==q};b={int(x['seed']):x for x in b if int(x['problem'])==q}
 assert set(a)==set(b) and a
 for k in a:
  assert a[k]['n']==b[k]['n']==a[k]['cleared']==b[k]['cleared']
 x=[float(a[k]['time_s']) for k in sorted(a)];y=[float(b[k]['time_s']) for k in sorted(a)];d=[i-j for i,j in zip(x,y)];n=len(d);mean=st.mean(d);se=st.stdev(d)/math.sqrt(n) if n>1 else 0
 from scipy.stats import t
 critical=float(t.ppf(.975,n-1))
 out={'n':n,'baseline_mean_s':st.mean(x),'candidate_mean_s':st.mean(y),'saving_s':mean,'saving_pct':100*mean/st.mean(x),'ci95_s':[mean-critical*se,mean+critical*se],'faster':sum(v>1e-4 for v in d),'slower':sum(v< -1e-4 for v in d),'ties':sum(abs(v)<=1e-4 for v in d),'max_regression_s':-min(d),'max_saving_s':max(d),'all_cleared':True,'mean_source_s':st.mean(float(i['avg_s']) for i in b.values()),'cpu_mean_s':st.mean(float(i['runtime_s']) for i in b.values()),'cpu_max_s':max(float(i['runtime_s']) for i in b.values()),'baseline_source_s':st.mean(float(i['avg_s']) for i in a.values())}
 out['decomposition_s']={k:st.mean((float(a[s][field])-float(b[s][field]))*factor for s in a) for k,field,factor in [('move','move_m',.2),('measure','measures',5),('switch','switches',1),('failed_clear','miss',3)]}
 out['candidate_counts']={field:st.mean(float(i.get(field,0)) for i in b.values()) for field in ['move_m','measures','switches','miss','fallbacks','residual_replaced','residual_retired','rollout_calls','rollout_replaced']}
 assert abs(sum(out['decomposition_s'].values())-mean)<.001
 out['pairs']=[{'seed':s,'baseline_s':float(a[s]['time_s']),'candidate_s':float(b[s]['time_s']),'saving_s':float(a[s]['time_s'])-float(b[s]['time_s'])} for s in sorted(a)]
 return out
if __name__=='__main__':
 development={};base=rows('dev56.csv')
 for method,name in [(79,'dev79.csv'),(80,'dev80.csv'),(81,'dev81b.csv'),(82,'dev82.csv'),(83,'dev83.csv'),(84,'dev84.csv'),(85,'dev85.csv'),(86,'dev86.csv')]:
  development[str(method)]={str(q):paired(base,rows(name),q) for q in [3,4]}
 out={'development':development,'iid':{},'stress':{}}
 for q in [3,4]:
  out['iid'][str(q)]={'vs56':paired(rows('iid56.csv'),rows('iid84.csv'),q),'vs78':paired(rows('iid78.csv'),rows('iid84.csv'),q)}
 for group in range(1,6):out['stress'][str(group)]={str(q):paired(rows(f'stress{group}_56.csv'),rows(f'stress{group}_84.csv'),q) for q in [3,4]}
 for q in ['3','4']:
  assert out['iid'][q]['vs56']['n']==200
  for group in out['stress']:assert out['stress'][group][q]['n']==40
 (R/'artifacts/summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({q:{k:{f:v for f,v in d.items() if f not in ['pairs']} for k,d in m.items()} for q,m in out['iid'].items()},ensure_ascii=False,indent=2))
