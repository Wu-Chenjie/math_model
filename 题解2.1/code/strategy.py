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
执行（实时反馈）：合同购电量按计划/调整执行；电池观测当期实际净负荷优先
  吸收偏差（富余充电/短缺放电），日循环方案（P2/P3）经终端可达区间投影
  保证日末=6000；两日滚动方案（P4）不投影，窗口末目标由次日滚动重解承接；
  剩余缺口→紧急购电（5倍价），富余→弃光（免费）。
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

def pv_fc_tmr(d):
    """d+1日光伏预测（合规版，供两日滚动用）：仅用d-1及更早的实际光伏，
    避免混入d日当日实际（0:00时尚不可得）。d<3时用可得历史均值/附件1。"""
    D = load_data()
    if d == 0:
        return D['pv_fc1'].copy()
    if d >= 3:
        return np.maximum((D['pv'][d - 1] + D['pv'][d - 2] + D['pv'][d - 3]) / 3, 0)
    return np.maximum(D['pv'][:d].mean(axis=0), 0)

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

def intraday_correct(Lh, La_act, t_now, win=36):
    """日内负载偏差修正：用当天最近win个时段的实际-预测平均偏差平移修正
    剩余时段预测（仅用t_now前已实现信息；无历史可用时z=0不修正）。"""
    Lh2 = Lh.copy()
    if t_now <= 0:
        return Lh2, 0.0
    t0 = max(0, t_now - win)
    z = float(np.mean(La_act[t0:t_now] - Lh[t0:t_now]))
    Lh2[t_now:] = np.maximum(Lh[t_now:] + z, 0.0)
    return Lh2, z

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

# ---------------- 执行层实时反馈 ----------------

