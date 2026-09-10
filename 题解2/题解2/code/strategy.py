# -*- coding: utf-8 -*-
"""最终策略引擎：两阶段SAA随机规划 + 预报滚动调整 + 实际执行仿真。

预测规则（全部仅用0:00/调整时刻可得信息）：
  负载  L̂[d] = L[d-7]（上周同期；周周期强，MAPE 3.96% vs naive 15.97%）
  光伏  P2/P4-2: P[d-1]（naive, MAPE 7.7%）；P3/P4-3: 附件3预报（corr≈0.99）
场景（SAA）：最近K天"实际−预测"误差样本叠加到当前预测，截断非负。

计划LP（0:00，两阶段）：
  min  Σ π p + λ Σ_k w_k Σ π e^k          λ=5（紧急倍率）
  s.t. p + P^k Δt + 0.9 d + e^k ≥ L^k Δt + c   ∀k   (第一/二阶段解耦)
       S_t = S_{t-1} + 0.9c_t − d_t, 1200≤S≤10800, c,d≤833.33
       S(24:00)=S(0:00)=6000（每日完整循环）
调整LP（6/12/18时，从预报可覆盖首时段t0起）：
  min  Σ_{t≥t0} [π p_t + 0.5π u_t] + 5 Σ w_k Σ π e^k,  u_t≥|p_t−p_plan,t|
费用（P3/P4-3）：总 = Σπ p_final + 0.5Σπ|p_final−p_plan| + 5Σπ E_emerg
执行：购电/充放电严格按（最终）计划；缺口=需求−供给>0 → 紧急购电；弃光无成本。
"""
import sys
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import (load_data, solve_day_lp, soc_track, DT, N,
                    CD_MAX, SOC_MIN, SOC_MAX, ETA)

ADJUST = [(1, 42), (2, 78), (3, 114)]   # (预报slot, 该slot预报可覆盖的首时段)
EM_MULT = 5.0
DEV_MULT = 0.5

def merge_emerg_segments(e):
    """紧急购电量向量 → [(start_t, end_t_excl, qty)] 连续段。"""
    segs, t = [], 0
    on = e > 1e-9
    while t < N:
        if on[t]:
            t2 = t
            while t2 < N and on[t2]:
                t2 += 1
            segs.append((t, t2, float(e[t:t2].sum())))
            t = t2
        else:
            t += 1
    return segs

def hhmm(t):
    m = int(t * 10)
    return f'{m//60:02d}:{m%60:02d}'

# ---------------- 预测与场景 ----------------

def pv_fc3(d):
    """近3日均值光伏预测（d>=3；不足用lag-1回退，d=0用附件1）。"""
    D = load_data()
    if d == 0:
        return D['pv_fc1'].copy()
    if d >= 3:
        return np.maximum((D['pv'][d - 1] + D['pv'][d - 2] + D['pv'][d - 3]) / 3, 0)
    return D['pv'][d - 1].copy()

def base_forecast(d):
    """d日0:00基准预测：负载上周同期（MAPE 3.96%），光伏近3日均值（MAPE 6.42%）。"""
    D = load_data()
    Lh = D['load'][d - 7] if d >= 7 else (D['load1'] if d == 0 else D['load'][d - 1])
    return Lh.copy(), pv_fc3(d)

def fc_pv_curve(d, slot):
    """附件3预报 → 144时段光伏曲线(kW)，整点值线性插值到时段中心。"""
    D = load_data()
    fc = D['fc_hours']
    H = np.concatenate([[0.0], fc[d, 0]])     # slot=0: 整点h=0..24
    if slot > 0:
        tau = slot * 6
        for k in range(1, 25):
            h = tau + k                        # 当天整点（>24 跳过）
            if h <= 24:
                H[h] = fc[d, slot, k - 1]
    centers = (np.arange(N) + 0.5) / 6.0
    return np.interp(centers, np.arange(25), H)

