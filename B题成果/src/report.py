"""Deterministic result aggregation and publication figures; no model decisions."""
import csv
import json
from pathlib import Path
import numpy as np
from scipy.stats import t, beta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Polygon

ROOT=Path(__file__).resolve().parents[1]
RES=ROOT/'results';FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
 'font.size':10.5,'axes.titlesize':10.5,'axes.labelsize':10.5,'legend.fontsize':9,
 'xtick.labelsize':9,'ytick.labelsize':9,'axes.unicode_minus':False,
 'pdf.fonttype':42,'ps.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
 'savefig.dpi':320})
COL=['#0072B2','#D55E00','#009E73','#CC79A7']
def read(name):
    rows=list(csv.DictReader((RES/name).open()))
    expected=None
    if name.startswith('test_'):expected=range(10001,10201)
    elif name=='pilot.csv' or name.startswith('dev_'):expected=range(1,41)
    elif name.startswith('stress_'):
        starts={'stress_boundary.csv':40001,'stress_collinear.csv':50001,'stress_correlated.csv':60001,'stress_endpoint.csv':70001,'stress_degenerate.csv':80001}
        expected=range(starts[name],starts[name]+100)
    if expected is not None:
        for p in [3,4]:
            actual=[int(r['seed'])for r in rows if int(r['problem'])==p]
            assert actual==list(expected),f'incomplete, reordered, or duplicate cases: {name}, p{p}'
        assert len(rows)==2*len(expected)
    return rows
def vals(rows,p,k):return np.array([float(r[k]) for r in rows if int(r['problem'])==p])
def stat(x):
    n=len(x);margin=float(t.ppf(.975,n-1)*np.std(x,ddof=1)/np.sqrt(n)) if n>1 else 0
    return dict(n=n,mean=float(np.mean(x)),median=float(np.median(x)),p95=float(np.quantile(x,.95)),
                min=float(np.min(x)),max=float(np.max(x)),ci95=[float(np.mean(x)-margin),float(np.mean(x)+margin)])
def save(fig,name):
    fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight')
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight')
    fig.savefig(FIG/(name+'.png'),bbox_inches='tight')
    plt.close(fig)

main=read('test_main.csv');names=['test_main.csv','test_square.csv','test_static.csv','test_strict.csv']
labels=['主策略','600米方格','固定访问顺序','禁用提前试清']
summary={'main':{},'ablation':{},'stress':{},'development':{}}
for p in [3,4]:
    summary['main'][p]={k:stat(vals(main,p,k)) for k in ['time_s','avg_s','move_m','measures','switches','miss','fallbacks','runtime_s']}
    selected=[r for r in main if int(r['problem'])==p]
    n=len(selected);success=sum(int(r['cleared'])==int(r['total']) for r in selected)
    summary['main'][p]['case_full_success']=dict(success=success,total=n,
        CP95_lower=float(beta.ppf(.025,success,n-success+1)) if success else 0.,
        CP95_upper=float(beta.ppf(.975,success+1,n-success)) if success<n else 1.)
for name,label in zip(names,labels):
    rows=read(name);s={}
    for p in [3,4]:
        assert [r['seed'] for r in rows if int(r['problem'])==p]==[r['seed'] for r in main if int(r['problem'])==p]
        x=vals(rows,p,'time_s');y=vals(main,p,'time_s');delta=x-y
        s[p]={'time_s':stat(x),'avg_s':stat(vals(rows,p,'avg_s')),'paired_extra_time_s':stat(delta),
              'mean_reduction_percent':float(100*(x.mean()-y.mean())/x.mean()),
              'case_wins_main':int(np.sum(delta>1e-6)),
              'move_time_s':float(vals(rows,p,'move_m').mean()/5),
              'measurement_time_s':float(vals(rows,p,'measures').mean()*5),
              'switch_time_s':float(vals(rows,p,'switches').mean()),
              'failed_clear_time_s':float(vals(rows,p,'miss').mean()*3),
              'success_clear_time_s':float(vals(rows,p,'cleared').mean()*5)}
    summary['ablation'][label]=s
