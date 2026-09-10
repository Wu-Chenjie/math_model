# -*- coding: utf-8 -*-
"""问题1：代表日计划购电策略（确定性LP）。
附件1：电价/负载/光伏预测已知；S(0:00)=S(24:00)=6000 kWh。
"""
import sys, json
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, solve_day_lp, soc_track, check_day, TBL1_SLOTS, TBL1_LABELS, TBL2_RANGES, TBL2_LABELS

D = load_data()
price, load, pv = D['price1'], D['load1'], D['pv_fc1']

sol = solve_day_lp(price, load, pv, s_init=6000.0, s_end=6000.0)
p, c, d, S = sol['p'], sol['c'], sol['d'], sol['S']
errs = check_day(S, c, d)
assert not errs, errs

# 负载平衡校验（供电-需求 >= 0）
supply = p + pv * (1/6) + 0.9 * d
demand = load * (1/6) + c
assert supply.min() >= demand.min() - 1e-6 and (supply - demand).min() > -1e-6, 'balance violated'

total_buy = p.sum()
total_cost = float(price @ p)
print(f"全天购电量 = {total_buy:.2f} kWh")
print(f"全天购电费 = {total_cost:.2f} 元")
print(f"0:00储电量 = 6000.00, 24:00储电量 = {S[-1]:.2f}")
print(f"总充电量 = {c.sum():.2f}, 总放电量 = {d.sum():.2f}")
print(f"光伏总发电量 = {pv.sum()/6:.2f} kWh, 负载总需求 = {load.sum()/6:.2f} kWh")

print('\n表1 指定时段购电量:')
for s, lab in zip(TBL1_SLOTS, TBL1_LABELS):
    print(f'  {lab}: {p[s]:.2f} kWh')
print('表2 指定时段充放电量:')
for (a, b), lab in zip(TBL2_RANGES, TBL2_LABELS):
    print(f'  {lab}: 充 {c[a:b].sum():.2f}, 放 {d[a:b].sum():.2f}')

np.savez(r'D:/shumo/shumoC/results/p1.npz', p=p, c=c, d=d, S=S)
print('\nsaved results/p1.npz')
