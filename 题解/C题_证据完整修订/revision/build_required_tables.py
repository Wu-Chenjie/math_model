from pathlib import Path
import numpy as np,json,hashlib
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT.parent/'C题_跨日随机控制';T=ROOT/'tables'
DATES=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
def h(t):return f'{t//6:02d}:{t%6*10:02d}'
def span(a,b):return h(a)+'--'+h(b)
def f(x):return f'{x:,.2f}'
def table(caption,cols,body):return '\\begin{table}[H]\\centering\\small\\setlength{\\tabcolsep}{4pt}\\caption{'+caption+'}\n\\begin{tabular}{'+cols+'}\\toprule\n'+body+'\n\\bottomrule\\end{tabular}\\end{table}\n'
checks=[]
emergency=[]
for kind,label in [('q2','问题二'),('q3','问题三'),('q4_2','问题四日前'),('q4_3','问题四日内')]:
 p=BASE/f'artifacts/global-terminal/{kind}_markov_mpc.npz';a=dict(np.load(p));blocks=[];events=[]
 for day in DATES:
  i=list(a['dates'].astype(str)).index(day);q,r,c,d,e,price=[a[k][i] for k in ['q','r','c','d','emergency','price']];ordinary=float((price*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0))).sum());ec=float((5*price*e).sum())
  # All values from fixed-terminal full trajectories. Actual physical purchase is r+e.
  lines=['时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量\\\\\\midrule']
  for hrs in [[10,12,14],[16,18,20]]:
   cells=[]
   for hh in hrs:
    j=hh*6;v=f(r[j]) if kind in ('q2','q4_2') else f(r[j])+' ('+f(q[j])+')';cells += [span(j,j+1),v]
   lines.append(' & '.join(cells)+'\\\\')
  lines += ['\\midrule','全天合同购电量 & \\multicolumn{2}{r}{'+f(r.sum())+'} & 全天合同购电费 & \\multicolumn{2}{r}{'+f(ordinary)+'}\\\\','全天实际购电量 & \\multicolumn{2}{r}{'+f((r+e).sum())+'} & 全天总购电费 & \\multicolumn{2}{r}{'+f(ordinary+ec)+'}\\\\']
  caption=label+' '+day+'购电结果（电量kWh，费用元）'
  s='\\subsubsection*{'+label+'：'+day+'}\n'+table(caption,'lr lr lr','\n'.join(lines))
  if kind in ('q3','q4_3'):s+='\\noindent\\small 购电量列为最终合同量，括号内为0时原合同。\\normalsize\n'
  lines=['时间段 & 充电量 & 放电量 & 时间段 & 充电量 & 放电量\\\\\\midrule']
  for j in [0,48,96]:lines.append(' & '.join([span(j,j+24),f(c[j:j+24].sum()),f(d[j:j+24].sum()),span(j+24,j+48),f(c[j+24:j+48].sum()),f(d[j+24:j+48].sum())])+'\\\\')
  lines+=['\\midrule','0:00库存 & \\multicolumn{2}{r}{'+f(a['state'][i,0])+'} & 24:00库存 & \\multicolumn{2}{r}{'+f(a['state'][i,-1])+'}\\\\']
  s+=table(label+' '+day+'储能结果（kWh）','lrr lrr','\n'.join(lines));blocks.append('\\par\\noindent\\begin{minipage}{\\textwidth}\n'+s+'\\end{minipage}\\par\n')
  ev=[];start=None
  for j in range(145):
   active=j<144 and e[j]>1e-6
   if active and start is None:start=j
   if not active and start is not None:ev.append((span(start,j),f(e[start:j].sum())));start=None
  events.append(ev or [('无','0.00')])
  checks.append({'kind':kind,'date':day,'sum_q':float(q.sum()),'sum_r':float(r.sum()),'physical_purchase':float((r+e).sum()),'ordinary_cost':ordinary,'emergency_cost':ec,'total_cost':ordinary+ec,'charge':float(c.sum()),'discharge':float(d.sum()),'initial':float(a['state'][i,0]),'final':float(a['state'][i,-1]),'events':events[-1],'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 (T/f'specified-{kind}.tex').write_text('\n\\par\\medskip\n'.join(blocks))
 emergency.append((label,events))
emer_parts=[]
for label,events in emergency:
 lines=[' & '.join('\\multicolumn{2}{c}{'+day+'}' for day in DATES)+'\\\\','时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量\\\\\\midrule']
 for row in range(max(map(len,events))):lines.append(' & '.join(v for ev in events for v in (ev[row] if row<len(ev) else ('','')))+'\\\\')
 emer_parts.append('\\textbf{'+label+'}\\\\\n\\begin{tabular}{lr lr lr lr}\\toprule\n'+'\n'.join(lines)+'\n\\bottomrule\\end{tabular}')
(T/'specified-emergency.tex').write_text('\\begin{table}[H]\\centering\\footnotesize\\setlength{\\tabcolsep}{3.5pt}\n\\caption{指定日期紧急购电（kWh；连续非零区间，数值零阈值为$10^{-6}$ kWh）}\n'+'\\par\\medskip\n'.join(emer_parts)+'\n\\end{table}\n')
(ROOT/'revision/required-tables.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');print('16 dates;32 daily tables;4 emergency tables')

# Q1 official-format tables, from the same saved deterministic optimum.
a=dict(np.load(BASE/'artifacts/q1.npz'));data=dict(np.load(BASE/'artifacts/data.npz'))
lines=['时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量\\\\\\midrule']
for hrs in [[10,12,14],[16,18,20]]:
 cells=[]
 for hh in hrs:cells += [span(hh*6,hh*6+1),f(a['q'][hh*6])]
 lines.append(' & '.join(cells)+'\\\\')
lines += ['\\midrule','全天购电量 & \\multicolumn{2}{r}{'+f(a['q'].sum())+'} & 全天购电费 & \\multicolumn{2}{r}{'+f(a['q']@data['day_price'])+'}\\\\']
(T/'q1buy.tex').write_text(table('问题一购电结果（电量kWh，费用元）','lr lr lr','\n'.join(lines)).replace('\\begin{tabular}',r'\label{tab:q1buy}\begin{tabular}',1))
lines=['时间段 & 充电量 & 放电量 & 时间段 & 充电量 & 放电量\\\\\\midrule']
for j in [0,48,96]:
 cells=[]
 for t in [j,j+24]:cells += [span(t,t+24),f(a['c'][t:t+24].sum()),f(a['d'][t:t+24].sum())]
 lines.append(' & '.join(cells)+'\\\\')
lines += ['\\midrule','0:00库存 & \\multicolumn{2}{r}{'+f(a['state'][0])+'} & 24:00库存 & \\multicolumn{2}{r}{'+f(a['state'][-1])+'}\\\\']
(T/'q1bat.tex').write_text(table('问题一充放电与首末库存（kWh）','lrr lrr','\n'.join(lines)))
