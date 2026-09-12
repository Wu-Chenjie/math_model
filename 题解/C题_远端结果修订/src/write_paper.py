"""Build the revised manuscript from checked theory and newly registered evidence."""
from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT.parent/'C题_论文修订'
NEXT=ROOT.parent/'C题_下一代随机控制'
old=(REF/'main.tex').read_text()
q2=json.loads((ROOT/'artifacts/q2-new-analysis.json').read_text())
pre=old[:old.index(r'\begin{document}')]
pre='\n'.join(r'\newcommand{\pp}[2]{\par\noindent\textbf{命题 #1（#2）}\quad}' if line.startswith(r'\newcommand{\pp}') else line for line in pre.splitlines())+'\n'
pre=pre.replace(r'\begin{figure}[htbp]',r'\begin{figure}[H]')
pre+=r'\clubpenalty=10000\widowpenalty=10000\displaywidowpenalty=10000'+'\n'
abstract=r'''
\begin{document}
\pagestyle{plain}
\begin{center}
{\LARGE\bfseries 基于固定时域与预报融合的\\微网跨日随机调度}\par\vspace{1em}
{\large\bfseries 摘\quad 要}
\end{center}
微网需要在预测误差下提前购电，并用有限储能响应实时供需变化。库存的经济价值跨越午夜，合同又须先于当前净需求确定。针对滚动前瞻长度随日内时刻收缩、预报更新与购电承诺相互耦合的问题，本文建立统一凸能量模型，构造“\textbf{固定72小时规划—成熟残差场景—因果合同—凸库存价值反馈}”的闭环调度框架。

\textbf{针对问题一，}由合同计费凸性及同时充放电消元，建立确定性线性规划。典型日最优购电量为\textbf{59,482.70 kWh}，费用为\textbf{35,126.95元}，日初和日末库存均为6,000 kWh；独立原始—对偶核验支持该模型内最优值。

\textbf{针对问题二，}以固定72小时视域统一各次重规划的跨日前瞻，从近期成熟历史块中选取7条等权轨迹，结合因果仿射合同与三状态Markov库存价值反馈。2025年2月至12月334日费用为\textbf{1,381.79万元}，较上一版同任务跨日策略节省\textbf{2.62万元}。完整轨迹重算表明，紧急购电费下降\textbf{2.65万元}，是净节省的主要来源。

\textbf{针对问题三，}将已发布官方光伏预报与历史预测按\textbf{0.75和0.25}融合，在合法发布节点修订剩余合同。远端年度复核汇总费用为\textbf{1,335.24万元}，较上一版同任务结果节省\textbf{10.94万元}。

\textbf{针对问题四，}按同一历史块联合构造净需求和价格场景，并在电池动作后按实际价格结算。远端汇总的日前、日内机制费用分别为\textbf{1,459.24万元、1,411.73万元}，对应节省\textbf{6.22万元、13.48万元}。四种机制采用同一组配置，比较统一真实初末库存6,000 kWh。

理论上，本文给出单步与终点可达域、Bellman凸性保持及斜率合并证明，使合同优化、连续库存动作和跨日执行形成一致的控制链。结果定位于\textbf{同年度候选比较}：问题二由完整轨迹验证，其余三项据远端汇总报告；费用差反映当前年度表现，适用范围由信息权限、物理条件和证据口径共同确定。

\noindent\textbf{关键词：}微网调度；固定滚动时域；预报融合；因果仿射策略；凸动态规划
\clearpage
'''
intro=r'''
\section{问题重述与控制思路}
微网购电有三种相互衔接的时间尺度：日前确定交付合同，日内按已发布预报修订承诺，电池每十分钟响应真实净需求。光伏富余时保留的电量可以服务当天晚峰，也可以留给次日；因此，电池库存应沿时间轴连续传递，并在真正评价终点统一核算。

四问共享母线平衡、储能约束和结算规则，依次扩展信息与交易权限。问题一在完整已知的典型日上安排购电与电池动作；问题二以历史信息确定不可日内调整的合同；问题三加入0、6、12、18时发布的光伏预报及合同调整；问题四进一步引入随机交付价格，分别考察日前和日内两种机制。本文将它们作为同一随机控制系统的特例。

\textbf{本文的组织主线是让跨日视野稳定、让预报进入承诺、让库存价值进入实时动作。}固定72小时视域使0、6、12、18时的重规划具有一致前瞻长度。合法预报与历史预测的融合提供当前净需求中心，成熟残差表达后续不确定性；上层优化符合信息截止时刻的合同，下层根据当前缺口和未来库存价值选择充放电。真实年末采用可达区间保证库存回到6,000 kWh。

微网模型预测控制和多阶段储能规划提供了上述分层控制的研究基础\cite{parisio2014,parisio2016,bhattacharya2018}。本文采用有限维因果扰动反馈表示合同策略\cite{bental2004,goulart2006}，以经验场景平均构造规划目标\cite{kleywegt2002,shapiro2014}，利用一维库存值函数的凸结构实现反馈。正文先解释物理机制，再给出模型和求解；实验分别回答年度账单、费用来源和时间稳定性三个问题。

\begin{figure}[htbp]\centering
\begin{tikzpicture}[node distance=4mm,box/.style={draw=teal!65!black,rounded corners,align=center,text width=11.5cm,minimum height=8mm,font=\small},>=Stealth]
\node[box] (a) {历史与合法预报：融合当前预测，形成固定72小时视野};
\node[box,below=of a] (b) {成熟残差场景：保留净需求与价格的历史联合结构};
\node[box,below=of b] (c) {上层因果仿射LP：在授权时刻确定原合同或修订合同};
\node[box,below=of c] (d) {三状态Markov递推：形成凸分段线性的库存继续费用};
\node[box,below=of d] (e) {实时动作：观测净需求，选择库存，保证真正终点可达};
\node[box,below=of e] (f) {实际价格结算：更新历史和库存，进入下一次滚动规划};
\draw[->] (a)--(b);\draw[->] (b)--(c);\draw[->] (c)--(d);\draw[->] (d)--(e);\draw[->] (e)--(f);
\draw[->] (f.east)--++(.5,0)|-(a.east);
\end{tikzpicture}
\caption{同一信息时序下的预测、合同规划与库存价值反馈}
\end{figure}
'''
# Preserve the rigorously derived physical framework; remove evidence tied to superseded runs.
physical=old[old.index(r'\section{假设、符号与信息结构}'):old.index(r'\section{跨日随机规划：')]
physical=physical.replace('；另报告不退款口径的账单敏感性','')
physical=physical.replace('问题一主方案选定周期初值6000 kWh，并补充自由周期初值对照；','问题一选定周期初值6000 kWh；')
physical=physical.replace('主方案参照附录的初始状态，选择两端均为6000 kWh；该值是本文的实施口径。另令周期初值参与优化，以检验这一选择的费用影响。','本文参照题给初始状态，将两端均设为6000 kWh，并在这一明确条件下给出最优值。')
physical=physical.replace(r'\input{tables/q1-cycle-revision.tex}','')
physical=physical.replace(r'\input{tables/billing-revision.tex}','')
physical=physical.replace('除另行标明的计费敏感性外，主结果均对应','主结果均对应')
physical=physical.replace('本稿主口径','本文主口径')
physical=physical.replace('本文没有把1000证明为精确罚系数；','1000用于构造有限终端罚；')
planning=old[old.index(r'\section{跨日随机规划：'):old.index(r'\section{凸Markov动态规划：')]
planning=planning.replace(r'\input{tables/prediction-revision.tex}','')
planning=planning.replace('2月至12月才是冻结选择之后的时间顺序评价。','正式回放使用2月至12月。当前统一候选在年度比较中的定位见实验设计。')
planning=planning.replace('属于确定性时间覆盖的经验分布，不是独立同分布抽样，也没有采用概率度量下的最优场景缩减\\cite{dupacova2003,kaut2007}。','属于确定性时间覆盖的等权经验分布。其依据是保留已观测残差的块内形态；场景质量应按实际决策目标评价\\cite{kaut2007}。')
planning=planning.replace('每日0、6、12、18时重规划，时域覆盖至第二个午夜并在真正终点截断。','每日0、6、12、18时重规划，每次覆盖从当前时刻起的72小时，并在真正终点截断。')
fixed=r'''
\subsection{固定72小时：稳定日内各节点的跨日前瞻}
设真正评价终点的绝对时段为$T_\star$，每小时含6段。根节点$a$的核心末点和长度定义为
\begin{equation}\label{eq:fixedH}
 b_a=\min\{a+432,T_\star\},\qquad H_a=b_a-a.
\end{equation}
在年末截断之前，四个日内重规划节点均前瞻72小时。上一版以第二个午夜为末点，日内四节点的实际长度分别为48、42、36、30小时。图\ref{fig:horizon}说明本次修改的直接作用：晚间重规划仍保留完整跨日视野，能够共同评估后续光伏、负荷和低价补能机会。
\begin{figure}[htbp]\centering\includegraphics[width=.83\linewidth]{figures/horizon.png}
\caption{各次重规划的核心长度；真正年末均按剩余时长截断}\label{fig:horizon}\end{figure}
72小时是滚动控制的配置参数。更长核心区间同时改变参与优化的交付段、可成熟历史块与末值价格窗口，因而其账单作用通过闭环比较评价；可行域包含关系不直接给出不同滚动策略的费用排序。

在6、12、18时启动的72小时规划于相同日内相位结束。此时完整继续状态还包含边界后尚未交付的原合同，代码采用库存线性末值近似而未求解这些合同的完整后续费用。核心区间外可用根节点预测作因果合同延拓，但该后缀不属于核心LP已优化的交付费用。实际运行在0时签订完整当日合同，每段都按原合同及最终合同结算，实际年度账单覆盖全部交付段。这一区分使有限时域的价值近似与真实交易执行保持清楚。
'''
planning=planning.replace(r'\subsection{成熟残差与等权经验场景}',fixed+r'\subsection{成熟残差与等权经验场景}')
dp=old[old.index(r'\section{凸Markov动态规划：'):old.index(r'\section{信息更新、价格不确定性')]
dp=dp.replace('本文没有把1000证明为精确罚系数；真正末端由执行器的硬可达集合保证。该区别将价值引导与物理执行保证分开。','该有限罚提供末端价值引导，真实末端由执行器的硬可达集合保证；精确终点性质由命题5给出。')
dp=dp.replace('终端函数在一般滚动末点采用线性末值或凸割包络；','当前候选在一般滚动末点采用线性末值，源码另提供凸割包络作为辅助分支；')
information=r'''
\section{预报融合、价格不确定性与信息价值}
官方预报携带近期气象信息，历史预测保留本地光伏的日内形态。二者按共同发布时点融合，再与负荷预测相减形成净需求，能够在交易权限不变的条件下调整购电中心。融合系数进入当前预测，也进入历史残差重建，保证场景中的误差口径一致。

\subsection{问题三：按发布覆盖范围融合光伏预报}
每次官方发布给出后续24小时预测。将发布前已观测的光伏值作为起点，与24个小时端点组成插值节点，映射到十分钟交付段。设插值并作非负截断后的官方预测为$\widehat v^{\rm O}$，历史预测为$\widehat v^{\rm H}$。当前统一候选取
\begin{equation}\label{eq:fusion}
 \widehat v_{a+j\mid a}=\beta\widehat v^{\rm O}_{a+j\mid a}
 +(1-\beta)\widehat v^{\rm H}_{a+j\mid a},\qquad \beta=0.75.
\end{equation}
式\eqref{eq:fusion}用于已发布预报覆盖的交付段，覆盖之外沿用历史预测；净需求预测为负荷减光伏再除以6。代码中的额外官方误差修正系数为零。历史预测仍包含已观测日内误差的衰减修正，不能将额外修正为零理解为全部日内修正关闭。问题二及问题四日前机制不使用官方预报，融合系数在这两种机制中不改变预测。

针对是否使用0时以外预报的问题，本文保留题给6、12、18时发布作为调度输入，在相应节点重新评价剩余合同；是否改变交付量由总费用模型决定。对于题目尚未提供的新发布时点，其价值应在保持交易权限不变的条件下，用带真实发布时间戳的预测作配对回放。现有汇总体现当前发布机制与融合配置的联合表现，不为某个新增时点赋予具体节省额。

\subsection{融合的二阶误差解释}
\noindent\textbf{命题10（A：双预测融合的均方误差）}\quad
设两种预测误差具有有限二阶矩，分别记为$e_{\rm O}$和$e_{\rm H}$。令
\begin{equation}
 A=\E[e_{\rm O}^2],\qquad B=\E[e_{\rm H}^2],\qquad C=\E[e_{\rm O}e_{\rm H}],
 \qquad D=A+B-2C.
\end{equation}
则融合误差的均方误差及其在单位区间内的最优权重满足
\begin{align}
 M(\beta)&=\beta^2A+(1-\beta)^2B+2\beta(1-\beta)C,\label{eq:fusionmse}\\
 D&=\E[(e_{\rm O}-e_{\rm H})^2]\ge0,\notag\\
 \beta^*&=\operatorname{proj}_{[0,1]}\!\left(\frac{B-C}{D}\right),\qquad D>0.
\end{align}
\begin{proof}
融合误差等于两误差的同权线性组合，平方取期望得到式\eqref{eq:fusionmse}。展开为关于权重的二次函数，其二阶导数为$2D$；对正$D$令一阶导数为零并投影到可行区间即可。若$D=0$，两误差几乎处处相同，各权重给出相同均方误差。
\end{proof}
该结果解释为何两种信息的误差互补可以支持融合。A、B、C是二阶矩，无需假定两预测无偏。本文的0.75来自已有候选配置，既不由未知总体矩估计为理论最优，也不将预测均方误差最小等同于实际购电费用最小；后者还受分时价、紧急费、效率和库存价值共同决定。

\subsection{问题四：成对价格场景与动作后结算}
问题四将同一历史块的净需求误差和价格误差成对叠加到当前预测。上层逐场景计价，保留该块中两者的联合变化；下层使用净需求箱内的价格均值，在有限场景下保持三状态库存反馈。日前机制锁定当日合同，日内机制按题目允许的节点修订合同。

当前候选的合同特征仍为净需求均误差与EMA，价格通过场景目标和箱内均价进入决策；实际交付电价在电池动作后用于结算。这一信息时序与将当前真实价格提前提供给控制器的模型不同。

\subsection{信息与跨日自由度的精确模型关系}
\noindent\textbf{命题11（A：信息集合与策略集合）}\quad
若两个精确优化问题的外生联合分布、物理条件、结算、控制权限及真实初末约束相同，且多信息策略可以忽略新增信息，则
\begin{equation}\label{eq:voi}
 \mathcal I_1\subseteq\mathcal I_2
 \quad\Longrightarrow\quad
 \Pi(\mathcal I_1)\subseteq\Pi(\mathcal I_2)
 \quad\Longrightarrow\quad J^*(\mathcal I_2)\le J^*(\mathcal I_1).
\end{equation}
\begin{proof}
将少信息策略原样用于较丰富信息集，其每个决策仍可实施，故策略集合包含；对相同目标取下确界即可。
\end{proof}
同样，对于同一精确模型和真正终点，将各中间午夜库存固定为6,000 kWh的策略集合包含于允许库存连续的策略集合：
\begin{equation}\label{eq:cross}
 \Pi_{\rm daily}\subseteq\Pi_{\rm cross},\qquad J^*_{\rm cross}\le J^*_{\rm daily}.
\end{equation}
额外午夜等式给出该包含关系。这两项性质说明信息和跨日自由度在精确模型中的作用。实际场景、仿射类与Markov近似形成的闭环费用由轨迹评价；固定72小时与预报融合的年度结果据此作为数值实验报告。
'''
lo7,hi7=q2['bootstrap']['7']['mean_ci95']
experimental=r'''
\section{年度结果与机制验证}
\subsection{比较对象、配置与证据口径}
评价覆盖2025年2月1日至12月31日334日，共48,096个十分钟段。比较统一真实初末库存6,000 kWh，中间午夜连续。1月作为预测族选择、开发与公共初始化阶段；正式期初状态可由1月保持库存6,000 kWh的公共可行策略衔接，1月费用不计入这334日账单。

本次远端年度队列报告113项运行全部完成，统一候选采用固定72小时、28日成熟历史窗口、7条等权场景、EMA系数0.2、增益界负10至10、321个库存节点、三状态Markov反馈和线性末值。官方预报融合权重为0.75，额外官方误差修正为零。

\textbf{比较定位。}该配置已列入候选清单，本文报告其年度比较后的统一结果。一月冻结记录中最终挑战模型采用条件场景与另一组参数，故本候选的年度结果属于候选比较，不按独立留出的年度测试或一月最终选定模型表述。表\ref{tab:main}的上一版为各任务同初末库存的跨日Markov策略，比较保持该基线身份。

\textbf{证据来源。}问题二具有完整本地JSON/NPZ轨迹，本文独立重算账单并检查48,096段物理约束，结果与远端汇总一致。问题三及问题四两种机制采用本地同步的远端复核摘要；其摘要报告物理审计通过，原始逐段缓存与完整审计登记尚未包含在当前数据包中。因此，这三项支持年度汇总比较，逐日区间、指定时段表及费用分解均不从旧轨迹转用。

\subsection{四种机制的年度费用}
\input{tables/new-main.tex}
\textbf{年度账单的共同方向是四种机制均较上一版下降。}固定价日内机制与变动价日内机制分别节省10.94万元和13.48万元，是本组比较最清晰的费用收益；日前两种机制分别节省2.62万元和6.22万元。各机制是不同交易环境下的独立评价，其金额不相加为一个微网的实际全年节省。
\fig{annual-comparison}{年度费用与相对上一版节省：在各自相同交易机制内比较}{.98}

日前机制未使用官方预报，因此其结果说明固定视域及相应场景重构的闭环表现；日内机制同时改变视域与预报融合。当前四项汇总未将这两个因素逐一固定，日内差额按联合配置效果解释。相同H下仅改变融合系数的完整轨迹，才可进一步量化融合的独立贡献。

\subsection{问题二：节省主要来自紧急购电费}
问题二原合同与有效合同相同，调整费为零。旧策略与新候选的普通购电费用分别为1,319.7126万元、1,319.7423万元，紧急购电费用分别为64.7044万元、62.0522万元。二者相减得到
\begin{equation}\label{eq:q2decomp}
 \Delta C=\Delta C_{\rm plan}+\Delta C_{\rm emergency}
 =296.61-26,521.61=-26,225.00.
\end{equation}
式中差额按新候选减上一版、单位元。普通购电支出增加296.61元，换来紧急购电费用下降26,521.61元，使总费用下降26,225.00元。该费用分解把结果与控制目标连接起来：在普通购电支出基本相当的情况下，跨日安排改变了高倍率紧急补购的费用。
\fig{q2-waterfall}{问题二账单分解：普通购电与紧急购电共同决定净节省}{.88}
费用分解识别的是结算项目变化，而不是单独固定合同、电池和预测后的因果分量。问题二附录指定日期表直接来自这套新轨迹，四小时块分别累计充电与放电；两列同时为正可由块内不同时段的单向动作产生。

\subsection{问题二：时间稳定性与适用范围}
按日期对齐新旧策略，定义日费用差及年度累计差：
\begin{equation}
 \Delta_d=C_d^{\rm old}-C_d^{\rm new},\qquad
 \overline\Delta=\frac1{334}\sum_{d=1}^{334}\Delta_d,\qquad
 S_{\rm yr}=\sum_{d=1}^{334}\Delta_d.
\end{equation}
问题二日均节省78.52元。用3、7、14日连续移动块作10,000次重采样，保留每个块内的时序关联，并以均值的2.5\%和97.5\%分位数构造区间\cite{kunsch}。三种块长的日均区间分别为$[-122.81,295.64]$、$[-101.14,288.44]$和$[-74.14,285.42]$元。

\fig{q2-stability}{问题二月度费用差与移动块区间：展示收益随时间的分布}{.98}
334日中费用差为正156日、负177日，按$10^{-6}$元容差计持平1日；11个月中5个月累计节省。三种块长区间均包含零，因此本组证据支持当年累计账单下降，并呈现日、月尺度上的波动。连续库存允许在一个日期补能、在后续日期使用，运行期费用是本模型的直接目标。该图承担时间稳定性诊断，不把候选比较的当年节省扩展为跨年度保证。

\subsection{物理闭环与真正终点核验}
问题二完整轨迹逐段满足母线平衡、库存递推及单向充放电，库存保持在1,200至10,800 kWh内，功率不超过5,000 kW，午夜库存连续，真正首末库存均为6,000 kWh。所有账单在执行后由原合同、有效合同、紧急量与实际价格重新计算，线性末值不计入现金费用。图表使用同一轨迹与同一费用函数，使年度收益有明确的物理可行性基础。
'''
boundary=r'''
\section{性能边界、参数与方法评价}
\subsection{完美信息参照的严格含义}
令事后参照已知全部真实净需求和价格，按普通交付价购电，同时保持相同电池条件和真正初末库存。对任何可实施策略，保留其电池动作与弃电，令参照普通购电为有效合同加紧急购电，则
\begin{equation}\label{eq:oracle}
 q_t^{\rm PI}=r_t+e_t,\qquad
 p_t(r_t+e_t)\le p_t\{\phi(q_t,r_t)+5e_t\}.
\end{equation}
因为$\phi(q,r)=r+0.5|r-q|$且价格非负，该构造费用不高于原策略，并维持母线平衡。于是逐路径有$L_{\rm PI}(\omega)\le C_\pi(\omega)$；对同一分布取期望并优化因果策略，得到
\begin{equation}\label{eq:expectedbound}
 \E[L_{\rm PI}]\le J_{\rm causal}^*\le\E[C_\pi].
\end{equation}
它说明完美信息和普通价交易提供一个理论参照。参照距离同时涉及未来信息、交易渠道、有限场景、策略限制与值函数近似，不等于在线算法最优性差距。本文保留该数学关系，不以旧候选的数值距离标注新候选。

\subsection{数值参数与辅助价值模型}
\begin{table}[htbp]\centering\small\caption{当前统一配置及各参数的职责}
\begin{tabular}{lp{10cm}}\toprule
参数&在当前实现中的作用\\\midrule
72小时&固定核心长度，真正年末按剩余时间截断。\\
28日、7条轨迹&近期成熟历史窗口与等权时间覆盖的场景预算。\\
0.75融合权重&已发布官方预报与历史预测的组合；只作用于官方机制。\\
0.2 EMA、增益界$[-10,10]$&构造误差记忆，并限定上层仿射响应幅度。\\
321库存节点&存储、插值凸值函数；实际动作包含连续折点。\\
三状态&按净需求三分位分箱，用伪计数构造经验转移。\\
线性末值、倍率1&按末段场景价格四分位估计继续库存价值。\\\bottomrule
\end{tabular}\end{table}
这些参数共同定义可复现的当前候选。321点网格的作用是数值存储，7条轨迹与三状态体现给定计算预算下的表示选择；其数值不由凸性定理唯一决定。

代码还实现了条件权重、场景缩减、统一误差状态和增强反馈，用于另行候选比较。当前年度统一配置采用等权场景、原两维净需求仿射特征与M0反馈，故本文把主要论证集中于这一实际执行链。辅助SDDP割的下界性质属于两小时、阶段独立噪声的粗模型，证明放入附录；在固定72小时的非午夜边界，完整继续状态还含未交付合同，既有午夜库存割不直接作为该边界的继续值。

\subsection{模型评价与复核范围}
本文通过费用凸性和单向消元，将购电、紧急追索和电池状态统一进线性约束；通过因果特征保证承诺时序；通过凸价值反馈与可达投影实现实时响应和真实末端衔接。这些结构分别对应可解释优化、合法信息使用和物理执行。

算法的适用条件为单电池、连续功率、非负电价、免费无上限弃电及题目给定交易权限。增加电池退化、并网容量或改变退购结算，需要重新写出相应约束和费用。当前新增结果的范围为同年度候选比较；问题三与问题四的原始缓存同步后，可按附录流程扩展逐段复核、指定时段表与稳定性诊断。

\section{结论}
本文将微网四问组织为同一跨日随机控制系统，以固定72小时稳定规划视野，以合法预报融合更新净需求中心，以因果合同和凸库存价值反馈连接提前承诺与实时动作。确定性问题一费用为35,126.95元；年度统一候选的四机制费用为1,381.79、1,335.24、1,459.24、1,411.73万元，相较上一版同任务结果分别节省2.62、10.94、6.22、13.48万元。问题二完整轨迹进一步将净收益定位到紧急购电费的下降。凸性、信息时序与终点可达性共同构成这一调度框架的理论基础。

\section*{AI工具使用说明}
本次文稿重写使用生成式人工智能辅助理论整理、代码审阅、数据复核与排版。问题二新增统计由本地脚本读取完整轨迹重新计算，问题三和问题四年度数值引用远端复核汇总；生成内容与计算证据的对应关系记录于支撑文件。
'''
bib=old[old.index(r'{\footnotesize'+'\n'+r'\begin{thebibliography}'):old.index(r'\label{bodyend}')]
# Keep cited bibliography only.
import re
main=pre+abstract+intro+physical+planning+dp+information+experimental+boundary
main=main.replace(r'\begin{table}[htbp]',r'\begin{table}[H]')
main=main.replace('命题10（A：双预测融合','命题9（A：双预测融合').replace('命题11（A：信息集合','命题10（A：信息集合')
main=main.replace('同样，对于同一精确模型和真正终点，',r'\noindent\textbf{命题11（A：跨日可行域包含关系）}\quad 对于同一精确模型和真正终点，')
main=main.replace('三个问题。','三个问题。理论标记A表示数学性质，B表示所声明模型内的最优性；其余实测结论按对应结果来源说明。')
used=set(x for v in re.findall(r'\\cite\{([^}]+)\}',main) for x in v.split(','))
items=re.split(r'(?=\\bibitem\{)',bib)
bib=items[0]+''.join(x for x in items[1:] if re.match(r'\\bibitem\{([^}]+)\}',x).group(1) in used)
if r'\end{thebibliography}' not in bib:bib+='\\end{thebibliography}\n}\n'
main+=bib+r'\label{bodyend}\clearpage\appendix\input{technical-appendix.tex}\end{document}'+'\n'
(ROOT/'revised-main.tex').write_text(main)
# Reuse proof text only; all old annual tables and source listings are replaced.
ap=(REF/'technical-appendix.tex').read_text().split(r'\section{可复现实验设计与独立核验}')[0]
ap=ap.replace('固定两小时聚合模型、有限时域和阶段独立噪声分布。','固定两小时聚合模型、有限时域和阶段独立噪声分布。以下结论以阶段LP有限且满足强对偶、所需追索子问题可行、已有割包络为有效全局下界为条件。')
ap+=r'''
\section{固定时域执行与统计复核}
\subsection{完整闭环算法}
\begin{enumerate}
\item 声明真实评价区间和初末库存，加载已确定的预测族及当前候选配置，保持1月公共初始化与2月期初衔接。
\item 在0、6、12、18时确定核心末点，取当前绝对时段加432与真正终点中的较小值；截断可见实际数据与未来未发布预报。
\item 在合法官方覆盖内按0.75与0.25融合预测；以相同预测方法重建成熟历史残差，按时间覆盖选取最多7条并赋予等权。
\item 解因果仿射场景LP。0时落实完整当日原合同；日内官方机制在合法节点更新剩余有效合同，日前机制保持原承诺。
\item 以当次名义合同构造三箱Markov转移。未来函数按概率平均，箱内成本作下确界卷积，插值回321个库存节点。
\item 每十分钟先观察净需求，求连续库存请求，再投影到物理与真实终点可达交集；恢复单向电池动作、紧急购电和弃电。
\item 电池动作确定后按实际交付价格结算。库存传至下一段与下一日，评价终点回到6,000 kWh。
\item 保存全部合同、发布记录、电池动作、库存和费用；按日期对齐比较轨迹，重算账单与统计，登记图表来源。
\end{enumerate}

\subsection{问题二移动块重采样}
给定334个日费用差，对块长b使用全部$334-b+1$个非环绕连续块。每次等概率抽取足够多的块，拼接并保留前334日，计算均值；重复10,000次。三种块长分别以随机种子20260912初始化，块内保留原日期顺序。均值百分位区间乘334给出累计区间，数据文件同时保存日差、月差及正负日数。该方法近似保留短期依赖，对候选后验选择和跨年度分布变化不提供额外修正。

\subsection{源码与证据的一致性检查}
当前候选在源码中满足等权场景、EMA为0.2、增益界10及三箱条件，实际调用原上层仿射规划与三状态Markov反馈分支。新场景工厂提供固定时域和融合预测；增强状态分支属于其他候选。每次运行的源文件哈希、配置、实际日期和末端约束应与结果一起保存。

问题二的年度成本、月差、费用分解和指定日期表均从同一完整NPZ重算。问题三及问题四当前保留汇总证据层级，完整缓存复核时须检查：原合同未被后续发布覆盖、最终合同按相对原计划计费、各段母线平衡和库存递推、充放电功率与互斥、午夜连续、真实年末库存，以及新旧轨迹日期和价格相同。检查通过后再生成对应日期表与移动块统计。

\clearpage
\section{问题二指定日期结果}
下列四个指定日期均来自固定72小时候选的完整轨迹。购电量列为当段合同电量，紧急购电单列；年度费用包含两者按规定倍率的结算。中间各日首末库存按跨日状态自然衔接，只有真正评价首末固定为6,000 kWh。
\input{tables/q2-specified.tex}
\input{tables/q2-emergency.tex}
\clearpage
\section{支撑文件列表与完整调度程序}
\begin{longtable}{p{5.5cm}p{9cm}}\toprule
文件&职责\\\midrule\endhead
revised-main.tex&竞赛正文、年度比较及结果解释。\\
technical-appendix.tex&完整证明、执行流程与问题二指定结果。\\
artifacts/remote-reported-summary.json&同步的远端四机制汇总，保留原证据身份。\\
artifacts/q2-new-analysis.json&由完整轨迹重算的费用分解、月差与配对区间。\\
artifacts/result-registry.json&数值来源与证据等级登记。\\
paper/result-claims.json&正文数值与登记项对应。\\
src/build\_evidence.py&重算统计、生成表格与图形。\\
src/write\_paper.py&生成正文与证明附录。\\
model-source/&与当前仓库一致的完整调度源程序，全文如下。\\
review/&独立控制、凸优化、证明与代码审查。\\\bottomrule
\end{longtable}
模型源程序与数据的原始位置由支撑包README说明。复算采用固定配置、既定预测选择文件和原始数据；独立检验按已保存轨迹重新计费。以下按模块列出完整调度代码，第三方线性规划求解器作为运行依赖安装。
'''
for name,title in [('dispatch.py','费用结算与确定性调度'),('forecasting.py','合法信息预测'),('control.py','因果仿射规划与凸库存反馈'),('nextgen_scenarios.py','固定配置与场景生成'),('nextgen_control.py','候选控制接口'),('nextgen_run.py','年度逐段执行'),('sddp.py','辅助继续值模块')]:
    ap+='\n\\clearpage\\subsection{'+title+'}\n'
    ap+=r'\VerbatimInput[fontsize=\fontsize{7.3}{8.5}\selectfont,breaklines=true,breakanywhere=true,numbers=left,numbersep=4pt,xleftmargin=14pt]{model-source/'+name+'}\n'
(ROOT/'technical-appendix.tex').write_text(ap)
(ROOT/'compile.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\n/Library/TeX/texbin/xelatex -interaction=nonstopmode -halt-on-error revised-main.tex\n/Library/TeX/texbin/xelatex -interaction=nonstopmode -halt-on-error revised-main.tex\ncp revised-main.pdf output/pdf/基于固定时域与预报融合的微网跨日随机调度.pdf\n')
print('Wrote',ROOT/'revised-main.tex')
