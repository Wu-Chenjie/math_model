from pathlib import Path
import shutil,json
R=Path(__file__).resolve().parents[2];D=R.parent/'C题_远端结果修订/review'
for n in ['restoration-control-diagnostics.md','restoration-control-diagnostics.json','restoration_control_diagnostics.py']:
 shutil.copy2(D/n,R/'review'/n)
s=(R/'main.tex').read_text()
s=s.replace('库存价值反馈相对跨日仿射还可再节省','库存价值反馈相对跨日仿射节省').replace('Markov反馈相对跨日仿射再节省','Markov反馈相对跨日仿射节省')
s=s.replace('三种块长的配对重采样区间均位于正值侧，11个评价月份均累计节省。','相对跨日贪心，三种块长的配对重采样区间均位于正值侧，11个评价月份均累计节省。')
s=s.replace('主结果以跨日贪心为对照；每日闭合基线只用来说明午夜强制复位的附加效应。','主结果以跨日贪心为对照；每日闭合贪心作为附加参照，午夜复位的单因素作用由同一仿射框架的配对消融识别。')
s=s.replace('图中的分项变化均以各自每日闭合基线为参照','图中的分项变化均以各自跨日贪心基线为参照')
s=s.replace(r'\fig{decomposition}',r'\fig{decomposition-primary}')
s=s.replace('分解图的论证职责是解释主表账单变化，不另立与费用目标无关的竞赛指标。','以问题三为例，原合同费用减少25.63万元，增购和退购净额合计再减少1.48万元，紧急费用增加3.98万元，净节省23.13万元。该策略通过联合安排合同与库存降低总账单；紧急费增支是已计入净收益的成本。')
s=s.replace('令每日配对差为每日闭合基线费用减主策略费用：','以跨日贪心账单减主策略账单定义每日配对差，两者均保持相同真实初末库存和中间午夜连续：')
s=s.replace(r'\input{tables/bootstrap.tex}',r'\input{tables/bootstrap-primary.tex}').replace(r'\input{tables/stability.tex}',r'\input{tables/stability-primary.tex}').replace(r'\fig{bootstrap}',r'\fig{bootstrap-primary}')
s=s.replace('日级仍有负费用差，表中如实给出正负日数；优化对象是整个运行期账单，连续库存允许在某日补能以服务后日。','日表同时报告节省与增支日期；连续库存允许在某日补能以服务后日，月度累计与运行期总账单衡量这种跨日安排的整体效果。')
s=s.replace('这些区间是单年度时间稳定性诊断，不是新年份费用保证；季节变化及有限年份会限制重采样的外推解释。','这些区间用于本年度时间稳定性诊断，跨年度效果需由新增年份的顺序回放评价。')
s=s.replace('既有自由终点同口径全年对照中SDDP末值未改善真实账单，因此未进入主策略。','按已冻结的开发期账单规则，主策略采用线性末值；既有自由终点同口径全年SDDP对照未降低真实账单，两者分别承担选型和补充评价职责。')
s=s.replace('机制消融表明，仿射合同规划需要与库存价值反馈共同使用：','在已比较候选中，因果合同规划与Markov库存价值反馈的组合取得主表费用优势：')
s=s.replace('强基线比较说明性能提升不只来自取消每日库存复位。','在共同允许跨日的条件下，主策略节省15.29至23.13万元，量化了合同规划与库存价值反馈的联合收益。')
section=r'''
\subsection{规划时域与预报融合的独立诊断}
延长前瞻会增加可见供需，但也改变成熟历史池、末值取价区间及规划边界，因此应由相同结算和真实终点下的闭环对照评价。固定场景、反馈与预报权重，分别比较第二个午夜、固定48小时、固定72小时三种视域，完整费用见附录。48小时延长至72小时，四种机制费用分别变化为节省2.57万元、增支1.13万元、节省6.12万元及节省0.81万元。时域作用随合同权限和电价机制而变；问题二相对两午夜视域的增量日均节省78.52元，七日块区间为$[-101.14,288.44]$元/日，尚不足以支持稳定正增益。该组事后诊断保留完整正负结果，不据评价期账单重新选择主配置。

对光伏官方预报与历史预测，进一步以配对误差二阶矩解释融合权重。两个一月窗口的样本MSE最优权重分别为0.8341和0.7617；0.75在预设离散候选中取得最低开发期MAE。其依据是预测层的内部开发比较，年度经济评价还需同时计入合同调整与紧急购电。相关推导、误差矩和选择范围见附录；主结果、预报删减实验及结果工作簿统一采用原两午夜视域和已发布官方预报权重1。
'''
s=s.replace(r'\section{模型评价与推广}',section+'\n'+r'\section{模型评价与推广}')
(R/'main.tex').write_text(s)
a=(R/'technical-appendix.tex').read_text()
a=a.replace('新增跨日贪心对照在各机制均使用default\\_rng(20260911)，从而共享相同的七日块抽样索引；两套区间分别报告，不混用随机数约定。','主文跨日贪心对照对各机制、各块长分别重置default\\_rng(20260911)，同一块长的四机制共享抽样索引；3、7、14日块各重复10,000次。原每日闭合对照作为补充统计单独登记。')
a=a.replace(r'\input{tables/monthly.tex}',r'\input{tables/monthly-primary.tex}')
a=a.replace('修订稿采用新公共初始化','本文采用因果公共初始化')
a=a.replace('当前修订重新计算正式轨迹','正式轨迹独立重算')
idx=a.index(r'\clearpage'+ '\n'+r'\section{指定日期完整结果}')
a=a[:idx]+r'\input{tables/nextgen-diagnostics.tex}'+'\n'+a[idx:]
(R/'technical-appendix.tex').write_text(a)
x=json.loads((R/'review/restoration-control-diagnostics.json').read_text());ks=['q2','q3','q4_2','q4_3'];labs=['问题二','问题三','问题四日前','问题四日内']
t=r'''\subsection{固定时域的闭环对照与边界状态}
下表每项均来自本地完整334日轨迹，统一真实初末6000 kWh，保持预报权重1、28日窗口、7条等权场景、321库存网格与三箱Markov反馈。第二个午夜视域随重规划时刻取48、42、36、30小时，固定视域则分别取48或72小时，评价终点统一截断。
\begin{table}[H]\centering\small
\caption{同配置下的时域诊断（万元）}
\begin{tabular}{lrrrr}\toprule
机制 & 第二个午夜 & 固定48小时 & 固定72小时 & 48至72小时节省\\\midrule
'''
for k,l in zip(ks,labs):
 d=x['annual'][k];t+=l+''.join(f' & {d["runs"][m]["cost_yuan"]/10000:.2f}' for m in ['midnight','fixed48','fixed72'])+f' & {d["comparisons"]["fixed48_to_fixed72"]["saving_yuan"]/10000:+.2f}'+r' \\'+'\n'
