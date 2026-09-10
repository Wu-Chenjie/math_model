# -*- coding: utf-8 -*-
"""数据预处理：将附件1-4统一转为numpy数组(.npz)，供各问题求解脚本加载。
时间粒度：10分钟，每日144时段；Δt = 1/6 h。
"""
import numpy as np
import pandas as pd
import os

ATT = r"C:/Users/y'h/Downloads/CUMCM2026Problems/C题/附件"
OUT = r"D:/shumo/shumoC/data"
os.makedirs(OUT, exist_ok=True)

DT = 1.0 / 6.0  # h
N = 144

# ---------- 附件1：代表日 ----------
df1 = pd.read_excel(os.path.join(ATT, '附件1.xlsx'))
df1.columns = ['time', 'price', 'load', 'pv_fc']
a1 = {
    'price1': df1['price'].to_numpy(float),      # 元/kWh (144,)
    'load1': df1['load'].to_numpy(float),        # kW (144,)
    'pv_fc1': df1['pv_fc'].to_numpy(float),      # kW (144,)
}

# ---------- 附件2：全年负载与光伏实际 (365,144) ----------
xl2 = pd.ExcelFile(os.path.join(ATT, '附件2.xlsx'))
load = pd.read_excel(xl2, sheet_name=0).iloc[:, 1:].to_numpy(float)
pv = pd.read_excel(xl2, sheet_name=1).iloc[:, 1:].to_numpy(float)
assert load.shape == (365, N) and pv.shape == (365, N)

# ---------- 附件3：光伏预报 ----------
df3 = pd.read_excel(os.path.join(ATT, '附件3.xlsx'))
df3.columns = ['date', 'fc_time'] + [f'h{i}' for i in range(1, 25)]
df3['date'] = df3['date'].ffill()
# fc_hours[d, s, k]: 第d天(0-based)、第s次发布(0=0:00,1=6:00,2=12:00,3=18:00)、
# 预报k小时(1..24) -> 整点 (τ+k) mod 24 的功率预报
fc_order = {'0:00': 0, '6:00': 1, '12:00': 2, '18:00': 3}
df3['slot'] = df3['fc_time'].map(fc_order)
fc_hours = np.full((365, 4, 24), np.nan)
for _, r in df3.iterrows():
    d = pd.to_datetime(r['date']).dayofyear - 1
    s = int(r['slot'])
    fc_hours[d, s, :] = r[[f'h{i}' for i in range(1, 25)]].to_numpy(float)
assert not np.isnan(fc_hours).any()

# ---------- 附件4：全年波动电价 (365,144) ----------
price4 = pd.read_excel(os.path.join(ATT, '附件4.xlsx')).iloc[:, 1:].to_numpy(float)
assert price4.shape == (365, N)

np.savez_compressed(
    os.path.join(OUT, 'data.npz'),
    price1=a1['price1'], load1=a1['load1'], pv_fc1=a1['pv_fc1'],
    load=load, pv=pv, fc_hours=fc_hours, price4=price4, dt=DT,
)
print('saved:', os.path.join(OUT, 'data.npz'))
print('load shape', load.shape, 'pv shape', pv.shape, 'fc shape', fc_hours.shape, 'price4 shape', price4.shape)