def make_scenarios(d, K, Lh, Ph, slot=None):
    """误差样本场景。slot=None→光伏naive误差；0→fc0误差；1/2/3→对应预报误差。
    返回 (K,144,2) 数组 [...,0]=负载, [...,1]=光伏。"""
    D = load_data()
    L, P = D['load'], D['pv']
    days = [j for j in range(max(7, d - K), d)]      # 负载误差需 j≥7
    if not days:
        return np.stack([np.stack([Lh, Ph], 1)])
    SL, SP = [], []
    for j in days:
        SL.append(L[j] - (L[j - 7] if j >= 7 else L[j - 1]))
        if slot is None:
            SP.append(P[j] - pv_fc3(j))          # 与基准预测规则一致
        else:
            SP.append(P[j] - fc_pv_curve(j, slot))
    SL = np.array(SL[-K:]); SP = np.array(SP[-K:])
    S = np.empty((len(SL), N, 2))
    S[:, :, 0] = np.maximum(Lh[None, :] + SL, 0)      # 负载场景
    S[:, :, 1] = np.maximum(Ph[None, :] + SP, 0)      # 光伏场景（截断非负）
    return S

# ---------------- SAA 计划/调整 LP ----------------

def solve_sp_lp(price, Lh, Ph, scen, s_init, s_end=None, t0=0, p_plan=None,
                lam=EM_MULT):
    """两阶段SAA LP（时段t0..len(price)-1，支持单日或两日窗口）。
    p_plan: 调整模式下0:00计划的购电量(用于违约项u_t)。
    s_end: 窗口末时段SOC固定值(None=自由)。
    返回窗口长度 dict(p,c,d)。"""
    K = len(scen)
    n = len(price) - t0
    pr = price[t0:]
    nv = 3 * n + K * n + n                       # p c d | e | S
    iP, iC, iD, iE, iS = 0, n, 2 * n, 3 * n, 3 * n + K * n

    c_obj = np.zeros(nv)
    c_obj[iP:iP + n] = pr
    c_obj[iE:iE + K * n] = (lam / K) * np.tile(pr, K)
    if p_plan is not None:
        # 违约项 0.5π·u_t，u_t ≥ |p_t − p_plan,t|（u槽附加在末尾）
        nv += n
        iU = nv - n
        c_obj = np.concatenate([c_obj, DEV_MULT * pr])

    # 平衡约束 (K*n 行): -p -0.9d + c - e^k ≤ P^kΔt - L^kΔt
    rows, cols, vals = [], [], []
    b_ub = np.empty(K * n)
    for k in range(K):
        r0 = k * n
        rows += [r0 + i for i in range(n)]; cols += [iP + i for i in range(n)]; vals += [-1.0] * n
        rows += [r0 + i for i in range(n)]; cols += [iD + i for i in range(n)]; vals += [-ETA] * n
        rows += [r0 + i for i in range(n)]; cols += [iC + i for i in range(n)]; vals += [1.0] * n
        rows += [r0 + i for i in range(n)]; cols += [iE + k * n + i for i in range(n)]; vals += [-1.0] * n
        b_ub[r0:r0 + n] = scen[k][t0:, 1] * DT - scen[k][t0:, 0] * DT
    if p_plan is not None:
        # u ≥ p − plan → p − u ≤ plan ; u ≥ plan − p → −p − u ≤ −plan
        r0 = K * n
        rows += [r0 + i for i in range(n)]; cols += [iP + i for i in range(n)]; vals += [1.0] * n
        rows += [r0 + i for i in range(n)]; cols += [iU + i for i in range(n)]; vals += [-1.0] * n
        b_ub = np.concatenate([b_ub, p_plan[t0:]])
        rows += [r0 + n + i for i in range(n)]; cols += [iP + i for i in range(n)]; vals += [-1.0] * n
        rows += [r0 + n + i for i in range(n)]; cols += [iU + i for i in range(n)]; vals += [-1.0] * n
        b_ub = np.concatenate([b_ub, -p_plan[t0:]])
    A_ub = coo_matrix((vals, (rows, cols)), shape=(b_ub.size, nv)).tocsr()

    # SOC 等式 (n 行): S_t − S_{t−1} − 0.9c + d = 0；S_0 = s_init
    rows, cols, vals = [], [], []
    b_eq = np.zeros(n)
    for i in range(n):
        rows.append(i); cols.append(iS + i); vals.append(1.0)
        if i > 0:
            rows.append(i); cols.append(iS + i - 1); vals.append(-1.0)
        rows.append(i); cols.append(iC + i); vals.append(-ETA)
        rows.append(i); cols.append(iD + i); vals.append(1.0)
    b_eq[0] = s_init
    A_eq = coo_matrix((vals, (rows, cols)), shape=(n, nv)).tocsr()

    bounds = ([(0, None)] * n + [(0, CD_MAX)] * n + [(0, CD_MAX)] * n
              + [(0, None)] * (K * n) + [(SOC_MIN, SOC_MAX)] * n)
    if p_plan is not None:
        bounds += [(0, None)] * n                # u 槽
    if s_end is not None:
        bounds[iS + n - 1] = (s_end, s_end)

    res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method='highs')
    if not res.success:
        raise RuntimeError('SP LP failed: ' + res.message)
    x = res.x
    pad = lambda v: np.concatenate([np.zeros(t0), v])
    clean = lambda v: np.where(np.abs(v) < 1e-9, 0.0, v)
    return dict(p=pad(clean(x[iP:iP + n])), c=pad(clean(x[iC:iC + n])),
                d=pad(clean(x[iD:iD + n])))

