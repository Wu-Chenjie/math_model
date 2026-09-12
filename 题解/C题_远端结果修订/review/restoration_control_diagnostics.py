"""Read-only annual horizon contrasts and retrospective forecast moment audit."""
from pathlib import Path
import sys, json, hashlib
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'C题_下一代随机控制'
sys.path.insert(0, str(ROOT / 'src'))
from nextgen_scenarios import ScenarioFactory

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
data = dict(np.load(ROOT/'artifacts/data.npz'))
selection = json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
ids = {'midnight':'cc3ebe6953b57007', 'fixed48':'5c5eb1d7988dccd0', 'fixed72':'7a7d9f1f5f762810'}
out = {'source':'local complete formal JSON+NPZ, recomputed independently', 'annual':{}, 'moments':{}, 'files':{}}
source_versions=set()
for kind in ('q2','q3','q4_2','q4_3'):
    rows = {}
    for mode, uid in ids.items():
        p = ROOT/f'artifacts/formal/{kind}_{uid}.npz'; j = p.with_suffix('.json')
        if not p.exists() or not j.exists():
            rows[mode] = {'available':False}; continue
        a = dict(np.load(p)); m = json.loads(j.read_text()); c = m['configuration']
        source_versions.add(json.dumps(m['source_hashes'],sort_keys=True))
        assert np.array_equal(a['days'],np.arange(31,365))
        assert a['state'].shape == (334,145)
        assert abs(a['state'][0,0]-6000)<1e-5 and abs(a['state'][-1,-1]-6000)<1e-5
        assert c['fusion_weight']==1 and c['scenario_method']=='legacy' and c['upper']=='legacy' and c['lower']=='M0'
        q,r,e,price = [a[k] for k in ('q','r','emergency','price')]
        bill = price*(r+.5*np.abs(r-q)+5*e)
        daily = bill.sum(1); recompute_gap = abs(daily.sum()-m['totals']['total_cost'])
        assert recompute_gap<1e-5
        balance = r+e+a['d']-a['c']-a['spill']-(data['load'][31:]-data['pv'][31:])/6
        recurrence = np.diff(a['state'],axis=1)-.9*a['c']+a['d']/.9
        assert np.max(abs(balance))<1e-5 and np.max(abs(recurrence))<1e-5
        dec = m['decisions']
        rows[mode] = {'available':True,'configuration':c,'cost_yuan':float(daily.sum()),
            'daily_cost_yuan':daily.tolist(), 'recompute_gap_yuan':float(recompute_gap),
            'balance_max_abs':float(np.max(abs(balance))), 'recurrence_max_abs':float(np.max(abs(recurrence))),
            'nonmidnight_core_end_count':sum(v['end']%144!=0 for v in dec),
            'effective_windows':sorted(set(v['effective_window'] for v in dec)),
            'core_lengths':sorted(set(v['end']-v['as_of'] for v in dec))}
        out['files'][str(p.relative_to(ROOT))]=digest(p)
        out['files'][str(j.relative_to(ROOT))]=digest(j)
    comparisons = {}
    for old,new in (('midnight','fixed48'),('fixed48','fixed72'),('midnight','fixed72')):
        if not rows[old]['available'] or not rows[new]['available']: continue
        differences={k:[rows[old]['configuration'][k],v] for k,v in rows[new]['configuration'].items() if rows[old]['configuration'].get(k)!=v}
        delta=np.array(rows[old]['daily_cost_yuan'])-np.array(rows[new]['daily_cost_yuan'])
        comparisons[old+'_to_'+new]={'configuration_differences':differences,'saving_yuan':float(delta.sum()),
            'saving_percent':float(100*delta.sum()/rows[old]['cost_yuan']), 'positive_days':int(np.sum(delta>1e-6)),
            'negative_days':int(np.sum(delta < -1e-6)), 'zero_days':int(np.sum(abs(delta)<=1e-6))}
    out['annual'][kind]={'runs':rows,'comparisons':comparisons}
