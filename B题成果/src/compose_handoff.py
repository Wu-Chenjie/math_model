"""Insert computed tables into the authored manuscript, without estimating data."""
import csv
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
def table(headers,rows):
    return '|'+ '|'.join(headers)+'|\n|'+'|'.join([':--']*len(headers))+'|\n'+'\n'.join('|'+ '|'.join(map(str,row))+'|'for row in rows)
def ci(x):return f"[{x[0]:.2f}, {x[1]:.2f}]"
def f(x):return f'{x:.2f}'
dev=[]
for label,name in [('h950/τ35','pilot.csv'),('h900/τ35','dev_h900_e35.csv'),('h990/τ35','dev_h990_e35.csv'),('h950/τ20','dev_h950_e20.csv'),('h950/τ50','dev_h950_e50.csv')]:
    dev.append([label]+[f(s['development'][name][str(p)]['mean'])for p in [3,4]])
q2=[]
for row in s['q2']:
    if (row['a'],row['b']) in [('750','0'),('650','300'),('750','300'),('750','400'),('850','400')]:
        q2.append([row['a'],row['b'],f(float(row['worst_radius_m'])),f(float(row['mean_radius_m'])),f(float(row['travel_m']))])
main=[]
for p in [3,4]:
    d=s['main'][str(p)];raw=list(csv.DictReader((ROOT/'results/test_main.csv').open()))
    pooled=sum(float(r['time_s'])for r in raw if int(r['problem'])==p)/sum(int(r['cleared'])for r in raw if int(r['problem'])==p)
    main.append([p,f(d['time_s']['mean']),f(d['time_s']['p95']),f(d['avg_s']['mean']),ci(d['avg_s']['ci95']),f(pooled)])
abl=[]
for label in ['固定访问顺序','600米方格','禁用提前试清']:
    for p in [3,4]:
        if label=='600米方格'and p==3:continue
        d=s['ablation'][label][str(p)];abl.append([p,label,f(d['time_s']['mean']),f(d['paired_extra_time_s']['mean']),ci(d['paired_extra_time_s']['ci95']),f(d['mean_reduction_percent'])+'%'])
stress=[]
for label,name in [('边界向外/正端点','stress_boundary.csv'),('近共线/负端点','stress_collinear.csv'),('平滑相关误差','stress_correlated.csv'),('分区端点误差','stress_endpoint.csv'),('重合及近距离','stress_degenerate.csv')]:
    ds=s['stress'][name];stress.append([label]+[f"{ds[str(p)]['full_success']}/{ds[str(p)]['n']}"for p in [3,4]]+[f(ds['3']['avg_s']['mean']),f(ds['4']['avg_s']['mean']),f(max(ds[str(p)]['time_s']['max']for p in [3,4]))])
mock=json.loads((ROOT/'results/original_mock_validation.json').read_text(encoding='utf-8'))
http=[]
for r in mock:
    if r['layer']=='local_HTTP':http.append([r['problem'],f"LOCAL-P{r['problem']}-{r['seed']}",r['cleared'],f(r['virtual_time_s']/r['cleared']),f(r['runtime_s']),r['certificate']])
cost=''
for p in [3,4]:
    d=s['ablation']['主策略'][str(p)];cost+=f"问题{p}平均总时间中，移动占{100*d['move_time_s']/d['time_s']['mean']:.2f}%，检测占{100*d['measurement_time_s']/d['time_s']['mean']:.2f}%。"
cost+='因此优化路线和覆盖扫描比压缩几何计算时间更能降低任务虚拟耗时；C++的主要作用是让大量可复现实验与在线计算开销保持较小。'
bound=r'''按实现还可给出保守总预算。目标域外切多边形的顶点半径为 $R_p=1800\sec(\pi/64)=1802.171$ 米，覆盖网格最大半径为 $R_g=950\sqrt7=2513.464$ 米。第二测点半径不超过 $R_g+\sqrt{750^2+300^2}=3321.239$ 米；精确最小包围圆圆心在凸区域内，横移检测点半径不超过 $R_p+50$；光学外接矩形在任意一组正交轴上的投影均不超过 $R_p$，故其清除点半径不超过 $\sqrt2R_p$。统一向上取3322米覆盖全部动作位置。

全局至多31段移动，每个源在兜底前至多11段（2个第二测点加3轮各1清除、2检测），再计进入兜底的1段，共不超过223段长距离移动。near后的清除在原位置，不增加移动段。每源兜底内部至多107段，每段不超过28米。因此

$$L\le223\times6644+16\times107\times28=1529548\text{米}.$$

检测至多 $31\times20+16\times8=748$ 次；清除至多 $16\times(3+108)=1776$ 次，成功至多16次。含enter/exit的有效动作至多2526个。结合式(1)，

$$T\le1529548/5+6\times748+3\times1776+2\times16=315757.6\text{秒}<100\text{小时}. \tag{15}$$

该87.7104小时界非常宽松，只证明理想几何与合法响应下不会触及虚拟上限，并非平均性能估计。位置界使用“精确最小包围圆圆心位于凸集内”和外接矩形投影界；独立数学预审保留完整推导。'''
replacements={
 'DEV_TABLE':table(['开发配置','问题3平均总时间/秒','问题4平均总时间/秒'],dev),
 'Q2_TABLE':table(['a/米','b/米','离散最大半径/米','离散平均半径/米','首段路长/米'],q2),
 'MAIN_TABLE':table(['问题','平均总时间/秒','总时间P95/秒','平均单源/秒','单源均值95%区间','合并单源/秒'],main),
 'ABLATION_TABLE':table(['问题','对照','对照均时/秒','主策略节省/秒','配对节省95%区间','均时下降'],abl),
 'STRESS_TABLE':table(['压力设置','问题3全清除','问题4全清除','问题3单源/秒','问题4单源/秒','两问最大总时间/秒'],stress),
 'MOCK_TABLE':'以下六条专门标记为**本地HTTP演练**，仅借用题目表1的列含义。\n\n'+table(['问题','本地案例标识','清除数','平均时间/秒','桥接运行时间/秒','终止证书'],http),
 'COST_TEXT':cost,'BOUND_TEXT':bound,
 'REVIEW_TEXT':(ROOT/'review/审稿结论摘录.md').read_text(encoding='utf-8') if (ROOT/'review/审稿结论摘录.md').exists() else '数学与实现独立审查已完成；论文完整稿已生成，最终模拟评分与文字证据审查正在进行。其评分将与人工及官方评审明确区分。'
}
text=(ROOT/'论文撰写交接_模板.md').read_text(encoding='utf-8')
for k,v in replacements.items():text=text.replace('{{'+k+'}}',v)
assert '{{'not in text
(ROOT/'B题_论文撰写交接.md').write_text(text,encoding='utf-8')
print('Handoff generated:',len(text),'characters')
