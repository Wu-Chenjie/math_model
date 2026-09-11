"""Turn verified executed ledgers into paper tables and a numeric claim registry."""
from pathlib import Path
import hashlib
import json
import sys
import time
import numpy as np
from compare_incremental_results import daily_ledger, pair, block_indices
from current_evidence import require_formal_current, require_figures_current, require_baseline_current

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nextgen_scenarios import Config
KINDS=('q2','q3','q4_2','q4_3')
LABELS={'q2':'问题二','q3':'问题三','q4_2':'问题四-2','q4_3':'问题四-3'}
SOURCE_HASHES={}


def read(relative):
    p=ROOT/relative;SOURCE_HASHES[relative]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())


def ledger(relative):
    p=(ROOT/relative).with_suffix('.npz')
    SOURCE_HASHES[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return daily_ledger(ROOT/relative)


def table(caption,headers,rows,alignment=None):
    alignment=alignment or 'l'+'r'*(len(headers)-1)
    body=['\\begin{table}[htbp]\\centering\\small',f'\\caption{{{caption}}}',
          '\\begin{tabular}{'+alignment+'}\\toprule',' & '.join(headers)+r' \\\midrule']
    body+=[' & '.join(str(v) for v in row)+r' \\' for row in rows]
    return '\n'.join(body+['\\bottomrule\\end{tabular}\\end{table}'])


def fig(file,caption,width='.96'):
    return '\n'.join(['\\begin{figure}[htbp]\\centering',
        f'\\includegraphics[width={width}\\linewidth]{{../figures/{file}.png}}',
        f'\\caption{{{caption}}}','\\end{figure}'])


def main():
    started=time.perf_counter()
    adopted=read('artifacts/model-adoption.json');assert adopted['status']=='PASS'
    baseline=read('artifacts/baseline-reproduction-check.json');assert baseline['status']=='PASS'
    require_baseline_current(ROOT,baseline)
    formal=read('artifacts/formal-validation.json');assert formal['status']=='PASS'
    require_formal_current(ROOT,formal)
    require_figures_current(ROOT);read('artifacts/figure-execution.json')
    frozen=read('artifacts/frozen-development-selection.json')
    comparisons=read('artifacts/incremental-comparisons.json');assert comparisons['status']=='complete'
    freeze_sha=hashlib.sha256((ROOT/'artifacts/frozen-development-selection.json').read_bytes()).hexdigest()
    assert adopted['selection_sha256']==freeze_sha
    assert comparisons['selection_sha256']==freeze_sha
    assert formal['frozen_selection_sha256']==freeze_sha
    info_run=read('artifacts/information-terminal-execution.json');assert info_run['status']=='complete'
    info_review=read('review/information-terminal-independent.json')
    assert info_review['status']=='PASS' and info_review['independent'] is True and not info_review['unresolved']
    assert len(info_review['results'])==4 and {r['name'] for r in info_review['results']}=={'0only','without6','without12','without18'}
    for path,digest in info_review['reviewed_artifact_hashes'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest, 'Information review evidence changed: '+path
        SOURCE_HASHES[path]=digest
    config=Config(**adopted['adopted_configuration']);challenger=Config(**frozen['challenger'])
    rows=comparisons['summaries'];questions={};crossday={};horizons={};direct={}
    idx=block_indices()
    for kind in KINDS:
        questions[kind]=next(r for r in rows if r['kind']==kind and r['configuration_id']==config.identity() and r['comparison']=='legacy_matched_terminal')
        closed=read(f'baseline_frozen/artifacts/annual/{kind}_closed_affine.json')['totals']['total_cost']
        fixed=read(f'baseline_frozen/artifacts/global-terminal/{kind}_affine_mpc.json')['fixed_total_cost']
        crossday[kind]={'closed_affine_cost_yuan':closed,'crossday_affine_cost_yuan':fixed,
                       'crossday_affine_saving_percent':100*(closed-fixed)/closed,
                       'selected_vs_closed_affine_saving_percent':100*(closed-questions[kind]['total_cost_yuan'])/closed}
        horizons[kind]=[next(r for r in rows if r['kind']==kind and r['configuration_id']==Config(horizon_hours=h).identity() and r['comparison']=='fixed48_reference') for h in (48,72,96)]
        m0,m1=Config(**frozen['final_matched_M0']),Config(**frozen['final_matched_M1'])
        d,_,_=pair(ledger(f'artifacts/formal/{kind}_{m1.identity()}'),ledger(f'artifacts/formal/{kind}_{m0.identity()}'),idx)
        direct[kind]=d
    q1=read('baseline_frozen/artifacts/q1.json')
    q1_path=ROOT/'baseline_frozen/artifacts/q1.npz'
    SOURCE_HASHES['baseline_frozen/artifacts/q1.npz']=hashlib.sha256(q1_path.read_bytes()).hexdigest()
    with np.load(q1_path,allow_pickle=False) as day_arrays:
        q1.update(purchased_energy_kwh=float(day_arrays['q'].sum()),charged_energy_kwh=float(day_arrays['c'].sum()),
            discharged_energy_kwh=float(day_arrays['d'].sum()),inventory_min_kwh=float(day_arrays['state'].min()),inventory_max_kwh=float(day_arrays['state'].max()))
    SOURCE_HASHES['artifacts/data.npz']=hashlib.sha256((ROOT/'artifacts/data.npz').read_bytes()).hexdigest()
    with np.load(ROOT/'artifacts/data.npz') as data:
        no_battery=float(data['day_price']@np.maximum((data['day_load']-data['day_pv'])/6,0))
    q1.update(no_battery_cost_yuan=no_battery,saving_vs_no_battery_percent=100*(no_battery-q1['expected_cost'])/no_battery)
    information={}
    for entry in info_run['results']:
        proof=read(entry['validation']);assert proof['status']=='PASS'
        assert hashlib.sha256((ROOT/entry['validation']).read_bytes()).hexdigest()==entry['validation_sha256']
        for suffix,key in [('.npz','input_npz_sha256'),('.json','input_json_sha256')]:
            assert hashlib.sha256((ROOT/entry['source']).with_suffix(suffix).read_bytes()).hexdigest()==proof[key]
        lost=ledger(entry['source'])
        full=ledger('baseline_frozen/artifacts/global-terminal/q3_markov_mpc')
        result,_,_=pair(full,lost,idx)
        information[entry['name']]=result
    oracle=read('baseline_frozen/review/global-oracle.json')['results']
    record={'status':'verified','selected_configuration':adopted['adopted_configuration'],
        'adoption_decision':adopted['decision'],'q1':q1,'questions':questions,'challenger':adopted['question_results'],
        'crossday_affine':crossday,'horizons':horizons,'matched_M1_vs_M0':direct,'information_release_value':information,
        'optimality':{'J_perfect_fixed_yuan':oracle['fixed_fixed6000']['objective_cost_yuan'],
            'J_perfect_variable_yuan':oracle['variable_fixed6000']['objective_cost_yuan'],
            'J_causal_lower_bound':None,'causal_gap':None,
            'scope':'No identifiable true-process expected causal lower bound from this single year; auxiliary SDDP bounds and pathwise perfect-information reference are distinct.'},
        'parameter_selection':'Frozen January selection, followed only by preregistered accept/reject. No annual winner search.',
        'source_hashes':SOURCE_HASHES}
    (ROOT/'artifacts/paper-results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    destination=ROOT/'paper/generated';destination.mkdir(exist_ok=True)
    method='因果仿射合同规划与增强联合状态凸反馈' if config.lower=='M1' else '因果仿射合同规划与凸 Markov 反馈'
    summary=[f"本文构建连续跨日库存、合法预测与因果合同协同的微网控制模型，并以同初末库存的完整年度账单检验算法价值。问题一采用确定性线性规划，购电费为 {q1['expected_cost']:,.2f} 元，较无电池调节节省 {q1['saving_vs_no_battery_percent']:.2f}\\%，结论限于给定确定性日。"]
    for kind in ('q2','q3'):
        r=questions[kind];c=crossday[kind]
        boundary='原日合同不可修改' if kind=='q2' else '仅可使用已发布光伏预报和合法日内合同更新'
        summary.append(f"{LABELS[kind]}采用{method}，334 日费用为 {r['total_cost_yuan']/10000:.2f} 万元，较同真实首末库存的每日闭合仿射方案节省 {c['selected_vs_closed_affine_saving_percent']:.2f}\\%，相对冻结跨日基线变化为节省 {r['saving_percent']:.2f}\\%，适用于{boundary}的设置。")
    r2,r3=questions['q4_2'],questions['q4_3'];c2,c3=crossday['q4_2'],crossday['q4_3']
    summary.append(f"问题四在保持两种合同权限下处理浮动电价，全年费用分别为 {r2['total_cost_yuan']/10000:.2f}、{r3['total_cost_yuan']/10000:.2f} 万元，较同终点每日闭合仿射方案分别节省 {c2['selected_vs_closed_affine_saving_percent']:.2f}\\%、{c3['selected_vs_closed_affine_saving_percent']:.2f}\\%；当期真实价格只用于动作后结算。")
    info0=information['0only']
    summary.append(f"原框架问题三的同终点信息消融表明，完整合法预报相对仅保留零点预报的配对节省为 {info0['saving_yuan']/10000:.2f} 万元；该差额是固定策略的信息敏感性，不是最优信息价值。")
    summary.append('参数仅由一月开发选择，逐时物理约束、合同信息截止和账单经独立检查；7 日块重采样用于评价该年份配对节省的稳定性。')
    if adopted['decision']=='retain_incumbent':summary.append('增量挑战模型未通过预注册年度采用门槛，故保留原框架，并将负结果用于约束模型复杂度。')
    else:summary.append('一月选定挑战模型通过同口径年度采用门槛，全部消融与亏损日期均保留。')
    summary.append('未将完美信息差距解释为纯算法损失，也不声称取得原随机控制问题全局最优。')
    (destination/'abstract.tex').write_text('\n'.join(summary)+'\n')
    content=['\\subsection{问题一的确定性基准}']
    content.append(table('问题一同一确定性日的储能价值',['方案','购电费用 / 元','相对无电池节省 / \\%'],
        [['无电池调节',f"{q1['no_battery_cost_yuan']:.2f}",'0.00'],['线性规划储能调节',f"{q1['expected_cost']:.2f}",f"{q1['saving_vs_no_battery_percent']:.2f}"]]))
    content.append(f"最优方案购买电量为 {q1['purchased_energy_kwh']:.2f} kWh，母线侧总充电和放电分别为 {q1['charged_energy_kwh']:.2f}、{q1['discharged_energy_kwh']:.2f} kWh。初末库存相同，充放电总量的差异反映转换损耗；储能通过时段转移降低费用，并不创造能量。原始与对偶目标及约束残差经独立核验；本问的确定性 LP 最优性不延伸为问题二至四的随机全局最优性。")
    content.append('\\subsection{主策略、冻结基线与挑战模型}')
    content.append('最终采用结论为'+('保留冻结旧框架。' if adopted['decision']=='retain_incumbent' else '采用一月选定挑战模型。')+'所有费用均按实际交付与同一结算公式计算。')
    content.append(table('最终主策略的计算与统计参数',['参数','采用值','类别'],[
        ['规划窗口','两午夜滚动' if config.horizon_mode=='legacy' else str(config.horizon_hours)+' 小时','策略'],
        ['场景概率',{'legacy':'均匀历史代表','medoids':'经验质量缩减','conditional':'条件质量缩减'}[config.scenario_method],'模型结构'],
        ['下层反馈',config.lower,'模型结构'],
        ['历史窗口上限',config.window,'统计'],['代表场景数',config.scenarios,'统计与近似'],
        ['指数平滑系数',config.alpha,'统计'],['仿射增益边界',config.gain_bound,'策略正则'],
        ['库存网格数',config.grid,'数值收敛'],['Markov 组数',config.bins,'统计与近似'],
        ['光伏融合权重',config.fusion_weight,'统计'],['官方误差修正系数',config.official_correction,'统计'],
        ['线性末值倍率',config.tail_scale,'策略']],alignment='lrl'))
    content.append('题面物理参数不参与搜索。增量候选的库存网格按相对细网格的逐问收敛选择，不能因粗网格账单更低而采用它；窗口和场景数报告的是上限，实际成熟样本数逐次记录。若挑战模型被拒绝，表中保留原基线配置。')
    content.append(table('同真实首末库存的年度主比较',['问题','冻结基线 / 万元','主策略 / 万元','节省 / \\%'],
        [[LABELS[k],f"{questions[k]['baseline_cost_yuan']/10000:.4f}",f"{questions[k]['total_cost_yuan']/10000:.4f}",f"{questions[k]['saving_percent']:.4f}"] for k in KINDS]))
    content.append(table('一月选定挑战模型的全年配对节省',['问题','节省 / 万元','95\\% 区间 / 万元','正收益日数'],
        [[LABELS[r['kind']],f"{r['saving_yuan']/10000:.4f}",f"[{r['bootstrap_95_lower_yuan']/10000:.4f}, {r['bootstrap_95_upper_yuan']/10000:.4f}]",r['positive_days']] for r in adopted['question_results']]))
    content.append(fig('全年节省与配对区间','冻结挑战模型相对原框架的年度配对差；区间不代表未来年份的分布无关保证。','.86'))
    content.append(fig('挑战模型逐日累计配对差','累计配对差保留亏损日期；同一曲线不参与正式期参数选择。'))
    content.append(table('主策略的偏差与计算代价',['问题','紧急电量 / 万kWh','弃电 / 万kWh','合同 LP / h'],
        [[LABELS[k],f"{questions[k]['emergency_kwh']/10000:.3f}",f"{questions[k]['spill_kwh']/10000:.3f}",f"{questions[k]['planning_seconds']/3600:.3f}"] for k in KINDS]))
    content.append('弃电为母线总富余弃置，可能包括已经购买的电能，不能直接换算为纯光伏弃电率。求解时间为本机并行回放中的累计测量，不作硬件无关的复杂度结论。')
    content.append('\\subsection{时域与反馈的同口径消融}')
    content.append(fig('固定时域收益与计算量','固定 48、72、96 小时时域在相同生成规则与 M0 下比较；合法历史集合及末值取价窗口随时域变化。'))
    content.append(table('最终配置中 M1 相对匹配 M0 的直接贡献',['问题','节省 / \\%','节省 / 万元','95\\% 区间 / 万元'],
        [[LABELS[k],f"{direct[k]['saving_percent']:.4f}",f"{direct[k]['saving_yuan']/10000:.4f}",f"[{direct[k]['bootstrap_95_lower_yuan']/10000:.4f}, {direct[k]['bootstrap_95_upper_yuan']/10000:.4f}]"] for k in KINDS]))
    content.append('此处 M0/M1 除下层外所有参数完全一致，包括最终末值。其他模块的收益不能抵消 M1 自身缺乏稳定贡献的证据。')
    content.append('\\subsection{跨日库存与合法预报的信息价值}')
    content.append(table('同仿射执行层下跨日架构相对每日闭合',['问题','每日闭合 / 万元','跨日 / 万元','节省 / \\%'],
        [[LABELS[k],f"{crossday[k]['closed_affine_cost_yuan']/10000:.4f}",f"{crossday[k]['crossday_affine_cost_yuan']/10000:.4f}",f"{crossday[k]['crossday_affine_saving_percent']:.4f}"] for k in KINDS]))
    content.append('该对照共同固定真正首末库存并保持仿射执行层，跨日模型同时允许跨日库存和两午夜规划；不把架构差异全部归因于单一末端约束。')
    names={'0only':'仅保留零点预报','without6':'去除六点更新','without12':'去除十二点更新','without18':'去除十八点更新'}
    content.append(table('原框架问题三的合法预报发布消融，统一年末库存',['受限信息','完整预报节省 / 万元','95\\% 区间 / 万元'],
        [[names[n],f"{information[n]['saving_yuan']/10000:.4f}",f"[{information[n]['bootstrap_95_lower_yuan']/10000:.4f}, {information[n]['bootstrap_95_upper_yuan']/10000:.4f}]"] for n in names]))
    content.append('四种受限信息策略均先执行完整年度顺序回放，再经原两午夜策略的前缀等价检查统一真实终点；不向长时域新模型外推该前缀证明。')
    content.append(fig('跨日库存与日内范围','挑战模型库存的日内范围和日末轨迹，所有午夜保持物理连续。'))
    (destination/'results.tex').write_text('\n\n'.join(content)+'\n')
    appendix=[table('完美信息参照与实际策略；未识别因果期望下界',['问题','完美信息 / 万元','主策略 / 万元','因果下界'],
        [[LABELS[k],f"{record['optimality']['J_perfect_variable_yuan' if k.startswith('q4') else 'J_perfect_fixed_yuan']/10000:.4f}",f"{questions[k]['total_cost_yuan']/10000:.4f}",'未获得'] for k in KINDS])]
    appendix.append('全部阶段消融、7 日块重采样的逐日配对表、冻结参数和独立证据均随代码交付。正式评价费用不用于重新选择候选。')
    (destination/'appendix.tex').write_text('\n\n'.join(appendix)+'\n')
    (destination/'discussion.tex').write_text('本文结果限定于原始年度数据、明确的价格披露假设及退购净额口径。条件经验分布、有限时域和状态投影均为可检验近似；复杂模块的负结果构成保留简单模型的证据。\n')
    registry=[];claims=[]
    def walk(value,path=''):
        if isinstance(value,dict):
            for k,v in value.items():
                if k not in ('source_hashes',):walk(v,path+'/'+k.replace('~','~0').replace('/','~1'))
        elif isinstance(value,list):
            for i,v in enumerate(value):walk(v,path+'/'+str(i))
        elif isinstance(value,(float,int)) and not isinstance(value,bool):
            ident='paper'+path.replace('/','.')
            registry.append({'id':ident,'value':value,'source_artifact':'artifacts/paper-results.json','source_path':path,'status':'verified'})
            claims.append({'result_id':ident,'value':value,'usage':'Generated tables, abstract or supporting calculation ledger; text formats numbers without changing raw values.'})
    walk(record)
    (ROOT/'artifacts/result-registry.json').write_text(json.dumps({'schema_version':1,'results':registry},ensure_ascii=False,indent=2)+'\n')
    (ROOT/'paper/result-claims.json').write_text(json.dumps({'schema_version':1,'claims':claims},ensure_ascii=False,indent=2)+'\n')
    (ROOT/'artifacts/metrics.json').write_text(json.dumps({k+'_total_cost':questions[k]['total_cost_yuan'] for k in KINDS},indent=2)+'\n')
    (ROOT/'artifacts/baseline-metrics.json').write_text(json.dumps({k+'_total_cost':questions[k]['baseline_cost_yuan'] for k in KINDS},indent=2)+'\n')
    handoff=['# 已验证结果与采用结论','',
        '本文数字由逐时账单及验证文件生成。所有年度主比较均为 2025-02-01 至 2025-12-31 的 334 日，初始和真实年末库存均为 6000 kWh。', '',
        '**采用结论：'+('保留冻结旧框架。' if adopted['decision']=='retain_incumbent' else '采用一月选定挑战模型。')+'** 全年消融表中的最小值不用于另选模型。', '',
        '| 问题 | 原基线费用 / 元 | 主策略费用 / 元 | 相对节省 / % | 主策略节省 95% 区间 / 元 |', '|---|---:|---:|---:|---|']
    for k in KINDS:
        r=questions[k];handoff.append(f"| {LABELS[k]} | {r['baseline_cost_yuan']:.2f} | {r['total_cost_yuan']:.2f} | {r['saving_percent']:.6f} | [{r['bootstrap_95_lower_yuan']:.2f}, {r['bootstrap_95_upper_yuan']:.2f}] |")
    handoff+=['','| 问题 | 紧急电量 / kWh | 紧急费用 / 元 | 弃电 / kWh | 合同求解时间 / 秒 |', '|---|---:|---:|---:|---:|']
    for k in KINDS:
        r=questions[k];handoff.append(f"| {LABELS[k]} | {r['emergency_kwh']:.3f} | {r['emergency_cost_yuan']:.2f} | {r['spill_kwh']:.3f} | {r['planning_seconds']:.3f} |")
    handoff+=['','弃电为母线总富余，可能包括已购电能。时间是实际并行回放中测量的合同 LP 累计时间；完整时间分解见消融汇总。','',
        '## 冻结挑战模型的直接配对结果','', '| 问题 | 节省 / 元 | 节省 / % | 95% 区间 / 元 | 正收益日数 |','|---|---:|---:|---|---:|']
    for r in adopted['question_results']:
        handoff.append(f"| {LABELS[r['kind']]} | {r['saving_yuan']:.2f} | {r['saving_percent']:.6f} | [{r['bootstrap_95_lower_yuan']:.2f}, {r['bootstrap_95_upper_yuan']:.2f}] | {r['positive_days']} |")
    handoff+=['','区间采用共同日期索引的 7 日移动块 bootstrap，10000 次重采样；仅诊断该年稳定性，不是未来年份保证。亏损日期保留。','',
        '## 主策略配置','', '```json',json.dumps(adopted['adopted_configuration'],ensure_ascii=False,indent=2),'```','',
        '## 可追溯文件','',
        '- 建模公式、时序和实现边界：`建模与计算交接.md`。',
        '- 开发选择：`一月开发冻结记录.md` 与 `artifacts/frozen-development-selection.json`。',
        '- 所有配置及费用：`计算结果/增量消融汇总.csv`、`计算结果/阶段同口径消融.csv`。',
        '- 334 日逐日配对表及原始输出：`计算结果/`、`artifacts/formal/`。',
        '- 采用门槛及失败项：`artifacts/model-adoption.json`。',
        '- 独立物理/计费验证：`artifacts/formal-validation.json`；信息与小型数学反例：`artifacts/model-check-validation.json`。',
        '- 完美信息参照和不可识别的因果下界：`artifacts/paper-results.json`，不把两者差距解释为纯算法损失。',
        '- 一键复现：在本目录执行 `./复现.sh --workers 8`。', '',
        '该文件确认数值与采用结果，不替代 PDF 逐页检查或独立终审；最终完成状态以完整交付清单为准。']
    (ROOT/'结果与采用结论.md').write_text('\n'.join(handoff)+'\n')
    execution={'status':'complete','command':sys.argv,'exit_code':0,'runtime_seconds':time.perf_counter()-started,'registry_results':len(registry),
               'source_hashes':SOURCE_HASHES,'generated':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.tex')}}
    (ROOT/'artifacts/paper-results-execution.json').write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
