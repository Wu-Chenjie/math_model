"""Final mathematical/data review, scoped separately from source appendix/PDF QA."""
from pathlib import Path
import json,hashlib,subprocess,numpy as np
R=Path(__file__).resolve().parents[1];B=R.parent/'C题_跨日随机控制'
main=(R/'main.tex').read_text();app=(R/'technical-appendix.tex').read_text();checks=[]
rows=json.loads((R/'revision/results/strong-baseline.json').read_text());data=np.load(R/'artifacts/data.npz')
for row in rows:
 k=row['kind'];A=dict(np.load(R/f'revision/results/{k}_cross_baseline_fixed.npz'));M=dict(np.load(B/f'artifacts/global-terminal/{k}_markov_mpc.npz'))
 bills=[]
 for name,a in [('cross_greedy',A),('main',M)]:
  q,r,e,p,c,d,w,E=[a[x] for x in ['q','r','emergency','price','c','d','spill','state']]
  assert np.array_equal(a['days'],np.arange(31,365)); assert E[0,0]==6000 and abs(E[-1,-1]-6000)<1e-6
  assert abs(E[1:,0]-E[:-1,-1]).max()<1e-6
  assert abs(np.diff(E,axis=1)-.9*c+d/.9).max()<1e-6
  assert abs(r+e+d-c-w-(data['load'][a['days']]-data['pv'][a['days']])/6).max()<1e-6
  assert np.minimum(c,d).max()<1e-6 and E.min()>=1200-1e-6 and E.max()<=10800+1e-6 and max(c.max(),d.max())*6<=5000+1e-6
  bills.append((p*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0)+5*e)).sum(1))
 diff=bills[0]-bills[1]
 assert abs(diff.sum()-row['saving'])<1e-6
 rng=np.random.default_rng(20260911);starts=rng.integers(0,328,size=(10000,48));inds=(starts[:,:,None]+np.arange(7)).reshape(10000,-1)[:,:334]
 ci=np.quantile(diff[inds].sum(1),[.025,.975]);assert np.max(abs(ci-row['saving_95ci']))<1e-6
 assert f'{row["saving"]/10000:.2f}' in main
 checks.append({'kind':k,'status':'PASS','bill':float(bills[1].sum()),'saving':float(diff.sum()),'bootstrap_95ci':ci.tolist()})
findings=[]
def add(id,where,msg,required=True):findings.append({'id':id,'location':where,'message':msg,'required':required})
if '图示9月23日' in main and '2025年3月20日' in main:add('F1','main.tex:官方预报图前段','图前正文仍称9月23日，图题已为3月20日，须改为同一日期。')
if '本稿数值均对应式' in main:add('F2','main.tex:合同结算凸性末段','已补另一计费解释与敏感性表，不应再称本稿全部数值均按原phi；应限定为主结果。')
if any(x in main for x in ['（B/D）','（B/C/D）']):add('F3','main.tex:上层定位/参数表题','仅A/B定义后仍有B/D、B/C/D残留，用户意见15尚未处理完整。')
if '手里这度电' in main:add('F4','main.tex:库存反馈节开头','仍有用户点名的口语表达，意见16未完整处理。')
if '独立声明的SeedSequence' in app and not all(z in app for z in ['原每日闭合基线','default\\_rng(20260911)','共享相同']):add('F5','technical-appendix.tex:移动块实现','新增强基线四问均default_rng(20260911)，与每机制独立SeedSequence笼统表述不符；区分原对照与新增对照，注明共同索引不影响各边际区间。')
add('L1','tables/gain-revision.tex','有效列剔除和界限20测试只覆盖一月七日，不能视为已给出全年有效列触边比例。当前正文明确限制范围，属于可接受但应保留的局限。',False)
check17={str(i):'ADDRESSED_IN_CONTENT' for i in range(1,18)}
check17.update({'1':'CONTENT_CHECKED_RENDER_PENDING','2':'SOURCE_APPENDIX_SEPARATE_REVIEW_PENDING','7':'DEVELOPMENT_SCOPE_ONLY_DISCLOSED','10':'NEEDS_TEXT_DATE_FIX' if any(f['id']=='F1' for f in findings) else 'ADDRESSED_IN_CONTENT','15':'NEEDS_LABEL_CLEANUP' if any(f['id']=='F3' for f in findings) else 'ADDRESSED_IN_CONTENT','16':'NEEDS_LANGUAGE_CLEANUP' if any(f['id']=='F4' for f in findings) else 'ADDRESSED_IN_CONTENT','17':'PDF_RENDER_REVIEW_PENDING'})
pdf_checks={}
if (R/'main.pdf').exists():
 abstract=subprocess.check_output(['/opt/homebrew/bin/pdftotext','-f','1','-l','1','-layout',str(R/'main.pdf'),'-'],text=True)
 body=subprocess.check_output(['/opt/homebrew/bin/pdftotext','-f','1','-l','23','-layout',str(R/'main.pdf'),'-'],text=True)
 expected=['1,384.42','1,346.18','1,465.46','1,425.21','20.24','23.13','15.29','22.89','35,126.95','17.93']
 for v in expected:assert v in abstract,('abstract missing',v)
 for v in ['35118.60','14073209.01','14907515.48','345349.60','384732.76','8550','8.35','33.78','36.62','35.60','42.96']:assert v in body,('body missing',v)
 pdf_checks={'status':'PASS_NUMERICAL_TEXT_ONLY','abstract_values':expected,'body_values':['35118.60','14073209.01','14907515.48','345349.60','384732.76'],'pdf_sha256':hashlib.sha256((R/'main.pdf').read_bytes()).hexdigest(),'visual_layout_checked':False}
