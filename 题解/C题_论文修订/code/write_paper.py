from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
s=(R/'main.tex').read_text()
s=s.replace('\\usepackage{graphicx,float,caption,fancyhdr,enumitem}','\\usepackage{graphicx,float,caption,fancyhdr,enumitem,tikz,fvextra}\n\\usetikzlibrary{arrows.meta,positioning}')
a=s.index('微网储能既承担');b=s.index('\\clearpage',a)
s=s[:a]+r'''微网购电的关键在于把提前签署的合同与随后实现的负荷、光伏和电价协调起来。电池库存跨日传递，使当日调度同时影响次日购电成本。本文以\textbf{连续库存、因果合同和实时价值反馈}为主线，建立跨日随机经济调控模型。

\textbf{针对问题一，}从能量平衡和充放电效率出发，证明免费弃电条件下可消去同时充放电，建立确定性线性规划。全天最优购电量为\textbf{59,482.70 kWh}，购电费为\textbf{35,126.95元}，日首末储电量均为6,000 kWh，原始与对偶目标之差小于$10^{-10}$元。

\textbf{针对问题二，}以完整成熟的历史残差块构造跨日情景，上层采用因果仿射策略样本平均近似规划，下层通过凸Markov动态规划按当前净负荷和库存选择连续动作。在2025年2—12月334日回放中，费用为\textbf{1,384.17万元}，较每日闭合基线节省\textbf{34.03万元}。保持仿射反馈及年末库存一致的单因素对照，进一步识别出\textbf{22.66万元}的跨日库存自由收益。

\textbf{针对问题三，}完整接入已发布24小时光伏预报，以原合同为基准统一核算增购、退购和紧急费用。334日费用为\textbf{1,345.92万元}，较每日闭合基线节省\textbf{36.88万元}。保持调约权限不变，全部现有预报较只用0时预报节省\textbf{31.69万元}；移除12时发布增加费用\textbf{17.93万元}，明确午间信息的调度价值。

\textbf{针对问题四，}用同一历史块联合生成净需求与价格情景，按预测价格决策、实际价格结算。日前及日内两种机制的334日费用分别为\textbf{1,465.21、1,424.94万元}，较各自每日闭合基线节省\textbf{35.85、43.23万元}。统一年末库存的仿射对照分别节省\textbf{27.30、33.36万元}，支持浮动电价下跨日协调的经济作用。

逐时轨迹通过供需、功率、库存和午夜连续性核验。结论对应给定年度、净额退购结算和既定信息结构；同末端对照分离库存终点影响，预报消融识别现有信息贡献，形成从物理可行性到费用收益的完整证据链。

\vspace{.6em}\noindent\textbf{关键词：}微网调控；跨日库存；因果仿射规划；凸随机动态规划；信息价值
''' +s[b:]
s=s.replace('不作为1月经济最优结果。','该共同初始化使各候选从相同的真实库存进入正式评价期。')
s=s.replace('夜间','夜间')
# derive contract economics
mark='不同日期各有自己的0时合同'
pos=s.index(mark)
s=s[:pos]+r'''式\eqref{eq:phi}由两种结算情况直接得到。当$r\ge q$时，原合同支付$pq$，增购支付$1.5p(r-q)$，合计$p(1.5r-0.5q)$；当$r<q$时，保留合同支付$pr$，退购部分支付$0.5p(q-r)$违约费，合计$p(0.5r+0.5q)$。两条直线在$r=q$相交，斜率由0.5上升为1.5，因此计费函数凸。例如$q=100$、$p=1$时，$r=80$的费用为90元，$r=120$为130元。该推导明确了本文采用的退购退款及最终净额口径。

''' + s[pos:]
s=s.replace('式\\eqref{eq:phi}与\\eqref{eq:shortage}都是仿射函数最大值，故用上图变量即可写成LP。',r'''式\eqref{eq:phi}与\eqref{eq:shortage}都是仿射函数最大值，故用上图变量即可写成LP。库存可达集合见图\ref{fig:feasible}，其斜带宽度由单步功率与效率确定；上下截断由电池容量确定。充入1 kWh内部电能需要$1/\eta$ kWh母线电能，释放后可供$\eta$ kWh，故完整往返效率为$\eta^2=0.81$。
\begin{figure}[H]\centering\includegraphics[width=.70\linewidth]{figures/feasible.pdf}\caption{单步可达库存：容量与充放电功率约束的几何解释}\label{fig:feasible}\end{figure}''')
s=s.replace('并满足库存递推和功率边界。由前述命题，无需互斥二元变量。',r'''完整约束为
\begin{equation}
\left\{\begin{aligned}
&q_t+b_t-c_t\ge\bar n_t,\quad E_{t+1}=E_t+\eta c_t-b_t/\eta,&&t=0,\ldots,143,\\
&0\le c_t,b_t\le M,\quad q_t\ge0,&&t=0,\ldots,143,\\
&E_{\min}\le E_t\le E_{\max},&&t=0,\ldots,144,\\
&E_0=E_{144}=6000.&&
\end{aligned}\right.
\end{equation}
能量盈余由免费弃电消纳，因而平衡式可写成供给不少于净需求。由前述命题，无需互斥二元变量。''')
s=s.replace('首末库存相同。\n\n\\section{成熟',r'''首末库存相同。求解器原始与对偶目标差为$7.28\times10^{-12}$元，等式残差为$9.09\times10^{-13}$ kWh；这两项检查分别验证目标最优性和能量递推精度。
\begin{figure}[H]\centering\includegraphics[width=.75\linewidth]{figures/q1state.pdf}\caption{典型日库存轨迹：在容量范围内完成日循环}\end{figure}

\section{成熟''')
# formal measurable information and flow
mark='\\subsection{跨日残差必须完整成熟}'
s=s.replace(mark,r'''\subsection{信息结构与两层控制}
记$\mathcal F_{a^-}$为签约前已经实现的历史、已发布预报、库存及现存合同。当前合同满足$q_a,r_a\in\mathcal F_{a^-}$；当前净需求揭示后，电池动作满足$(c_a,b_a)\in\sigma(\mathcal F_{a^-},n_a)$。浮动电价实值在本文信息结构下进入事后结算。图\ref{fig:flow}把三种信息时刻对应到具体动作。
\begin{figure}[H]\centering
\begin{tikzpicture}[node distance=7mm,box/.style={draw=teal!65,rounded corners,align=center,text width=10cm,minimum height=9mm,font=\small},>=Stealth]
\node[box] (a) {历史观测与当前正式发布 $\longrightarrow$ 因果预测、成熟联合残差};
\node[box,below=of a] (b) {每6小时：SAA规划合同与库存响应，保留跨日末值};
\node[box,below=of b] (c) {按交易权限签约或调约，重建固定合同下的Markov值函数};
\node[box,below=of c] (d) {每10分钟：观测净需求，最小化当前紧急费与未来库存费用};
\node[box,below=of d] (e) {执行单向充放电、补足缺口，按实际价格记账并继承库存};
\draw[->] (a)--(b);\draw[->] (b)--(c);\draw[->] (c)--(d);\draw[->] (d)--(e);
\end{tikzpicture}
\caption{合同先确定、净需求后揭示、库存连续继承的控制逻辑}\label{fig:flow}\end{figure}

''' +mark)
# numerical controls
s=s.replace('其每个线段有斜率及对应横向长度。','其每个线段有斜率及对应横向长度。将$W$的定义域限制在$[E_{\min},E_{\max}]$，将$h$的定义域限制在$[-\eta M,M/\eta]$，并在定义域外赋值$+\infty$，即可把全部功率和容量边界并入卷积。')
# typo escape python \e fine
s=s.replace('这里$N$按真正评估终点计算，不能将移动窗口末点或每日午夜当成全局终点。',r'''这里$N$按真正评估终点计算，中间午夜使用状态继承。全局6000 kWh对照在上层施加相应终端条件，下层以$1000|E-6000|$构造有限终端惩罚，再由式\eqref{eq:reach}确保实际轨迹达到终点；硬可达条件承担终点保证。''')
# explicit Q3 and 4 (before auxiliary)
s=s.replace('\\section{辅助SDDP末值与可核验的模型选型}',r'''\section{问题三与问题四的机制扩展}
\subsection{问题三：光伏发布与合同重配}
0时节点同时确定当日原合同$q_{d,t}$，6、12、18时节点对各自尚未交付时段确定生效合同$r_{d,t}$。一次修订保存最终合同量$r$；实际外网取电为$r+e$。原$q$作为全天计费基准保留。原合同、修订合同和紧急电构成不同经济功能：$q$锁定常规供给，$r$利用新信息重配，$e$承担已实现缺口的追索。

令$v_0$为发布前最后一段已观测光伏，$v_1,\ldots,v_{24}$为本次发布的整点预报。对位于相邻预报节点$h,h+1$之间的目标时刻，线性插值为
\begin{equation}
\widehat G(\rho+h+\theta)=(1-\theta)v_h+\theta v_{h+1},\quad 0\le\theta\le1.
\end{equation}
程序按目标区间右端点取值，所有已经发布的次日部分都参与规划。对新信息的经济评价固定调约权限，再比较保留或屏蔽某批预报后的完整闭环账单；这样费用变化对应信息内容的实际使用，而非新增交易机会。

\subsection{问题四：净需求与价格联合不确定性}
浮动价日前机制保留$r=q$，其场景目标为
\begin{equation}
\min\frac1S\sum_s\left[\sum_t p_{s,t}(q_{s,t}+5e_{s,t})+\widehat V_H(E_{s,H})\right].
\end{equation}
浮动价日内机制允许按发布节点修订$r$，以式\eqref{eq:upper}的$\phi(q,r)$计费。其余库存、功率、因果仿射规则与信息截断保持一致。预测电价用历史条件均值及同块残差生成，交付后使用附件4实际价格核算式\eqref{eq:bill}。

净需求较高时，若条件价格也较高，同样1 kWh短缺会产生更大的紧急费用。因此情景应保留需求与价格的联合变化，并把价格作为短缺项的系数，而不以紧急电量直接代替费用目标。下层$\bar p_{t,k}$体现当前净需求箱对应的条件价格，库存的边际保留价值随未来费用曲线改变。

\section{辅助SDDP末值与可核验的模型选型}''')
s=s.replace('通过真实账单选择线性末值主方案','按开发期规则选择线性末值主方案')
s=s.replace('共同轨迹跨日基线说明放开库存接口后的基础表现；跨日仿射说明上层响应规则的作用；', '共同轨迹基线与因果仿射规划分别代表共享计划和情景反馈两类上层结构；')
s=s.replace('因此作为主方案。模型选型落在可执行费用证据上。','与1月开发期预先确定的主方案一致。全年比较用于评价冻结方案。')
s=s.replace('\\subsection{统一终点后仍成立的跨日收益}',r'''\begin{figure}[H]\centering\includegraphics[width=\linewidth]{figures/savings.pdf}\caption{主方案较每日闭合基线的累计节省及七日移动块Bootstrap区间}\label{fig:savings}\end{figure}
334个配对日按连续7日为块进行10,000次移动块重采样，抽取完整块后截至334日，使用百分位95\%区间。四种机制的日均节省分别为1,019、1,104、1,073、1,294元，对应区间为$[827,1216]$、$[931,1253]$、$[882,1252]$、$[1077,1486]$元。该区间描述本回放期配对节省在七日相关结构假设下的重采样稳定性；比较双方的终点条件与表\ref{tab:annual}相同。

\subsection{统一终点条件下的跨日收益}''')
s=s.replace('\\subsection{经济收益与运行配比}',r'''\begin{figure}[H]\centering\includegraphics[width=.92\linewidth]{figures/waterfall.pdf}\caption{问题三较每日闭合基线的费用分项变化。负增量表示节省，正增量表示新增支出；首尾柱为总费用，纵轴采用局部范围。}\end{figure}
分项瀑布图将普通合同、增购、退购净额和紧急费用的变化相加，严格回到36.88万元总节省。其论证对象是完整账单的来源分解，各项按同一结算口径计算。

\subsection{经济收益与运行配比}''')
s=s.replace('本文又从四组主轨迹独立重算费用与库存。','本文又从四组主轨迹重算费用与库存，账单重算最大偏差小于$2\times10^{-9}$元，库存递推残差小于$1.2\times10^{-13}$ kWh，午夜跳变为零。')
s=s.replace('网格由321点改为161或641点时费用变化较小；',r'网格由321点改为161或641点时，七日费用相对变化分别为$-0.0058\%$、$+0.0107\%$，支持321点配置的数值稳定性；')
s=s.replace('\\clearpage\\section{结论}', '\\clearpage\\section{结论}')
# primary source official docs instead of unverified citation
s=s.replace(r'Dowson O, Kapelevich L. SDDP.jl: A Julia Package for Stochastic Dual Dynamic Programming[J]. INFORMS Journal on Computing, 2021, 33(1): 27--33. \url{https://doi.org/10.1287/ijoc.2020.0987}.',r'SDDP.jl. Here-and-now and hazard-decision[EB/OL]. \url{https://sddp.dev/stable/tutorial/decision_hazard/}. 访问日期：2026-09-11.')
s=s.replace('\\end{document}',r'''\label{bodyend}
\clearpage\appendix
\section{支撑材料与复算入口}
支撑材料以单独ZIP文件提供，目录及职责见表。原始赛题与附件使用题目提供版本；计算从同名附件读取。输出表中“调整购电量”表示最终生效量$r$，不与原计划$q$相加。
\begin{longtable}{p{4.4cm}p{9cm}}
\toprule 文件或目录&内容与用途\\\midrule
src/*.py、src/*.mjs & 数据读取、因果预测、LP与动态规划、SDDP、回放和结果导出的完整源程序。\\
review/*.py & 小树、因果边界、物理轨迹及原始对偶验证程序。\\
artifacts/ & 主费用、逐日配对数据、结果登记和重采样结果。\\
计算结果/result*.xlsx & 五份题定格式结果工作簿。\\
main.tex、tables/、figures/ & 完整论文、指定日期表及绘图结果。\\
code/ & 本文绘图、重采样及论文生成程序。\\
requirements-model.txt、复现.sh & 环境依赖及数值复算命令。\\
\bottomrule
\end{longtable}
安装依赖后运行\texttt{bash 复现.sh}可重算数值链；全文源程序见下附录。本文图表使用已完成回放轨迹重算，并以结果登记文件追溯；七日块Bootstrap使用随机种子20260911。跨平台执行需安装对应平台的HiGHS，工作簿导出需可用的artifact-tool Node模块。
\section{完整源程序}
下面按数据、模型、求解、输出、验证的文件顺序列出完整代码。代码中的内部路径均相对于项目目录，原始附件保持原名。
\fvset{fontsize=\fontsize{6.5}{8}\selectfont,breaklines=true,breakanywhere=true,numbers=left,numbersep=3pt,tabsize=4}
\input{code-listings.tex}
\end{document}''')
(R/'main.tex').write_text(s)
# listings all executable model and validation/export files
files=sorted((R/'src').glob('*.py'))+sorted((R/'src').glob('*.mjs'))+sorted((R/'review').glob('*.py'))
(R/'code-listings.tex').write_text('\n'.join('\\subsection{\\texttt{'+str(p.relative_to(R)).replace('_',r'\_')+'}}\n\\VerbatimInput{'+str(p.relative_to(R))+'}' for p in files))
(R/'compile.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nxelatex -interaction=nonstopmode -halt-on-error main.tex\nxelatex -interaction=nonstopmode -halt-on-error main.tex\n')
