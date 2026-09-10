# -*- coding: utf-8 -*-
"""独立验证：对P1-P4全部结果做物理/费用一致性校验（不依赖求解器输出）。
校验项：
  1. SOC轨迹 = 6000 + cumsum(0.9c - d)，且全程∈[1200,10800]，日末=6000
  2. 充/放电量 ≤ 833.333 kWh/时段，c·d不同时>0
  3. 供电-需求平衡（弃光 = max(0, 供给-需求) ≥ 0）
  4. 紧急购电量 = max(0, 需求-供给)
  5. 费用重算：计划费=Σπp、紧急费=5Σπe、违约费=0.5Σπ|p-p_plan|（调整方案）
  6. 完美预测下界（用当天实际的确定性LP）——量化策略gap
"""
import sys
import numpy as np
sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, solve_day_lp, DT, N, ETA, SOC_MIN, SOC_MAX, CD_MAX

D = load_data()
load, pv, price1, price4 = D['load'], D['pv'], D['price1'], D['price4']
fail = 0

def check(name, cond, detail=''):
    global fail
    if not cond:
        fail += 1
        print(f'  [FAIL] {name}: {detail}')

def verify_run(tag, npz, price_mode, has_dev, daily_cycle=True):
    z = np.load(npz)
    p, c, d, e = z['p'], z['c'], z['dd'], z['e']
    plan_p = z['plan_p'] if 'plan_p' in z.files else p
    n_days = p.shape[0]
    worst = dict(soc=0, cd=0, em=0, dev=0, bal=0)
    tot = dict(plan=0.0, em=0.0, dev=0.0)
    s_cur = 6000.0                            # 跨日SOC结转（P4两日滚动≠6000）
    for i in range(n_days):
        di = i  # npz从d=0开始
        price = price1 if price_mode == 'fixed' else price4[di]
        S = s_cur + np.cumsum(ETA * c[i] - d[i])
        s_cur = float(S[-1])
        worst['soc'] = max(worst['soc'], SOC_MIN - S.min(), S.max() - SOC_MAX)
        worst['cd'] = max(worst['cd'], c[i].max() - CD_MAX, d[i].max() - CD_MAX)
        check(f'{tag} d{di} c·d互斥', not ((c[i] > 1e-6) & (d[i] > 1e-6)).any())
        supply = p[i] + pv[di] * DT + ETA * d[i]
        demand = load[di] * DT + c[i]
        e_true = np.maximum(demand - supply, 0)
        worst['em'] = max(worst['em'], np.abs(e[i] - e_true).max())
        worst['bal'] = max(worst['bal'], (supply - demand + e[i]).max(),
                           -(supply - demand + e[i]).max() * 0)
        if di >= 31:                             # 统计口径与论文一致(2025.2.1起)
            tot['plan'] += price @ p[i]
            tot['em'] += 5 * (price @ e[i])
            if has_dev:
                tot['dev'] += 0.5 * (price @ np.abs(p[i] - plan_p[i]))
        if daily_cycle:                           # 日循环方案日末=6000
            check(f'{tag} d{di} 日末SOC', abs(S[-1] - 6000.0) < 1e-6, f'{S[-1]:.4f}')
    check(f'{tag} SOC界', worst['soc'] < 1e-6, f'worst viol {worst["soc"]:.2e}')
    check(f'{tag} 充放功率界', worst['cd'] < 1e-6, f'{worst["cd"]:.2e}')
    check(f'{tag} 紧急购电量一致', worst['em'] < 1e-6, f'{worst["em"]:.2e}')
    print(f'  {tag}: 计划费={tot["plan"]:.0f}, 紧急费={tot["em"]:.0f}'
          + (f', 违约费={tot["dev"]:.0f}' if has_dev else '')
          + f', 总={sum(tot.values()):.0f} 元')
    return sum(tot.values())

print('=== P1 ===')
z = np.load(r'D:/shumo/shumoC/results/p1.npz')
p, c, d, S = z['p'], z['c'], z['d'], z['S']
check('P1 SOC轨迹', np.allclose(S, 6000 + np.cumsum(ETA * c - d), atol=1e-6))
check('P1 SOC界', S.min() >= SOC_MIN - 1e-6 and S.max() <= SOC_MAX + 1e-6)
check('P1 功率界', c.max() <= CD_MAX + 1e-6 and d.max() <= CD_MAX + 1e-6)
check('P1 日末=6000', abs(S[-1] - 6000) < 1e-6)
gap = D['load1'] * DT + c - (p + D['pv_fc1'] * DT + ETA * d)
check('P1 平衡(不缺供)', gap.max() < 1e-6, f'{gap.max():.2e}')
curt = np.maximum(-(D['load1'] * DT + c - p - D['pv_fc1'] * DT - ETA * d), 0)
print(f'  P1: 购电={p.sum():.1f} kWh, 费用={price1 @ p:.2f} 元, 弃光={curt.sum():.1f} kWh')

