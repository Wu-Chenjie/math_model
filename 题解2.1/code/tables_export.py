# -*- coding: utf-8 -*-
"""导出论文全部表格数据 → results/paper_tables.json + 控制台摘要。
包含：P1表1/表2、P2-P4指定日期结果、紧急购电明细、全年方案对比、
K敏感性、分位数校正对照、弃光统计。
"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, TBL1_SLOTS, TBL1_LABELS, TBL2_RANGES, TBL2_LABELS, solve_day_lp, DT, ETA
from strategy import run_year, summarize, merge_emerg_segments, hhmm, SPEC_DATES

D = load_data()
OUT = {}
R = r'D:/shumo/shumoC/results'
SKIP_K = '--skip-k' in sys.argv   # 跳过K敏感性重算（复用已有json值，节省复跑时间）

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
    # 紧急购电费用重尾统计（逐日紧急费的最大值/95分位，论文稳健性分析用）
    em_day = np.array([5 * ((D['price1'] if price_mode == 'fixed' else D['price4'][d]) @ E[i])
                       for i, d in enumerate(range(31, 365))])
    tot['em_cost_max'] = float(em_day.max())
    tot['em_cost_p95'] = float(np.percentile(em_day, 95))
    return tot

for tag, npz, pm, hd in [('p2', 'p2.npz', 'fixed', False),
                         ('p3', 'p3.npz', 'fixed', True),
                         ('p4_2', 'p4_2.npz', 'realtime', False),
                         ('p4_3', 'p4_3.npz', 'realtime', True)]:
    OUT[tag]['year'] = stats(f'{R}/{npz}', pm, hd)

# ---------- 对照方案（P3的A/C，全部从结果文件统计，禁止硬编码） ----------
OUT['p3']['year_A_fc0_noAdj'] = stats(f'{R}/p3_A.npz', 'fixed', False)
OUT['p3']['year_C_naive'] = dict(cost_total=float(OUT['p2']['year']['cost_total']))
zd = np.load(f'{R}/p2_det.npz')       # 确定性LP对照（旧预报器lag-1）
OUT['p2']['year_baseline_det'] = dict(
    cost_total=float((D['price1'] * zd['p'][31:]).sum() + 5 * (D['price1'] * zd['e'][31:]).sum()))
zdf = np.load(f'{R}/p2_det_fc.npz')   # 确定性LP对照（本文预报器，归因分解用）
OUT['p2']['year_baseline_det_fc'] = dict(
    cost_total=float((D['price1'] * zdf['p'][31:]).sum() + 5 * (D['price1'] * zdf['e'][31:]).sum()))

# ---------- 完美预测下界 / 参考最优 ----------
# p2_lb: P2策略类为日循环，逐日全知LP确为其下界；
# p4_2_lb: P4为两日滚动、日末SOC自由，此值仅作"日循环参考最优"（非严格下界）。
lo = {}
for name, pm in [('p2_lb', 'fixed'), ('p4_2_lb', 'realtime')]:
    tot = 0.0
    for di in range(31, 365):
        price = D['price1'] if pm == 'fixed' else D['price4'][di]
        tot += solve_day_lp(price, D['load'][di], D['pv'][di], 6000.0, 6000.0)['cost']
    lo[name] = tot
OUT['lower_bounds'] = lo

# ---------- P3 调整时刻子集消融（回答"需要哪些时刻的预报"） ----------
t0 = time.time()
abl = {}
for name, adj in [('adj_full', True), ('adj_6_12', [(1, 42), (2, 78)]), ('adj_12', [(2, 78)])]:
    days = run_year('fixed', pv_plan='fc0', adjust=adj, K=15, d0=0, d1=365)
    s = summarize(days)
    abl[name] = dict(cost_total=s['cost_total'], cost_em=s['cost_em'],
                     cost_dev=s['cost_dev'], emerg=s['emerg'])
    print(f'{name}: total={s["cost_total"]:.0f} ({time.time()-t0:.0f}s)')
OUT['p3']['adjust_ablation'] = abl

# ---------- K 敏感性（P2） ----------
old_json = None
if os.path.exists(f'{R}/paper_tables.json'):
    with open(f'{R}/paper_tables.json', encoding='utf-8') as f:
        old_json = json.load(f)
if SKIP_K and old_json and 'K_sensitivity' in old_json:
    OUT['K_sensitivity'] = old_json['K_sensitivity']
    print('K敏感性：复用已有json值（--skip-k）')
else:
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
print(f"P4-2参考最优={lo['p4_2_lb']/1e4:.1f}万 (P4-2总/参考={(OUT['p4_2']['year']['cost_total'])/lo['p4_2_lb']*100:.1f}%)")
print(f"P3: A={OUT['p3']['year_A_fc0_noAdj']['cost_total']/1e4:.1f}万, "
      f"B={OUT['p3']['year']['cost_total']/1e4:.1f}万, C={OUT['p3']['year_C_naive']['cost_total']/1e4:.1f}万")
for nm, v in OUT['p3']['adjust_ablation'].items():
    print(f"  消融 {nm}: 总={v['cost_total']/1e4:.1f}万")
print(f"确定性LP: 旧预报器={OUT['p2']['year_baseline_det']['cost_total']/1e4:.1f}万, "
      f"本文预报器={OUT['p2']['year_baseline_det_fc']['cost_total']/1e4:.1f}万 → "
      f"SAA={OUT['p2']['year']['cost_total']/1e4:.1f}万")
