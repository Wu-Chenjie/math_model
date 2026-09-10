# -*- coding: utf-8 -*-
"""论文图表生成（学术风格，中文，dpi=300，供LaTeX直接引用）。
fig1: P1代表日调度机理（电价/负载/光伏 + 购电 + 储能SOC）
fig2: P2全年日费用与紧急购电
fig3: SAA场景机理与方法对比（确定性LP vs SAA）
fig4: P3调整效果（指定日计划vs调整曲线 + 三方案对比）
fig5: P4波动电价特征与费用对比
"""
import sys
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

sys.path.insert(0, r'D:/shumo/shumoC/code')
from common import load_data, DT, ETA
from strategy import base_forecast, make_scenarios, fc_pv_curve, merge_emerg_segments

plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei'],
    'axes.unicode_minus': False,
    'font.size': 11, 'axes.titlesize': 12, 'axes.labelsize': 11.5,
    'legend.fontsize': 10, 'xtick.labelsize': 10, 'ytick.labelsize': 10,
    'lines.linewidth': 1.4, 'figure.dpi': 300, 'savefig.dpi': 300,
    'axes.grid': True, 'grid.alpha': 0.3, 'axes.axisbelow': True,
})
C_BLUE, C_RED, C_ORANGE, C_GREEN, C_GRAY = '#2166ac', '#b2182b', '#ef8a62', '#1a9850', '#666666'
FIG = r'D:/shumo/shumoC/figures'
D = load_data()
# 论文全部数值以 paper_tables.json 为唯一来源（禁止图内硬编码运行结果）
with open(r'D:/shumo/shumoC/results/paper_tables.json', encoding='utf-8') as f:
    TAB = json.load(f)
hours = np.arange(144) / 6 + 1/12   # 时段中心(小时)
SPEC = {78: '2025-3-20', 171: '2025-6-21', 265: '2025-9-23', 354: '2025-12-21'}

def hhaxis(ax):
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 4))
    ax.set_xlabel('时刻 (h)')

# ---------------- fig1: P1 调度机理 ----------------
z1 = np.load(r'D:/shumo/shumoC/results/p1.npz')
p1, c1, d1, S1 = z1['p'], z1['c'], z1['d'], z1['S']
fig, axes = plt.subplots(3, 1, figsize=(8.2, 7.2), sharex=True)
ax = axes[0]
ax.plot(hours, D['load1'], color=C_RED, label='小区负载')
ax.plot(hours, D['pv_fc1'], color=C_ORANGE, label='光伏预测功率')
ax2 = ax.twinx()
ax2.plot(hours, D['price1'], color=C_GRAY, ls='--', lw=1.2, label='电价')
ax2.set_ylabel('电价 (元/kWh)'); ax2.grid(False)
ax.set_ylabel('功率 (kW)')
ax.legend(loc='upper left'); ax2.legend(loc='upper right')
ax.set_title('(a) 代表日电价、负载与光伏预测')

ax = axes[1]
ax.bar(hours, p1, width=1/6, color=C_BLUE, label='购电功率')
ax.set_ylabel('购电功率 (kW)')
ax.legend(); ax.set_title('(b) 计划购电功率（避高就低：低价与午间光伏富余时段购电充电）')

ax = axes[2]
ax.bar(hours, ETA * c1, width=1/6, color=C_GREEN, alpha=0.75, label='充电功率(储能侧)')
ax.bar(hours, -ETA * d1, width=1/6, color=C_ORANGE, alpha=0.85, label='放电功率(储能侧)')
ax3 = ax.twinx()
ax3.plot(hours, S1, color=C_BLUE, lw=1.8, label='储电量')
ax3.set_ylabel('储电量 (kWh)'); ax3.grid(False)
ax3.set_ylim(0, 12000)
ax.axhline(0, color='k', lw=0.8)
ax.set_ylabel('充/放功率 (kW)')
hhaxis(ax)
ax.legend(loc='upper left'); ax3.legend(loc='upper right')
ax.set_title('(c) 储能充放电计划与储电量轨迹')
plt.tight_layout()
plt.savefig(f'{FIG}/fig1_p1_dispatch.png', bbox_inches='tight')
plt.close()