for name in ['stress_boundary.csv','stress_collinear.csv','stress_correlated.csv','stress_endpoint.csv','stress_degenerate.csv']:
    rows=read(name)
    summary['stress'][name]={p:{'n':len(vals(rows,p,'ratio')),'full_success':sum(int(r['cleared'])==int(r['total']) for r in rows if int(r['problem'])==p),'min_ratio':float(min(vals(rows,p,'ratio'))),'time_s':stat(vals(rows,p,'time_s')),
                                 'avg_s':stat(vals(rows,p,'avg_s')),'max_fallbacks':float(max(vals(rows,p,'fallbacks')))} for p in [3,4]}
for name in ['pilot.csv','dev_h900_e35.csv','dev_h990_e35.csv','dev_h950_e20.csv','dev_h950_e50.csv']:
    rows=read(name);summary['development'][name]={p:stat(vals(rows,p,'time_s')) for p in [3,4]}
summary['q2']=read('q2_candidates.csv')
(RES/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

# Figure 1: genuine intersection polygon and second-point feasible set.
fig,ax=plt.subplots(1,2,figsize=(7.2,3.8))
tri=np.array([[0,0],[40,0],[20,20*np.sqrt(3)]])
ax[0].add_patch(Polygon(tri,fc='#DCEAF2',ec=COL[0],lw=2))
ax[0].add_patch(Circle((20,20/np.sqrt(3)),40/np.sqrt(3),fill=False,ec=COL[2],lw=1.8,label='最小包围圆：R=23.094米'))
ax[0].add_patch(Circle((20,0),20,fill=False,ec=COL[1],ls='--',lw=1.8,label='最长边为直径的圆'))
ax[0].scatter(*tri.T,c=COL[0],s=24)
ax[0].set(xlim=(-8,48),ylim=(-24,42),xlabel='x / 米',ylabel='y / 米',title='(a) 直径与覆盖圆反例')
ax[0].set_aspect('equal');ax[0].legend(loc='lower left',fontsize=9)
eps=np.deg2rad(1.005)
ax[1].fill([0,1500*np.cos(eps),1500*np.cos(eps)],[0,-1500*np.sin(eps),1500*np.sin(eps)],color='#DCEAF2',label='首次观测位置集合')
for sign in [-1,1]:ax[1].add_patch(Rectangle((650,200 if sign>0 else -400),200,200,color=COL[2],alpha=.22))
ax[1].scatter([0,750,750],[0,300,-300],c=[COL[0],COL[1],COL[1]],s=35)
ax[1].annotate('650≤a≤850\n200≤|b|≤400',(500,390),fontsize=9)
ax[1].set(xlim=(-50,1550),ylim=(-500,600),xlabel='沿示向方向 a / 米',ylabel='横向 b / 米',title='(b) 全向第二测点候选区')
ax[1].grid(alpha=.2)
fig.tight_layout();save(fig,'图1_定位几何与选点')

# Figure 2: coverage coordinates from independently checked mesh JSON.
g=json.loads((ROOT/'review'/'geometry_results.json').read_text(encoding='utf-8'))
fig,axes=plt.subplots(1,2,figsize=(7.2,3.7))
th=np.arange(6)*np.pi/3
seven=np.vstack([[0,0],np.column_stack([1200*np.cos(th),1200*np.sin(th)])])
for q in seven:axes[0].add_patch(Circle(q,1000,fc=COL[0],ec=COL[0],alpha=.07,lw=1))
axes[0].scatter(*seven.T,c=COL[0],s=24,zorder=4)
# Use independently generated vertex list if available; parse dedicated output in generic way below.
# Own deterministic exact circle-cell intersection for plotting only.
def ds(a,b):
    d=b-a;tt=np.clip(-np.dot(a,d)/np.dot(d,d),0,1);return np.linalg.norm(a+tt*d)
points=set();edges=[];h=950
for i in range(-6,6):
 for j in range(-6,6):
    v=lambda i,j:np.array([h*(i+j*.5),h*np.sqrt(3)/2*j])
    a,b,c,d=v(i,j),v(i+1,j),v(i,j+1),v(i+1,j+1)
    for pol in [[a,b,c],[d,c,b]]:
        signs=[(pol[(k+1)%3]-pol[k])[0]*(-pol[k])[1]-(pol[(k+1)%3]-pol[k])[1]*(-pol[k])[0] for k in range(3)]
        inside=all(z>=-1e-8 for z in signs) or all(z<=1e-8 for z in signs)
        if inside or min(ds(pol[k],pol[(k+1)%3]) for k in range(3))<=1800+1e-7:
            for p in pol:points.add(tuple(p))
            edges.append(np.array(pol+[pol[0]]))
for ed in edges:axes[1].plot(*ed.T,c=COL[2],alpha=.35,lw=.8)
xy=np.array(sorted(points));assert len(xy)==31
axes[1].scatter(*xy.T,c=np.where(np.linalg.norm(xy,axis=1)>1800,COL[1],COL[2]),s=23,zorder=4)
for ax in axes:
    ax.add_patch(Circle((0,0),1800,fill=False,ec='#333333',lw=1.8));ax.set_aspect('equal');ax.set(xlim=(-2800,2800),ylim=(-2600,2600),xlabel='x / 米',ylabel='y / 米');ax.grid(alpha=.15)
axes[0].set_title('(a) 全向7点：覆盖半径968.902米')
axes[1].set_title('(b) 定向31点：三角格边长950米')
fig.tight_layout();save(fig,'图2_连续覆盖证书')

fig,axes=plt.subplots(1,2,figsize=(7.2,3.5))
for ax,p in zip(axes,[3,4]):
    data=[vals(read(n),p,'time_s')/60 for n in names]
    bp=ax.boxplot(data,tick_labels=['主策略','方格','固定顺序','禁用试清'],patch_artist=True,showfliers=False,widths=.55)
    for patch,c in zip(bp['boxes'],COL):patch.set_facecolor(c);patch.set_alpha(.5)
    ax.set(ylabel='全任务虚拟时间 / 分钟',title=f'问题{p}：同案例配对，n=200');ax.grid(axis='y',alpha=.2)
    ax.tick_params(axis='x',labelsize=9)
fig.tight_layout();save(fig,'图3_配对消融分布')

fig,axes=plt.subplots(1,2,figsize=(7.2,3.5))
costkeys=['move_time_s','measurement_time_s','switch_time_s','failed_clear_time_s','success_clear_time_s']
costlabels=['移动','检测','换频','失败清除','成功清除'];colors=[COL[0],COL[2],'#E69F00',COL[1],'#999999']
for ax,p in zip(axes,[3,4]):
    bottom=np.zeros(4)
    for key,lab,col in zip(costkeys,costlabels,colors):
        ys=np.array([summary['ablation'][lab0][p][key]/60 for lab0 in labels]);ax.bar(['主策略','方格','固定顺序','禁用试清'],ys,bottom=bottom,label=lab,color=col);bottom+=ys
    ax.set(ylabel='平均全任务虚拟时间 / 分钟',title=f'问题{p}：动作成本分解');ax.grid(axis='y',alpha=.2)
axes[0].legend(ncol=3,loc='upper left',fontsize=9)
fig.tight_layout();save(fig,'图4_动作成本分解')

fig,axes=plt.subplots(1,2,figsize=(7.2,3.7))
for ax,p in zip(axes,[3,4]):
    rows=read(f'trace_p{p}_10001.csv');path=np.array([[0,0]]+[[float(r['x']),float(r['y'])]for r in rows])
    ax.plot(*path.T,lw=.75,color=COL[0],alpha=.65)
    cp=np.array([[float(r['x']),float(r['y'])]for r in rows if r['kind']=='clear' and r['result']=='1'])
    ax.scatter(*cp.T,marker='*',s=85,color=COL[1],label='成功清除点',zorder=3)
    ax.scatter([0],[0],marker='s',s=35,color='black',label='起点')
    ax.add_patch(Circle((0,0),1800,fill=False,ec='gray',ls='--'))
    ax.set_aspect('equal');ax.set(xlabel='x / 米',ylabel='y / 米',title=f'问题{p}：测试集首个案例');ax.legend(fontsize=9,loc='upper left');ax.grid(alpha=.15)
fig.tight_layout();save(fig,'图5_代表案例轨迹')

print(json.dumps({p:{'time':summary['main'][p]['time_s']['mean'],'avg':summary['main'][p]['avg_s']['mean'],
                      'p95':summary['main'][p]['time_s']['p95']} for p in [3,4]},ensure_ascii=False))