assert len(source_versions)==1, 'Horizon comparisons must use identical source versions'
out['annual_shared_source_hashes']=json.loads(next(iter(source_versions)))

# Replicate only the as-of prediction interface. No optimization or annual selection.
masked={k:v.copy() for k,v in data.items()}
for name in ('load','pv','price'): masked[name][31:]=np.nan
masked['forecast'][31:]=np.nan
official=ScenarioFactory(masked,selection,True,False,fusion_weight=1.,official_correction=0.)
historical=ScenarioFactory(masked,selection,False,False)
for name,start,stop in (('forecast_development_Jan15_24',14,24),('controller_development_Jan25_31',24,31)):
    eo=[]; eh=[]
    for day in range(start,stop):
        for phase in (0,36,72,108):
            a=day*144+phase; target=masked['pv'].ravel()[a:a+36]
            eo.extend(official.forecast(a,36)['pv']-target)
            eh.extend(historical.forecast(a,36)['pv']-target)
    eo=np.array(eo); eh=np.array(eh)
    A=float(eo@eo/len(eo)); B=float(eh@eh/len(eh)); C=float(eo@eh/len(eo)); D=float(np.mean((eo-eh)**2))
    beta=float(np.clip((B-C)/D,0,1)) if D>0 else None
    grid=[0,.25,.5,.75,1]+([] if beta is None else [beta])
    out['moments'][name]={'dates':[str(data['dates'][start]),str(data['dates'][stop-1])],
        'origins':4*(stop-start),'prediction_horizon_slots':36,'paired_slots':len(eo),
        'A_kw2':A,'B_kw2':B,'C_kw2':C,'D_kw2':D,'beta_star_sample_mse':beta,
        'official_bias_kw':float(eo.mean()),'historical_bias_kw':float(eh.mean()),
        'error_correlation':float(np.corrcoef(eo,eh)[0,1]),
        'weights':[{'beta':b,'mse_kw2':float(np.mean((b*eo+(1-b)*eh)**2)),
                    'mae_kw':float(np.mean(abs(b*eo+(1-b)*eh)))} for b in grid]}
