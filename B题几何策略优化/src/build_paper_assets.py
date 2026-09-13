import json,sys,math
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle
from matplotlib.collections import PatchCollection
from figqa import assert_no_overlap
R=Path(__file__).resolve().parents[1];P=R/'paper';S=json.loads((R/'artifacts/summary.json').read_text())
plt.rcParams.update({'font.family':'Songti SC','font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
reports=[]
def save(fig,name):
 fig.tight_layout(pad=1.5);assert_no_overlap(fig);fig.savefig(R/'figures'/f'{name}.pdf');fig.savefig(R/'figures'/f'{name}.png',dpi=180);plt.close(fig);reports.append({'figure':name,'collision_gate':'PASS'})
fig,axes=plt.subplots(1,2,figsize=(10,3.5))
for ax,q in zip(axes,['3','4']):
 pairs=S['iid'][q]['vs56']['pairs'];x=np.arange(1,len(pairs)+1);y=np.array([v['saving_s'] for v in pairs]);ax.scatter(x,y,s=10,c=np.where(y>=0,'#187b7d','#b64635'),alpha=.8);ax.axhline(0,color='#222',lw=.7);ax.set(xlabel='配对案例序号',ylabel='相对方法56节省（秒）',title='Q'+q);ax.grid(alpha=.15)
save(fig,'paired_results')
fig,axes=plt.subplots(1,2,figsize=(9,3.2))
for ax,q in zip(axes,['3','4']):
 d=S['iid'][q]['vs56']['decomposition_s'];vals=list(d.values());ax.bar(['走路','测向','换频','失败清除'],vals,color=['#187b7d' if v>=0 else '#b64635' for v in vals]);ax.axhline(0,color='#222',lw=.7);ax.set(ylabel='平均节省（秒）',title='Q'+q);ax.tick_params(axis='x',labelsize=8);ax.grid(axis='y',alpha=.15)
save(fig,'cost_components')
a=json.loads((R/'artifacts/residual-witness.json').read_text());sites=np.array(a['sites']);boxes=a['boxes'];fig,axes=plt.subplots(1,2,figsize=(9,4))
patches=[Rectangle((x0,y0),x1-x0,y1-y0) for x0,y0,x1,y1 in boxes];axes[0].add_collection(PatchCollection(patches,facecolor='#dae7ec',edgecolor='#adbdc4',linewidth=.15));axes[0].add_patch(Circle((0,0),1800,fill=False,color='#333',lw=1));axes[0].scatter(sites[:,0],sites[:,1],s=14,color='#187b7d');axes[0].set(xlim=(-2100,2100),ylim=(-2100,2100),xlabel='x (m)',ylabel='y (m)',title='连续覆盖认证分区');axes[0].set_aspect('equal')
old=np.array([995,0]);q=sites[1];axes[1].plot([old[0],q[0]],[old[1],q[1]],color='#187b7d');axes[1].scatter([old[0]],[old[1]],label='静态点',marker='x',s=50,color='#b64635');axes[1].scatter([q[0]],[q[1]],label='证书通过的替换点',s=40,color='#187b7d');axes[1].set(xlim=(989,998),ylim=(-2,3),xlabel='x (m)',ylabel='y (m)',title='可行替换位移3.595米');axes[1].legend(loc='upper center',bbox_to_anchor=(.5,-.23),fontsize=8);axes[1].set_aspect('equal');save(fig,'residual_geometry')
(R/'artifacts/figure-qa.json').write_text(json.dumps({'status':'PASS','figures':reports},indent=2))
# Numeric macros are generated directly from executed artifacts.
a=S['iid']['3']['vs56'];b=S['iid']['4']['vs56'];f=lambda x:f'{x:.2f}'
(P/'numbers.tex').write_text('\n'.join([r'\newcommand{\QthreeMean}{'+f(a['candidate_mean_s'])+'}',r'\newcommand{\QthreeSave}{'+f(a['saving_s'])+'}',r'\newcommand{\QfourMean}{'+f(b['candidate_mean_s'])+'}',r'\newcommand{\QfourSave}{'+f(b['saving_s'])+'}',r'\newcommand{\QfourCI}{['+f(b['ci95_s'][0])+','+f(b['ci95_s'][1])+']}']))
names={79:'最坏半径与行走门槛',80:'最近保证第二测',81:'连续发现点替换',82:'几何门槛及单源续跑',83:'原覆盖的邻域巡游',85:'连续替换及机会删点',86:'可变覆盖及邻域巡游',84:'冻结候选组合'}
tex=r'\begin{table}[H]\centering\small\caption{开发40局每问的配对总时间，正值表示节省；未混入独立集}\begin{tabular}{rlrr}\toprule 方法&变化&Q3节省秒&Q4节省秒\\\midrule'+'\n'
for m,n in names.items():tex+=f"{m}&{n}&{f(S['development'][str(m)]['3']['saving_s'])}&{f(S['development'][str(m)]['4']['saving_s'])}"+r'\\'+'\n'
tex+=r'\bottomrule\end{tabular}\end{table}';(P/'development_table.tex').write_text(tex)
tex=r'\begin{table}[H]\centering\small\caption{独立200局每问，候选84与方法56比较；时间单位为秒}\begin{tabular}{lrr}\toprule 指标&Q3&Q4\\\midrule'+'\n'
for name,key in [('方法56总均时','baseline_mean_s'),('默认78总均时','RECOMMENDED_MEAN'),('默认78单源均时','RECOMMENDED_SOURCE'),('候选84总均时','candidate_mean_s'),('候选84单源均时','mean_source_s'),('总均时节省','saving_s'),('CPU平均时间','cpu_mean_s'),('CPU最大时间','cpu_max_s')]:
 vals=[S['iid'][q]['vs78']['baseline_mean_s'] if key=='RECOMMENDED_MEAN' else S['iid'][q]['vs78']['baseline_source_s'] if key=='RECOMMENDED_SOURCE' else d[key] for q,d in [('3',a),('4',b)]]
 tex+=f"{name}&{f(vals[0])}&{f(vals[1])}"+r'\\'+'\n'
tex+=f"84对78新增节省&{f(S['iid']['3']['vs78']['saving_s'])}&{f(S['iid']['4']['vs78']['saving_s'])}"+r'\\'+'\n'
tex+=f"节省率/\\%&{a['saving_pct']:.3f}&{b['saving_pct']:.3f}"+r'\\'+'\n'
tex+=f"配对95\\%区间&[{f(a['ci95_s'][0])},{f(a['ci95_s'][1])}]&[{f(b['ci95_s'][0])},{f(b['ci95_s'][1])}]"+r'\\'+'\n'
tex+=f"更快/持平/更慢&{a['faster']}/{a['ties']}/{a['slower']}&{b['faster']}/{b['ties']}/{b['slower']}"+r'\\'+'\n'+r'全部清除&200/200&200/200\\\bottomrule\end{tabular}\end{table}'
(P/'iid_table.tex').write_text(tex)
c=S['iid']['4']['vs78'];(P/'iid_interpretation.tex').write_text(f"Q3与方法78逐局相同；其对方法56的{f(a['saving_s'])}秒收益全部来自已有提前停车，不能记为本轮新增规划收益。Q4相对方法78平均节省{f(c['saving_s'])}秒、{c['saving_pct']:.3f}\\%，95\\%区间为[{f(c['ci95_s'][0])},{f(c['ci95_s'][1])}]秒，{c['slower']}局变慢。相对方法56的最大单局退步为{f(b['max_regression_s'])}秒。\\textbf{{两个Q4比较的区间均跨零，按预声明规则不推广候选84，推荐默认保留方法78。}}实验候选可由geometric策略名显式运行。")
tex=r'\begin{table}[H]\centering\small\caption{五组压力测试，每组每问40局，候选84相对56；全部清除}\begin{tabular}{lrrrr}\toprule 组别&Q3节省秒&Q4节省秒&Q3更慢局&Q4更慢局\\\midrule'+'\n'
for i,n in enumerate(['边界外向','共线端点','近重合','相关角误差','分区端点误差'],1):
 d=S['stress'][str(i)];tex+=f"{n}&{f(d['3']['saving_s'])}&{f(d['4']['saving_s'])}&{d['3']['slower']}&{d['4']['slower']}"+r'\\'+'\n'
tex+=r'\bottomrule\end{tabular}\end{table}';(P/'stress_table.tex').write_text(tex)
(P/'conclusion_numeric.tex').write_text(f"冻结独立集候选Q4虽平均节省{f(b['saving_s'])}秒，但区间跨零，因此只将其作为进一步研究的可行算法交付，默认仍为方法78。")
# Print complete source required to build the online solver and reproduce the
# reported geometric proofs. Historical alternatives are labelled as such.
files=sorted((R/'src').glob('*.hpp'))+[R/'review/certified_layout21_hex.hpp',R/'src/robot.cpp',R/'src/benchmark.cpp',R/'src/bridge.py',R/'src/q2_full_domain_certificate.py',R/'src/q4_area_arc_certificate.py',R/'src/run_experiments.py',R/'src/analyze_revision.py',R/'tests/replay_residual_fraction.py',R/'tests/q3_coverage_bound.py',R/'tests/test_geometry_revision.cpp',R/'tests/run_checks.py',R/'src/validate_mock.py',R/'tests/test_bridge_deadline.py',R/'run_all.py']
tex=r'\section{完整计算源程序}\small 此附录列出在线机器人、实验内核、消融模块和几何证书的完整源码。历史方法分支仅供复核，不表示默认启用。模块标题与支撑包同名。'+'\n'
for path in files:
 rel=path.relative_to(R).as_posix();title=rel.replace('_',r'\_')
 if rel=='run_all.py':tex+=r'\clearpage'+'\n'
 tex+=r'\subsection*{\texttt{'+title+r'}}'+'\n'+r'\lstinputlisting[basicstyle=\ttfamily\fontsize{8}{9.5}\selectfont,breaklines=true,breakatwhitespace=false,columns=fullflexible,keepspaces=true,numbers=left,numberstyle=\tiny,numbersep=3pt]{../'+rel+'}\n'
(P/'source_appendix.tex').write_text(tex)
print('assets generated, figure collision checks passed')