files=[R/'main.tex',R/'technical-appendix.tex',*sorted((R/'tables').glob('*revision.tex')),R/'tables/strong-baseline.tex',R/'revision/results/strong-baseline.json',R/'revision/numeric-audit/q1-billing-audit.json',R/'revision/numeric-audit/january-billing-independent.json']
report={'status':'NEEDS_EDITORIAL_CORRECTION' if any(f['required'] for f in findings) else 'PASS_MATH_AND_DATA_SCOPE_ONLY','review_scope':'Independent mathematics, causal/terminal/billing interpretation, recomputed strong-baseline trajectories/bills/bootstrap and numeric insertions. Does not approve unfinished source appendix or unrendered final PDF.','model_recompute_blockers':[],'checks':checks,'pdf_numerical_text':pdf_checks,'findings':findings,'seventeen_items':check17,'pending':['Full source-code appendix completeness and executable packaging','Final PDF per-page rendering/layout verification'],'hashes':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(R/'revision/final-math-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
s='# 独立数学与控制终稿审查\n\n状态：'+report['status']+'。本报告不替代尚未完成的源码附录和PDF渲染验收。\n\n'
s+='已重新读取四种同初末6000主轨迹和新增跨日贪心，独立核对334日、母线平衡、库存递推、午夜连续、功率与充放电互斥；重新计算全部账单和10000次七日块区间。主摘要四问费用与新增节省相符。Q1周期初值、另一计费公式及其一月重规划与独立数值证据一致。当前没有需要回到模型阶段重算的已发现错误。\n\n'
s+='PDF第1页摘要核对四问总费与跨日贪心主对照；每日闭合33.78至42.96万元作为跨日复位附加效应保留在摘要末段与正文主表。8550 kWh/8.35元的周期初值对照保留在正文。此检查只核对数值文本，不替代页面视觉验收。\n\n'
s+='数学结构检查：合同上图、同时充放电消元、可达域、有限紧域凸PWL卷积、实际反馈与硬终端投影的区分均有充分边界；未发现把辅助SDDP下界冒充原问题因果下界，或把完美信息差额冒充可实现算法损失的论断。Jan开发选型回顾性与正式区间冻结性已区分。\n\n'
for f in findings:s+=f'- {f["id"]}（'+('需修改' if f['required'] else '已披露局限')+f'）：{f["location"]}。{f["message"]}\n'
s+='\n17项逐项状态见JSON。指定日期结果已包含全天合同/实际购电费用与电量、六个四小时充放电块、两端库存及紧急区间；源代码和最终PDF仍需另行完成检查，不能给整篇无条件PASS。\n'
(R/'revision/final-math-review.md').write_text(s)
print(json.dumps({'status':report['status'],'findings':findings,'checks':checks},ensure_ascii=False,indent=2))
