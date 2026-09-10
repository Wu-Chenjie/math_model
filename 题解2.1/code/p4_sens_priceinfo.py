# -*- coding: utf-8 -*-
"""P4 信息假设敏感性（论文 A-P4-1 防御）：
基准 P4-2 假设 D日0:00 已知未来48h真实电价；此处改为「明日电价用近7日同时刻均值预测」
（更严口径），其余与 run_year_h2(not adjust) 完全一致。若费用接近基准，说明结论对该假设不敏感。"""
import sys, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, DT, ETA
from strategy import (base_forecast, pv_fc_tmr, make_scenarios, fc_pv_curve,
                      solve_sp_lp, feedback_execute, N)

D = load_data()
K = 15
t0 = time.time()
s_cur = 6000.0
costs = np.zeros(365)
emerg = np.zeros(365)
for d in range(365):
    L1, P1 = base_forecast(d)
    if d < 364:
        L2 = base_forecast(d + 1)[0]
        P2 = pv_fc_tmr(d)
        # 敏感性口径：明日电价=近7日同时刻均值（更严，不用明日真实电价）
        Ptmr = D['price4'][max(0, d - 6):d].mean(0) if d >= 6 else D['price4'][0]
        price2 = np.concatenate([D['price4'][d], Ptmr])
        Lh2 = np.concatenate([L1, L2]); Ph2 = np.concatenate([P1, P2])
        scen_d = make_scenarios(d, K, L1, P1, slot=None)
        Kd = len(scen_d)
        pt_tmr = np.stack([np.stack([L2, P2], 1)])
        scen2 = np.concatenate([scen_d, np.repeat(pt_tmr, Kd, axis=0)], axis=1)
        plan = solve_sp_lp(price2, Lh2, Ph2, scen2, s_cur, s_end=6000.0)
    else:
        plan = solve_sp_lp(D['price4'][d], L1, P1, make_scenarios(d, K, L1, P1),
                           s_cur, s_end=6000.0)
    p_f = plan['p'][:N].copy()
    fb = feedback_execute(p_f, D['load'][d], D['pv'][d], s_cur, s_tgt=None)
    e = fb['e']
    s_cur = float(fb['S'][-1])
    costs[d] = float(D['price4'][d] @ p_f) + float(5 * D['price4'][d] @ e)
    emerg[d] = float(e.sum())
    if d % 60 == 0:
        print(f'day {d} {time.time()-t0:.0f}s', flush=True)

tot = costs[31:].sum()
print(f'P4-2 strict-price-info: total={tot:.0f} ({tot/1e4:.1f} wan), '
      f'emerg={emerg[31:].sum()/1e3:.1f} MWh')
np.savez_compressed(r'D:/shumo/shumoC/results/p4_2_sens_priceinfo.npz',
                    cost=costs, e=emerg)
print('saved p4_2_sens_priceinfo.npz')
