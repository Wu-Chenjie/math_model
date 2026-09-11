"""Freeze executed contest results, traceable tables and scientific figures."""
from pathlib import Path
import json,shutil,hashlib,sys,time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from control import prune_cuts
from analyze_tail import main as analyze_tails

ROOT=Path(__file__).resolve().parents[1]
KINDS=['q2','q3','q4_2','q4_3']
LABELS={'closed_baseline':'每日闭合基线','cross_baseline':'跨日基线','closed_affine':'每日闭合仿射反馈','affine_mpc':'跨日仿射反馈','markov_mpc':'跨日Markov反馈','sddp_markov':'SDDP末值＋Markov反馈'}
def read(f):return json.loads((ROOT/f).read_text())
def dump(f,x):(ROOT/f).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def source(kind,candidate):
    phase='annual_sddp' if candidate.startswith('sddp') else 'annual'
    return f'artifacts/{phase}/{kind}_{candidate}.json'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(v) for v in r)+' |' for r in rows])

def main():
    begin=time.perf_counter();analyze_tails();selection=read('artifacts/selection.json');summary={'selected':selection['selected'],'models':{},'warmup':read('artifacts/warmup.json'),'q1':read('artifacts/q1.json'),'tail_shape_analysis':read('artifacts/tail-shape-analysis.json')}
    q1=dict(np.load(ROOT/'artifacts/q1.npz'));data=dict(np.load(ROOT/'artifacts/data.npz'))
    summary['development_sddp_comparison']={k:{'linear_markov':v['markov_mpc'],'sddp_markov':v['sddp_markov'],'difference_yuan':v['sddp_markov']-v['markov_mpc']} for k,v in selection['development_costs'].items()}
    summary['q1']['total_cost']=float(data['day_price']@q1['q']);summary['q1']['planned_energy']=float(q1['q'].sum())
    baseline={};metrics={};rows=[];allcases={}
    for kind in KINDS:
        cases={c:read(source(kind,c)) for c in LABELS};allcases[kind]=cases
        base=cases['closed_baseline']['totals']['total_cost'];selected=selection['selected'][kind]
        summary['models'][kind]={}
        for c,m in cases.items():
            summary['models'][kind][c]={**m['totals'],**m['validation'],'saving_vs_daily_baseline_percent':100*(1-m['totals']['total_cost']/base),'source_artifact':source(kind,c)}
        metric=f'{kind}_total_cost';baseline[metric]=base;metrics[metric]=cases[selected]['totals']['total_cost']
        for suffix in ['json','npz']:
            src=ROOT/source(kind,selected).replace('.json','.'+suffix);shutil.copy2(src,ROOT/f'artifacts/{kind}.{suffix}')
        rows.append([kind,LABELS[selected],f'{metrics[metric]:,.2f}',f'{base:,.2f}',f'{100*(1-metrics[metric]/base):.4f}%',f"{cases[selected]['validation']['final_inventory']:.4f}"])
    tails=[]
    for path in sorted((ROOT/'artifacts/tails').glob('*.json')):
        m=json.loads(path.read_text());ev=m['evaluation']
        tails.append({'model':path.stem,'configuration':m['configuration'],'iterations':m['iterations'],**ev,
          'estimated_gap_percent':100*(ev['mean_policy_cost']-ev['root_lower_bound'])/ev['mean_policy_cost'],
          'root_cut_count':len(m['root_cuts']),'active_root_cut_count':len(prune_cuts(m['root_cuts']))})
    summary['sddp_training']=tails
    summary['annual_sddp_difference']={k:summary['models'][k]['sddp_markov']['total_cost']-summary['models'][k]['markov_mpc']['total_cost'] for k in KINDS}
    experiments={p.stem:json.loads(p.read_text()) for p in (ROOT/'artifacts/experiments').glob('*.json')}
    assert len(experiments)>=15,'Validation experiments not completed'
    def compact(m):return {'total_cost':m['totals']['total_cost'],'emergency_energy':m['totals']['emergency_energy'],
       'final_inventory':m['validation']['final_inventory'],'configuration':m['configuration'],'design':m['validation_design']}
    short_order=['reference','grid161','grid641','scenarios14','horizon3','tail_zero','tail_double','terminal6000','stress_load_up_pv_down','pv_0only','pv_without6','pv_without12','pv_without18','variable_reference','variable_stress']
    annual_order=['annual_pv_0only','annual_pv_without6','annual_pv_without12','annual_pv_without18']
    summary['experiments']={n:compact(experiments[n]) for n in short_order}
    summary['annual_release_ablations']={n:compact(experiments[n]) for n in annual_order}
    assert len(summary['experiments'])==15 and len(summary['annual_release_ablations'])==4
    summary['global_terminal']=sorted(read('artifacts/global-terminal.json')['results'],key=lambda m:(KINDS.index(m['kind']),['affine_mpc','markov_mpc'].index(m['candidate'])))
    for m in summary['global_terminal']:
        if m['candidate']=='affine_mpc':
            m['saving_vs_closed_affine_same_global_terminal']=summary['models'][m['kind']]['closed_affine']['total_cost']-m['fixed_total_cost']
    for m in summary['annual_release_ablations'].values():
        m['increment_vs_markov_all_releases']=m['total_cost']-summary['models']['q3']['markov_mpc']['total_cost']
    summary['perfect_information_reference']={k:{z:v[z] for z in ['objective_cost_yuan','terminal_constraint','initial_inventory_kwh','final_inventory_kwh','checks']} for k,v in read('review/global-oracle.json')['results'].items()}
    summary['scope_notes']=['Annual means February–December, with a separate common January initialization.',
       'Primary endpoint is free; daily-closure comparisons also differ in terminal inventory. Fixed-global-end sensitivity is reported separately.',
       'SDDP bounds concern fixed coarse auxiliary models, not the richer original contest process.',
       'March seven-day experiments are finite subproblems, not annual savings estimates.']
    dump('artifacts/summary.json',summary);dump('artifacts/baseline-metrics.json',baseline);dump('artifacts/metrics.json',metrics)
    figure_data={'annual_comparison':{c:{k:summary['models'][k][c]['saving_vs_daily_baseline_percent'] for k in KINDS} for c in LABELS},'midnight_inventory':{}}
    plt.rcParams.update({'font.family':'Songti SC','font.size':11,'axes.unicode_minus':False,'svg.fonttype':'none'})
    colors=['#777777','#2B718B','#C97840','#597948','#795C91','#AB535A']
    fig,ax=plt.subplots(figsize=(7.2,3.8),layout='constrained');x=np.arange(4);cs=['cross_baseline','closed_affine','affine_mpc','markov_mpc','sddp_markov']
    for j,c in enumerate(cs):ax.plot(x,[summary['models'][k][c]['saving_vs_daily_baseline_percent'] for k in KINDS],marker=['o','s','^','D','v','P'][j],color=colors[j],label=LABELS[c],lw=1.4)
    ax.axhline(0,color='#444444',lw=.7);ax.set(xticks=x,xticklabels=['第二问','第三问','第四问·2','第四问·3'],ylabel='相对每日闭合基线的费用减少 / %',title='2025年2—12月费用比较（跨日候选年末自由）');ax.grid(axis='y',alpha=.15);ax.legend(fontsize=9,ncol=2,loc='upper center',bbox_to_anchor=(.5,-.12))
    savefig(fig,'年度方法比较')
    fig,axs=plt.subplots(2,2,figsize=(7.2,4.8),layout='constrained',sharex=True,sharey=True)
    for panel,(ax,k) in enumerate(zip(axs.ravel(),KINDS)):
        a=dict(np.load(ROOT/f'artifacts/{k}.npz'));dates=a['dates'].astype('datetime64[D]')
        figure_data['midnight_inventory'][k]={'dates':a['dates'].tolist(),'inventory_kwh':a['state'][:,-1].tolist()}
        ax.plot(dates,a['state'][:,-1],color='#2B718B',lw=.9);ax.axhline(6000,color='#999999',ls=':',lw=.8)
        ax.set(title=['第二问','第三问','第四问·2','第四问·3'][panel],ylabel='午夜储电量 / kWh' if panel%2==0 else '',ylim=(900,11100));ax.grid(alpha=.13)
        loc=mdates.AutoDateLocator(minticks=3,maxticks=5);ax.xaxis.set_major_locator(loc);ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    fig.suptitle('跨日库存连续传递，午夜不再固定为6000 kWh');savefig(fig,'午夜库存轨迹')
    figure_data['sddp']=plot_sddp()
    exp=summary['experiments'];keys=['reference','pv_0only','pv_without6','pv_without12','pv_without18']
    fig,ax=plt.subplots(figsize=(7.2,3.4),layout='constrained');base=exp['reference']['total_cost'];vals=[exp[k]['total_cost']-base for k in keys]
    figure_data['short_release_ablation']=dict(zip(keys,vals));dump('artifacts/figure-data.json',figure_data)
    ax.bar(np.arange(len(keys)),vals,color=['#2B718B']+['#C97840']*4);ax.axhline(0,color='#555',lw=.7)
    ax.set(xticks=np.arange(len(keys)),xticklabels=['全部发布','仅0点发布','不使用6点','不使用12点','不使用18点'],ylabel='相对全部发布的费用变化 / 元',title='3月连续七天子问题：保持调约权限不变的预报消融');ax.grid(axis='y',alpha=.12);savefig(fig,'预报发布消融')
    text=['# C题跨日随机控制建模计算交接',
      '本目录已运行的主结果为连续SOC的跨日因果仿射计划与Markov随机动态规划反馈。通用SDDP引擎已实现，并通过独立小树验证；其按月训练的粗未来费用被接入相同MPC，作为备选比较。方法在1月开发期确定，2—12月不再按实际费用重选。论文由用户手工撰写。',
      '详细题意、假设、公式、推导、信息时序和算法限制见[模型与推导](模型与推导.md)。原附件、代码、五份工作簿、完整CSV、科学图表及审查证据均保存在本目录。',
      '## 主结果',table(['问题','开发期选定模型','费用/元','每日闭合基线/元','相对费用减少','年末库存/kWh'],rows),
      '上述主结果允许年末库存自由；每日闭合基线同时要求每个日末6000，所以费用差包含中间跨日自由与一次年末库存变化，不能全部解释成可持续跨日套利。1月暖启动的费用单列，各方法均从其真实末库存6000衔接2月。',
      f"第一问确定性LP购电费为{summary['q1']['total_cost']:,.4f}元，购电量为{summary['q1']['planned_energy']:,.4f} kWh；保留题给首末6000条件。",'## 完整候选对照']
    text.append(table(['方法']+KINDS,[[LABELS[c]]+[f"{summary['models'][k][c]['total_cost']:,.2f}" for k in KINDS] for c in LABELS]))
    text.append(table(['问题','同Markov反馈下SDDP末值减线性末值费用/元'],[[k,f'{v:,.4f}'] for k,v in summary['annual_sddp_difference'].items()]))
    text += ['表中六种候选均实际独立运行整段时间序列，没有事后逐日挑最低费用。SDDP末值＋仿射反馈也已参加1月开发期比较；因其开发期费用不占优，全年备选保留SDDP末值＋Markov反馈。SDDP未被预设为优胜者；其数字反映当前辅助随机模型、训练程度和尾值接入方式，不是对SDDP算法一般优劣的证明。',
      '## 统一年末库存的跨日对照',
      table(['问题','跨日反馈','自由年末费用/元','年末6000费用/元','终端约束增量/元'],[[m['kind'],LABELS[m['candidate']],f"{m['free_total_cost']:,.2f}",f"{m['fixed_total_cost']:,.2f}",f"{m['terminal_constraint_increment']:,.2f}"] for m in summary['global_terminal']]),
      '此处仅在12月31日末施加6000，所有中间午夜仍连续自由。程序复用前332天，并重算最后两天；先复现自由末端后缀、验证每个决策和状态与原轨迹一致，再增加真正的全年末约束。复用依据是本实现的两午夜前瞻及此前不活跃的期末可达约束，不能推广为任意长时域最优策略的结论。',
      table(['问题','每日闭合仿射费用/元','跨日仿射且年末6000费用/元','同末端费用减少/元'],[[m['kind'],f"{summary['models'][m['kind']]['closed_affine']['total_cost']:,.2f}",f"{m['fixed_total_cost']:,.2f}",f"{m['saving_vs_closed_affine_same_global_terminal']:,.2f}"] for m in summary['global_terminal'] if m['candidate']=='affine_mpc']),
      '这组对照保持仿射策略、情景数、信息集、前瞻时域和真实年末库存一致，用于判断移除中间午夜闭合的实际效果；不能以主策略相对基线的全部收益代替这一单因素比较。',
      '## 完美信息乐观参考',
      table(['电价与真实末端','全时域LP费用/元'],[[n,f"{m['objective_cost_yuan']:,.2f}"] for n,m in summary['perfect_information_reference'].items()]),
      '这四个LP预先知道全部实际负载、光伏和电价，采用与回放相同的期初及对应期末约束。它们是不可实施的乐观费用参考；同末端策略费用相对它们的差距同时含信息限制、模型近似和策略类限制，不能称为求解器或SDDP最优性间隙。独立原始—对偶核验见review/global-oracle.json。',
      '## 全年预报发布消融',
      table(['实验','2—12月费用/元','相对同Markov反馈全部发布增量/元'],[[n,f"{m['total_cost']:,.2f}",f"{m['increment_vs_markov_all_releases']:,.2f}"] for n,m in summary['annual_release_ablations'].items()]),
      '此处均保留0、6、12、18点合同调整权限，只移除指定官方预报；消融沿全年连续运行。增量描述当前策略使用该信息后的实测效果，不等同于所有最优策略下的严格信息价值。',
      '第三问“其他时刻的预报”若指现有四个发布时点之外增加发布频率，附件并未提供这些额外时点的预报序列。删除已有发布的消融不能识别新增发布的收益；需要新增时点的带时间戳预报、误差分布及更新成本，再按同一信息时序对照。当前结果只支持评估已有发布的利用效果。',
      '## 参数、预报与压力验证',
      '以下是预先固定的3月14—20日连续七天子问题，均独立从6000开始，除期末6000对照外允许末端自由；不能把七天差值外推成年度收益。预报消融只改变可用官方发布，合同调整权限保持一致。',
      table(['实验','费用/元','紧急电量/kWh','末库存/kWh'],[[n,f"{m['total_cost']:,.4f}",f"{m['emergency_energy']:,.4f}",f"{m['final_inventory']:.4f}"] for n,m in exp.items()]),
      '压力情景在窗口内使实际负载上升10%、实际光伏下降20%，既有官方预报保持不变，后续自建预测可利用已经观察的变化。这是计算反事实，不是原附件另有这些观测。',
      '## SDDP完成范围',
      table(['问题','1月开发期线性末值Markov/元','SDDP末值Markov/元','SDDP减线性/元'],[[k,f"{v['linear_markov']:,.4f}",f"{v['sddp_markov']:,.4f}",f"{v['difference_yuan']:,.4f}"] for k,v in summary['development_sddp_comparison'].items()]),
      '上述开发期为1月25—31日。费用在0.01%以内的差异按预定规则优先采用较简单的线性末值Markov反馈，不能把接近浮点精度的差异写成算法改进。全年费用比较见前表。',
      '通用引擎支持本轮已验证的有限时域、有限阶段独立噪声、连续状态凸线性问题。合同在前置阶段确定，电池在交付噪声揭示后决策。独立小树对照、全路径策略枚举与割检查见review/sddp-checks.json。',
      f"正式回放使用的{summary['tail_shape_analysis']['count']}个三日月模型，在允许库存区间内各有{summary['tail_shape_analysis']['minimum_active_cuts']}—{summary['tail_shape_analysis']['maximum_active_cuts']}条有效根割，其中{summary['tail_shape_analysis']['single_segment_models']}个为单段。这里描述的是500次迭代后已得到的下界形状，不能据此认定真实最优值函数形状。详见artifacts/tail-shape-analysis.json。",
      '每月辅助模型只用此前完整日拟合，两小时聚合、通常三天时域、500次迭代；真实年末或开发子问题末点前只剩一两天时，使用相应缩短的辅助模型，真实末点继续费用为零。其根下界与64条独立模拟策略费用见artifacts/summary.json。模拟均值及区间不是确定上界；部分模型可能仍有训练间隙。当前原数据比较使用SDDP末值增强MPC，不冒称已经直接精确求解全年多阶段随机问题。',
      '## 写作与结果追溯',
      '指定日期的购电、六段充放电、首末SOC和全部紧急事件见[指定日期结果表](指定日期结果表.md)。计算结果目录提供五份附件5格式工作簿及逐10分钟CSV，调整量表填写最终生效合同量r，实际取电量为r+紧急电量，不能将q与r相加。',
      '所有可引用结果由本地程序产生并登记至artifacts/result-registry.json。主要限制：经验场景数有限；前瞻仿射类不模拟未来官方预报创新；Markov下层使用名义未来合同及三箱近似；SDDP辅助模型进行了时间聚合和阶段独立化；没有对电池老化和配网暂态作无数据支撑的扩展。',
      '数据仅含2025年一个历史年度，正式比较为2—12月334日的连续回放。它不能证明跨年泛化、稳态平均成本或未来年度稳定收益。延长运行期与增加独立年份的验证仍需额外数据。',
      '独立审查与模拟评分见review。评分只针对这份建模计算交接，不是尚未手工撰写的论文分数，也不是获奖承诺。']
    (ROOT/'建模计算交接.md').write_text('\n\n'.join(text)+'\n')
    dump('artifacts/execution-finish.json',{'command':'python3 '+' '.join(sys.argv),'exit_code':0,'runtime_seconds':time.perf_counter()-begin})
    print(json.dumps(metrics),flush=True)

