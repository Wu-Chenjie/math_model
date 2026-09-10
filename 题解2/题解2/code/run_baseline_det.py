# -*- coding: utf-8 -*-
"""确定性LP对照方案（无不确定性防护）：全年逐日 naive预测 + 确定性LP + 执行仿真。
仅作论文对比基准。输出 results/p2_det.npz 与日均费用。
"""
import sys, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, solve_day_lp, soc_track, DT, ETA
from strategy import summarize

D = load_data()
days = []
t0 = time.time()
for d in range(365):
    if d == 0:
        Lh, Ph = D['load1'].copy(), D['pv_fc1'].copy()
    else:
        Lh, Ph = D['load'][d - 1].copy(), D['pv'][d - 1].copy()
    sol = solve_day_lp(D['price1'], Lh, Ph, 6000.0, 6000.0)
    p, c, dd = sol['p'], sol['c'], sol['d']
    e = np.maximum(D['load'][d] * DT + c - p - D['pv'][d] * DT - ETA * dd, 0)
    days.append(dict(d=d, p=p, c=c, dd=dd, e=e, plan_p=p,
                     cost_plan=float(D['price1'] @ p),
                     cost_em=float(5 * D['price1'] @ e), cost_dev=0.0,
                     buy=float(p.sum()), emerg=float(e.sum())))
np.savez_compressed(r'D:/shumo/shumoC/results/p2_det.npz',
                    p=np.array([x['p'] for x in days]),
                    dd=np.array([x['dd'] for x in days]),
                    e=np.array([x['e'] for x in days]))
s = summarize(days)
print(f'确定性LP对照 {time.time()-t0:.0f}s: 日均总费用={s["cost_total"]/334:.0f} 元 '
      f'(计划{s["cost_plan"]/334:.0f} + 紧急{s["cost_em"]/334:.0f}), 紧急量日均={s["emerg"]/334:.0f} kWh')
