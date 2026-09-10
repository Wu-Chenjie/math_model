# -*- coding: utf-8 -*-
"""问题4主求解：波动电价（附件4）下重算问题2与问题3。
两日滚动窗口（今天场景+明天点预测，今天日末SOC自由、明天日末=6000），
捕捉波动电价下的跨日套利（附件4相邻日价差可超往返损耗成本）。
result4-2: 波动电价下P2框架（不调整）
result4-3: 波动电价下P3框架（0:00两日计划 + 6/12/18调整）
输出 results/p4_2.npz, results/p4_3.npz。
"""
import sys, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from strategy import run_year_h2, summarize, SPEC_DATES

for tag, kw, out in [('P4-2', dict(adjust=False), 'p4_2'),
                     ('P4-3', dict(adjust=True), 'p4_3')]:
    t0 = time.time()
    days = run_year_h2('realtime', K=15, d0=0, d1=365, **kw)
    s = summarize(days)
    print(f'\n[{tag}] {time.time()-t0:.0f}s: 计划费={s["cost_plan"]:.0f}, 违约费={s["cost_dev"]:.0f}, '
          f'紧急费={s["cost_em"]:.0f}, 总={s["cost_total"]:.0f} 元, 紧急量={s["emerg"]:.0f} kWh')
    for date, d in SPEC_DATES.items():
        x = days[d]
        print(f"  {date}: 购电={x['buy']:.0f} kWh, 计划费={x['cost_plan']:.0f}, "
              f"违约费={x['cost_dev']:.0f}, 紧急费={x['cost_em']:.0f}, 总={x['cost_total']:.0f} 元")
    np.savez_compressed(rf'D:/shumo/shumoC/results/{out}.npz',
                        p=np.array([x['p'] for x in days]),
                        c=np.array([x['c'] for x in days]),
                        dd=np.array([x['dd'] for x in days]),
                        e=np.array([x['e'] for x in days]),
                        plan_p=np.array([x['plan_p'] for x in days]))
    print(f'saved results/{out}.npz')