def feedback_execute(r, La, Pa, s_init, s_tgt=None, t_off=0):
    """执行层实时反馈：观测当期实际净负荷，电池优先吸收偏差，越界部分
    走紧急购电/弃光；终端可达区间投影保证日末目标可达（s_tgt=None 时不
    投影，仅受SOC硬界——用于两日滚动窗口，窗口末目标由次日重解承接）。
    口径与计划LP一致：c=交流侧充入（电池得0.9c），d=电池侧放出（母线得0.9d）。
    r: 合同购电量(144,)；返回 dict(c,d,e,w,S)。
    可达带归纳论证：若 E_t ∈ [max(1200,tgt−R·750), min(10800,tgt+R·833.3)]
    （R=剩余步数），单步充升≤750、放降≤833.3，投影clamp后仍落回下一步
    同构区间；R=0 时区间收缩为单点 tgt，日末精确闭合。"""
    n_seg = len(r)
    c_f = np.zeros(n_seg); d_f = np.zeros(n_seg)
    e_f = np.zeros(n_seg); w_f = np.zeros(n_seg)
    S = np.empty(n_seg + 1); S[0] = s_init
    n_act = DT * (La - Pa)
    s = s_init
    for t in range(n_seg):
        n = n_act[t]
        x = r[t] - n                       # 合同-需求 盈余
        c = d = 0.0
        if x >= 0:                         # 富余：优先充入电池
            c = min(x, CD_MAX, (SOC_MAX - s) / ETA)
        else:                              # 短缺：优先放电
            d = min(-x / ETA, CD_MAX, s - SOC_MIN)
        s1 = s + ETA * c - d
        if s_tgt is not None:              # 终端可达带投影（R按距日末步数，t_off为段起点）
            R = N - 1 - (t_off + t)
            Lb = max(SOC_MIN, s_tgt - R * ETA * CD_MAX)
            Ub = min(SOC_MAX, s_tgt + R * CD_MAX)
            if s1 > Ub:
                if c > 0:
                    c = max(0.0, (Ub - s) / ETA); s1 = s + ETA * c
                if s1 > Ub:                # 起点已超带：主动放电（多余弃光）
                    d = min(CD_MAX, s - Ub, s - SOC_MIN)
                    s1 = s + ETA * c - d
            elif s1 < Lb:
                if d > 0:
                    d = max(0.0, s - Lb); s1 = s + ETA * c - d
                if s1 < Lb:                # 起点已低于带：主动充电（缺口走紧急购电）
                    c = min(CD_MAX, (Lb - s) / ETA)
                    s1 = s + ETA * c
        s = s1
        c_f[t], d_f[t] = c, d
        e_f[t] = max(0.0, n + c - ETA * d - r[t])
        w_f[t] = max(0.0, r[t] + ETA * d - c - n)
        S[t + 1] = s
    return dict(c=c_f, d=d_f, e=e_f, w=w_f, S=S)

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
            L2, P2 = base_forecast(d + 1)[0], pv_fc_tmr(d)   # 明日光伏用合规预测
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
        p_f = plan_p.copy()
        La, Pa = load[d], pv[d]
        if not adjust:
            # P4-2：全天实时反馈；窗口末目标由次日滚动重解承接，不做日投影
            fb = feedback_execute(p_f, La, Pa, s_cur, s_tgt=None)
            c_f, d_f, e = fb['c'], fb['d'], fb['e']
        else:
            # P4-3：调整点之间反馈执行，调整LP以实际SOC为起点，
            # 末态锚定当天计划末态（保留0点两日窗口的跨日套利结构）
            S_plan_end = s_cur + ETA * plan['c'][:N].sum() - plan['d'][:N].sum()
            e = np.zeros(N)
            c_f[:] = 0.0; d_f[:] = 0.0
            t_first = ADJUST[0][1]
            fb = feedback_execute(p_f[:t_first], La[:t_first], Pa[:t_first],
                                  s_cur, s_tgt=S_plan_end, t_off=0)
            c_f[:t_first], d_f[:t_first] = fb['c'], fb['d']
            e[:t_first] = fb['e']
            s_cur = float(fb['S'][-1])
            for si, (slot, t0) in enumerate(ADJUST):
                if t0 > 0:
                    L1c, _ = intraday_correct(L1, La, t0)
                    Ph2 = fc_pv_curve(d, slot)
                    scen2 = make_scenarios(d, K, L1c, Ph2, slot=slot)
                    new = solve_sp_lp(price_d, L1c, Ph2, scen2, s_cur,
                                      s_end=S_plan_end, t0=t0, p_plan=plan_p)
                    p_f[t0:] = new['p'][t0:]
                t_end = ADJUST[si + 1][1] if si + 1 < len(ADJUST) else N
                seg = slice(t0, t_end)
                fb = feedback_execute(p_f[seg], La[seg], Pa[seg], s_cur,
                                      s_tgt=S_plan_end, t_off=t0)
                c_f[seg], d_f[seg] = fb['c'], fb['d']
                e[seg] = fb['e']
                s_cur = float(fb['S'][-1])
        cost_plan = float(price_d @ p_f)
        cost_em = float(EM_MULT * (price_d @ e))
        cost_dev = float(DEV_MULT * (price_d @ np.abs(p_f - plan_p))) if adjust else 0.0
        if not adjust:
            s_cur = float(fb['S'][-1])
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
        # ---- 实际执行（实时反馈，日循环投影目标6000） ----
        La, Pa = load[d], pv[d]
        if not adjust:
            fb = feedback_execute(p_f, La, Pa, 6000.0, s_tgt=6000.0)
            c_f, d_f, e = fb['c'], fb['d'], fb['e']
        else:
            # adjust=True 用全部调整时刻；也可传 (slot,t0) 列表做子集消融。
            # 调整点之间反馈执行，调整LP以实际SOC为起点（INN-3口径）
            e = np.zeros(N)
            c_f[:] = 0.0; d_f[:] = 0.0
            s_real = 6000.0
            adj = ADJUST if adjust is True else adjust
            t_first = adj[0][1]
            fb = feedback_execute(p_f[:t_first], La[:t_first], Pa[:t_first],
                                  s_real, s_tgt=6000.0, t_off=0)
            c_f[:t_first], d_f[:t_first] = fb['c'], fb['d']
            e[:t_first] = fb['e']
            s_real = float(fb['S'][-1])
            for si, (slot, t0) in enumerate(adj):
                if t0 > 0:
                    Lh2, _ = intraday_correct(Lh, La, t0)   # 当天实际偏差修正
                    Ph2 = fc_pv_curve(d, slot)
                    scen2 = make_scenarios(d, K, Lh2, Ph2, slot=slot)
                    new = solve_sp_lp(price, Lh2, Ph2, scen2, s_real,
                                      6000.0, t0=t0, p_plan=plan['p'])
                    p_f[t0:] = new['p'][t0:]
                t_end = adj[si + 1][1] if si + 1 < len(adj) else N
                seg = slice(t0, t_end)
                fb = feedback_execute(p_f[seg], La[seg], Pa[seg], s_real,
                                      s_tgt=6000.0, t_off=t0)
                c_f[seg], d_f[seg] = fb['c'], fb['d']
                e[seg] = fb['e']
                s_real = float(fb['S'][-1])
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