# ---------------- fig2: P2 全年 ----------------
z2 = np.load(r'D:/shumo/shumoC/results/p2.npz')
days = np.arange(31, 365)
cost_d = (D['price1'] * z2['p'][31:]).sum(1)
em_d = (D['price1'] * 5 * z2['e'][31:]).sum(1)
fig, axes = plt.subplots(2, 1, figsize=(8.2, 5.2), sharex=True)
ax = axes[0]
ax.bar(days, cost_d / 1e4, width=0.8, color=C_BLUE, label='计划购电费')
ax.set_ylabel('计划购电费 (万元/日)')
ymax = (cost_d / 1e4).max()
for x0, lab in SPEC.items():
    ax.axvline(x0, color=C_GRAY, ls=':', lw=0.9)
    ax.text(x0 + 1.5, ymax * 0.97, lab.replace('2025-', ''), rotation=90,
            fontsize=8.5, color=C_GRAY, va='top', ha='left')
ax.legend(loc='upper left')
ax.set_title('(a) P2 全年日计划购电费（2025.2.1–12.31）')

ax = axes[1]
ax.bar(days, z2['e'][31:].sum(1), width=0.8, color=C_RED, label='紧急购电量')
ax.set_ylabel('紧急购电量 (kWh/日)')
ax.set_xlabel('日期 (2025年, day-of-year)')
ax.legend()
em_daily_avg = z2['e'][31:].sum(1).mean() / 1000
ax.set_title(f'(b) 全年日紧急购电量（执行层反馈下日均仅约 {em_daily_avg:.2f} MWh）')
plt.tight_layout()
plt.savefig(f'{FIG}/fig2_p2_year.png', bbox_inches='tight')
plt.close()

# ---------------- fig3: SAA 机理与对比 ----------------
d_demo = 78
Lh, Ph = base_forecast(d_demo)
scen = make_scenarios(d_demo, 15, Lh, Ph, slot=None)
fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2))
ax = axes[0]
for k in range(15):
    ax.plot(hours, scen[k, :, 1] / 1000, color=C_ORANGE, alpha=0.35, lw=0.8)
ax.plot(hours, Ph / 1000, color=C_RED, lw=2, label='基准光伏预测')
ax.plot(hours, D['pv'][d_demo] / 1000, color='k', ls='--', lw=1.6, label='实际光伏')
ax.plot([], [], color=C_ORANGE, alpha=0.5, lw=2, label='15个误差场景')
ax.set_ylabel('光伏功率 (MW)')
hhaxis(ax); ax.legend(loc='upper left', fontsize=9)
ax.set_title('(a) 光伏预测的SAA误差场景 (d=78)')

ax = axes[1]
# 归因分解三柱：旧预报器确定性LP → 本文预报器确定性LP → SAA（全部来自json）
det_old = TAB['p2']['year_baseline_det']['cost_total'] / 1e4
det_new = TAB['p2']['year_baseline_det_fc']['cost_total'] / 1e4
saa = TAB['p2']['year']['cost_total'] / 1e4
labels = ['确定性LP\n(旧预报器)', '确定性LP\n(本文预报器)', 'SAA(K=15)\n本文方法']
bars = ax.bar(labels, [det_old, det_new, saa], width=0.55, color=[C_GRAY, '#92c5de', C_BLUE])
for b, v in zip(bars, [det_old, det_new, saa]):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.12, f'{v:.1f}', ha='center', fontsize=10)
ax.set_ylabel('全年总购电费 (万元)')
ax.set_title('(b) 预报器改进与SAA防护的归因分解（全年总费用）')
ax.set_ylim(0, max(det_old, det_new, saa) * 1.18)
plt.tight_layout()
plt.savefig(f'{FIG}/fig3_saa.png', bbox_inches='tight')
plt.close()

