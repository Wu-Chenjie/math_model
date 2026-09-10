# -*- coding: utf-8 -*-
"""建模审查用数据核查（非求解代码）：预报对齐、预报技巧、naive预报预筛、电价统计"""
import numpy as np
import pandas as pd

d = np.load('D:/shumo/shumoC/data/data.npz')
price1, load1, pvfc1 = d['price1'], d['load1'], d['pv_fc1']
load, pv, fc, price4 = d['load'], d['pv'], d['fc_hours'], d['price4']

print('== 0. 数据健全性 ==')
print('fc NaN:', np.isnan(fc).sum(), ' fc range:', fc.min(), fc.max())
print('pv NaN:', np.isnan(pv).sum(), ' load NaN:', np.isnan(load).sum())

def hourly_to_144(hourly, first_hour):
    """把24个整点预报值广播到144个10分钟时段。first_hour=预报第1个值对应的钟点(1..24)。
    约定: 时段k(1..144)属于钟点 ceil(k*10/60)（附件1行k标签=该段末时刻）。"""
    hours = np.ceil(np.arange(1, 145) * 10 / 60).astype(int)  # 1..24
    idx = hours - first_hour  # 0..23
    ok = (idx >= 0) & (idx <= 23)
    out = np.full(144, np.nan)
    out[ok] = hourly[idx[ok]]
    return out

print('\n== 1. 附件3发布时刻对齐检验（广播到144段后对实际PV的MAE, kW）==')
tau = [0, 6, 12, 18]
for r in range(4):
    for shift in [1, 0]:  # 预报k小时= tau+shift+k
        errs = []
        for dd in range(1, 364):
            errs.append(np.nanmean(np.abs(hourly_to_144(fc[dd, r, :], tau[r] + shift) - pv[dd])))
        print(f'release {tau[r]:2d}h, shift={shift}: MAE={np.nanmean(errs):8.1f}')

print('\n== 2. 各发布时刻预报 vs 持续性预报(前一日实际) ==')
print('persistence(lag1): MAE=', np.round(np.abs(pv[1:] - pv[:-1]).mean(), 1))

print('\n== 3. P2 naive预报预筛 (预报D日144段, 评估2.1-12.31, MAE kW) ==')
def mae(pred, act):
    return np.abs(pred - act).mean()
def pmw(pred, act):
    w = price1 / price1.mean()
    return (np.abs(pred - act) * w).mean()
N = 365
weekday = np.array([pd.Timestamp('2025-01-01').dayofweek + i for i in range(N)]) % 7
for name, arr in [('负载', load), ('光伏', pv)]:
    res = {}
    lag1, lag7, wk4, ewma, mean3, mix = [], [], [], [], [], []
    for D in range(31, N):  # 2.1起
        a = arr[D]
        lag1.append(mae(arr[D-1], a)); lag7.append(mae(arr[D-7], a))
        idxs = [D-7*k for k in range(1, 5)]
        wk4.append(mae(np.mean(arr[idxs], axis=0), a))
        mean3.append(mae(arr[[D-1, D-2, D-3]].mean(axis=0), a))
        e = arr[D-1]
        for j in range(D-2, D-8, -1):
            e = 0.3*arr[j] + 0.7*e
        ewma.append(mae(e, a))
        mix.append(mae(arr[D-7]*0.5 + arr[D-1]*0.5, a))
    print(f'{name}: lag1={np.mean(lag1):7.1f}  lag7={np.mean(lag7):7.1f}  周均4={np.mean(wk4):7.1f} '
          f'  EWMA={np.mean(ewma):7.1f}  3日均={np.mean(mean3):7.1f}  lag1+lag7混合={np.mean(mix):7.1f}')
    print(f'{name} 价格加权: lag1={np.mean([pmw(p,a) for p,a in zip([arr[D-1] for D in range(31,N)],[arr[D] for D in range(31,N)])]):7.1f}')

print('\n== 4. 附件4波动电价统计 ==')
dm = price4.mean(axis=1)
print('全体均值', price4.mean().round(4), ' 日均值范围', dm.min().round(4), dm.max().round(4),
      ' 日内极差均值', (price4.max(axis=1)-price4.min(axis=1)).mean().round(4))
print('相邻日日均值差的|均值|:', np.abs(np.diff(dm)).mean().round(4), ' 与分时电价均值差:', abs(price4.mean()-price1.mean()).round(4))
print('附件1电价: min', price1.min(), 'max', price1.max(), 'unique days=1（每天相同）')

print('\n== 5. P1可行性速览: 附件1净负荷(负载-光伏, kW) ==')
net = load1 - pvfc1
print('净负荷 min', net.min().round(0), 'max', net.max().round(0), ' 需购电时段数:', (net > 0).sum(), '/144')
print('峰谷电价时刻: 最低价', price1.argmin(), '最高价', price1.argmax())
