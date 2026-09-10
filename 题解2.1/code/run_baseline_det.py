# -*- coding: utf-8 -*-
"""确定性LP对照方案（无不确定性防护）：全年逐日预测 + 确定性LP + 执行仿真。
两个口径（供论文归因分解，避免"预报器改进"与"SAA防护"混为一谈）：
  1. 旧预报器(lag-1负载+lag-1光伏) → results/p2_det.npz
  2. 本文预报器(lag-7负载+近3日光伏) → results/p2_det_fc.npz
"""
import sys, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, solve_day_lp, soc_track, DT, ETA
from strategy import base_forecast, feedback_execute, summarize

D = load_data()
t0 = time.time()

def run_det(forecast_fn, out_npz, label):
    days = []
    for d in range(365):
        Lh, Ph = forecast_fn(d)
        sol = solve_day_lp(D['price1'], Lh, Ph, 6000.0, 6000.0)
        p = sol['p']
        # 执行层与SAA方案统一：实时反馈+日末投影（归因阶梯口径一致）
        fb = feedback_execute(p, D['load'][d], D['pv'][d], 6000.0, s_tgt=6000.0)
        c, dd, e = fb['c'], fb['d'], fb['e']
        days.append(dict(d=d, p=p, c=c, dd=dd, e=e, plan_p=p,
                         cost_plan=float(D['price1'] @ p),
                         cost_em=float(5 * D['price1'] @ e), cost_dev=0.0,
                         buy=float(p.sum()), emerg=float(e.sum())))
    np.savez_compressed(out_npz,
                        p=np.array([x['p'] for x in days]),
                        c=np.array([x['c'] for x in days]),
                        dd=np.array([x['dd'] for x in days]),
                        e=np.array([x['e'] for x in days]))
    s = summarize(days)
    print(f'{label} {time.time()-t0:.0f}s: 年总费={s["cost_total"]:.0f} 元, '
          f'日均={s["cost_total"]/334:.0f} 元 (计划{s["cost_plan"]/334:.0f} + 紧急{s["cost_em"]/334:.0f}), '
          f'紧急量日均={s["emerg"]/334:.0f} kWh')
    return s

def fc_old(d):
    if d == 0:
        return D['load1'].copy(), D['pv_fc1'].copy()
    return D['load'][d - 1].copy(), D['pv'][d - 1].copy()

run_det(fc_old, r'D:/shumo/shumoC/results/p2_det.npz', '确定性LP(旧预报器lag-1)')
run_det(base_forecast, r'D:/shumo/shumoC/results/p2_det_fc.npz', '确定性LP(本文预报器)')
