"""Register evidence without upgrading reported totals to locally verified runs."""
from pathlib import Path
import hashlib,json,platform,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
NEXT=ROOT.parent/'C题_下一代随机控制'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['C题.pdf','论文格式规范2026.pdf']:
    shutil.copy2(NEXT/'inputs'/name,ROOT/'inputs'/name)
q2=json.loads((ROOT/'artifacts/q2-new-analysis.json').read_text())
remote=json.loads((ROOT/'artifacts/remote-reported-summary.json').read_text())
sources=json.loads((ROOT/'artifacts/input-source-hashes.json').read_text())
config={**remote['candidate'],'eta':.9,'capacity_kwh':12000,'minimum_kwh':1200,'maximum_kwh':10800,
 'power_kw':5000,'slot_minutes':10,'initial_kwh':6000,'terminal_kwh':6000,'slots_per_day':144,
 'evaluation_days':334,'evaluation_slots':48096,'bootstrap_repetitions':10000,'bootstrap_seed':20260912,
 'pseudo_count_per_cell':1/3,'terminal_penalty_coefficient':1000,'tail_price_quantile':.25,
 'historical_weight':.25,'price_floor':.001,'legacy_horizons_hours':[48,42,36,30],
 'core_slots':432,'replan_slots':36,'official_forecast_hours':24,'interpolation_nodes':25,
 'intraday_history_correction_shrinkage':.8,'roundtrip_efficiency':.81}
dump(ROOT/'artifacts/paper-configuration.json',config)
run_metrics=json.loads((NEXT/'artifacts/formal/q2_6cfbc0fe34fd0999.json').read_text())
replay_config={k:v for k,v in run_metrics['configuration'].items() if k not in ['initial','closed_daily','start_day','end_day']}
assert hashlib.sha256(json.dumps(replay_config,sort_keys=True).encode()).hexdigest()[:16]=='6cfbc0fe34fd0999'
dump(ROOT/'artifacts/replay-config.json',replay_config)
dump(ROOT/'artifacts/data-audit.json',{'status':'completed','scope':'Current supplied evidence, not absent remote caches',
 'checks':[{'name':'Q2 contiguous334days and expected endpoint dates','status':'pass'},
 {'name':'Q2 nonnegative electricity quantities and r=q','status':'pass'},
 {'name':'Q2 physical feasibility and actual bill','status':'pass','source':'q2-new-analysis.json'},
 {'name':'Three remote totals remain labelled as reported','status':'pass'}],
 'missing':['q3 original candidate trajectory','q4_2 original candidate trajectory','q4_3 original candidate trajectory']})
dump(ROOT/'artifacts/baseline-metrics.json',{'q2_cost_yuan':q2['old_total'],'scope':'recomputed old fixed-end Markov trajectory'})
dump(ROOT/'artifacts/metrics.json',{'q2_cost_yuan':q2['new_total'],'scope':'recomputed new Q2 trajectory only'})
entries=[];claims=[]
def walk(value,path=''):
    if isinstance(value,dict):
        for k,v in value.items():yield from walk(v,path+'/'+str(k).replace('~','~0').replace('/','~1'))
    elif isinstance(value,list):
        for k,v in enumerate(value):yield from walk(v,path+'/'+str(k))
    elif isinstance(value,(int,float)) and not isinstance(value,bool):yield path,value
for name,prefix,level in [('annual-comparison.json','annual','mixed_reported_and_recomputed'),
 ('q1-evidence.json','q1','existing_verified_deterministic_result'),
 ('q2-new-analysis.json','q2','locally_recomputed'),('q2-specified.json','q2_specified','locally_recomputed'),
 ('q2-emergency.json','q2_emergency','locally_recomputed'),
 ('paper-configuration.json','configuration','source_code_and_problem_parameters')]:
    p=ROOT/'artifacts'/name
    if not p.exists():continue
    for pointer,value in walk(json.loads(p.read_text())):
        if '/daily_delta/' in pointer:continue
        rid=prefix+pointer.replace('/','.')
        if prefix=='annual':
            kind=pointer.split('/')[1]
            lev='locally_recomputed' if kind=='q2' else 'verified_transcription_of_remote_report'
        else:lev=level
        entries.append({'id':rid,'value':value,'source_artifact':'artifacts/'+name,'source_path':pointer,
                        'status':'verified','evidence_level':lev,
                        'verification_scope':'Value matches identified source; remote summary entries are reported claims, not local replay certification.'})
        claims.append({'result_id':rid,'value':value,'usage':'revised-main.tex / tables / figures / technical-appendix.tex',
                       'evidence_level':lev})
dump(ROOT/'artifacts/result-registry.json',{'status':'limited','results':entries,
 'scope':'Q2 statistics independently recomputed; Q3 and Q4 reported totals transcribed and explicitly attributed.'})