t+=r'''\bottomrule\end{tabular}\end{table}
改变时域还会改变完整成熟残差的可用集合和末值定价时段，因此该表识别配置变化的闭环总效应。固定72小时在6、12、18时起算时，规划末点落在日内；完整继续状态应包含未交付合同，而当前实现用库存线性末值近似。实际年度账单覆盖全部交付，这一近似影响规划继续价值。上述时域对照同时改变历史池和末值时段，不能独立量化边界近似误差；其识别需要在相同72小时条件下增加完整合同继续状态的匹配回放。主策略的滚动末点位于午夜。

问题二固定72小时相对两午夜视域，334日节省26,225.00元，日均78.52元。3、7、14日块95\%区间分别为$[-122.81,295.64]$、$[-101.14,288.44]$、$[-74.14,285.42]$元/日；节省日156、增支日177、近零日1，正累计月份5个。区间跨零表示该年度增量证据尚不足以确认稳定正收益，不表示真实效果已被证明为零。该诊断对应固定72小时候选，不替代正文的强跨日贪心对照。

\subsection{预报融合的二阶矩推导与开发诊断}
记官方和历史预测误差为$e_O,e_H$，融合误差为$e_\beta=\beta e_O+(1-\beta)e_H$。假设二阶矩有限，令
\begin{equation}
 A=\E[e_O^2],\quad B=\E[e_H^2],\quad C=\E[e_Oe_H],\quad D=A+B-2C.
\end{equation}
则
\begin{equation}
 \E[e_\beta^2]=B+2(C-B)\beta+D\beta^2,
 \qquad D=\E[(e_O-e_H)^2]\ge0.
\end{equation}
当$D>0$时，凸二次式在$[0,1]$的最小点为
\begin{equation}
 \beta^*=\operatorname{proj}_{[0,1]}\frac{B-C}{D}.
\end{equation}
证明由求导及闭区间投影直接得到。当$D=0$时，两误差几乎处处相等，所有权重具有相同MSE。二阶矩包含偏差平方，不能在有偏预测下直接以方差替代。将期望替换为同一组配对段平均，可得到对应样本MSE的最优权重。

\begin{table}[H]\centering\small\setlength{\tabcolsep}{3pt}
\caption{配对光伏误差矩与样本最优权重（误差单位kW）}
\begin{tabular}{lrrrrrr}\toprule
一月窗口 & 段数 & $A$ & $B$ & $C$ & $D$ & $\widehat\beta^*$\\\midrule
'''
for name,label in [('forecast_development_Jan15_24','15至24日'),('controller_development_Jan25_31','25至31日')]:
 d=x['moments'][name];t+=label+f' & {d["paired_slots"]}'+''.join(f' & {d[v+"_kw2"]:.2f}' for v in 'ABCD')+f' & {d["beta_star_sample_mse"]:.4f}'+r' \\'+'\n'
t+=r'''\bottomrule\end{tabular}\end{table}
每个0、6、12、18时原点预测后续36段，每个目标在所属窗口计入一次。15至24日的离散候选权重为0、0.25、0.5、0.75、1，MAE分别为96.68、75.89、59.42、50.50、52.04 kW；因此0.75的选取具有该候选集的开发期MAE依据。25至31日中0.75的MSE为21,130.50 kW$^2$，样本最优权重0.7617对应21,124.30 kW$^2$，两者接近。

历史预测族已用1月15至31日选型，因此两个窗口均属于内部开发诊断；按原点截断未来输入不能消除预测族选型的日期重叠。这里不使用2至12月样本估计融合矩，也不将样本MSE最优权重解释为无偏留出估计或账单最优权重。全年账单受净需求尾部、合同调整费与库存约束共同影响，预测误差降低的经济作用需由固定时域下的完整配对执行验证。
'''
(R/'tables/nextgen-diagnostics.tex').write_text(t)
# Code appendix includes all new reproducible analysis; original production listing preserved.
f=R/'source-code.tex';z=f.read_text();z+=r'''
\subsection*{\texttt{revision/restore/build\_primary\_evidence.py}}
\compactcode{revision/restore/build_primary_evidence.py}
\subsection*{\texttt{review/restoration\_control\_diagnostics.py}}
\compactcode{review/restoration_control_diagnostics.py}
''';f.write_text(z)
