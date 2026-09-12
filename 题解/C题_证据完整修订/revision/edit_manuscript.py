from pathlib import Path
import json,re
R=Path(__file__).resolve().parents[1];p=R/'main.tex';s=p.read_text()
s=s.replace('\\usepackage{caption}','\\usepackage{caption,float}')
s=s.replace('适用范围（D）','适用范围')
# Retain theorem classification only; remove repeated experiment badges.
s=s.replace('（C）','').replace('（C；','（').replace('（A）','').replace('（B）','')
s=s.replace('该数值证书对应本确定性模型和浮点精度。','该数值证书对应本确定性模型和浮点精度。')
s=s.replace('实时净需求。电池可以把当前富余挪到后面用，但效率、容量和功率限制了能挪多少。','实时净需求。储能将当前富余电量转移至后续时段，其转移规模受效率、容量和功率约束。')
s=s.replace('下层电池可以在看见当前净需求后再决定这度电现在用还是留着','下层电池在观测当前净需求后，权衡即时供能与未来库存价值')
s=s.replace('首末钉在','首末固定为').replace('共享计划贪心','场景共同合同贪心').replace('它不是每日闭合Markov。','')
s=s.replace('为区分不同性质的结论，正文用A、B、C、D分别标记数学命题、指定模型内的最优性或下界、实际数值实验，以及解释范围。写出的节省数字都属于C。','文中仅在理论命题处保留结论类型标记：A表示数学性质，B表示所声明近似模型内的最优性或下界；实验结果和适用范围直接用文字说明。')
# Explicit assumptions rather than hiding them in narrative.
anchor='\\section{假设、符号与信息结构}'
assumptions=r'''
\subsection{模型假设}
\begin{enumerate}
\item 附件功率按对应十分钟区间均值积分；电量统一在交流母线侧计量，内部库存单独递推。
\item 将题给90\%解释为充电和放电各自的转换效率；不额外引入题面未给的自放电、线路损耗和循环退化参数。
\item 不向外网售电，允许免费弃置母线富余；紧急购电无题外容量上限。
\item 采用退购退款后支付50\%违约费的主口径；另报告不退款口径的账单敏感性。
\item 合同只使用签约前已知信息；电池可观测本时段净需求，实际浮动电价在动作后用于结算。
\item 问题一主方案选定周期初值6000 kWh，并补充自由周期初值对照；问题二至四正式比较统一真实初末库存6000 kWh。
\end{enumerate}
\subsection{物理参数与符号}
'''
s=s.replace(anchor,anchor+assumptions)
s=s.replace('物理参数取自题目：十分钟一段，单向效率0.9，功率5,000 kW，库存介于1,200与10,800 kWh。','容量、功率与库存上下界取自题目；单向效率0.9采用上述解释。十分钟为一个控制时段，功率上限5,000 kW，库存介于1,200与10,800 kWh。')
# Overview figure at end introduction.
flow=r'''
\begin{figure}[H]\centering
\begin{tikzpicture}[node distance=5mm,box/.style={draw=teal!65!black,rounded corners,align=center,text width=11.2cm,minimum height=8mm,font=\small},>=Stealth]
\node[box] (a) {已实现历史与已发布光伏预报：构造合法预测};
\node[box,below=of a] (b) {完整成熟残差：生成净需求与价格的联合场景};
\node[box,below=of b] (c) {上层场景LP：签订或调整合同，保持信息因果性};
\node[box,below=of c] (d) {下层Markov/Bellman递推：估计未来库存价值};
\node[box,below=of d] (e) {每十分钟：观测净需求，选择并执行可行电池动作};
\node[box,below=of e] (f) {计算紧急购电与真实账单，库存连续传至下一时段};
\draw[->] (a)--(b);\draw[->] (b)--(c);\draw[->] (c)--(d);\draw[->] (d)--(e);\draw[->] (e)--(f);
\draw[->] (f.east)--++(.6,0)|-(a.east);
\end{tikzpicture}
\caption{预测、合同规划、实时价值反馈与闭环结算的总体框架}
\end{figure}
'''
s=s.replace(anchor,flow+'\n'+anchor)
# Explicit initial choice prior to Q1 equations.
a='\\section{确定性问题一：凸模型的基准验证}'
s=s.replace(a,a+'\n题目要求日初与日末库存相同，并未对该典型日另行固定周期库存。主方案参照附录的初始状态，选择两端均为6000 kWh；该值是本文的实施口径。另令周期初值参与优化，以检验这一选择的费用影响。\n')
s=s.replace('\\input{tables/q1bat.tex}','\\input{tables/q1bat.tex}\n\\input{tables/q1-cycle-revision.tex}')
# Predictions and billing empirical inserts.
s=s.replace('\\subsection{有限维因果扰动反馈}',r'\input{tables/prediction-revision.tex}'+'\n\\subsection{有限维因果扰动反馈}')
s=s.replace('\\subsection{同时充放电消元与紧急电量}',r'\input{tables/billing-revision.tex}'+'\n\\subsection{同时充放电消元与紧急电量}')
s=s.replace('\\input{tables/main.tex}','\\input{tables/main.tex}\n\\input{tables/strong-baseline.tex}')
s=s.replace('指定日期的合同见附录，实际充放电和连续紧急购电区间见配套结果工作簿。','附录完整列出四个指定日期的购电表、全天电量与费用、六个四小时充放电块、首末库存及紧急购电区间；工作簿提供逐时明细。')
s=s.replace('后一列说明：同样允许跨日，把电池从仿射响应换成库存价值反馈后，全年大约再少花60至76万元。','该比较表明，所实施Markov反馈闭环优于仿射库存响应闭环。')
s=s.replace('这样比的是预报本身，而不是“能不能改合同”。','该设计将预报内容与合同调整权限的作用分离。')
s=s.replace('\\fig{contracts}{问题三指定日的合同更新及紧急追索}{0.85}','\\fig{contracts-revision}{问题三2025年3月20日：合同更新与09:20--10:00紧急补购}{0.94}')
# Remove redundant SDDP derivation in body; complete derivation retained in appendix.
start=s.index('\\subsection{辅助继续价值的下界性质}');end=s.index('\\subsection{参数的作用及诊断}',start)
s=s[:start]+r'''\subsection{末值的模型选择作用}
辅助SDDP的状态包含库存和未交付合同，按两小时聚合、有限阶段独立噪声训练；其割的下界性质仅针对该辅助模型，证明置于附录。既有全年对照中SDDP末值未改善真实账单，因此未进入主策略。局部窗口中线性末值倍率影响很小，也不能据此将末值精细化列为本模型的主要贡献。保留原线性末值作为已冻结实现，并将零末值、倍率变化及SDDP作为模型选择的负结果，而不事后寻找效果较好的日期。 

'''+s[end:]
s=s.replace('\\IfFileExists{tables/gains.tex}{\\input{tables/gains.tex}}{}','\\input{tables/gains.tex}\n\\input{tables/gain-revision.tex}')
# Explicit strengths limitations generalization.
start=s.index('\\section{模型评价与结论}');end=s.index('\\section*{AI工具使用声明}',start)
s=s[:start]+r'''\section{模型优缺点与推广}
\subsection{模型优点}
模型用连续库存连接相邻日期，分别约束合同与实时动作的信息权限；利用费用凸性和一维库存值函数减少计算复杂度。全部费用依据逐时执行轨迹重算，并通过相同初末库存的对照分离跨日效应。强基线比较说明性能提升不只来自取消每日库存复位。
\subsection{局限与推广}
上层仿射库存响应单独使用时并不优于贪心控制，不能将上层策略形式本身视为已证实的收益来源。预测族较朴素、场景数有限，Markov状态压缩和固定名义合同值函数都是近似；增益界及退购解释的影响须分别报告。当前末值精细化缺乏稳定账单收益，故不增加主模型复杂度。完美信息参照同时改变信息与成交条件，不能把全部差距解释为算法损失。
如获得新的带发布时间戳预报或多年度样本，可在开发期比较条件场景和增强状态；电池退化、自放电及并网容量仅在参数有依据时作为独立扩展。新增模块须通过同终点闭环对照，而不能仅以预测误差或辅助优化目标的改善代替费用验证。
\section{结论}
四问以同一能量平衡和信息因果约束组织。问题一采用确定性LP；问题二以场景合同规划与库存价值反馈应对净需求不确定性；问题三按官方预报发布更新合同；问题四联合处理净需求与价格误差。334日固定初末库存下，四种机制费用分别为1384.42、1346.18、1465.46、1425.21万元。相对于同样允许跨日的贪心基线，改善仍成立；仿射库存响应单独使用及更精细末值未获得相同收益，说明主模型的有效性须由完整反馈闭环解释。

'''+s[end:]
s=s.replace('本参赛队在竞赛过程中使用了AI工具，主要用于语言润色、代码辅助和文稿核验，详细使用情况见支撑材料。','本稿为赛后研究参考。AI工具用于模型讨论、代码辅助、论文写作与审查；所有报告数值由本地或远程程序计算。使用情况与计算证据见支撑材料。')
# Dense result-centered abstract, final new numbers already computed by program.
start=s.index('微网调度同时受到');end=s.index('\\noindent\\textbf{关键词',start)
s=s[:start]+r'''针对微网购电合同先于实际需求确定、储能库存跨日传递的问题，建立上层合同滚动规划与下层电池价值反馈相结合的随机调度模型，统一处理预测误差、合同调整和紧急补购。

\textbf{针对问题一，}建立包含充放电损耗、功率和库存约束的确定性线性规划。选定首末库存6000 kWh时，日购电量为\textbf{59482.70 kWh}、费用为\textbf{35126.95元}；允许周期初值优化，一组最优初值为8550 kWh，费用降低\textbf{8.35元}。

\textbf{针对问题二，}用成熟历史误差生成场景，在合同信息约束下进行滚动规划，并用Markov动态规划决定实时充放电。2025年2—12月334日费用为\textbf{1384.42万元}，较每日闭合基线节省\textbf{33.78万元}，较同样跨日运行的贪心基线节省\textbf{20.24万元}。

\textbf{针对问题三，}在0、6、12、18时接入已发布光伏预报并调整未交付合同，费用为\textbf{1346.18万元}，较跨日贪心基线节省\textbf{23.13万元}；保持调约权限不变时，删除12时预报增加费用\textbf{17.93万元}。

\textbf{针对问题四，}以同一历史块保留净需求和价格误差的联合变化。日前、日内机制费用分别为\textbf{1465.46、1425.21万元}，较跨日贪心基线分别节省\textbf{15.29、22.89万元}。实际价格用于交付结算，规划仅使用当时可得预测。

主比较统一初始及年末库存6000 kWh，逐时供需、库存、功率与充放电互斥均通过核验。结论适用于给定年度和声明的退购结算规则；另一计费解释另行报告。仿射库存反馈和SDDP末值的负结果用于约束模型复杂度。

'''+s[end:]
p.write_text(s)
# Appendix must contain all runnable source files, plus added reproducible calculations.
a=R/'technical-appendix.tex';t=a.read_text();start=t.index('\\section{指定日期结果}');t=t[:start]+r'''\section{指定日期完整结果}
各表对应固定真实初末库存6000 kWh的同一334日主轨迹。表1格式同时报告最终合同量和合同费用；另列实际购电量（最终合同加紧急量）与含紧急费的总账单。表2的每个四小时块是分时动作累计，不表示同时充放电。表3合并连续非零紧急区间，数值零阈值为$10^{-6}$ kWh。
\input{tables/specified-q2.tex}
\clearpage\input{tables/specified-q3.tex}
\clearpage\input{tables/specified-q4_2.tex}
\clearpage\input{tables/specified-q4_3.tex}
\input{tables/repetition-revision.tex}
\clearpage\section{支撑文件与完整源程序}
源程序全文列于本附录；同名可运行文件同时保存在支撑材料中。原始附件放入inputs目录，安装依赖后按运行说明复算。新增审稿对照采用独立脚本和结果路径，不覆盖原已验证轨迹。
\input{support-files.tex}
\input{source-code.tex}
''';a.write_text(t)
print('Main and appendix revised')