# ---------------- 全年滚动 ----------------

def run_year_h2(price_mode, adjust=False, K=15, d0=0, d1=365, verbose=False):
    """两日滚动（用于波动电价P4，捕捉跨日套利）：
    每天d解 [d, d+1] 两日LP：今天日末SOC自由，明天日末=6000（明日循环近似），
    今天带K个误差场景、明天为点预测；只执行今天部分，SOC结转，明天滚动重优化。
    adjust=True 时在6/12/18时对当天剩余时段调整（日末=计划当日末SOC）。"""
    D = load_data()
    price4, load, pv = D['price4'], D['load'], D['pv']
    days = []
    s_cur = 6000.0
    for d in range(d0, d1):
        price_d = price4[d]
        L1, P1 = base_forecast(d)
        if d < d1 - 1:
            L2, P2 = base_forecast(d + 1)
            price2 = np.concatenate([price_d, price4[d + 1]])
            Lh2 = np.concatenate([L1, L2]); Ph2 = np.concatenate([P1, P2])
            scen_d = make_scenarios(d, K, L1, P1, slot=None)
            Kd = len(scen_d)
            pt_tmr = np.stack([np.stack([L2, P2], 1)])            # (1,144,2)
            scen2 = np.concatenate([scen_d,
                                    np.repeat(pt_tmr, Kd, axis=0)], axis=1)
            plan = solve_sp_lp(price2, Lh2, Ph2, scen2, s_cur, s_end=6000.0)
            plan_p = plan['p'][:N].copy()
        else:
            plan = solve_sp_lp(price_d, L1, P1, make_scenarios(d, K, L1, P1),
                               s_cur, s_end=6000.0)
            plan_p = plan['p'].copy()
        c_f, d_f = plan['c'][:N].copy(), plan['d'][:N].copy()
        S_track = s_cur + np.cumsum(ETA * c_f - d_f)
        p_f = plan_p.copy()
        if adjust:
            for slot, t0 in ADJUST:
                Ph2 = fc_pv_curve(d, slot)
                scen2 = make_scenarios(d, K, L1, Ph2, slot=slot)
                new = solve_sp_lp(price_d, L1, Ph2, scen2, S_track[t0 - 1],
                                  s_end=S_track[-1], t0=t0, p_plan=plan_p)
                p_f[t0:] = new['p'][t0:]
                c_f[t0:] = new['c'][t0:]
                d_f[t0:] = new['d'][t0:]
                S_track = s_cur + np.cumsum(ETA * c_f - d_f)
        La, Pa = load[d], pv[d]
        supply = p_f + Pa * DT + ETA * d_f
        demand = La * DT + c_f
        e = np.maximum(demand - supply, 0.0)
        cost_plan = float(price_d @ p_f)
        cost_em = float(EM_MULT * (price_d @ e))
        cost_dev = float(DEV_MULT * (price_d @ np.abs(p_f - plan_p))) if adjust else 0.0
        s_cur = float(S_track[-1])
        days.append(dict(d=d, p=p_f, c=c_f, dd=d_f, e=e, plan_p=plan_p,
                         cost_plan=cost_plan, cost_em=cost_em, cost_dev=cost_dev,
                         cost_total=cost_plan + cost_em + cost_dev,
                         buy=float(p_f.sum()), emerg=float(e.sum())))
        if verbose and d % 50 == 0:
            print(f'  day {d}: total={days[-1]["cost_total"]:.0f} S_end={s_cur:.0f}')
    return days