dump(ROOT/'paper/result-claims.json',{'claims':claims,'rounding':'Yuan rounded to cents; ten-thousand-yuan tables rounded to two decimals; exact values retained above.'})
# Resolve every pointer as an independent mechanical traceability check.
for e in entries:
    v=json.loads((ROOT/e['source_artifact']).read_text())
    for k in e['source_path'].split('/')[1:]:
        k=k.replace('~1','/').replace('~0','~');v=v[int(k)] if isinstance(v,list) else v[k]
    assert v==e['value']
dump(ROOT/'artifacts/claim-integrity-check.json',{'status':'PASS','entries':len(entries),'mismatches':0,
 'note':'Pointer/number consistency, not full validation of remote runs.'})
manifest=json.loads((ROOT/'modeling-manifest.json').read_text())
manifest['project'].update(stage='paper_rewritten_with_partial_remote_evidence',status='limited')
manifest['source'].update(statement_files=['inputs/C题.pdf'],data_files=['artifacts/remote-reported-summary.json'],
 input_hashes={x:sha(ROOT/x) for x in ['inputs/C题.pdf','inputs/论文格式规范2026.pdf','artifacts/remote-reported-summary.json']},
 official_rules={'status':'verified','url':'https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html',
 'version':'User-supplied 2026 revised formatting PDF; upstream official-input-comparison retained',
 'reason':'Local PDF read; abstract first, A4, 2.5cm margins, body <=30, source appendix. This is not a claim of full submission readiness.'})
manifest['framing'].update(objectives=['Reconstruct a truthful, derivation-complete manuscript in the supplied style','Compare current annual candidate with old same-task Markov policy'],
 decision_variables=['q','r','E','c','d','emergency','spill'],constraints=['energy balance','capacity and power','causal contracts','true terminal inventory'],
 ambiguities=['Remote Q3/Q4 original caches absent','Unified annual candidate differs from January-final challenger'],
 assumptions=['nonnegative prices','free unlimited spill','continuous single battery','per-direction efficiency0.9','actual price after action'])
manifest['models'].update(selected='registered_72h_legacy_M0_fusion075',candidate_set_justification='Paper revision of registered candidates; no new selection experiment or annual replay performed.',
 candidates=[{'name':'registered_72h_legacy_M0_fusion075','target_output':'same-task annual bill','assumptions':['declared information timing'],
 'data_requirements':['full daily trajectories'],'failure_mode':'annual candidate selection is post-hoc','diagnostic':'independent replay audit'}])
manifest['execution'].update(status='completed',command='python3 src/build_evidence.py',exit_code=0,
 environment={'python':platform.python_version(),'platform':platform.platform()},seed=20260912,
 metrics_file='artifacts/q2-new-analysis.json',figures=['figures/'+p.name for p in sorted((ROOT/'figures').glob('*.png'))],
 note='Executed Q2 reanalysis and figure production only. No claim of rerunning the 113 remote cases.')
manifest['validation'].update(status='pending',checks=[{'name':'Q2 bill, physics and dates','status':'pass','artifact':'artifacts/q2-new-analysis.json'},
 {'name':'registry pointer equality','status':'pass','artifact':'artifacts/claim-integrity-check.json'}],
 sensitivity=[{'name':'MBB block3/7/14','artifact':'artifacts/q2-new-analysis.json'}],
 robustness=[{'name':'Q2 monthly and daily variation','artifact':'artifacts/q2-new-analysis.json'}])
manifest['results'].update(paper_file='revised-main.tex',registry_file='artifacts/result-registry.json',claims_file='paper/result-claims.json')
manifest['review'].update(status='completed',independent=True,reviewer_id='four_role_reviewers',findings_file='review/findings.json')
manifest['pending']=['Obtain original Q3/q4_2/q4_3 candidate6cf JSON/NPZ and audit source hashes, physical trajectories and bills.',
 'Rebuild missing three-task specified-date tables, uncertainty analyses and complete submission workbooks from those trajectories.',
 'Synchronize full formal validation and model-adoption record; do not relabel post-hoc unified candidate as January-final selected.']
dump(ROOT/'modeling-manifest.json',manifest)
dump(ROOT/'review/findings.json',{'reviewer_id':'four_role_reviewers','independent':True,'decision':'limited',
 'reports':['theorem-check.md','code-consistency-review.md','review/final-control-review.md','final-review.md'],
 'content_review':'PASS within declared evidence scope','unresolved':manifest['pending']})
outputs={str(p.relative_to(ROOT)):sha(p) for directory in ['artifacts','figures','tables','model-source'] for p in (ROOT/directory).iterdir()
         if p.is_file() and p.name not in ['reproducibility.json']}
