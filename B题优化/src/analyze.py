"""Paired statistics and figures for frozen second-round experiments."""
import csv,json
from pathlib import Path
import numpy as np
from scipy.stats import t,beta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';F=ROOT/'figures';F.mkdir(exist_ok=True)
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'axes.titlesize':10.5,'axes.labelsize':10,'legend.fontsize':8.5,'pdf.fonttype':42,'savefig.dpi':320})
configs={'旧最近邻':'test_baseline.csv','分层2-opt':'test_route.csv','联合31点':'test_joint31.csv','25点最近邻':'test_mesh25_nn.csv','联合25点':'test_joint25.csv','最终方案':'test_final.csv'}
def read(name):
 rows=list(csv.DictReader((R/name).open()))
 if name.startswith('test_'):
  assert len(rows)==400
  for p in [3,4]:assert [int(r['seed'])for r in rows if int(r['problem'])==p]==list(range(90001,90201))
 for r in rows:
  if 'total'in r:assert int(r['total'])==int(r['cleared'])and abs(float(r['ratio'])-1)<1e-12
 return rows
data={k:read(v)for k,v in configs.items()}
def arr(rows,p,k):return np.array([float(r[k])for r in rows if int(r['problem'])==p])
def stats(x):
 m=x.mean();half=t.ppf(.975,len(x)-1)*x.std(ddof=1)/np.sqrt(len(x));return {'mean':float(m),'ci95':[float(m-half),float(m+half)],'p95':float(np.quantile(x,.95)),'max':float(max(x))}
out={'configs':{},'stress':{},'development':{}}
for label,rows in data.items():
 out['configs'][label]={}
 for p in [3,4]:
  base=arr(data['旧最近邻'],p,'time_s');x=arr(rows,p,'time_s');delta=base-x
  out['configs'][label][p]={'time_s':stats(x),'avg_s':stats(arr(rows,p,'avg_s')),'move_m':stats(arr(rows,p,'move_m')),'runtime_s':stats(arr(rows,p,'runtime_s')),
   'saving_s':stats(delta),'saving_percent':float(100*delta.mean()/base.mean()),'wins':int(sum(delta>1e-6)),'full_cases':len(x),'CP95_lower':float(beta.ppf(.025,len(x),1)),
   'move_fraction':float(arr(rows,p,'move_m').mean()/5/x.mean()),'measures':float(arr(rows,p,'measures').mean()),'miss':float(arr(rows,p,'miss').mean())}
for name in ['stress_boundary.csv','stress_collinear.csv','stress_correlated.csv','stress_endpoint.csv','stress_degenerate.csv']:
 rows=read(name);assert len(rows)==200
 out['stress'][name]={p:{'count':len(arr(rows,p,'ratio')),'avg_s':stats(arr(rows,p,'avg_s')),'time_s':stats(arr(rows,p,'time_s'))}for p in [3,4]}
for file in sorted(R.glob('dev*.csv')):
 rows=read(file.name);out['development'][file.stem]={p:float(arr(rows,p,'time_s').mean())for p in [3,4]}
(R/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
def save(fig,name):
 fig.tight_layout()
 for ext in ['png','pdf','svg']:fig.savefig(F/(name+'.'+ext),bbox_inches='tight')
 plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(7.2,3.4))
labels=['旧最近邻','分层2-opt','联合31点','联合25点','最终方案'];short=['旧策略','分层','联合31','联合25','最终']
for ax,p in zip(axes,[3,4]):
 ds=[arr(data[k],p,'time_s')/60 for k in labels]
 bp=ax.boxplot(ds,tick_labels=short,patch_artist=True,showfliers=False)
 for patch,col in zip(bp['boxes'],['#aaaaaa','#56B4E9','#0072B2','#009E73','#D55E00']):patch.set_facecolor(col);patch.set_alpha(.6)
 ax.set(ylabel='总虚拟时间 / 分钟',title=f'问题{p}：新测试集n=200');ax.tick_params(axis='x',labelsize=8.5);ax.grid(axis='y',alpha=.2)
save(fig,'图1_新盲测配对消融')

fig,ax=plt.subplots(figsize=(5.2,4.3))
xy=np.loadtxt(ROOT/'review/layout_production_points.csv',delimiter=',')
assert xy.shape==(25,2)
ax.scatter(xy[:,0],xy[:,1],c='#009E73',s=25,label='25个测点')
ax.add_patch(Circle((0,0),1800,fill=False,ec='#333333',lw=1.5))
ax.scatter([0],[0],marker='s',color='#D55E00',s=30,label='起点（不额外检测）')
for i in range(len(xy)):
 for j in range(i):
  if abs(np.linalg.norm(xy[i]-xy[j])-999)<1e-5:ax.plot([xy[i,0],xy[j,0]],[xy[i,1],xy[j,1]],color='#009E73',alpha=.28,lw=.8)
ax.set_aspect('equal');ax.set(xlabel='x / 米',ylabel='y / 米',title='平移三角格：25点连续覆盖证书');ax.legend(loc='upper left');ax.grid(alpha=.15)
save(fig,'图2_25点连续覆盖')

fig,axes=plt.subplots(1,2,figsize=(7.2,3.4))
for ax,p in zip(axes,[3,4]):
 for label,style,col in [('旧最近邻','--','#999999'),('最终方案','-','#D55E00')]:
  x=np.sort(arr(data[label],p,'time_s')/60);ax.plot(x,np.arange(1,len(x)+1)/len(x),style,c=col,label=label)
 ax.set(xlabel='总虚拟时间 / 分钟',ylabel='累计案例比例',title=f'问题{p}');ax.legend();ax.grid(alpha=.2)
save(fig,'图3_时间经验分布')
print(json.dumps(out['configs']['最终方案'],ensure_ascii=False,indent=2))
