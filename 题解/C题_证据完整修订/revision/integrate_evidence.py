from pathlib import Path
import json,shutil,re
R=Path(__file__).resolve().parents[1];T=R/'tables'
f=(R/'revision/numeric-audit/q1-billing-tables.tex').read_text();parts=f.split('\\begin{table}')
(T/'q1-cycle-revision.tex').write_text('\\begin{table}'+parts[1]+r'''
自由周期模型仅将固定边界替换为$E_0=E_{144}$，并令两端库存共同满足$[1200,10800]$的容量范围，仍是线性规划。一组最优周期起点为8550 kWh，费用35118.60元，比固定6000少8.35元；最优周期起点不据此宣称唯一。前者对应可选择周期库存的设计，后者对应给定初始状态的实施，不能把改变实际起点库存视为免费操作。
''')
(T/'billing-revision.tex').write_text(r'''
\paragraph{另一种违约解释的对照}
若原计划费照付，再对退购加收50\%违约费，则应改为
\begin{equation}
 \phi_{+}(q,r)=q+1.5(r-q)^++0.5(q-r)^+,
 \qquad \phi_{+}(q,r)-\phi(q,r)=(q-r)^+.
\end{equation}
以下将同一334日主轨迹按两种规则重计费，以隔离口径变化；它不是新口径下重新优化的年度最优费用。
'''+ '\\begin{table}'+parts[2]+r'''
在非负价格、免费且不受限的弃电条件下，将$r<q$改为$r'=q$、保持原电池动作并增加弃电$q-r$，物理平衡不变，新口径费用减少$0.5p(q-r)$。因此该条件下总存在不退购的最优动作，结论不覆盖负价或弃电受限情形。

另在1月25--31日保持初末6000 kWh、预测和权限一致，改变上层计费上图并重新滚动执行：问题三新口径费用345349.60元，较原策略直接重计费的350544.87元少5195.27元；问题四日内为384732.76元，较390984.78元少6252.02元。新策略的退购量均为数值零。这是开发窗口的计费敏感性，不替换主口径全年结果。
''')
forecast=(R/'revision/prediction-control/forecast-metrics.tex').read_text()
(T/'prediction-revision.tex').write_text(r'''
\paragraph{预测误差与可复核对照}
用MAE和RMSE分别衡量平均绝对偏差及较大误差：
\begin{equation}
 \mathrm{MAE}=N^{-1}\sum_i|y_i-\widehat y_i|,
 \quad \mathrm{RMSE}=\sqrt{N^{-1}\sum_i(y_i-\widehat y_i)^2}.
\end{equation}
'''+forecast+r'''
表中正式期是冻结预测族后的逐日评价，不用其误差重新选型；开发期分数属于回顾性选择窗口。按四个合法发布点分别评估随后六小时，历史修正与官方预报下的净需求MAE分别为264.29和207.41 kW。预测族较简单是模型局限；完美信息费用差同时含交易与控制差异，不能单独用来诊断预测器。
\begin{figure}[H]\centering\includegraphics[width=.95\linewidth]{revision/prediction-control/forecast-vs-actual.pdf}\caption{冻结预测与实际轨迹对照；图中各预报遵循其发布时刻}\end{figure}
''')
g=(R/'revision/prediction-control/gain-diagnostic.tex').read_text()
(T/'gain-revision.tex').write_text(g+r'''
补充诊断在1月25--31日逐列检查约束矩阵与目标中的精确零列，将其从有效反馈分母剔除。两种界限下有效列触边均为零；问题三费用相差14.47元，仅0.00423\%，另三问不变。放宽界限可能影响非唯一最优解及浮点择优，不据此宣称策略类扩张产生了稳定收益，故不修改冻结的界限10。此表是开发期诊断，不能将其有效列触边比例外推为全年比例。
''')
(T/'repetition-revision.tex').write_text(r'''
\paragraph{重复合同数值核验}
问题三6月21日18时与20时的原合同，以及9月23日12时与14时原合同，问题四日内对应两对值，均由原数组直接提取。对相关规划LP重新求解，与保存合同一致；四对中三对全精度相等，另一对相差$3.55\times10^{-15}$ kWh。当前待签合同的场景反馈增益被禁用，因此不能把这些重复值归因为当日共享反馈增益。它们是所求LP的数值解特征，不是排版复制；表内仍保留真实结果，不人为扰动数值。
''')
rows=json.loads((R/'revision/results/strong-baseline.json').read_text());names=['问题二','问题三','问题四日前','问题四日内'];lines=[]
for name,x in zip(names,rows):lines.append(f"{name} & {x['baseline_total']/1e4:.2f} & {x['main_total']/1e4:.2f} & {x['saving']/1e4:.2f} & {x['saving_pct']:.2f}\\% & [{x['saving_95ci'][0]/1e4:.2f},{x['saving_95ci'][1]/1e4:.2f}] \\\\")
(T/'strong-baseline.tex').write_text(r'''\begin{table}[H]\centering\small
\caption{更强基线：同初末6000 kWh的跨日贪心与主策略（万元）}
\begin{tabular}{lrrrrr}\toprule
机制&跨日贪心&主策略&节省&降幅&7日块95\%区间\\\midrule
'''+ '\n'.join(lines)+r'''
\bottomrule\end{tabular}\end{table}
跨日贪心采用场景共同合同与即时电量平衡反馈，保留中间午夜连续性，仅在真正年末恢复6000 kWh。主策略相对该基线节省15.29至23.13万元，降幅1.03\%至1.69\%，且四组七日块重采样下界均为正。这是在同样允许跨日的条件下，合同规划与库存反馈整体框架相对贪心执行的差额，不能与主表每日闭合基线的节省相加，也不能把全部差额归因于单独一层。
''')
# Updated common January initialisation, preserve historical evidence as alternative.
p=R/'technical-appendix.tex';s=p.read_text();a=s.index('\\subsection{一月公共初始化账单}');b=s.index('\\subsection{固定真实终点数据链}',a)
s=s[:a]+r'''\subsection{一月因果公共初始化}
首日无前一完整日数据，保留库存6000 kWh并由紧急购电满足缺口；1月2日至31日只使用前一完整日的负荷与光伏构造合同，以每日闭合的贪心电池策略执行，不使用1月31日才选定的预测器。所有候选共用该初始化轨迹，每日末库存6000 kWh，故2月1日的库存和可用历史与原正式回放完全相同。预测使用的负荷、光伏和电价不受该初始化动作影响，正式334日输出无需改变。
\begin{table}[H]\centering\small\caption{一月公共初始化账单（万元，不进入正式评价）}
\begin{tabular}{lrr}\toprule
电价&原全月应急初始化&因果预测与闭合贪心初始化\\\midrule
固定价&945.64&294.07\\
浮动价&1064.20&335.38\\\bottomrule\end{tabular}\end{table}
原初始化保留为历史复现记录，修订稿采用新公共初始化作为完整运行年的实施说明。该比较不是正式期策略收益；首日仍因缺少历史而采用应急方案，后续日不虚构过去样本。

'''+s[b:];p.write_text(s)
# Sync authoritative fixed-end workbooks and CSVs from specified base.
base=Path('/Users/wuchenjie/Downloads/math-model-theory-59af4e0/题解/C题_跨日随机控制/theory_revision')
old=R/'计算结果';arc=R/'revision/superseded-start/计算结果'
if not arc.exists():shutil.move(str(old),str(arc));shutil.copytree(base/'计算结果',old)
print('evidence integrated')
