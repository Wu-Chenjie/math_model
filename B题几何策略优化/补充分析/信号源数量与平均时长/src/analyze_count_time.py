"""Fit only original IID data; verify the frozen model on new seed data."""
import csv,hashlib,json,math,sys,time
from pathlib import Path
import numpy as np
from scipy.stats import t,pearsonr,spearmanr
R=Path(__file__).resolve().parents[1];P=R.parents[1]
def read(p):return list(csv.DictReader(p.open()))
def col(a,k):return np.array([float(z[k]) for z in a])
def design(n,name):
 if name=='proportional':return n[:,None]
 if name=='affine':return np.column_stack([np.ones(len(n)),n])
 if name=='quadratic':return np.column_stack([np.ones(len(n)),n,n*n])
 return np.column_stack([np.ones(len(n)),n,n==16])
def fit(a,name):
 n=col(a,'n');y=col(a,'time_s');x=design(n,name);b=np.linalg.lstsq(x,y,rcond=None)[0];res=y-x@b;inv=np.linalg.inv(x.T@x);hat=np.sum((x@inv)*x,axis=1);w=res/(1-hat)
 cov=inv@((x*w[:,None]).T@(x*w[:,None]))@inv;crit=t.ppf(.975,len(n)-x.shape[1]);ci=np.stack([b-crit*np.sqrt(np.diag(cov)),b+crit*np.sqrt(np.diag(cov))],axis=1)
 return {'model':name,'n_cases':len(n),'coefficients':b.tolist(),'HC3_covariance':cov.tolist(),'HC3_t95_intervals':ci.tolist(),'total_R2':float(1-np.sum(res**2)/np.sum((y-y.mean())**2)),'avg_R2':float(1-np.sum((res/n)**2)/np.sum((y/n-(y/n).mean())**2)),'LOOCV_avg_RMSE_s':float(np.sqrt(np.mean((res/(1-hat)/n)**2))),'LOOCV_total_RMSE_s':float(np.sqrt(np.mean((res/(1-hat))**2)))}
def assess(f,a):
 n=col(a,'n');y=col(a,'time_s');x=design(n,f['model']);pred=x@np.array(f['coefficients']);e=y-pred
 return {'n_cases':len(n),'mean_avg_error_s':float(np.mean(e/n)),'avg_RMSE_s':float(np.sqrt(np.mean((e/n)**2))),'total_RMSE_s':float(np.sqrt(np.mean(e**2))),'avg_R2':float(1-np.sum((e/n)**2)/np.sum((y/n-(y/n).mean())**2)),'total_R2':float(1-np.sum(e**2)/np.sum((y-y.mean())**2))}
def groups(a):
 out=[]
 for n in range(10,17):
  g=[z for z in a if int(z['n'])==n];y=col(g,'avg_s');crit=t.ppf(.975,len(g)-1);margin=crit*y.std(ddof=1)/np.sqrt(len(g))
  out.append({'N':n,'cases':len(g),'total_mean_s':float(col(g,'time_s').mean()),'avg_mean_s':float(y.mean()),'avg_mean_t95_s':[float(y.mean()-margin),float(y.mean()+margin)],'avg_sd_s':float(y.std(ddof=1)),'discovery_sites_mean':float(col(g,'scans').mean()),'discovery_measure_mean':float(col(g,'discovery_measures').mean()),'directional_sources_mean':float(col(g,'directional_n').mean())})
 return out
