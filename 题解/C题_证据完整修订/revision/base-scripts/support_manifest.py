from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parents[1]
files=[]
for folder in ['scripts','tables','figures','计算结果','reviews']:
 files += [p for p in (O/folder).iterdir() if p.is_file() and p.suffix in ['.py','.mjs','.tex','.png','.csv','.xlsx','.md','.json']]
files += list(O.glob('*.md'))+[O/x for x in ['revised-main.tex','technical-appendix.tex','source-code.tex','support-files.tex','fvextra.sty'] if (O/x).exists()]
files += [p for p in (O/'artifacts').rglob('*') if p.is_file() and p.suffix in ['.json','.npz'] and 'previews' not in p.parts and p.name!='delivery-manifest.json']
files=sorted(set(files))
manifest=[{'file':str(p.relative_to(O)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
(O/'artifacts/delivery-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
# Print the principal support contract; the JSON manifest enumerates every local file.
groups=[('计算结果/result1.xlsx','典型日结果'),('计算结果/result2.xlsx','固定价日前结果'),('计算结果/result3.xlsx','固定价日内结果'),('计算结果/result4-2.xlsx','变动价日前结果'),('计算结果/result4-3.xlsx','变动价日内结果'),('计算结果/q1_逐时完整策略.csv','典型日完整轨迹')]
for k in ['q2','q3','q4_2','q4_3']:
 groups += [(f'计算结果/{k}_逐时完整策略.csv','正式固定终点轨迹'),(f'计算结果/{k}_费用汇总.csv','逐日分项账单'),(f'计算结果/{k}_调整发布记录.csv','有效合同发布'),(f'计算结果/{k}_紧急购电.csv','连续紧急购电事件'),(f'artifacts/{k}.npz','同口径完整二进制轨迹')]
groups += [('artifacts/result-claims.json','所有论文数值登记'),('artifacts/delivery-manifest.json','完整文件名、大小与散列'),('claim-code-map.md','逐式证据映射'),('theory-audit.md','定理假设与范围'),('theorem-check.md','独立数学复审'),('code-consistency-review.md','独立实现复审'),('final-review.md','本轮评阅与版式核查')]
lines=[r'\begin{longtable}{p{10.8cm}p{3.4cm}}',r'\caption{主要支撑文件列表；完整散列清单见登记文件}\\',r'\toprule 文件 & 内容 \\ \midrule\endfirsthead',r'\toprule 文件 & 内容 \\ \midrule\endhead']
lines += [r'\small '+n.replace('_',r'\_')+r' & \small '+d+r' \\' for n,d in groups]
lines += [r'\bottomrule\end{longtable}']
(O/'support-files.tex').write_text('\n'.join(lines)+'\n')
