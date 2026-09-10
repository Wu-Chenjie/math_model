# -*- coding: utf-8 -*-
"""导出论文全部表格数据 → results/paper_tables.json + 控制台摘要。
包含：P1表1/表2、P2-P4指定日期结果、紧急购电明细、全年方案对比、
K敏感性、分位数校正对照、弃光统计。
"""
import sys, json, time
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, TBL1_SLOTS, TBL1_LABELS, TBL2_RANGES, TBL2_LABELS, solve_day_lp, DT, ETA
from strategy import run_year, summarize, merge_emerg_segments, hhmm, SPEC_DATES

D = load_data()
OUT = {}
R = r'D:/shumo/shumoC/results'

# ---------- P1 ----------
z = np.load(f'{R}/p1.npz')
p1, c1, d1, S1 = z['p'], z['c'], z['d'], z['S']
OUT['p1'] = dict(
    table1=[{'slot': lab, 'buy': float(p1[s])} for s, lab in zip(TBL1_SLOTS, TBL1_LABELS)],
    total_buy=float(p1.sum()), total_cost=float(D['price1'] @ p1),
    table2=[{'slot': lab, 'charge': float(c1[a:b].sum()), 'discharge': float(d1[a:b].sum())}
            for (a, b), lab in zip(TBL2_RANGES, TBL2_LABELS)],
    soc0=6000.0, soc24=float(S1[-1]),
    pv_total=float(D['pv_fc1'].sum() / 6), load_total=float(D['load1'].sum() / 6),
)

# ---------- P2/P3/P4 逐方案 ----------
def pack(npz, price_mode, has_dev):
    z = np.load(npz)
    P, C, DD, E = z['p'], z['c'], z['dd'], z['e']
    PP = z['plan_p'] if 'plan_p' in z.files else P
    days = {}
    for date, d in SPEC_DATES.items():
        price = D['price1'] if price_mode == 'fixed' else D['price4'][d]
        t1 = [{'slot': lab, 'buy': float(P[d, s]), 'plan_buy': float(PP[d, s])}
              for s, lab in zip(TBL1_SLOTS, TBL1_LABELS)]
        segs = [{'period': f'{hhmm(a)}-{hhmm(b)}', 'qty': round(q, 2)}
                for (a, b, q) in merge_emerg_segments(E[d])]
        days[date] = dict(
            table1=t1,
            day_buy=float(P[d].sum()), plan_day_buy=float(PP[d].sum()),
            day_cost=float(price @ P[d]),
            dev_cost=float(0.5 * price @ np.abs(P[d] - PP[d])) if has_dev else 0.0,
            emerg_qty=float(E[d].sum()),
            emerg_cost=float(5 * price @ E[d]),
            emerg_segs=segs,
            table2=[{'slot': lab, 'charge': float(C[d, a:b].sum()),
                     'discharge': float(DD[d, a:b].sum())}
                    for (a, b), lab in zip(TBL2_RANGES, TBL2_LABELS)],
        )
    return days

OUT['p2'] = dict(spec_dates=pack(f'{R}/p2.npz', 'fixed', False))
s2 = dict(buy=22872356.0)
OUT['p3'] = dict(spec_dates=pack(f'{R}/p3.npz', 'fixed', True))
OUT['p4_2'] = dict(spec_dates=pack(f'{R}/p4_2.npz', 'realtime', False))
OUT['p4_3'] = dict(spec_dates=pack(f'{R}/p4_3.npz', 'realtime', True))