def run_year(price_mode, pv_plan='naive', adjust=False, K=15,
             d0=0, d1=365, verbose=False):
    D = load_data()
    price1, price4, load, pv = D['price1'], D['price4'], D['load'], D['pv']
    days = []
    for d in range(d0, d1):
        price = price1 if price_mode == 'fixed' else price4[d]
        Lh, Ph = base_forecast(d)
        slot0 = None if pv_plan == 'naive' else 0
        if pv_plan == 'fc0':
            Ph = fc_pv_curve(d, 0)
        scen = make_scenarios(d, K, Lh, Ph, slot=slot0)
        plan = solve_sp_lp(price, Lh, Ph, scen, 6000.0, 6000.0)
        p_f, c_f, d_f = plan['p'].copy(), plan['c'].copy(), plan['d'].copy()
        if adjust:
            for slot, t0 in ADJUST:
                S_track = soc_track(6000.0, c_f, d_f)
                Lh2 = Lh                        # 负载预测不变
                Ph2 = fc_pv_curve(d, slot)
                scen2 = make_scenarios(d, K, Lh2, Ph2, slot=slot)
                new = solve_sp_lp(price, Lh2, Ph2, scen2, S_track[t0 - 1],
                                  6000.0, t0=t0, p_plan=plan['p'])
                p_f[t0:], c_f[t0:], d_f[t0:] = new['p'][t0:], new['c'][t0:], new['d'][t0:]
        # ---- 实际执行 ----
        La, Pa = load[d], pv[d]
        supply = p_f + Pa * DT + ETA * d_f
        demand = La * DT + c_f
        e = np.maximum(demand - supply, 0.0)
        cost_plan = float(price @ p_f)
        cost_em = float(EM_MULT * (price @ e))
        cost_dev = float(DEV_MULT * (price @ np.abs(p_f - plan['p']))) if adjust else 0.0
        days.append(dict(d=d, p=p_f, c=c_f, dd=d_f, e=e, plan_p=plan['p'],
                         cost_plan=cost_plan, cost_em=cost_em, cost_dev=cost_dev,
                         cost_total=cost_plan + cost_em + cost_dev,
                         buy=float(p_f.sum()), emerg=float(e.sum())))
        if verbose and d % 50 == 0:
            print(f'  day {d}: total={days[-1]["cost_total"]:.0f} em={cost_em:.0f}')
    return days

def summarize(days, d_start=31):
    sel = [x for x in days if x['d'] >= d_start]
    t = dict(days=len(sel),
             buy=sum(x['buy'] for x in sel),
             emerg=sum(x['emerg'] for x in sel),
             cost_plan=sum(x['cost_plan'] for x in sel),
             cost_em=sum(x['cost_em'] for x in sel),
             cost_dev=sum(x['cost_dev'] for x in sel),
             emerg_days=sum(1 for x in sel if x['emerg'] > 1e-6))
    t['cost_total'] = t['cost_plan'] + t['cost_em'] + t['cost_dev']
    return t

SPEC_DATES = {'2025-03-20': 78, '2025-06-21': 171, '2025-09-23': 265, '2025-12-21': 354}
