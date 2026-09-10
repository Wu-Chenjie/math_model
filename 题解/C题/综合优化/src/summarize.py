"""Programmatic selection, derived comparisons, traceable handoff, static figures."""
import json,csv,shutil,importlib.util
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_comparison import ROOT,BASE,CANDIDATES,KINDS,dump

LABELS={'baseline':'原SAA＋贪心','common_mpc':'原SAA＋均值MPC','affine_feedback':'仿射规划＋仿射反馈',
        'affine_mpc':'仿射规划＋均值MPC','affine_saa_mpc':'仿射规划＋场景MPC','affine_sdp':'仿射规划＋Markov DP',
        'common_saa_mpc':'原SAA＋场景MPC（补充）','common_sdp':'原SAA＋Markov DP（补充）',
        'january_selected':'1月选定后固定','adaptive28':'过去28日选择','convex28':'过去28日凸组合'}
DIAGNOSTICS=['common_saa_mpc','common_sdp']

def read(phase,kind,c):return json.loads((ROOT/f'artifacts/{phase}/{kind}_{c}.json').read_text())

def main():
    from parameter_bounds import main as parameter_bounds
    parameter_bounds()
    out=ROOT/'计算结果';out.mkdir(exist_ok=True)
    names=list(CANDIDATES);summary={};baseline={};selection={};metrics={};claims=[]
    oracle=json.loads((BASE/'artifacts/oracle.json').read_text())
    dump(ROOT/'artifacts/perfect-information-reference.json',oracle)
    for kind in KINDS:
        cal={c:read('calibrate',kind,c) for c in names};ann={c:read('annual',kind,c) for c in names}
        jan=min(names,key=lambda c:cal[c]['totals']['total_cost'])
        daily=np.array([[r['total_cost'] for r in ann[c]['daily']] for c in names]).T
        history=np.vstack([np.array([[r['total_cost'] for r in cal[c]['daily']] for c in names]).T,daily])
        chosen=[];scores=[]
        for i in range(len(daily)):
            score=history[max(0,i+10-28):i+10].sum(0)
            chosen.append(int(np.argmin(score)));scores.append(score.tolist())
        arrays={c:dict(np.load(ROOT/f'artifacts/annual/{kind}_{c}.npz')) for c in names}
        adaptive={key:np.stack([arrays[names[chosen[i]]][key][i] for i in range(len(daily))])
                  for key in arrays[names[0]]}
        daily_adaptive=[ann[names[j]]['daily'][i] for i,j in enumerate(chosen)]
        np.savez_compressed(ROOT/f'artifacts/{kind}_adaptive.npz',**adaptive)
        comparisons={c:ann[c]['totals'].copy() for c in names}
        diag={c:read('diagnostic',kind,c) for c in DIAGNOSTICS}
        comparisons.update({c:diag[c]['totals'].copy() for c in DIAGNOSTICS})
        convex=json.loads((ROOT/f'artifacts/{kind}_convex.json').read_text())
        comparisons['convex28']=convex['totals'].copy()
        comparisons['convex28']['mixed_weight_days']=int(np.sum((np.array(convex['weights'])>1e-6).sum(axis=1)>1))
        with (out/f'{kind}_凸组合权重.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f);writer.writerow(['日期',*names,'总费用_元','按当日权重计算的专家费用_元','凸组合节省_元'])
            writer.writerows([[row['date'],*convex['weights'][i],row['total_cost'],row['weighted_expert_cost'],row['convex_combination_gain_yuan']] for i,row in enumerate(convex['daily'])])
        comparisons['january_selected']=ann[jan]['totals'].copy()
        comparisons['adaptive28']={k:float(sum(r[k] for r in daily_adaptive)) for k in daily_adaptive[0]
                                   if k not in ['date','projection_max_kwh']}
        adcost=np.array([r['total_cost'] for r in daily_adaptive])
        comparisons['adaptive28'].update(daily_cost_p95=float(np.quantile(adcost,.95)),worst_day_cost=float(adcost.max()),
                                       projection_max_kwh=max(r['projection_max_kwh'] for r in daily_adaptive))
        basecost=ann['baseline']['totals']['total_cost']
        for c in comparisons:
            comparisons[c]['saving_vs_baseline_yuan']=basecost-comparisons[c]['total_cost']
            comparisons[c]['saving_vs_baseline_percent']=100*(basecost-comparisons[c]['total_cost'])/basecost
            bound=oracle['variable' if kind.startswith('q4') else 'fixed']['total_cost']
            comparisons[c]['perfect_information_daily_cyclic_lower_bound_yuan']=bound
            comparisons[c]['excess_over_perfect_information_percent']=100*(comparisons[c]['total_cost']-bound)/bound
        monthly={c:[float(sum(r['total_cost'] for r in ann[c]['daily'] if int(r['date'][5:7])==m)) for m in range(2,13)] for c in names}
        monthly['january_selected']=monthly[jan]
        monthly['adaptive28']=[float(sum(r['total_cost'] for r in daily_adaptive if int(r['date'][5:7])==m)) for m in range(2,13)]
        for c in DIAGNOSTICS:monthly[c]=[float(sum(r['total_cost'] for r in diag[c]['daily'] if int(r['date'][5:7])==m)) for m in range(2,13)]
        monthly['convex28']=[float(sum(r['total_cost'] for r in convex['daily'] if int(r['date'][5:7])==m)) for m in range(2,13)]
        retrospective=min(names,key=lambda c:ann[c]['totals']['total_cost'])
        selection[kind]={'january_selected':jan,'january_costs':{c:cal[c]['totals']['total_cost'] for c in names},
                         'retrospective_best_candidate':retrospective,'adaptive_choices':[names[i] for i in chosen],
                         'adaptive_history_scores':scores,'dates':arrays[jan]['dates'].tolist(),
                         'adaptive_counts':{c:chosen.count(j) for j,c in enumerate(names)},
                         'retrospective_best_including_diagnostics':min(names+DIAGNOSTICS,key=lambda c:comparisons[c]['total_cost']),
                         'warning':'Retrospective winner is an evaluation statistic, not an ex-ante selection rule.'}
        summary[kind]={'comparisons':comparisons,'monthly_cost_yuan':monthly}
        baseline[kind]=ann['baseline']['totals'];metrics[kind]=comparisons['january_selected']
        # Main deliverable is frozen January choice, not the annual hindsight winner.
        shutil.copy2(ROOT/f'artifacts/annual/{kind}_{jan}.npz',ROOT/f'artifacts/{kind}.npz')
        shutil.copy2(ROOT/f'artifacts/annual/{kind}_{jan}.json',ROOT/f'artifacts/{kind}.json')
        with (out/f'{kind}_每日专家选择.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['日期','1月固定候选','在线候选','在线当日费用_元','历史窗口内各候选费用_JSON'])
            w.writerows(zip(selection[kind]['dates'],[jan]*len(chosen),selection[kind]['adaptive_choices'],adcost,
                           [json.dumps(s) for s in scores]))
    # Grid321 comparator is the exact corresponding subset from the annual run.
    grid={}
    for kind in KINDS:
        g=read('grid641',kind,'affine_sdp');a=read('annual',kind,'affine_sdp');dates={r['date'] for r in g['daily']}
        oldsum=sum(r['total_cost'] for r in a['daily'] if r['date'] in dates)
        grid[kind]={'dates':sorted(dates),'grid321_cost':oldsum,'grid641_cost':g['totals']['total_cost'],
                    'difference_yuan':g['totals']['total_cost']-oldsum,
                    'difference_percent':100*(g['totals']['total_cost']-oldsum)/oldsum,
                    'scope':'Same predeclared11dates; closed-loop policies and subsequent contracts may differ.'}
    dump(ROOT/'artifacts/selection.json',selection);dump(ROOT/'artifacts/comparisons.json',summary)
    dump(ROOT/'artifacts/grid-sensitivity.json',grid);dump(ROOT/'artifacts/metrics.json',metrics)
    dump(ROOT/'artifacts/baseline-metrics.json',baseline)
    # Reuse verified table exporter with explicit destination injection.
    for name in ['q1.json','data.npz']:shutil.copy2(BASE/'artifacts'/name,ROOT/'artifacts'/name)
    spec=importlib.util.spec_from_file_location('baseline_export',BASE/'src/export_results.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=ROOT;module.OUT=out;module.main()
    payload=json.loads((ROOT/'artifacts/workbook-payload.json').read_text())
    payload['notes'][-1]=['最优性边界','本增量主结果由1月开发费用选定候选后固定运行；有限策略类近似，不是全体随机控制策略的全局最优。']
    payload['notes'].append(['增量模型','因果仿射SOC合同规划＋共同开环场景经济MPC；六候选对照和在线选择另见综合建模计算交接.md。'])
    dump(ROOT/'artifacts/workbook-payload.json',payload)
    for name in ['build_workbooks.mjs','verify_workbooks.py']:
        shutil.copy2(BASE/'src'/name,ROOT/'src'/name)
    (ROOT/'artifacts/previews').mkdir(exist_ok=True)
    figures(summary)
    handoff(summary,selection,grid)
    from export_aggregates import main as export_aggregates
    export_aggregates()
    # Freeze every numeric JSON leaf used by tables/summary as a directly resolvable result.
    entries=[]
    def walk(obj,path,artifact,prefix):
        if isinstance(obj,dict):
            for k,v in obj.items():walk(v,path+'/'+str(k).replace('~','~0').replace('/','~1'),artifact,prefix)
        elif isinstance(obj,list):
            for i,v in enumerate(obj):walk(v,path+'/'+str(i),artifact,prefix)
        elif isinstance(obj,(float,int)) and not isinstance(obj,bool):
            entries.append({'id':prefix+path.replace('/','.'),'value':obj,'source_artifact':artifact,'source_path':path,'status':'verified'})
    for file in ['comparisons.json','grid-sensitivity.json','selection.json','handoff-tables.json','aggregate-handoff-tables.json','robustness.json','falsification.json','annual-validation.json','tie-break-bound.json']:
        walk(json.loads((ROOT/'artifacts'/file).read_text()),'',f'artifacts/{file}',file[:-5])
    dump(ROOT/'artifacts/result-registry.json',{'results':entries})
    print(json.dumps({'selected':{k:v['january_selected'] for k,v in selection.items()},'metrics':metrics},ensure_ascii=False))

def figures(summary):
    plt.rcParams.update({'font.family':'Songti SC','font.size':11,'axes.unicode_minus':False,'svg.fonttype':'none',
                         'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':300})
    names=list(CANDIDATES)+DIAGNOSTICS+['adaptive28','convex28'];kinds=list(KINDS)
    vals=np.array([[summary[k]['comparisons'][c]['saving_vs_baseline_percent'] for k in kinds] for c in names])
    fig,ax=plt.subplots(figsize=(9.2,6.5),constrained_layout=True)
    lim=max(1,abs(vals).max());im=ax.imshow(vals,cmap='RdBu',vmin=-lim,vmax=lim,aspect='auto')
    ax.set_xticks(range(4),['问题2','问题3','问题4-2','问题4-3'])
    ax.set_yticks(range(len(names)),[LABELS[c] for c in names]);ax.tick_params(length=0)
    for i in range(len(names)):
        for j in range(4):ax.text(j,i,f'{vals[i,j]:+.2f}%',ha='center',va='center',fontsize=11,
                                  color='white' if abs(vals[i,j])>.55*lim else '#202020')
    fig.colorbar(im,ax=ax,label='相对原方案费用节省率 / %（正值较好）',shrink=.85)
    ax.set_title('固定数据顺序回测：不同组合的费用比较',pad=12)
    for ext in ['png','svg']:fig.savefig(ROOT/f'figures/01_策略比较.{ext}',bbox_inches='tight',facecolor='white')
    plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(9,6.4),constrained_layout=True,sharex=True)
    for ax,k,title in zip(axs.flat,kinds,['问题2','问题3','问题4-2','问题4-3']):
        for c,color in [('january_selected','#207A8A'),('adaptive28','#BD6C37'),('convex28','#73589A')]:
            saving=(np.array(summary[k]['monthly_cost_yuan']['baseline'])-summary[k]['monthly_cost_yuan'][c])/1e4
            ax.plot(range(2,13),saving,'o-',ms=3,color=color,label=LABELS[c])
        ax.axhline(0,color='gray',lw=.7);ax.set_title(title);ax.set_ylabel('相对原方案节省 / 万元');ax.grid(axis='y',alpha=.18)
        ax.set_xticks([2,4,6,8,10,12])
        monthly=summary[k]['monthly_cost_yuan']
        if max(np.max(abs(np.array(monthly[c])-monthly['january_selected'])) for c in ['adaptive28','convex28'])<.005:
            ax.text(.03,.95,'三种策略曲线重合',transform=ax.transAxes,va='top',fontsize=9,color='#555555')
    axs[0,0].legend(fontsize=9);axs[1,0].set_xlabel('2025年月');axs[1,1].set_xlabel('2025年月')
    for ext in ['png','svg']:fig.savefig(ROOT/f'figures/02_月度节省.{ext}',bbox_inches='tight',facecolor='white')
    plt.close(fig)

def handoff(summary,selection,grid):
    text=['# 综合建模计算交接：因果反馈规划与储能控制',
          '本文件为原交接的增量版本。主结果按1月开发费用选择候选后固定运行；另报告预先定义的过去28日在线选择。全部结果来自本地程序，论文由使用者手工撰写。当前数据已在原方案开发中被查看，此处是同一固定数据上的增量顺序回测，不是全新外部验证集。',
          '## 1. 结果与“最佳”的边界',
          '算法名称多不代表效果好。这里的比较对象是预声明六种组合，第一优先指标为实际购电总费用，同时核验硬约束。不能由有限历史回测证明未知真实分布下的绝对最优；也不允许用事后当日最低费用拼接成可执行策略。',
          '| 设置 | 原方案费用/元 | 1月选定方案费用/元 | 节省/元 | 节省率 | 在线选择费用/元 | 凸组合费用/元 |',
          '|---|---:|---:|---:|---:|---:|---:|']
    for k in KINDS:
        c=summary[k]['comparisons'];m=c['january_selected']
        text.append(f"| {k} | {c['baseline']['total_cost']:,.2f} | {m['total_cost']:,.2f} | {m['saving_vs_baseline_yuan']:,.2f} | {m['saving_vs_baseline_percent']:.4f}% | {c['adaptive28']['total_cost']:,.2f} | {c['convex28']['total_cost']:,.2f} |")
    text+=['','### 全部候选的年度费用（元）','| 组合 | 问题2 | 问题3 | 问题4-2 | 问题4-3 |','|---|---:|---:|---:|---:|']
    for c in list(CANDIDATES)+DIAGNOSTICS:text.append('| '+LABELS[c]+' | '+' | '.join(f"{summary[k]['comparisons'][c]['total_cost']:,.2f}" for k in KINDS)+' |')
    text+=['','### 费用之外的运行指标',
           '| 设置 | 策略 | 紧急购电/kWh | 弃电/kWh | 日费用95%分位/元 |','|---|---|---:|---:|---:|']
    for k in KINDS:
        for c in ['baseline','january_selected','adaptive28','convex28']:
            m=summary[k]['comparisons'][c]
            text.append(f"| {k} | {LABELS[c]} | {m['emergency_energy']:,.2f} | {m['spill_energy']:,.2f} | {m['daily_cost_p95']:,.2f} |")
    text+=['','本题以总费用最小为主目标，紧急供电按五倍价格计费且未设容量上限，所以费用降低不保证紧急电量也减少。紧急购电不等于失供电。日费用分位数还受季节负荷和价格影响，不是已经校准的失供风险指标。若另设紧急容量约束或可靠性目标，应重新建模求解。']
    text+=['','### 固定主方案相对原方案的费用变化（元）',
           '| 设置 | 0点计划费变化 | 增购费变化 | 退购净费变化 | 紧急费变化 |','|---|---:|---:|---:|---:|']
    for k in KINDS:
        c=summary[k]['comparisons'];a,b=c['january_selected'],c['baseline']
        text.append('| '+k+' | '+' | '.join(f"{a[x]-b[x]:+,.2f}" for x in ['planned_cost','increase_cost','reduction_net_cost','emergency_cost'])+' |')
    text.append('四项变化之和等于总费用变化；负值表示该项减少。其作用是解释实际账单构成，不把上层和下层的交互作用强行作唯一因果拆分。')
    text+=['','主输出xlsx和指定日期表对应“1月选定后固定”策略；历史选择与凸组合的完整逐时策略、发布记录、费用CSV另存计算结果/综合策略，指定日期摘录见综合策略指定日期表.md。',
           '两个标注“补充”的对照用于隔离上层贡献，加入时间见补充对照记录.md，不参与原六专家选择。表中如出现补充候选更优，应如实保留；不能把1月固定主输出称为全部候选的年度最优。',
           '| 设置 | 1月选定 | 原六候选回顾性最低 | 含补充候选回顾性最低 |','|---|---|---|---|']
    for k in KINDS:text.append(f"| {k} | {LABELS[selection[k]['january_selected']]} | {LABELS[selection[k]['retrospective_best_candidate']]} | {LABELS[selection[k]['retrospective_best_including_diagnostics']]} |")
    text+=['','## 2. 统一目标与约束',
           r'以策略π最小化条件期望总费用。实际核算统一为 $C=\sum_t[p_tq_t+1.5p_t(r_t-q_t)^+-0.5p_t(q_t-r_t)^++5p_te_t]$。退购口径沿用原交接：退回原费用后收50%违约费；调整按最终净额相对0点合同结算。另一种不退款解释下须重新计算，不能挪用本数值。',
           r'能量平衡为 $r_t+b_t+e_t-c_t-w_t=n_t$；电池递推为 $E_{t+1}=E_t+0.9c_t-b_t/0.9$。SOC为1200至10800kWh，母线侧每10分钟充放电量不超过5000/6kWh。免费弃电、无售电、紧急购电无外加上限。',
           '为了控制比较变量，本轮第二至四问仍每日回到6000kWh；这是附加运行政策，不是赛题对所有问题的要求。因此“最佳”还受到每日闭合政策限制。第一问结果沿用原确定性LP，未进行无意义的算法替换。',
           '## 3. 上层：有限维因果仿射策略类SAA',
           r'在每个合同决策窗口，历史误差形成净需求与价格场景。共同决定合同q或r、基准库存a和分块增益g。场景内下一库存满足 $E^s_{t+1}=a_t+g_{b(t),0}(n^s_t-\bar n_t)+g_{b(t),1}z^s_t$，其中 $z^s_t=0.8z^s_{t-1}+0.2(n^s_t-\bar n_t)$，在发布起点统一重置为0。',
           '增益按六小时块共享，范围[-10,10]。日末仅最后一行反馈特征清零，基准库存为6000。所有历史场景满足能量、SOC和功率约束。当前净负荷特征只供随后电池反馈使用，合同q/r不能先看到当前10分钟实际净负荷。',
           '模型是LP，数值最优结论针对所定义经验分布、策略类与含极小周转项的目标；不等于对一切因果策略最优。周转项不计入实际账单，它对单次经济子问题的保守扰动界和参数来源见符号与参数来源.md。零增益包含共同库存轨迹，程序在抽查发布窗口验证了场景内经济目标不劣于原共同轨迹计划。但真实未见误差可能使目标库存不可行，需要投影；该投影扩展的样本外性能没有从LP最优性自动得到保证。',
           'projection相关字段仅记录execute_target对外部目标库存的显式投影，主要用于审计直接仿射策略。原贪心内部也有终端可达修正，但未记入这些字段；不能用其数值零宣称该策略从未受安全约束修正。',
           '## 4. 下层：场景经济MPC和替代控制',
           '下层只使用当前已生效合同。先根据最近6个已观测净需求对历史场景软匹配，再混合20%均匀权重，防止权重完全塌缩。它仍可能集中于少数样本，均匀混合不等于已经证明有足够有效样本量。',
           r'场景MPC求解 $\min\sum_s\omega_s\sum_{j=t}^{143}5p_j^se_j^s$，满足共同电池动作序列、各场景缺口约束、实际初始SOC和当日末6000条件。当前净需求替换为已观测值，未来保持不确定。每次仅执行第一步，再读取新观测重算。',
           '这里未来充放电路径在场景间共同，是保守的开环情景近似加滚动反馈；没有把逐路径先知最优解包装成多阶段策略。完整场景树MPC或SDDP仍是更大的候选类，本轮没有声称已求解它们。',
           '均值MPC使用相同条件权重但压缩为一条均值路径。Markov DP使用净需求三分位状态、相邻时刻历史转移、状态内经验发射及平均价格，SOC网格321点；其Bellman递推是先在当前已观测发射下取最小值，再取发射期望。它保留部分持续性，但丢弃状态内净需求与价格相关性，且不声称历史连续过程严格Markov。',
           '第四问的实际当期价格在本轮仅用于结算；控制器使用条件预测价格。这是较保守的信息策略类。若允许观测交易当期价格，可加入只揭示当期价格的新候选；不能提前揭示未来价格。',
           '## 5. 分层组合与第三问的解释',
           '仿射上层和MPC/DP下层是组合策略：下层替换后并非完全执行上层优化的仿射策略，因此不能把整个组合称为该LP策略类的精确最优执行。其有效性由实际闭环费用比较支持。',
           '当前0点上层没有完整前瞻未来预报更新后的合同修订选择价值；它规划的是储能反馈，随后在实际发布时刻重新求解合同。这也是相对完整多阶段模型的一个近似。',
           '问题2的合同在0点固定。问题3在0、6、12、18点更新预测和合同，每次使用本候选当时的实际SOC。后续合同尚未发布时，下层只知道最新合同快照，不能读取最终r。问题3的费用差因此包含电池反馈对后续调约的影响，是整套闭环差异，不能全归因于电池控制。',
           '本轮在每个允许窗口都重算合同；未加入人为固定调整费或为减少计算而跳过优化。已有调整费用会使某些时段自然保持不变。事件触发若用于减少求解，在计算成本不受限时没有优先性；若研究减少实际调约，则需明确其独立业务目标。原方案的“新增PV预报价值”消融数值不自动适用于新策略。',
           '## 6. 在线综合选择',
           '六个候选均做因果影子回放。每天0点只根据前28个已评估日的累计费用选择当天候选，历史不足时用已有开发日；当天保持不变。每日相同初末SOC使这些每日反事实可直接比较。若改为跨日不闭合SOC，必须重新处理专家间库存状态差异，不能照搬本选择器。',
           '在线选择结果为预声明规则的实测表现；回顾性最低候选是另一项事后统计。也没有保证在线选择在每个月、每条新路径上总胜出。',
           '### 6.1 真正的凸组合控制',
           r'另增加一个综合候选：每天0点只用前28个已评估日学习非负权重w，满足$\sum_iw_i=1$。当日六专家继续用各自影子SOC因果运行，实际只签发加权合同$q=\sum_iw_iq_i,r=\sum_iw_ir_i$，并执行加权SOC轨迹$E=\sum_iw_iE_i$。权重日内固定，各专家合同不分别实际签发。',
           r'令$\delta=E_{t+1}-E_t$，按$c=\delta^+/\eta,b=\eta(-\delta)^+$恢复单一电池动作。SOC和功率可行集凸，合同费用及$e=\max\{0,n-r+\eta\delta,n-r+\delta/\eta\}$也凸，因此逐日$C_{mix}\le\sum_iw_iC_i$。这不保证低于当天最优单专家。',
           '权重由过去窗口中的真实组合费用最小化LP确定，不是把当天已实现最低费用当作权重。训练窗口LP不劣于其中最佳固定专家、每个真实日的凸性费用上界与物理约束均逐项检查。此性质依赖净负荷/价格外生、共同物理参数、免费弃电、统一合同净额账户及每日共同初末SOC。',
           '该凸组合是在主实验启动后的综合扩展，新增时点与动机单独记录，不冒称最初预声明模型，也不改变原六候选固定选择器。滚动历史经验最小化没有自动的样本外最优或无遗憾保证。它的完整权重、合同、SOC和费用分别见*_凸组合权重.csv与artifacts/*_convex.npz/json。',
           '## 7. 验证与敏感性',
           '年度物理、费用与原基线复现检查见artifacts/annual-validation.json；未来观测及未发布预报扰动不变性见artifacts/falsification.json；独立递归枚举、MPC机会成本算例与仿射场景重放见review/controller-small-checks.json。',
           '| 设置 | 321格参照费用/元 | 641格费用/元 | 差异率 |','|---|---:|---:|---:|']
    for k,g in grid.items():text.append(f"| {k} | {g['grid321_cost']:,.2f} | {g['grid641_cost']:,.2f} | {g['difference_percent']:+.4f}% |")
    text+=['','网格检查只针对预声明的每月首日共11天，不能写成全年收敛证明。实际费用不要求随网格加密单调，因为它同时受到模型误差、执行路径和后续合同变化影响。物理压力验证见artifacts/robustness.json；其可行性结论不表示极端情景费用也受到控制。',
           'comparisons.json同时列出原计算得到的完美信息每日闭合LP下界。由于当前合同结算费不低于普通价乘最终购电量、紧急价不低于普通价，该下界在相同首末SOC下适用；实际费用与它的差包含不可获得的未来信息价值，不能全部称为数值求解误差或可实现的节省空间。',
           '## 8. 可进一步扩大的优化边界',
           '若继续追求更宽策略类，应依次研究：允许当期可观测价格反馈；取消第二至四问额外每日闭合，采用跨日状态传递和经验证的期末库存价值；用保留条件误差持续性的多阶段树或SDDP联合优化未来信息下的合同与库存；为预测误差分布构造严格历史校准的分布鲁棒集合。这些属于尚未执行的新实验，不能把它们的预期收益写入当前论文结果。',
           '算力增加能缩小数值误差、扩展候选和加强验证，无法确定未知未来分布。复杂度必须由结果支持。当前最强结论是明确口径下的可执行候选比较，而非真实系统绝对最优。',
           '## 9. 文件与复现',
           'src/controllers.py对应控制方程；src/run_comparison.py对应时序仿真；src/validate_extension.py对应反例与核算；src/summarize.py生成统计、图表、选择规则及交接表；artifacts/result-registry.json逐项关联JSON数值。执行命令与环境见artifacts/execution-*.json，完整步骤见复现.sh。',
           '计算结果/result*.xlsx、逐时CSV与指定日期结果表.md是1月固定选择的主交付；在线策略见*_adaptive.npz及每日专家选择CSV。源题和附件未修改。新增工作目录独立于原已审查交接，原89分不适用于本增量。',
           '## 10. 理论来源',
           '[随机MPC电力调度原始论文](https://skoge.folk.ntnu.no/prost/proceedings/cdc-ecc-2011/data/papers/1092.pdf)；[储能ADP原始论文](https://danielrjiang.github.io/files/publications/drj-wbp-bidding-2015.pdf)；[储能双阈值结构原始研究的作者机构页面](https://research.ibm.com/publications/optimal-management-and-sizing-of-energy-storage-under-dynamic-pricing-for-the-efficient-integration-of-renewable-energy)。本题仿射SOC策略、Markov近似和具体组合由本项目明确构造并验证，不能声称上述文献直接证明这些具体模型的所有性质。']
    mixing=['### 凸组合收益的分解',
            '| 设置 | 多个非零权重的日数 | 相对按当日权重加权专家费用的节省/元 | 相对每日单选节省/元 |','|---|---:|---:|---:|']
    for k in KINDS:
        c=summary[k]['comparisons'];m=c['convex28']
        gain,delta=[0. if abs(x)<.005 else x for x in [m['convex_combination_gain_yuan'],c['adaptive28']['total_cost']-m['total_cost']]]
        mixing.append(f"| {k} | {m['mixed_weight_days']} | {gain:,.2f} | {delta:,.2f} |")
    mixing.append('第一项节省比较实际组合与相同当日权重下的专家费用加权和，直接对应凸性上界；第二项还包含权重学习改变策略选择的影响，不能全部归因于物理混合。混合日按权重大于1e-6计数，数值极小权重不作实质混合解释。')
    worse=[]
    for k in KINDS:
        monthly=summary[k]['monthly_cost_yuan']
        for month,(b,c) in enumerate(zip(monthly['baseline'],monthly['convex28']),2):
            if c-b>.005:worse.append(f'{k}的{month}月高出{c-b:,.2f}元')
    if worse:mixing.append('逐月检查中，凸组合仍有不及原方案的月份：'+'；'.join(worse)+'。年度节省不等于逐月一致占优，历史窗口的选择规则也不保证新时期收益。')
    at=text.index('## 7. 验证与敏感性');text[at:at]=mixing
    # Table rows must remain adjacent under CommonMark/GFM.
    rendered=('\n\n'.join(text)+'\n').replace('|\n\n|','|\n|')
    while '\n\n\n' in rendered:rendered=rendered.replace('\n\n\n','\n\n')
    (ROOT/'综合建模计算交接.md').write_text(rendered)

if __name__=='__main__':main()