print('=== P2/P3/P4 ===')
tot2 = verify_run('P2  ', r'D:/shumo/shumoC/results/p2.npz', 'fixed', False)
tot3 = verify_run('P3  ', r'D:/shumo/shumoC/results/p3.npz', 'fixed', True)
tot42 = verify_run('P4-2', r'D:/shumo/shumoC/results/p4_2.npz', 'realtime', False, daily_cycle=False)
tot43 = verify_run('P4-3', r'D:/shumo/shumoC/results/p4_3.npz', 'realtime', True, daily_cycle=False)

print('=== 完美预测下界（d≥31统计口径） ===')
bounds = {}
for name, price_mode in [('P2下界', 'fixed'), ('P4-2参考最优', 'realtime')]:
    tot_lo = 0.0
    for di in range(31, 365):
        price = price1 if price_mode == 'fixed' else price4[di]
        sol = solve_day_lp(price, load[di], pv[di], 6000.0, 6000.0)
        tot_lo += sol['cost']
    bounds[name] = tot_lo
    print(f'  {name} = {tot_lo:.0f} 元')

print(f'\nP2总费={tot2:.0f}, 下界={bounds["P2下界"]:.0f}, gap={(tot2-bounds["P2下界"])/bounds["P2下界"]*100:.1f}%')

# ---------------- result xlsx ↔ npz 一致性（防止输出层与计算层脱节） ----------------
print('=== result xlsx vs npz 一致性 ===')
import openpyxl
OUTD = r'D:/shumo/shumoC/results'

def check_xlsx(fname, npzf, has_adjust, price_mode):
    z = np.load(f'{OUTD}/{npzf}')
    p, c, d, e = z['p'][31:], z['c'][31:], z['dd'][31:], z['e'][31:]
    plan_p = z['plan_p'][31:] if 'plan_p' in z.files else p
    wb = openpyxl.load_workbook(f'{OUTD}/{fname}')
    # 1) 充放电量sheet：逐日0:00/24:00储电量 = SOC链重建值（P4日初≠6000）
    ws = wb['充放电量']
    s0, bad = 6000.0, 0
    for i in range(334):
        base = 2 + i * 6
        s1 = s0 + float(np.cumsum(0.9 * c[i] - d[i])[-1])
        if (abs(ws.cell(row=base, column=6).value - s0) > 0.01
                or abs(ws.cell(row=base + 1, column=6).value - s1) > 0.01):
            bad += 1
        s0 = s1
    check(f'{fname} 储电量栏', bad == 0, f'{bad}天不符')
    # 2) 计划购电量sheet：指定日期整行 + 全天统计列（购电费用对应电价口径）
    ws = wb['计划购电量']
    for di in (78, 171, 265, 354):
        i, row = di - 31, 2 + di - 31
        xs = np.array([ws.cell(row=row, column=2 + t).value for t in range(144)])
        check(f'{fname} d{di} 计划购电量行', np.abs(xs - plan_p[i]).max() < 0.011,
              f'max diff {np.abs(xs - plan_p[i]).max():.3f}')
        price = price1 if price_mode == 'fixed' else price4[di]
        check(f'{fname} d{di} 全天统计列',
              abs(ws.cell(row=row, column=146).value - plan_p[i].sum()) < 0.02
              and abs(ws.cell(row=row, column=147).value - price @ plan_p[i]) < 0.02)
    # 3) 调整购电量sheet（最终执行值）
    if has_adjust:
        ws = wb['调整购电量']
        for di in (78, 171, 265, 354):
            i, row = di - 31, 2 + di - 31
            xs = np.array([ws.cell(row=row, column=2 + t).value for t in range(144)])
            check(f'{fname} d{di} 调整购电量行', np.abs(xs - p[i]).max() < 0.011,
                  f'max diff {np.abs(xs - p[i]).max():.3f}')
    # 4) 紧急购电量sheet：合计 = npz紧急量（容差=逐段0.01 kWh四舍五入的累积上界）
    ws = wb['紧急购电量']
    n_rows = ws.max_row - 1
    tot_e = sum(ws.cell(row=r, column=3).value or 0 for r in range(2, ws.max_row + 1))
    check(f'{fname} 紧急购电量合计', abs(tot_e - e.sum()) < 0.005 * n_rows + 0.01,
          f'{tot_e:.2f} vs {e.sum():.2f} ({n_rows}段)')

check_xlsx('result2.xlsx', 'p2.npz', False, 'fixed')
check_xlsx('result3.xlsx', 'p3.npz', True, 'fixed')
check_xlsx('result4-2.xlsx', 'p4_2.npz', False, 'realtime')
check_xlsx('result4-3.xlsx', 'p4_3.npz', True, 'realtime')
z1 = np.load(f'{OUTD}/p1.npz')
ws1 = openpyxl.load_workbook(f'{OUTD}/result1.xlsx')['计划购电量']
xs1 = np.array([ws1.cell(row=2 + t, column=2).value for t in range(144)])
check('result1 购电量', np.abs(xs1 - z1['p']).max() < 0.011)

print(f'\n{"全部通过" if fail==0 else f"{fail}项失败"}')
