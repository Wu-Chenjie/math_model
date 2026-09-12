from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];s=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
def f(x):return f'{x:.2f}'
def ci(v):return f'[{v[0]:.2f}, {v[1]:.2f}]'
def table(head,rows):return '|'+ '|'.join(head)+'|\n|'+'|'.join([':--']*len(head))+'|\n'+'\n'.join('|'+ '|'.join(map(str,r))+'|'for r in rows)
arc=json.loads((ROOT/'review/q4_area_arc_certificate.json').read_text(encoding='utf-8'))
lower=[[str(r['r_interval_m']),f"{r['deficit_lower']:.7f}",r['delta_upper_rad'],f"{r['verified_slack_lower']:.7f}"]for r in arc['intervals']]
iid=[];plan=[]
for p in ['3','4']:
 for m in range(6):
  d=s['iid'][p][str(m)];iid.append([p,'M'+str(m),f(d['time_s']['mean']),f(d['avg_s']['mean']),f(d['saving_percent'])+'%'])
 for m in ['4','5']:
  d=s['iid'][p][m];plan.append([p,'M'+m,d['plans'],d['exact_plans'],d['nonlocal_plans'],f(100*d['max_relative_gap'])+'%',f(d['max_absolute_gap_m'])])
q2=[]
for p in ['3','4']:
 d=s['iid'][p]['2'];q2.append(f"问题{p}的C点配置比M0平均增加{-d['saving_percent']:.2f}%总时间，增加的总时间均值为{-d['saving_s']['mean']:.2f}秒，其中移动增加{d['extra_movement_s']:.2f}秒。")
ctrl=[[p,d['n'],f(d['old_time']['mean']),f(d['new_time']['mean']),f(d['saving_percent'])+'%',ci(d['saving_s']['ci95'])]for p,d in s['controlled'].items()]
neg=[[d['problem'],d['n'],d['nd'],d['nb'],['均匀角','近共线','聚集'][d['geometry']],f(d['saving']['mean']),ci(d['saving']['ci95'])]for d in s['negative_cells']]
rep={'LOWER_TABLE':table(['外部半径区间米','缺额下界','半角上界弧度','耦合余量下界'],lower),
'IID_TABLE':table(['题号','方法','总均时秒','单源均时秒','较M0节省'],iid),
'Q2_RESULT':'\n\n'.join(q2),
'PLAN_TABLE':table(['题号','代理','规划次数','DP次数','未获局部终止','最大相对差距','最大绝对差距米'],plan),
'CONTROL_TABLE':table(['题号','环境数','M0均时秒','M5均时秒','节省比例','节省区间秒'],ctrl),
'NEGATIVE_TABLE':('全部'+str(len(neg))+'个负均值单元如下。\n\n'+table(['题号','源数','定向数','边界数','几何','M5节省秒','描述性区间'],neg))if neg else'本组完整单元中未出现负均值单元，但个案仍不保证逐一更快。',
'REVIEW':(ROOT/'review/最终审稿摘要.md').read_text(encoding='utf-8')if(ROOT/'review/最终审稿摘要.md').exists()else'下界、正裕量与控制器已完成专项独立审查；最终论文说明正在有限复核，相关原始审稿记录将随交接归档。'}
text=(ROOT/'第四轮交接_模板.md').read_text(encoding='utf-8')
for k,v in rep.items():text=text.replace('{{'+k+'}}',v)
assert '{{'not in text and not any(ord(c)<32 and c!='\n'for c in text)
(ROOT/'B题鲁棒优化_论文交接.md').write_text(text,encoding='utf-8');print('Composed',len(text),'characters')
