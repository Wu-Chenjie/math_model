# -*- coding: utf-8 -*-
"""问题2主求解：全年逐日SAA计划 + 执行仿真。
输出 results/p2.npz（逐日计划/执行/紧急购电），并打印统计与指定日期结果。
"""
import sys, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from strategy import run_year, summarize, SPEC_DATES
from common import TBL1_SLOTS, TBL1_LABELS

t0 = time.time()
days = run_year('fixed', pv_plan='naive', adjust=False, K=15, d0=0, d1=365)
print(f'P2完成 {time.time()-t0:.1f}s')

s = summarize(days)
print(f"【P2 全年 2025.2.1-12.31, {s['days']}天】")
print(f"  总购电量      = {s['buy']:.0f} kWh")
print(f"  计划购电费    = {s['cost_plan']:.0f} 元")
print(f"  紧急购电量    = {s['emerg']:.0f} kWh ({s['emerg_days']}天发生)")
print(f"  紧急购电费    = {s['cost_em']:.0f} 元")
print(f"  总购电费      = {s['cost_total']:.0f} 元")

# 指定日期
for date, d in SPEC_DATES.items():
    x = days[d]
    print(f"\n--- {date} (d={d}) ---")
    print(f"  计划购电量={x['buy']:.1f} kWh, 计划购电费={x['cost_plan']:.1f} 元")
    print(f"  紧急购电量={x['emerg']:.1f} kWh, 紧急购电费={x['cost_em']:.1f} 元, 当日总费用={x['cost_total']:.1f} 元")
    for sl, lab in zip(TBL1_SLOTS, TBL1_LABELS):
        print(f"    {lab}: {x['p'][sl]:.2f} kWh")

np.savez_compressed(r'D:/shumo/shumoC/results/p2.npz',
                    p=np.array([x['p'] for x in days]),
                    c=np.array([x['c'] for x in days]),
                    dd=np.array([x['dd'] for x in days]),
                    e=np.array([x['e'] for x in days]),
                    plan_p=np.array([x['plan_p'] for x in days]))
print('\nsaved results/p2.npz')
