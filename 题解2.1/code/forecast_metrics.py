# -*- coding: utf-8 -*-
"""预测精度指标 → paper/tables/fc_metrics.tex（零手抄）。"""
import sys
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data
from strategy import base_forecast, fc_pv_curve

D = load_data()
load, pv = D['load'], D['pv']

def mape(act, pred, d0=31):
    m = np.ones_like(act, bool); m[:d0] = False
    return float(np.abs((pred - act)[m] / act[m]).mean() * 100)

# 负载：lag-7 vs lag-1
ml7 = mape(load, np.roll(load, 7, 0))
ml1 = mape(load, np.roll(load, 1, 0))
# 光伏：夜间出力为0，MAPE 无定义 → 用日发电量相对误差（更稳）
def daily_err(act, pred, d0=31):
    m = np.ones(act.shape[0], bool); m[:d0] = False
    ea = act.sum(1); ep = pred.sum(1)
    return float(np.abs((ep - ea)[m] / ea[m]).mean() * 100)

pv3 = (np.roll(pv, 1, 0) + np.roll(pv, 2, 0) + np.roll(pv, 3, 0)) / 3
mp3 = daily_err(pv, pv3)
mp1 = daily_err(pv, np.roll(pv, 1, 0))
# 附件3整点预报线性插值 vs 当日实际（0:00发布）
corrs = [float(np.corrcoef(fc_pv_curve(d, 0), pv[d])[0, 1]) for d in range(31, 365)]
s = (r"""\begin{tabular}{lrr}
\toprule
预测对象 & 方法 & MAPE / 相关系数 \\
\midrule
小区负载 & 上周同期（lag-7，本文） & """ + f'{ml7:.2f}' + r"""\% \\
小区负载 & 昨日同期（lag-1） & """ + f'{ml1:.2f}' + r"""\% \\
光伏功率 & 近3日均值（本文） & """ + f'{mp3:.2f}' + r"""\% \\
光伏功率 & 昨日同期（lag-1） & """ + f'{mp1:.2f}' + r"""\% \\
光伏功率 & 附件3预报线性插值 & $r\in[""" + f'{min(corrs):.3f}, {max(corrs):.3f}' + r"""]$ \\
\bottomrule
\end{tabular}""")
with open(r'D:/shumo/shumoC/paper/tables/fc_metrics.tex', 'w', encoding='utf-8') as f:
    f.write(s)
print(f'load lag7={ml7:.2f}% lag1={ml1:.2f}% | pv 3day={mp3:.2f}% lag1={mp1:.2f}% corr=[{min(corrs):.3f},{max(corrs):.3f}]')
