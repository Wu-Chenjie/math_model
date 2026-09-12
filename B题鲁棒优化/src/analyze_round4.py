import csv,json
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from scipy.stats import t
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';G=ROOT/'figures';G.mkdir(exist_ok=True)
labels=['原21点','矩形Q2点','全域Q2点','发现16停扫','带界点代理','带界服务代理']
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'axes.titlesize':10.5,'legend.fontsize':9,'pdf.fonttype':42,'savefig.dpi':320})
def read(name):return list(csv.DictReader((R/name).open()))
def stat(a):
 a=np.array(a,dtype=float);n=len(a);mean=float(a.mean());h=float(t.ppf(.975,n-1)*a.std(ddof=1)/np.sqrt(n))if n>1 else 0
 return {'n':n,'mean':mean,'ci95':[mean-h,mean+h],'p95':float(np.quantile(a,.95)),'min':float(a.min()),'max':float(a.max())}
def values(rows,key):return [float(r[key])for r in rows]
rows=read('iid.csv');assert len(rows)==2400
out={'iid':{},'controlled':{},'cells':[],'development':{}}
for p in [3,4]:
 out['iid'][p]={};base=[r for r in rows if int(r['problem'])==p and r['method']=='0'];bt=np.array(values(base,'time_s'))
 for m in range(6):
  rr=[r for r in rows if int(r['problem'])==p and int(r['method'])==m]
  assert [int(r['seed'])for r in rr]==list(range(510001,510201))and all(r['n']==r['cleared']for r in rr)
  d=bt-np.array(values(rr,'time_s'));out['iid'][p][m]={'label':labels[m],**{k:stat(values(rr,k))for k in ['time_s','avg_s','move_m','measures','miss','runtime_s']},'saving_s':stat(d),'saving_percent':float(100*d.mean()/bt.mean()),'wins':int(sum(d>1e-6)),
   'plans':sum(int(r['plans'])for r in rr),'exact_plans':sum(int(r['exact_plans'])for r in rr),'nonlocal_plans':sum(int(r['nonlocal_plans'])for r in rr),'max_relative_gap':max(values(rr,'max_relative_gap')),'max_absolute_gap_m':max(values(rr,'max_route_gap_m')),
   'extra_movement_s':float((np.array(values(rr,'move_m'))-np.array(values(base,'move_m'))).mean()/5)}
factor=read('stratified.csv');assert len(factor)==6480;pairs=defaultdict(dict)
for r in factor:pairs[(int(r['problem']),int(r['case_id']))][int(r['method'])]=r
assert len(pairs)==3240 and all(set(v)=={0,5}for v in pairs.values())
for p in [3,4]:
 ps=[v for k,v in pairs.items()if k[0]==p];a=np.array([float(v[0]['time_s'])for v in ps]);b=np.array([float(v[5]['time_s'])for v in ps]);d=a-b
 out['controlled'][p]={'n':len(ps),'old_time':stat(a),'new_time':stat(b),'saving_s':stat(d),'saving_percent':float(100*d.mean()/a.mean()),'wins':int(sum(d>1e-6))}
 groups=defaultdict(list)
 for v in ps:rr=v[5];groups[(rr['n'],rr['nd'],rr['nb'],rr['geometry'])].append(v)
 for key,vs in groups.items():
  assert len(vs)==30;d=np.array([float(v[0]['time_s'])-float(v[5]['time_s'])for v in vs]);a=np.array([float(v[0]['time_s'])for v in vs]);out['cells'].append({'problem':p,'n':int(key[0]),'nd':int(key[1]),'nb':int(key[2]),'geometry':int(key[3]),'saving':stat(d),'saving_percent':float(100*d.mean()/a.mean())})
assert len(out['cells'])==108
out['negative_cells']=[c for c in out['cells']if c['saving']['mean']< -1e-6]
hardware=read('hardware.csv');assert len(hardware)==320
out['hardware']={'aware_total':sum(r['aware']=='1'for r in hardware),'aware_complete':sum(r['aware']=='1'and r['status']=='ok'and r['cleared']==r['total']for r in hardware),'nominal_reasons':dict(Counter(r['reason']for r in hardware if r['aware']=='0'))}
assert out['hardware']['aware_complete']==160
dev=read('development.csv')
for p in [3,4]:out['development'][p]={m:stat([float(r['time_s'])for r in dev if int(r['problem'])==p and int(r['method'])==m])['mean']for m in range(6)}
(R/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
def save(fig,name):
 fig.tight_layout()
 for ext in ['png','pdf','svg']:fig.savefig(G/(name+'.'+ext),bbox_inches='tight')
 plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(7.2,3.3))
for ax,p in zip(axes,[3,4]):
 ds=[out['iid'][p][m]['time_s']['mean']/60 for m in range(6)];ax.bar(range(6),ds,color=['#999999','#D55E00','#E69F00','#56B4E9','#0072B2','#009E73']);ax.set(xticks=range(6),xticklabels=['原方案','矩形点','全域点','停扫','点代理','服务代理'],ylabel='平均总虚拟时间 / 分钟',title=f'问题{p} 新IID n=200');ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.2)
save(fig,'图1_Q2在线与路径消融')
fig,ax=plt.subplots(figsize=(5.5,3.8));y=np.linspace(-14,14,300);boundary=np.sqrt(1800**2-y*y)-1800;line=1864*np.cos(np.pi/12)-1800
ax.plot(y,boundary,c='#222222',label='目标圆边界');ax.axhline(line,color='#0072B2',label='名义外环支持线');ax.axhline(line-.4,color='#D55E00',ls='--',label='向内扰动0.4米后');ax.fill_between(y,boundary,line-.4,color='#009E73',alpha=.15);ax.set(xlabel='局部切向坐标 / 米',ylabel='相对1800米的法向位置 / 米',title='外圆角平分方向的局部裕量示意');ax.legend();ax.grid(alpha=.2);save(fig,'图2_正方向裕量示意')
fig,ax=plt.subplots(figsize=(5.5,3.2));xs=np.arange(6);ys=[float(x['verified_slack_lower'])for x in json.loads((ROOT/'review/q4_area_arc_certificate.json').read_text())['intervals']];ax.bar(xs,ys,color='#0072B2');ax.set(xticks=xs,xticklabels=['1800–1900','1900–1950','1950–2000','2000–2025','2025–2050','2050–2800'],ylabel='缺额减1.38倍半角的认证余量',title='六个连续径向区间均有正余量');ax.tick_params(axis='x',labelsize=7.5,rotation=20);ax.grid(axis='y',alpha=.2);save(fig,'图3_测点数下界15')
print(json.dumps({'iid_final':{p:out['iid'][p][5]['saving_percent']for p in [3,4]},'controlled':out['controlled'],'negative_cells':len(out['negative_cells']),'hardware':out['hardware']},ensure_ascii=False,indent=2))