def savefig(fig,name):
    for ax in fig.axes:ax.spines[['top','right']].set_visible(False)
    for ext in ['png','svg']:fig.savefig(ROOT/f'figures/{name}.{ext}',dpi=300,bbox_inches='tight',facecolor='white')
    plt.close(fig)

def plot_sddp():
    tail=read('artifacts/tails/q2_31.json');fig,axs=plt.subplots(1,2,figsize=(7.2,3.5),layout='constrained')
    tr=tail['trace'];axs[0].plot([z['iteration'] for z in tr],[z['root_lower_bound']/1e4 for z in tr],color='#2B718B',label='辅助模型根下界')
    ev=tail['evaluation'];ci=np.array(ev['normal_approximation_95_interval'])/1e4
    axs[0].axhspan(*ci,color='#C97840',alpha=.16);axs[0].axhline(ev['mean_policy_cost']/1e4,color='#C97840',ls='--',label='策略均值（95%近似区间）')
    axs[0].set(xlabel='SDDP训练迭代',ylabel='三天辅助模型期望费用 / 万元',title='模型下界与独立模拟估计');axs[0].legend(fontsize=9)
    E=np.linspace(1200,10800,401);cuts=prune_cuts(tail['root_cuts']);v=np.max([a+b*E for a,b in cuts],axis=0);v0=max(a+b*6000 for a,b in cuts)
    result={'trace':tr,'evaluation':ev,'inventory_kwh':E.tolist(),'relative_value_yuan':(v-v0).tolist(),'tail_source':'artifacts/tails/q2_31.json'}
    axs[1].plot(E,v-v0,color='#2B718B');axs[1].axvline(6000,color='#999999',ls=':');axs[1].set(xlabel='进入未来模型的库存 / kWh',ylabel='相对6000 kWh的继续费用 / 元',title='清空合同节点的SDDP库存价值')
    for ax in axs:ax.grid(alpha=.15)
    savefig(fig,'SDDP训练与库存价值')
    return result

if __name__=='__main__':main()
