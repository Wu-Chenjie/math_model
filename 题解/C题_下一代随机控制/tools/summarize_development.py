"""Describe the immutable January selection; no estimation or model selection."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def main():
    file=ROOT/'artifacts/frozen-development-selection.json';f=json.loads(file.read_text())
    assert f['status']=='frozen'
    cfg=f['challenger'];stages=f['stages']
    lines=['# 一月开发冻结记录','',f"冻结时间：{f['frozen_utc']}。配置文件 SHA-256：`{hashlib.sha256(file.read_bytes()).hexdigest()}`。",'',
        '开发账单仅使用 1 月 25—31 日，预测融合误差筛选使用 1 月 15—24 日；既有预测模型族亦由一月选择，因此不把开发费用称为无偏留出结果。正式评价为 2 月 1 日至 12 月 31 日。','',
        '## 冻结挑战配置','', '| 参数 | 值 | 类别 |','|---|---:|---|']
    groups={'horizon_hours':'策略','window':'统计','scenarios':'统计/数值近似','alpha':'统计',
        'gain_bound':'策略正则','grid':'数值收敛','bins':'统计/数值近似','scenario_method':'模型结构',
        'upper':'模型结构','lower':'模型结构','tail_scale':'策略','tail':'模型结构',
        'fusion_weight':'统计','official_correction':'统计','final':'共同评价边界'}
    for key,group in groups.items():lines.append(f'| `{key}` | {cfg[key]} | {group} |')
    lines+=['','题面物理参数未参与搜索；各方案共用初始库存与真实年末库存 6000 kWh。', '',
        f"共登记 {len(f['annual_configurations'])} 个不同经济配置，每个配置执行四种任务口径的 334 日顺序闭环。全年仅允许接受或拒绝该冻结挑战模型，不允许从消融表另挑赢家。", '',
        '## 阶段证据','', '| 阶段 | 候选数 | 用费用选型 | 对首候选的最小等权归一费用 |','|---|---:|---|---:|']
    for st in stages:
        lines.append(f"| `{st['name']}` | {len(st['configurations'])} | {'是' if st['selecting'] else '否，仅诊断'} | {min(st['scores']):.8f} |")
    lines+=['', '非选型阶段中的 `chosen_index` 只是通用费用诊断函数的返回值，不是正式采用结果。库存网格按与 641 点参照的逐问相对账单差收敛选择；M1 按独立稳定性门槛选择。真正采用参数以冻结配置为准。','',
        '## 网格收敛与 M1 直接对照','', '| 库存网格 | 对 641 点最大逐问账单差 / % |','|---|---:|']
    st=next(s for s in reversed(stages) if s['name'].endswith('inventory_grid_convergence'))
    costs=np.asarray(st['costs']);error=np.max(np.abs(costs/costs[-1]-1),axis=1)*100
    for c,e in zip(st['configurations'],error):lines.append(f"| {c['grid']} | {e:.6f} |")
    lines+=['','收敛容差为 0.02%，从小到大取首个全部任务均满足者；没有按最低账单选择网格。','',
        '| M1 相对最终匹配 M0 | 一月费用节省 / % |','|---|---:|']
    for kind,value in zip(('Q2','Q3','Q4-2','Q4-3'),f['final_M1_question_savings']):lines.append(f'| {kind} | {100*value:.6f} |')
    lines+=['',f"M1 开发门槛：{'通过' if f['final_M1_development_pass'] else '未通过'}。最终活动仿射增益触边比例为 {100*f['gain_hit_ratio_at_freeze']:.6f}%；触发扩大边界的阈值为 5%。",'',
        '较大窗口在一月可能没有更多成熟块，W=28 与 W=56 的开发结果不能证明全年窗口效应。分位状态数与场景数的年度敏感性全部保留。', '',
        '## 采用限制','',
        '当前记录仅确认开发冻结，不证明任何年度改善。官方预报融合参数可以退化为原预测；增强反馈可以保留为负结果。最终年度费用、逐日配对差、7 日块 bootstrap 区间和采用决定需等待完整回放及独立验证。']
    (ROOT/'一月开发冻结记录.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'reported','frozen_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'annual_configurations':len(f['annual_configurations'])}))
if __name__=='__main__':main()
