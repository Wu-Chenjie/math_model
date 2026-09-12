"""Paired, stratified descriptive analysis; every controlled cell is retained."""
import csv,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.stats import t
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';F=ROOT/'figures';F.mkdir(exist_ok=True)
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'axes.titlesize':10.5,'legend.fontsize':8.5,'pdf.fonttype':42,'savefig.dpi':320})

def load(name,total):
 rows=list(csv.DictReader((R/name).open()));assert len(rows)==total
 pairs=defaultdict(dict)
 for r in rows:
  assert int(r['cleared'])==int(r['n'])
  key=(int(r['problem']),int(r['case_id']));m=int(r['method']);assert m not in pairs[key];pairs[key][m]=r
  check=float(r['move_m'])/5+float(r['switches'])+5*float(r['measures'])+3*float(r['miss'])+5*float(r['cleared'])
  assert abs(check-float(r['time_s']))<.001
 assert all(set(v)=={0,1,2}for v in pairs.values())
 return list(pairs.values())
def arr(pairs,m,key):return np.array([float(x[m][key])for x in pairs])
def describe(x):
 n=len(x);a=float(x.mean());se=float(x.std(ddof=1)/np.sqrt(n))if n>1 else 0;h=float(t.ppf(.975,n-1))*se if n>1 else 0
 return {'n':n,'mean':a,'ci95_descriptive':[a-h,a+h],'min':float(min(x)),'max':float(max(x)),'p95':float(np.quantile(x,.95))}
def summarize(pairs):
 out={'environments':len(pairs),'all_cleared':True,'methods':{}}
 for m in [0,1,2]:out['methods'][m]={k:describe(arr(pairs,m,k))for k in ['time_s','avg_s','move_m','measures','miss','runtime_s']}
 out['comparisons']={}
 for baseline in [0,1]:
  b=arr(pairs,baseline,'time_s');now=arr(pairs,2,'time_s');d=b-now
  cost={'movement':float((arr(pairs,baseline,'move_m')-arr(pairs,2,'move_m')).mean()/5),
        'measurements':float((arr(pairs,baseline,'measures')-arr(pairs,2,'measures')).mean()*5),
        'switches':float((arr(pairs,baseline,'switches')-arr(pairs,2,'switches')).mean()),
        'failed_clears':float((arr(pairs,baseline,'miss')-arr(pairs,2,'miss')).mean()*3)}
  assert abs(sum(cost.values())-d.mean())<.001
  out['comparisons'][baseline]={'saving_s':describe(d),'saving_percent':float(100*d.mean()/b.mean()),'wins':int(sum(d>1e-6)),'losses':int(sum(d< -1e-6)),'cost_savings':cost}
 return out
iid=load('iid.csv',1200);controlled=load('stratified.csv',9720)
out={'iid':{},'controlled':{},'marginals':[],'cells':[]}
for p in [3,4]:
 ip=[x for x in iid if int(x[2]['problem'])==p];cp=[x for x in controlled if int(x[2]['problem'])==p]
 assert len(ip)==200 and len(cp)==(810 if p==3 else 2430)
 out['iid'][p]=summarize(ip);out['controlled'][p]=summarize(cp)
 axes={'源数':lambda r:r['n'],'定向占比':lambda r:('0'if int(r['nd'])==0 else '低'if int(r['nd'])/int(r['n'])<.35 else'中'if int(r['nd'])/int(r['n'])<.65 else'高'),
       '边界占比':lambda r:'0%'if int(r['nb'])==0 else'100%'if r['nb']==r['n'] else'约50%',
       '几何模式':lambda r:['均匀角','近共线','聚集'][int(r['geometry'])],
       '几何特征值比':lambda r:'<0.01'if float(r['eigen_ratio'])<.01 else'0.01—0.1'if float(r['eigen_ratio'])<.1 else'≥0.1',
       '接收半径':lambda r:r['radius'],'误差场':lambda r:r['error'],'朝向模式':lambda r:'向外'if int(r['outward'])else'随机'}
 for axis,func in axes.items():
  groups=defaultdict(list)
  for pair in cp:groups[func(pair[2])].append(pair)
  for level,ps in groups.items():out['marginals'].append({'problem':p,'axis':axis,'level':level,**summarize(ps)})
 groups=defaultdict(list)
 for pair in cp:
  rr=pair[2];groups[(int(rr['n']),int(rr['nd']),int(rr['nb']),int(rr['geometry']))].append(pair)
 for (n,nd,nb,g),ps in groups.items():
  assert len(ps)==30
  # Each cell has the full 3 radius x 5 error x 2 outward balance.
  assert len({(r[2]['radius'],r[2]['error'],r[2]['outward'])for r in ps})==30
  out['cells'].append({'problem':p,'n':n,'nd':nd,'nb':nb,'geometry':g,**summarize(ps)})