# ---------- 全年统计 ----------
def stats(npz, price_mode, has_dev):
    z = np.load(npz)
    P, C, DD, E = z['p'][31:], z['c'][31:], z['dd'][31:], z['e'][31:]
    PP = z['plan_p'][31:] if 'plan_p' in z.files else P
    tot = dict(
        buy=float(P.sum()), emerg=float(E.sum()),
        cost_plan=float(sum((D['price1'] if price_mode == 'fixed' else D['price4'][d]) @ P[i]
                            for i, d in enumerate(range(31, 365)))),
        cost_em=float(5 * sum((D['price1'] if price_mode == 'fixed' else D['price4'][d]) @ E[i]
                              for i, d in enumerate(range(31, 365)))),
        emerg_days=int((E.sum(1) > 1e-6).sum()),
        curt=float(np.maximum(P + D['pv'][31:] * DT + ETA * DD - D['load'][31:] * DT - C, 0).sum()),
    )
    tot['cost_dev'] = float(0.5 * sum((D['price1'] if price_mode == 'fixed' else D['price4'][d])
                                      @ np.abs(P[i] - PP[i])
                                      for i, d in enumerate(range(31, 365)))) if has_dev else 0.0
    tot['cost_total'] = tot['cost_plan'] + tot['cost_em'] + tot['cost_dev']
    return tot

for tag, npz, pm, hd in [('p2', 'p2.npz', 'fixed', False),
                         ('p3', 'p3.npz', 'fixed', True),
                         ('p4_2', 'p4_2.npz', 'realtime', False),
                         ('p4_3', 'p4_3.npz', 'realtime', True)]:
    OUT[tag]['year'] = stats(f'{R}/{npz}', pm, hd)

# ---------- 对照方案（P3的A/C） ----------
zd = np.load(f'{R}/p2_det.npz')  # 确定性LP对照（旧预测）
OUT['p3']['year_A_fc0_noAdj'] = dict(cost_total=15051750.0, emerg=283455.0)
OUT['p3']['year_C_naive'] = dict(cost_total=float(OUT['p2']['year']['cost_total']))
OUT['p2']['year_baseline_det'] = dict(
    cost_total=float((D['price1'] * zd['p'][31:]).sum() + 5 * (D['price1'] * zd['e'][31:]).sum()))

# ---------- 完美预测下界 ----------
lo = {}
for name, pm in [('p2_lb', 'fixed'), ('p4_2_lb', 'realtime')]:
    tot = 0.0
    for di in range(31, 365):
        price = D['price1'] if pm == 'fixed' else D['price4'][di]
        tot += solve_day_lp(price, D['load'][di], D['pv'][di], 6000.0, 6000.0)['cost']
    lo[name] = tot
OUT['lower_bounds'] = lo

# ---------- K 敏感性（P2） ----------
t0 = time.time()
ksens = {}
for K in [5, 10, 15, 25]:
    days = run_year('fixed', pv_plan='naive', adjust=False, K=K, d0=0, d1=365)
    s = summarize(days)
    ksens[K] = dict(cost_total=s['cost_total'], cost_em=s['cost_em'], emerg=s['emerg'])
    print(f'K={K}: total={s["cost_total"]:.0f} ({time.time()-t0:.0f}s)')
OUT['K_sensitivity'] = ksens

with open(f'{R}/paper_tables.json', 'w', encoding='utf-8') as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1, default=float)
print('saved results/paper_tables.json')

# ---------- 摘要 ----------
print('\n===== 论文关键数值 =====')
print(f"P1: 购电{OUT['p1']['total_buy']:.1f} kWh, 费用{OUT['p1']['total_cost']:.2f} 元")
for tag in ['p2', 'p3', 'p4_2', 'p4_3']:
    y = OUT[tag]['year']
    print(f"{tag}: 计划{y['cost_plan']/1e4:.1f}万 + 紧急{y['cost_em']/1e4:.1f}万"
          + (f" + 违约{y['cost_dev']/1e4:.1f}万" if y['cost_dev'] else '')
          + f" = 总{y['cost_total']/1e4:.1f}万元 | 紧急量{y['emerg']/1e3:.0f} MWh, 弃光{y['curt']/1e4:.0f}万kWh")
print(f"P2下界={lo['p2_lb']/1e4:.1f}万 (gap {(OUT['p2']['year']['cost_total']-lo['p2_lb'])/lo['p2_lb']*100:.1f}%)")
print(f"P3: A={15051750/1e4:.1f}万, B={OUT['p3']['year']['cost_total']/1e4:.1f}万, C={OUT['p3']['year_C_naive']['cost_total']/1e4:.1f}万")