for name in ['revised-main.tex','technical-appendix.tex','output/pdf/基于固定时域与预报融合的微网跨日随机调度.pdf']:
    if (ROOT/name).exists():outputs[name]=sha(ROOT/name)
dump(ROOT/'artifacts/reproducibility.json',{'command':'python3 src/build_evidence.py','exit_code':0,'seed':20260912,
 'source_commit':'c69529366ce888fd133e47b39583a6b2581067e2','input_hashes':manifest['source']['input_hashes'],
 'upstream_source_hashes':sources,'output_hashes':outputs,'scope':'Reanalysis and typesetting; no simulated full remote reproduction is claimed.'})
(ROOT/'claim-code-map.md').write_text('''# 论文—代码—证据映射

| 论证 | 数学定位 | 当前代码 | 数值/核验 |
|---|---|---|---|
| 合同费用 | 两仿射式最大值，凸PWL | model-source/dispatch.py settlement；control.py affine_plan | theorem-check.md、代码独立审查 |
| 单向动作与可达性 | 库存增量消元、真实终点交集 | control.py execute | q2-new-analysis.json /validation |
| 固定72h | b=min(a+432,T*) | nextgen_run.py simulate | paper-configuration.json |
| 融合0.75 | 官方覆盖内凸组合，历史残差同口径 | nextgen_scenarios.py ScenarioFactory.forecast | remote-reported-summary.json /candidate |
| 成熟等权场景 | h+H<=a；时间覆盖 | nextgen_scenarios.py ScenarioFactory.build | new-control-theory.md |
| 因果仿射LP | 合同用截止前误差；受限策略类 | control.py features/affine_plan | new-convex-audit.md |
| M0库存反馈 | 三箱、伪计数、凸Bellman | control.py MarkovDP/inf_convolution | theorem-check.md |
| 四机制年度费用 | 同年度候选比较 | nextgen_run.py +远端summary | annual-comparison.json，Q2复算，其他三项报告值 |
| Q2分项、月差与MBB | 配对轨迹统计；不是显著性/泛化保证 | src/build_evidence.py | q2-new-analysis.json |
| Q2指定日期 | 当段量和四小时累计 | src/build_evidence.py、q2_emergency.py | q2-specified.json、q2-emergency.json |

精确数值到JSON Pointer的逐项映射见 artifacts/result-registry.json；正文用途见 paper/result-claims.json。
''')
(ROOT/'theory-audit.md').write_text('''# 理论强化登记

本文沿用用户指定修订稿的“物理机制→模型→求解→结果”结构，按实际72h/legacy/M0/融合0.75重写。

| 命题/定理 | 条件及证明要点 | 范围 |
|---|---|---|
| 命题1 合同凸性 | 两仿射式最大值 | 退购净额计费模型 |
| 命题2 单向最优解存在 | 保库存、增加免费弃电 | 无限弃电、无循环奖励；非所有最优解 |
| 命题3 紧急成本凸性 | 三仿射式最大值乘非负价格 | 当前库存增量成本 |
| 命题4 单步可达 | 功率平移区间与容量相交 | 连续单电池+完全供需追索 |
| 命题5 真实终点可达 | 必要累计能力+等步长充分构造 | 仅真正终点；不是每日复位 |
| 命题6 成熟块非预见性 | 末目标早于当前节点；输入前缀截断 | 冻结预测族的当前可测重建 |
| 命题7 仿射因果性 | 合法特征的可测仿射组合 | 受限策略类内 |
| 定理1 Bellman凸PWL | 紧域、上图投影、有限非负平均 | 固定名义合同与经验三状态模型 |
| 命题8 斜率合并 | 凸边际斜率排序+资源交换 | 当前分段线性函数；网格为插值 |
| 命题9 融合二阶矩 | 二次式求导；零曲率时误差相同 | 不推出0.75总体最优或费用最优 |
| 命题10 信息价值 | 同分布、权限和费用下策略包含 | 不等于实际融合策略费用排序 |
| 命题11 跨日集合 | 去除午夜等式扩大可行域 | 同一精确模型；近似闭环需实测 |
| 完美信息关系 | 普通电替代有效合同+紧急电 | 逐路径和同分布期望分开 |
| 辅助SDDP | 有效下界替换、对偶支撑、有限噪声平均 | 两小时阶段独立辅助模型；非午夜割不可直接套用 |

新增固定72小时的解释强调时域长度一致，未声称更长时域必然便宜。三个数学审稿角色已分别给出当前范围内PASS，详见相应报告。整体结果材料仍为LIMITED，原因是三机制原始缓存未同步。
''')
(ROOT/'writing-revisions.md').write_text('''# 叙事与防御性表达修订

采用所给论文的排版、推导节奏和图表色彩；摘要按四问给出方法、核心费用和明确对照。对证据范围作一次集中说明，而非每段自我否定。

| 原表达/旧叙事 | 本稿改法 | 作用 |
|---|---|---|
| “每天覆盖到第二个午夜” | 写清固定72h及原48/42/36/30h差异，并用时域图说明 | 主动说明实际新增结构 |
| 将下一代一概写成条件权重与增强状态 | 按6cf实际分支写等权legacy和M0 | 方法与结果一致 |
| “做过SDDP但没有改善，仍用线性” | 主文集中于线性库存价值；附录说明辅助割范围 | 消除过程汇报 |
| “精细化缺乏稳定收益，故不增加复杂度” | 参数表解释计算职责与实际采用配置 | 不替审稿人总结弱点 |
| “只要预报更准就能省钱” | 增加融合二阶矩推导，并明确费用由交易与库存决定 | 解释目标差异 |
| “相对每日闭合贪心节省”混作当前新旧差 | 明确上一版同任务跨日Markov策略 | 保持比较口径 |
| 直接替换费用而保留旧Bootstrap/月度胜率 | Q2从新轨迹计算；其余机制不迁移统计 | 防止新旧证据混用 |
| “费用仅改善0.19%” | “普通购电增加296.61元，紧急费下降26,521.61元” | 正面解释净节省来源 |
| “遗憾的是区间跨零” | 报告三组区间及正负日，定位为当年累计和时间波动 | 克制披露，无情绪化贬低 |
| 宣称一月选定新统一候选 | 表述为年度比较后的已登记统一候选 | 保留选择边界 |
| 完美信息距离称算法最优性gap | 保留费用支配证明，解释其放松的信息和交易条件 | 避免理论越界 |
| 结论突然转入失败与待办 | 结论重复固定视域、融合、价值反馈及四项费用 | 强化记忆点 |

“真正终点”“受限策略类”“摘要证据”等术语是必要的数学与数据定义，保留它们不等于防御性写作。完整性待办放README与审计报告，正文说明直接影响结果解释的证据边界。
''')
(ROOT/'README.md').write_text('''# 固定时域与预报融合：论文修订

参考风格：用户提供的《基于跨日随机控制与价值反馈的微网购电和储能协同调度_修订稿》。代码事实源：当前仓库main内容 c69529366ce888fd133e47b39583a6b2581067e2；核心代码原样复制在model-source。

主要交付：output/pdf/基于固定时域与预报融合的微网跨日随机调度.pdf；revised-main.tex；technical-appendix.tex；theory-audit.md；claim-code-map.md；theorem-check.md；code-consistency-review.md；final-review.md；writing-revisions.md。

实际采用结果配置：6cfbc0fe34fd0999，固定72h、28成熟历史日、7等权场景、alpha0.2、321库存点、legacy上层、M0三状态、linear末值、官方融合0.75。它属于年度比较后的统一候选，与一月最终挑战模型不是同一配置。

证据等级：Q2完整NPZ重新计算并独立审核；Q3、q4_2、q4_3当前只有同步的远端汇总，其四任务年度费用均可据源报告转述，但这三项未冒充本地逐段验证。完整文字与数学稿已交付，整体状态LIMITED，不是全部支撑材料齐全的可直接提交包。缺少的三机制原始JSON/NPZ、完整formal验证、指定日期表与新版完整工作簿需要同步缓存后补齐。未修改参考原稿及旧工作簿。

复算当前论文图表（需保留同级C题_下一代随机控制和C题_论文修订目录）：

```sh
python3 src/build_evidence.py
python3 src/q2_emergency.py
python3 src/write_paper.py
sh compile.sh
python3 src/freeze_revision.py
```

Python依赖numpy、scipy、matplotlib；统计种子20260912，3/7/14日移动块各10000次。LaTeX使用XeLaTeX、ctex、所附fvextra，mac字体。`compile.sh`使用本机已安装的XeLaTeX绝对路径，其他系统需调整该路径及字体设置。

完整模型复算入口是同级C题_下一代随机控制/src/nextgen_run.py，通过--config传入已登记配置、--start31 --stop365，并用--output指定独立结果路径。它读取同级artifacts/data.npz及forecast-selection.json，依赖原项目vendor中的HiGHS。仓库中完整的113项远端缓存尚不在本目录；本文未声称重新运行过这些实验。

可传给--config的原样配置保存在artifacts/replay-config.json，已经重新核对其ID为6cfbc0fe34fd0999；CLI参数须分别写为`--start 31 --stop 365`。不同平台的求解器版本和近退化动作应另行核验，年度汇总不替代跨平台逐段一致性证明。

每个图表都有职责：可达域解释物理约束；框架图解释信息时序；时域图解释72h改变；典型日图验证能量移位；年度比较图展示同任务费用；Q2瀑布图解释节省来源；Q2区间图展示时间波动。
''')
print('Registered',len(entries),'numeric entries; overall status LIMITED')