assert len(out['cells'])==108
out['negative_cells']={str(base):[{'problem':x['problem'],'n':x['n'],'nd':x['nd'],'nb':x['nb'],'geometry':x['geometry'],**x['comparisons'][base]}for x in out['cells']if x['comparisons'][base]['saving_s']['mean']< -1e-6]for base in [0,1]}
(R/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
flat=[]
for x in out['marginals']:
 c=x['comparisons'][1];flat.append({'problem':x['problem'],'axis':x['axis'],'level':x['level'],'environments':x['environments'],'vs25_saving_s':c['saving_s']['mean'],'vs25_percent':c['saving_percent'],'ci_low':c['saving_s']['ci95_descriptive'][0],'ci_high':c['saving_s']['ci95_descriptive'][1]})
with(R/'all_strata.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
cells=[]
for x in out['cells']:
 c=x['comparisons'][1];cells.append({k:x[k]for k in ['problem','n','nd','nb','geometry']}|{'vs25_saving_s':c['saving_s']['mean'],'vs25_percent':c['saving_percent'],'movement_saving_s':c['cost_savings']['movement'],'measurement_saving_s':c['cost_savings']['measurements'],'switch_saving_s':c['cost_savings']['switches'],'failed_clear_saving_s':c['cost_savings']['failed_clears']})
with(R/'all_cells.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fieldnames=list(cells[0]));w.writeheader();w.writerows(cells)
def save(fig,name):
 fig.tight_layout()
 for ext in ['png','pdf','svg']:fig.savefig(F/(name+'.'+ext),bbox_inches='tight')
 plt.close(fig)

fig,ax=plt.subplots(figsize=(5.2,4.3));points=json.loads((R/'candidate21_995.json').read_text())['points'];xy=np.array(points)
ax.add_patch(Circle((0,0),1800,fill=False,ec='#333333',lw=1.5));ax.add_patch(Circle((0,0),995,fill=False,ec='#009E73',ls='--',alpha=.4));ax.add_patch(Circle((0,0),1864,fill=False,ec='#0072B2',ls='--',alpha=.4));ax.scatter(xy[:9,0],xy[:9,1],c='#009E73',s=30,label='中心+8内圈');ax.scatter(xy[9:,0],xy[9:,1],c='#0072B2',s=30,label='12外圈');ax.set_aspect('equal');ax.set(xlabel='x / 米',ylabel='y / 米',title='21点布局：998米连续凸包覆盖');ax.legend();ax.grid(alpha=.15);save(fig,'图1_21点布局')

fig,axes=plt.subplots(2,2,figsize=(7.2,5.8))
for ax,axis in zip(axes.flat,['源数','定向占比','边界占比','几何模式']):
 rows=[x for x in out['marginals']if x['problem']==4 and x['axis']==axis];means=[x['comparisons'][1]['saving_percent']for x in rows]
 ax.bar([x['level']for x in rows],means,color='#0072B2');ax.axhline(0,c='black',lw=.7);ax.set(title=axis,ylabel='较25点节省总时间 / %');ax.grid(axis='y',alpha=.2)
save(fig,'图2_问题4边际分层')

fig,axes=plt.subplots(1,3,figsize=(7.2,3.1));mats=[]
for g in range(3):
 mat=np.zeros((3,9))
 for x in out['cells']:
  if x['problem']!=4 or x['geometry']!=g:continue
  i=[10,13,16].index(x['n']);dl=0 if x['nd']/x['n']<.35 else 1 if x['nd']/x['n']<.65 else 2
  bl=0 if x['nb']==0 else 2 if x['nb']==x['n']else 1;mat[i,3*dl+bl]=x['comparisons'][1]['saving_percent']
 mats.append(mat)
vmax=max(abs(np.array(mats)).max(),1)
for ax,mat,title in zip(axes,mats,['均匀角','近共线','聚集']):
 im=ax.imshow(mat,cmap='RdBu',vmin=-vmax,vmax=vmax,aspect='auto');ax.set(yticks=[0,1,2],yticklabels=[10,13,16],xticks=[1,4,7],xticklabels=['低定向','中定向','高定向'],title=title,xlabel='每组三列：边界0/50/100%',ylabel='源数');ax.tick_params(labelsize=8)
fig.colorbar(im,ax=list(axes),fraction=.025,pad=.03,label='较25点节省 / %');fig.subplots_adjust(wspace=.4,right=.86,bottom=.22);fig.savefig(F/'图3_全部81单元.png',bbox_inches='tight');fig.savefig(F/'图3_全部81单元.pdf',bbox_inches='tight');fig.savefig(F/'图3_全部81单元.svg',bbox_inches='tight');plt.close(fig)

print(json.dumps({'iid_p4':out['iid'][4]['comparisons'],'controlled_p4':out['controlled'][4]['comparisons'],'negative_cell_counts':{k:len(v)for k,v in out['negative_cells'].items()}},ensure_ascii=False,indent=2))