# ---------------- fig4: P3 调整效果 ----------------
z3 = np.load(r'D:/shumo/shumoC/results/p3.npz')
fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2))
ax = axes[0]
d_show = 265
ax.plot(hours, z3['plan_p'][d_show], color=C_GRAY, lw=1.5, label='0:00计划购电')
ax.plot(hours, z3['p'][d_show], color=C_BLUE, lw=1.5, label='调整后购电')
for h in [6, 12, 18]:
    ax.axvline(h, color=C_RED, ls=':', lw=1)
ax.legend(handles=ax.get_legend_handles_labels()[0] +
          [Line2D([], [], color=C_RED, ls=':', lw=1)],
          labels=ax.get_legend_handles_labels()[1] + ['调整时刻 6/12/18时'],
          loc='upper left', fontsize=9)
ax.set_ylabel('购电功率 (kW)')
hhaxis(ax)
ax.set_title('(c) 调整前后购电计划对比 (2025-9-23)')

ax = axes[1]
CA = TAB['p3']['year_A_fc0_noAdj']['cost_total']
CB = TAB['p3']['year']['cost_total']
CC = TAB['p3']['year_C_naive']['cost_total']
bars = ax.bar(['A: 仅0:00预报', 'B: 加入调整\n(本文)', 'C: 无预报(naive)'],
              [CA / 1e4, CB / 1e4, CC / 1e4], width=0.55, color=[C_GRAY, C_BLUE, C_ORANGE])
for b, v in zip(bars, [CA, CB, CC]):
    ax.text(b.get_x() + b.get_width() / 2, v / 1e4 + 2, f'{v/1e4:.1f}', ha='center', fontsize=10)
ax.set_ylabel('全年总购电费 (万元)')
ax.set_ylim(1400, max(CA, CB, CC) / 1e4 * 1.02)
ax.set_title('(d) P3三方案全年总费用对比')
plt.tight_layout()
plt.savefig(f'{FIG}/fig4_p3_adjust.png', bbox_inches='tight')
plt.close()

# ---------------- fig5: P4 波动电价 ----------------
z42 = np.load(r'D:/shumo/shumoC/results/p4_2.npz')
z43 = np.load(r'D:/shumo/shumoC/results/p4_3.npz')
fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2))
ax = axes[0]
for di, lab in [(78, '3-20'), (171, '6-21')]:
    ax.plot(hours, D['price4'][di], lw=1.1, label=f'2025-{lab}')
ax.plot(hours, D['price1'], color='k', ls='--', lw=1.3, label='附件1分时电价')
ax.set_ylabel('电价 (元/kWh)')
hhaxis(ax); ax.legend(fontsize=9)
ax.set_title('(e) 波动电价示例（附件4）与分时电价')

ax = axes[1]
fee = [TAB['p2']['year']['cost_total'], TAB['p4_2']['year']['cost_total'],
       TAB['p3']['year']['cost_total'], TAB['p4_3']['year']['cost_total']]
bars = ax.bar(['P2\n(固定价)', 'P4-2\n(波动价)', 'P3\n(固定价)', 'P4-3\n(波动价)'],
              [f / 1e4 for f in fee], width=0.55,
              color=[C_BLUE, '#92c5de', C_GREEN, '#a6dba0'])
for b, f in zip(bars, fee):
    ax.text(b.get_x() + b.get_width() / 2, f / 1e4 + 3, f'{f/1e4:.0f}', ha='center', fontsize=9.5)
ax.set_ylabel('全年总购电费 (万元)')
ax.set_ylim(0, max(fee) / 1e4 * 1.15)
ax.set_title('(f) 固定电价 vs 波动电价的全年总费用')
plt.tight_layout()
plt.savefig(f'{FIG}/fig5_p4_price.png', bbox_inches='tight')
plt.close()

print('figures saved:', FIG)
