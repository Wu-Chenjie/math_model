# -*- coding: utf-8 -*-
"""问题3主求解：0:00预报计划 + 6/12/18时滚动调整。
三个方案对比（回答"是否需要引入其他时刻的预报制定调整购电策略"）：
  A: 仅0:00预报，不调整
  B: A + 6/12/18时调整（主方案）
  C: 无预报(naive, 即问题2策略) 作参考下界对比
输出 results/p3.npz。
"""
import sys, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from strategy import run_year, summarize, SPEC_DATES
from common import TBL1_SLOTS, TBL1_LABELS

res = {}
for tag, kw in [('A_fc0_noAdj', dict(pv_plan='fc0', adjust=False)),
                ('B_fc0_adj', dict(pv_plan='fc0', adjust=True)),
                ('C_naive', dict(pv_plan='naive', adjust=False))]:
    t0 = time.time()
    days = run_year('fixed', K=15, d0=0, d1=365, **kw)
    s = summarize(days)
    res[tag] = (days, s)
    print(f'[{tag}] {time.time()-t0:.0f}s: 计划费={s["cost_plan"]:.0f}, 调整违约费={s["cost_dev"]:.0f}, '
          f'紧急费={s["cost_em"]:.0f}, 总={s["cost_total"]:.0f} 元, 紧急量={s["emerg"]:.0f} kWh')

daysB, sB = res['B_fc0_adj']
print(f"\n【P3 主方案B 全年】总费用={sB['cost_total']:.0f} 元；"
      f"比方案A(仅0:00预报)节省 {res['A_fc0_noAdj'][1]['cost_total']-sB['cost_total']:.0f} 元 "
      f"({(res['A_fc0_noAdj'][1]['cost_total']-sB['cost_total'])/res['A_fc0_noAdj'][1]['cost_total']*100:.1f}%)")

for date, d in SPEC_DATES.items():
    x = daysB[d]
    print(f"\n--- {date} (d={d}) 方案B ---")
    print(f"  计划购电量={x['plan_p'].sum():.1f} kWh, 调整(最终执行)购电量={x['buy']:.1f} kWh")
    print(f"  计划费={x['cost_plan']:.1f}, 调整违约费={x['cost_dev']:.1f}, 紧急费={x['cost_em']:.1f}, 当日总={x['cost_total']:.1f} 元")
    for sl, lab in zip(TBL1_SLOTS, TBL1_LABELS):
        print(f"    {lab}: 计划{x['plan_p'][sl]:.2f} / 调整{x['p'][sl]:.2f} kWh")

np.savez_compressed(r'D:/shumo/shumoC/results/p3.npz',
                    p=np.array([x['p'] for x in daysB]),
                    c=np.array([x['c'] for x in daysB]),
                    dd=np.array([x['dd'] for x in daysB]),
                    e=np.array([x['e'] for x in daysB]),
                    plan_p=np.array([x['plan_p'] for x in daysB]))
print('\nsaved results/p3.npz')