begin=time.time();old=read(P/'results/iid78.csv');out={'method':78,'unit':'seconds; per-source average is total/N','training_role':'Post-hoc explanatory fit on original IID; not a new independent confirmation.','validation_role':'Fresh seeds frozen before run, never refitted.','Q':{}}
max_identity=0;matching=0
for q in [3,4]:
 a=read(R/'results'/f'training_replay_q{q}.csv');b=read(R/'results'/f'validation_q{q}.csv');reference={int(z['seed']):z for z in old if int(z['problem'])==q}
 assert len(a)==len(b)==200 and not {z['seed'] for z in a}&{z['seed'] for z in b}
 for z in a:
  for k in ['n','time_s','avg_s','move_m','measures','switches','miss']:assert abs(float(z[k])-float(reference[int(z['seed'])][k]))<.0001
  matching+=1
 for z in a+b:
  N=int(z['n']);m=int(z['scans']);assert int(z['discovery_measures'])==m*(20-N)+int(z['Jsum'])
  exact=float(z['move_m'])/5+6*(m*(20-N)+int(z['Jsum']))-int(z['discovery_same_channel_savings'])+5*int(z['local_measures'])+int(z['local_switches'])+3*int(z['miss'])+5*N
  max_identity=max(max_identity,abs(exact-float(z['time_s'])));assert max_identity<.001
  assert (m== (7 if q==3 else 21)) if N<16 else m<= (7 if q==3 else 21)
 models={name:fit(a,name) for name in ['proportional','affine','quadratic','affine_step16']}
 for name,f in models.items():f['fresh_validation']=assess(f,b)
 c=models['affine_step16'];predictions=[]
 x=design(col(a,'n'),'affine_step16')
 components={'walking':col(a,'move_m')/5,'discovery_scan':5*col(a,'discovery_measures')+col(a,'discovery_switches'),'known_sensing':5*col(a,'local_measures')+col(a,'local_switches'),'failed_clear':3*col(a,'miss'),'successful_clear':5*col(a,'n')}
 decomposition={k:np.linalg.lstsq(x,y,rcond=None)[0].tolist() for k,y in components.items()}
 assert np.max(np.abs(np.sum(list(decomposition.values()),axis=0)-np.array(c['coefficients'])))<.001
 # Independently sum per-row HC3 sandwich contributions.
 e=col(a,'time_s')-x@np.array(c['coefficients']);inv=np.linalg.inv(x.T@x);direct=np.zeros((3,3))
 for row,residual in zip(x,e):
  v=inv@row;h=float(row@v);direct+=np.outer(v,v)*(residual/(1-h))**2
 assert np.allclose(direct,c['HC3_covariance'],rtol=1e-10,atol=1e-10)
 c['accounting_coefficient_decomposition']=decomposition
 for n in range(10,17):
  g=np.array([1/n,1,(1/n if n==16 else 0)]);mu=float(g@np.array(c['coefficients']));se=math.sqrt(float(g@np.array(c['HC3_covariance'])@g));margin=t.ppf(.975,197)*se
  predictions.append({'N':n,'predicted_avg_s':mu,'conditional_mean_HC3_t95_s':[mu-margin,mu+margin]})
 corr={}
 for split,rows in [('training',a),('validation',b)]:
  n=col(rows,'n');y=col(rows,'time_s');corr[split]={'pearson_N_total':float(pearsonr(n,y).statistic),'pearson_N_avg':float(pearsonr(n,y/n).statistic),'spearman_N_avg':float(spearmanr(n,y/n).statistic)}
 out['Q'][str(q)]={'models':models,'selected':'affine_step16','training_groups':groups(a),'validation_groups':groups(b),'predictions':predictions,'correlations':corr}
out['checks']={'original_rows_matched':matching,'identity_checked_cases':800,'max_identity_residual_s':max_identity,'all_cleared_and_counter_checks':'C++ producer rejects any violation','validation_seed_disjoint':True};out['analysis_runtime_s']=time.time()-begin
(R/'artifacts/count_time_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({q:{'coefficients':d['models']['affine_step16']['coefficients'],'CI':d['models']['affine_step16']['HC3_t95_intervals'],'validation':d['models']['affine_step16']['fresh_validation'],'group_scans':[(z['N'],z['discovery_sites_mean']) for z in d['validation_groups']]} for q,d in out['Q'].items()},ensure_ascii=False,indent=2))
