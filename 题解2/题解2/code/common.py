# -*- coding: utf-8 -*-
"""公共模块：数据加载、单日计划LP、执行仿真、校验。

模型记号（每时段 t=0..143，Δt=1/6 h）：
  p_t  购电量(kWh)          c_t  充电量(kWh，储能侧充入前)
  d_t  放电量(kWh，储能侧放出)  S_t  时段末储能量(kWh)
  充放电效率 eta=0.9：充电 ΔS=0.9·c_t；放电 ΔS=−d_t，输出到交流侧 0.9·d_t
  供电-需求平衡(≥)：p_t + PV·Δt + 0.9·d_t ≥ L·Δt + c_t   （多余弃光，不售电）
"""
import numpy as np
from scipy.optimize import linprog

DT = 1.0 / 6.0
N = 144
CD_MAX = 5000.0 * DT          # 单时段最大充/放电量 833.333 kWh
SOC_MIN, SOC_MAX = 1200.0, 10800.0
ETA = 0.9

_DATA = None

def load_data():
    global _DATA
    if _DATA is None:
        z = np.load(r"D:/shumo/shumoC/data/data.npz")
        _DATA = {k: z[k] for k in z.files}
    return _DATA

# ---------------- 单日计划 LP ----------------

def solve_day_lp(price, load_hat, pv_hat, s_init, s_end):
    """单日计划LP：min Σ π_t·p_t
    price/load_hat/pv_hat: (144,) 电价(元/kWh)、预测负载(kW)、预测光伏(kW)
    s_init: 日初储电量; s_end: 日末储电量(None=自由，仅受上下限约束)
    返回 dict(p,c,d,S) 各 (144,)，S 为时段末储电量轨迹(含时段0)。
    """
    n = N
    # 变量: p(0..143) c(144..287) d(288..431) S(432..575=S_1..S_144)
    nv = 4 * n
    c_obj = np.zeros(nv)
    c_obj[:n] = price

    # 平衡: -p -0.9d + c <= PV·Δt - L·Δt
    A_ub = np.zeros((n, nv)); b_ub = np.zeros(n)
    idx = np.arange(n)
    A_ub[idx, idx] = -1.0                      # -p
    A_ub[idx, 2*n + idx] = -ETA                # -0.9 d
    A_ub[idx, n + idx] = 1.0                   # +c
    b_ub = pv_hat * DT - load_hat * DT

    # SOC递推: S_t - S_{t-1} - 0.9c_t + d_t = 0, S_0=s_init
    A_eq = np.zeros((n, nv)); b_eq = np.zeros(n)
    A_eq[idx, 3*n + idx] = 1.0                 # S_t (t=0 → S_1)
    if n > 1:
        A_eq[idx[1:], 3*n + idx[:-1]] = -1.0   # -S_{t-1}
    A_eq[idx, n + idx] = -ETA                  # -0.9 c
    A_eq[idx, 2*n + idx] = 1.0                 # +d
    b_eq[0] = ETA * 0.0 + s_init * 1.0         # S_1 = s_init + 0.9c - d → S_1-0.9c+d = s_init

    bounds = ([(0, None)] * n + [(0, CD_MAX)] * n + [(0, CD_MAX)] * n
              + [(SOC_MIN, SOC_MAX)] * n)
    if s_end is not None:
        # 替换最后一个SOC变量的界为等式
        bounds[3*n + n - 1] = (s_end, s_end)

    res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method='highs')
    if not res.success:
        raise RuntimeError('LP failed: ' + res.message)
    x = res.x
    p, c, d, S = x[:n], x[n:2*n], x[2*n:3*n], x[3*n:]
    # 清洗数值噪声
    p[np.abs(p) < 1e-9] = 0; c[np.abs(c) < 1e-9] = 0; d[np.abs(d) < 1e-9] = 0
    return dict(p=p, c=c, d=d, S=S, cost=float(price @ p))

# ---------------- 执行仿真 ----------------

def simulate_day(p, c, d, load_act, pv_act, price, emergency_mult=5.0):
    """按给定购电/充放电轨迹在实际负载/光伏下执行一天。
    缺口 = 负载 + 充电需求 − 购电 − 光伏 − 放电输出，若>0则紧急购电(emergency_mult倍价)。
    返回紧急购电量向量与费用分解。
    """
    supply = p + pv_act * DT + ETA * d
    demand = load_act * DT + c
    gap = demand - supply
    e = np.maximum(gap, 0.0)                   # 紧急购电量 (kWh)
    cost_plan = float(price @ p)
    cost_em = float(emergency_mult * price @ e)
    return dict(e=e, cost_plan=cost_plan, cost_em=cost_em,
                cost_total=cost_plan + cost_em, soc_end=None)

def soc_track(s_init, c, d):
    """由充放电轨迹计算SOC轨迹（时段末，144个）。"""
    return s_init + np.cumsum(ETA * c - d)

def check_day(S, c, d, e=None, load_act=None, pv_act=None, p=None):
    """校验SOC约束与功率约束，返回违例列表。"""
    errs = []
    if S.min() < SOC_MIN - 1e-6: errs.append(f'SOC min {S.min():.2f} < {SOC_MIN}')
    if S.max() > SOC_MAX + 1e-6: errs.append(f'SOC max {S.max():.2f} > {SOC_MAX}')
    if c.max() > CD_MAX + 1e-6: errs.append(f'charge {c.max():.2f} > {CD_MAX:.2f}')
    if d.max() > CD_MAX + 1e-6: errs.append(f'discharge {d.max():.2f} > {CD_MAX:.2f}')
    return errs

# ---------------- 表格输出辅助 ----------------

# 表1购电时段索引（10:00-10:10 起各时段）
TBL1_SLOTS = [60, 72, 84, 96, 108, 120]
TBL1_LABELS = ['10:00-10:10', '12:00-12:10', '14:00-14:10',
               '16:00-16:10', '18:00-18:10', '20:00-20:10']
# 表2充放电4小时段
TBL2_RANGES = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
TBL2_LABELS = ['0:00-4:00', '4:00-8:00', '8:00-12:00',
               '12:00-16:00', '16:00-20:00', '20:00-24:00']
