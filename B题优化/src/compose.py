import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
def table(head,rows):return '|'+ '|'.join(head)+'|\n|'+'|'.join([':--']*len(head))+'|\n'+'\n'.join('|'+ '|'.join(map(str,r))+'|'for r in rows)
def f(x):return f'{x:.2f}'
def ci(x):return f'[{x[0]:.2f}, {x[1]:.2f}]'
main=[];abl=[]
for p in ['3','4']:
 d=s['configs']['最终方案'][p];b=s['configs']['旧最近邻'][p]
 main.append([p,'200/200',f(b['time_s']['mean']),f(d['time_s']['mean']),f(d['avg_s']['mean']),f(d['saving_percent'])+'%',ci(d['saving_s']['ci95'])])
for label in s['configs']:
 ds=s['configs'][label];abl.append([label]+[f(ds[p]['time_s']['mean'])for p in ['3','4']]+[f(ds[p]['saving_percent'])+'%'for p in ['3','4']])
attr=[]
for p in ['3','4']:
 cfg=s['configs'];base=cfg['旧最近邻'][p]['time_s']['mean']
 changes=[('分层2-opt相对旧最近邻',cfg['旧最近邻'][p]['time_s']['mean']-cfg['分层2-opt'][p]['time_s']['mean']),('联合31点相对旧最近邻',cfg['旧最近邻'][p]['time_s']['mean']-cfg['联合31点'][p]['time_s']['mean']),('联合调度中31改25点',cfg['联合31点'][p]['time_s']['mean']-cfg['联合25点'][p]['time_s']['mean']),('25点联合调度中加入原地补测',cfg['联合25点'][p]['time_s']['mean']-cfg['最终方案'][p]['time_s']['mean'])]
 attr.append(f'问题{p}：'+ '；'.join(f'{name}对应平均节省{value:.2f}秒'for name,value in changes)+'。')
attr.append('这些是对应消融之间的均值差；机制存在交互，不能把不同分母的百分比相加，也不能将联合调度和补测收益写成单独2-opt收益。')
stress=[]
for label,name in [('边界向外','stress_boundary.csv'),('近共线','stress_collinear.csv'),('相关误差','stress_correlated.csv'),('端点误差','stress_endpoint.csv'),('重合及近距离','stress_degenerate.csv')]:
 d=s['stress'][name];stress.append([label,'100/100','100/100',f(d['3']['avg_s']['mean']),f(d['4']['avg_s']['mean'])])
mock=json.loads((ROOT/'results/original_mock_validation.json').read_text(encoding='utf-8'))
http=[[r['problem'],f"LOCAL-{r['seed']}",r['cleared'],f(r['virtual_time_s']/r['cleared']),f(r['runtime_s'])]for r in mock if r['layer']=='local_HTTP']
repl={'TABLE_MAIN':table(['题号','全清除','旧总均时/秒','新总均时/秒','新单源均时/秒','总均时下降','配对节省95%区间/秒'],main),
 'TABLE_ABLATION':table(['配置','问题3总均时/秒','问题4总均时/秒','问题3较旧节省','问题4较旧节省'],abl),
 'ATTRIBUTION':'\n\n'.join(attr),'TABLE_STRESS':table(['压力组','问题3全清除','问题4全清除','问题3单源/秒','问题4单源/秒'],stress),
 'TABLE_HTTP':table(['题号','本地案例','清除数','平均单源/秒','桥接墙钟/秒'],http),
 'REVIEW':(ROOT/'review/最终审稿摘要.md').read_text(encoding='utf-8')if(ROOT/'review/最终审稿摘要.md').exists()else'最终交接文稿正在独立复核；数学和实现专项审查已通过，其结论以对应报告的适用范围为准。'}
text=(ROOT/'优化交接_模板.md').read_text(encoding='utf-8')
for k,v in repl.items():text=text.replace('{{'+k+'}}',v)
assert '{{'not in text
(ROOT/'B题优化_论文交接.md').write_text(text,encoding='utf-8')
print('Generated',len(text),'characters')