out['files']['artifacts/data.npz']=digest(ROOT/'artifacts/data.npz')
out['files']['artifacts/forecast-selection.json']=digest(ROOT/'artifacts/forecast-selection.json')
out['files']['script']=digest(Path(__file__))
registered=json.loads((ROOT/'artifacts/development-forecast-selection.json').read_text())
fresh=out['moments']['forecast_development_Jan15_24']['weights']
mae_diffs=[abs(v['mae_kw']-next(z['january_pv_mae_kw'] for z in registered['rows'] if z['fusion_weight']==v['beta'] and z['official_correction']==0)) for v in fresh if v['beta'] in (0,.25,.5,.75,1)]
assert max(mae_diffs)<1e-9
out['forecast_mae_registration_max_abs_diff_kw']=max(mae_diffs)
out['boundary_effect']={'identified':False,'reason':'No matched counterfactual with identical fixed72 horizon/scenario pool/tail rule but full outstanding-contract continuation. Midnight-vs-fixed48 also changes actual horizon and mature history; fixed48-vs-fixed72 changes future deliveries/history/tail price interval. Completion metadata omits outside-core delivery cost and is not a measured error.'}
out['selection_scope']='Retrospective January moment diagnosis. Fixed historical forecast families were selected using Jan15-31, overlapping both reported windows. No Feb-Dec observations used in these moment calculations; this is not unbiased held-out validation, and beta_star is an in-sample MSE optimum, not a bill optimum or replacement for beta=.75.'
(HERE/'restoration-control-diagnostics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
lines=['# 控制结构恢复性诊断','', '本报告由同目录 restoration_control_diagnostics.py 实际计算；不修改主论文、模型或年度轨迹。','',
       '## 年度时域单配置因素对照','', '| 机制 | 旧两午夜/元 | 固定48h/元 | 固定72h/元 | 48h→72h节省/元 | 两午夜→72h节省/元 |','|---|---:|---:|---:|---:|---:|']
for k,v in out['annual'].items():
    r=v['runs']; c=v['comparisons']
    lines.append(f"| {k} | {r['midnight']['cost_yuan']:.2f} | {r['fixed48']['cost_yuan']:.2f} | {r['fixed72']['cost_yuan']:.2f} | {c['fixed48_to_fixed72']['saving_yuan']:.2f} | {c['midnight_to_fixed72']['saving_yuan']:.2f} |")
lines+=['','四机制各三组完整334日JSON/NPZ均已找到并重算。比较统一首末6000、β=1、legacy场景和上层、M0反馈及其余参数；固定48与72只改变配置horizon_hours，旧午夜与固定48只改变horizon_mode。它们是配置因素对照，时域变化还同时改变合法成熟历史池和末值取价区间，不是固定所有诱导量的纯物理前瞻效应。该表不使用β=.75的远端统一候选，避免把融合收益混入时域对照。正负日数、完整日账单、配置差及哈希见JSON。', '', '## 开发期配对预测误差矩','',
    '所有误差为PV预测减实际功率，单位kW；A=mean(eO²)、B=mean(eH²)、C=mean(eO eH)、D=mean((eO−eH)²)，不以方差替代有偏误差的二阶矩。每个0/6/12/18时原点预测接下来36段，窗口内每个目标出现一次。','',
    '| 窗口 | 配对段数 | A/kW² | B/kW² | C/kW² | D/kW² | 样本MSE最优β |','|---|---:|---:|---:|---:|---:|---:|']
for k,v in out['moments'].items():
    lines.append(f"| {k} | {v['paired_slots']} | {v['A_kw2']:.6f} | {v['B_kw2']:.6f} | {v['C_kw2']:.6f} | {v['D_kw2']:.6f} | {v['beta_star_sample_mse']:.6f} |")
lines+=['','β*=clip((B−C)/D,0,1)，D>0。MSE与MAE不同，更与受不对称紧急费和库存制约的闭环账单不同；不能把此样本β替代现有.75配置。完整候选权重的MSE、MAE、偏差与相关系数保存在JSON。','',
    '1月15—24日是现有融合MAE选择窗口；1月25—31日是控制器内部开发窗口。固定历史预测族已使用1月15—31日选型，因此两组结果均为事后内部开发诊断，不能称历史逐原点独立预测验证或无偏留出估计。脚本将2月至12月观测及官方发布置NaN，原点预测接口进一步遮蔽该原点后真实量及未发布预报；这些限制排除额外未来输入，却不消除预测族选型的1月重叠。','',
    '## 非午夜边界合同近似能否量化','',
    '当前数据不能识别其独立费用影响。所需反事实是相同固定72h、相同历史池、相同预测和执行条件下，将库存末值替换为含未交付合同的继续状态模型，再配对全年运行；现有缓存没有这一匹配对照。旧午夜与固定48h并非该反事实，因为两者实际时域不同；48与72也改变了历史池和末值时段。','',
    '可以核对非午夜边界出现次数、核心长度、后缀登记和逐段账单，但不能把域外后缀的名义购电费、完美信息差或时域差冒充截断误差。正式执行每日日初签完整当日合同，年度结算覆盖全部实际交付；缺少的是规划继续价值精确度的匹配反事实，不是年度账单遗漏。', '',
    '复现：在任意工作目录执行 `python3 /Users/wuchenjie/Downloads/CUMCM2026Problems/题解/C题_远端结果修订/review/restoration_control_diagnostics.py`。该脚本只读源缓存并重写本诊断MD/JSON。']
(HERE/'restoration-control-diagnostics.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'annual':{k:v['comparisons'] for k,v in out['annual'].items()},'moments':out['moments']},ensure_ascii=False))
