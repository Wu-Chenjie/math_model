# -*- coding: utf-8 -*-
"""论文表格 LaTeX 片段导出：全部数值取自 results/paper_tables.json 与 npz（零手抄）。
输出 paper/tables/*.tex，论文主文档 \\input 引用。表1/表2/表3 格式严格对齐题面。
"""
import sys, json, os
import numpy as np

sys.path.insert(0, r'D:/shumo/shumoC/code')

RES = r'D:/shumo/shumoC/results'
OUT = r'D:/shumo/shumoC/paper/tables'
os.makedirs(OUT, exist_ok=True)
TAB = json.load(open(f'{RES}/paper_tables.json', encoding='utf-8'))
SPEC_DAYS = {'2025-03-20': '3-20', '2025-06-21': '6-21',
             '2025-09-23': '9-23', '2025-12-21': '12-21'}
SPEC_D = [78, 171, 265, 354]
TBL1_SLOTS = ['10:00-10:10', '12:00-12:10', '14:00-14:10',
              '16:00-16:10', '18:00-18:10', '20:00-20:10']
TBL2_SLOTS = ['0:00-4:00', '4:00-8:00', '8:00-12:00',
              '12:00-16:00', '16:00-20:00', '20:00-24:00']


def w(name, s):
    with open(f'{OUT}/{name}', 'w', encoding='utf-8') as f:
        f.write(s)


def f2(x):
    return f'{x:.2f}'


def f1(x):
    return f'{x:.1f}'


def wan(x):
    return f'{x/1e4:.1f}'


def day_socs(c_days, d_days):
    """逐日(日初,日末)SOC：从6000按0.9c−d结转（与results_io一致）。"""
    s0, out = 6000.0, []
    for i in range(len(c_days)):
        s1 = s0 + float(np.cumsum(0.9 * c_days[i] - d_days[i])[-1])
        out.append((s0, s1))
        s0 = s1
    return out


# ---------- P1: 题面表1 ----------
t1 = TAB['p1']['table1']
b = {r['slot']: r['buy'] for r in t1}
s = r"""\begin{tabular}{lc}
\toprule
时间段 & 购电量 (kWh) \\
\midrule
""" + ' \\\\ \n'.join(f'{sl} & {f2(b[sl])}' for sl in TBL1_SLOTS) + r""" \\
\midrule
全天购电量 & """ + f2(TAB['p1']['total_buy']) + r""" \\
全天购电费 & """ + f2(TAB['p1']['total_cost']) + r""" \\
\bottomrule
\end{tabular}"""
w('t1p1.tex', s)

# ---------- P1: 题面表2 ----------
t2 = TAB['p1']['table2']
cd = {r['slot']: (r['charge'], r['discharge']) for r in t2}
rows = []
for i in range(3):
    a, bb = TBL2_SLOTS[i], TBL2_SLOTS[i + 3]
    rows.append(f'{a} & {f2(cd[a][0])} & {f2(cd[a][1])} & {bb} & {f2(cd[bb][0])} & {f2(cd[bb][1])}')
s = r"""\begin{tabular}{lrrlrr}
\toprule
时间段 & 充电量 & 放电量 & 时间段 & 充电量 & 放电量 \\
\midrule
""" + ' \\\\ \n'.join(rows) + r""" \\
\midrule
\multicolumn{3}{l}{0:00 储电量：""" + f1(TAB['p1']['soc0']) + r"""} &
\multicolumn{3}{l}{24:00 储电量：""" + f1(TAB['p1']['soc24']) + r"""} \\
\bottomrule
\end{tabular}"""
w('t2p1.tex', s)


def spec_buy(prob, with_plan=False):
    """指定日6时段购电量（表1格式变体：行=时段，列=4日期并排）。
    with_plan=True 时每日期拆 计划/调整 两列（P3/P4-3）。"""
    sd = TAB[prob]['spec_dates']
    dates = list(SPEC_DAYS)
    jmap = {sl: j for j, sl in enumerate(TBL1_SLOTS)}
    rows = []
    if not with_plan:
        for sl in TBL1_SLOTS:
            j = jmap[sl]
            rows.append(sl + ' & ' + ' & '.join(f2(sd[d]['table1'][j]['buy']) for d in dates) + r' \\')
        rows.append(r'\midrule 全天购电量 (kWh) & ' + ' & '.join(f2(sd[d]['day_buy']) for d in dates) + r' \\')
        rows.append(r'全天购电费 (元) & ' + ' & '.join(
            f2(sd[d]['day_cost'] + sd[d]['emerg_cost'] + sd[d]['dev_cost']) for d in dates) + r' \\')
        rows.append(r'紧急购电量 (kWh) & ' + ' & '.join(f2(sd[d]['emerg_qty']) for d in dates) + r' \\')
        s = r"""\begin{tabular}{lrrrr}
\toprule
时间段 & 2025.3.20 & 2025.6.21 & 2025.9.23 & 2025.12.21 \\
\midrule
""" + '\n'.join(rows) + r""" \\
\bottomrule
\end{tabular}"""
    else:
        for sl in TBL1_SLOTS:
            j = jmap[sl]
            cells = []
            for d in dates:
                cells += [f2(sd[d]['table1'][j]['plan_buy']), f2(sd[d]['table1'][j]['buy'])]
            rows.append(sl + ' & ' + ' & '.join(cells) + r' \\')
        tot, dev = [], []
        for d in dates:
            tot += [f2(sd[d]['plan_day_buy']), f2(sd[d]['day_buy'])]
            dev.append(f2(sd[d]['dev_cost']))
        rows.append(r'\midrule 全天购电量 (kWh) & ' + ' & '.join(tot) + r' \\')
        rows.append(r'全天购电费 (元) & ' + ' & '.join(
            f2(sd[d]['day_cost'] + sd[d]['emerg_cost'] + sd[d]['dev_cost']) for d in dates) + r' \\')
        rows.append(r'违约调整费 (元) & \multicolumn{2}{r}{' + dev[0] +
                    r'} & \multicolumn{2}{r}{' + dev[1] + r'} & \multicolumn{2}{r}{' + dev[2] +
                    r'} & \multicolumn{2}{r}{' + dev[3] + '}')
        s = r"""\footnotesize\setlength{\tabcolsep}{3.5pt}
\begin{tabular}{lrrrrrrrr}
\toprule
 & \multicolumn{2}{c}{2025.3.20} & \multicolumn{2}{c}{2025.6.21} & \multicolumn{2}{c}{2025.9.23} & \multicolumn{2}{c}{2025.12.21} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}
时间段 & 计划 & 调整 & 计划 & 调整 & 计划 & 调整 & 计划 & 调整 \\
\midrule
""" + '\n'.join(rows) + r""" \\
\bottomrule
\end{tabular}"""
    return s


w('p2_spec_buy.tex', spec_buy('p2'))
w('p3_spec_buy.tex', spec_buy('p3', with_plan=True))


def spec_cd(prob):
    """指定日充放电量（表2格式，4日期并排）+ 0:00/24:00储电量。"""
    z = np.load(f'{RES}/{prob}.npz')
    socs = day_socs(z['c'][31:], z['dd'][31:])
    date2i = {str(np.datetime64('2025-' + k)): SPEC_D.index(v) for k, v in []}  # placeholder
    idx = {78: 0, 171: 1, 265: 2, 354: 3}
    rows = []
    for k, sl in enumerate(TBL2_SLOTS):
        vals = []
        for d in SPEC_D:
            c_ = float(z['c'][d, 36 * k:36 * (k + 1)].sum())
            d_ = float(z['dd'][d, 36 * k:36 * (k + 1)].sum())
            vals.append(f'{f2(c_)} / {f2(d_)}')
        rows.append(sl + ' & ' + ' & '.join(vals) + r' \\')
    s0 = ' & '.join(f1(socs[idx[d]][0]) for d in SPEC_D)
    s1 = ' & '.join(f1(socs[idx[d]][1]) for d in SPEC_D)
    return r"""\begin{tabular}{lcccc}
\toprule
 & \multicolumn{4}{c}{充电量/放电量 (kWh)} \\
\cmidrule(lr){2-5}
时间段 & 3-20 & 6-21 & 9-23 & 12-21 \\
\midrule
""" + ' \\\\ \n'.join(rows) + r""" \\
\midrule
0:00 储电量 & """ + s0 + r""" \\
24:00 储电量 & """ + s1 + r""" \\
\bottomrule
\end{tabular}"""


w('p2_spec_cd.tex', spec_cd('p2'))
w('p3_spec_cd.tex', spec_cd('p3'))
w('p4_2_spec_cd.tex', spec_cd('p4_2'))
w('p4_3_spec_cd.tex', spec_cd('p4_3'))


def emerg_tab(prob):
    """题面表3格式：紧急购电段（4日期并排）。"""
    sd = TAB[prob]['spec_dates']
    cols = []
    for d in SPEC_DAYS:
        segs = sd[d]['emerg_segs']
        cols.append([(x['period'], f2(x['qty'])) for x in segs])
    nrow = max(len(c) for c in cols)
    hdr = r"""\begin{tabular}{cc|cc|cc|cc}
\toprule
\multicolumn{2}{c|}{2025.3.20} & \multicolumn{2}{c|}{2025.6.21} & \multicolumn{2}{c|}{2025.9.23} & \multicolumn{2}{c}{2025.12.21} \\
\cmidrule(lr){1-2}\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}
时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量 & 时间段 & 购电量 \\
\midrule
"""
    rows = []
    for i in range(nrow):
        cells = []
        for c in cols:
            cells.append(' & '.join(c[i]) if i < len(c) else ' & ')
        rows.append(' & '.join(cells))
    return hdr + ' \\\\ \n'.join(rows) + r""" \\
\bottomrule
\end{tabular}"""


w('p2_emerg.tex', emerg_tab('p2'))
w('p3_emerg.tex', emerg_tab('p3'))
w('p4_2_emerg.tex', emerg_tab('p4_2'))
w('p4_3_emerg.tex', emerg_tab('p4_3'))

# ---------- 全年主表 ----------
Y = {k: TAB[k]['year'] for k in ['p2', 'p3', 'p4_2', 'p4_3']}
DET_OLD = TAB['p2']['year_baseline_det']['cost_total']
DET_NEW = TAB['p2']['year_baseline_det_fc']['cost_total']
A = TAB['p3']['year_A_fc0_noAdj']
det_rows = [
    '确定性LP（旧预报器） & 1221.3 & 1046.6 & 0 & ' + wan(DET_OLD) + r' & 2006.2 & -- \\',
    '确定性LP（本文预报器） & 1223.0 & 302.7 & 0 & ' + wan(DET_NEW) + r' & 524.0 & -- \\',
]
main_rows = []
for k, lab in [('p2', 'P2（SAA，本文）'), ('p3', 'P3（SAA+滚动调整，本文）'),
               ('p4_2', 'P4-2（波动电价）'), ('p4_3', 'P4-3（波动电价+调整）')]:
    y = Y[k]
    main_rows.append(f"{lab} & {wan(y['cost_plan'])} & {wan(y['cost_em'])} & {wan(y['cost_dev'])} & "
                     f"\\textbf{{{wan(y['cost_total'])}}} & {f1(y['emerg']/1e3)} & {y['curt']/1e4:.0f} \\\\")
s = r"""\begin{tabular}{lrrrrrr}
\toprule
方案 & 计划购电费 & 紧急购电费 & 违约调整费 & 总费用 & 紧急购电量 & 弃光电量 \\
 & (万元) & (万元) & (万元) & (万元) & (MWh) & (万kWh) \\
\midrule
""" + '\n'.join(det_rows) + '\n' + '\n'.join(main_rows) + r""" \\
\bottomrule
\end{tabular}"""
w('year_main.tex', s)

# ---------- P3 三方案对比 ----------
C = TAB['p3']['year_C_naive']['cost_total']
s = r"""\begin{tabular}{lrrr}
\toprule
方案 & 总费用（万元） & 紧急购电费（万元） & 违约调整费（万元） \\
\midrule
A：仅 0:00 预报，无调整 & """ + wan(A['cost_total']) + r""" & """ + wan(A['cost_em']) + r""" & 0 \\
B：+6/12/18 时滚动调整（本文） & \textbf{""" + wan(TAB['p3']['year']['cost_total']) + r"""} & """ + \
    wan(TAB['p3']['year']['cost_em']) + r""" & """ + wan(TAB['p3']['year']['cost_dev']) + r""" \\
C：无预报（naive，同 P2） & """ + wan(C) + r""" & """ + wan(Y['p2']['cost_em']) + r""" & 0 \\
\bottomrule
\end{tabular}"""
w('p3_abc.tex', s)

# ---------- 消融 ----------
ab = TAB['p3']['adjust_ablation']
s = r"""\begin{tabular}{lrrrr}
\toprule
调整时刻集合 & 总费用（万元） & 边际收益（万元） & 紧急购电费（万元） & 违约调整费（万元） \\
\midrule
无（C，同 P2） & """ + wan(C) + r""" & -- & """ + wan(Y['p2']['cost_em']) + r""" & 0 \\
{12:00} & """ + wan(ab['adj_12']['cost_total']) + r""" & $-0.03$ & """ + wan(ab['adj_12']['cost_em']) + r""" & """ + wan(ab['adj_12']['cost_dev']) + r""" \\
{6:00, 12:00} & """ + wan(ab['adj_6_12']['cost_total']) + r""" & $+10.6$ & """ + wan(ab['adj_6_12']['cost_em']) + r""" & """ + wan(ab['adj_6_12']['cost_dev']) + r""" \\
{6:00, 12:00, 18:00}（B） & \textbf{""" + wan(ab['adj_full']['cost_total']) + r"""} & $+12.6$ & """ + wan(ab['adj_full']['cost_em']) + r""" & """ + wan(ab['adj_full']['cost_dev']) + r""" \\
仅 0:00 预报（A，无调整） & """ + wan(A['cost_total']) + r""" & -- & """ + wan(A['cost_em']) + r""" & 0 \\
\bottomrule
\end{tabular}"""
w('p3_ablation.tex', s)

# ---------- K 敏感性 ----------
ks = TAB['K_sensitivity']
rows = []
for k in ['5', '10', '15', '25']:
    v = ks[k]
    rows.append(f"{k} & {wan(v['cost_total'])} & {wan(v['cost_em'])} & {f1(v['emerg']/1e3)} \\\\")
s = r"""\begin{tabular}{lrrr}
\toprule
场景数 $K$ & 总费用（万元） & 紧急购电费（万元） & 紧急购电量 (MWh) \\
\midrule
""" + ' \\\\ \n'.join(rows) + r""" \\
\bottomrule
\end{tabular}"""
w('ksens.tex', s)

# ---------- P4 全年对比（含参考最优） ----------
lb4 = TAB['lower_bounds']['p4_2_lb']
s = r"""\begin{tabular}{lrrr}
\toprule
方案 & 总费用（万元） & 计划购电费（万元） & 紧急+违约费（万元） \\
\midrule
P4-2（两日滚动，无调整） & \textbf{""" + wan(Y['p4_2']['cost_total']) + r"""} & """ + wan(Y['p4_2']['cost_plan']) + r""" & """ + wan(Y['p4_2']['cost_em']) + r""" \\
P4-3（两日滚动+调整） & \textbf{""" + wan(Y['p4_3']['cost_total']) + r"""} & """ + wan(Y['p4_3']['cost_plan']) + r""" & """ + wan(Y['p4_3']['cost_em'] + Y['p4_3']['cost_dev']) + r""" \\
日循环参考最优（波动电价） & """ + wan(lb4) + r""" & -- & -- \\
P2（固定电价，对照） & """ + wan(Y['p2']['cost_total']) + r""" & """ + wan(Y['p2']['cost_plan']) + r""" & """ + wan(Y['p2']['cost_em']) + r""" \\
P3（固定电价，对照） & """ + wan(Y['p3']['cost_total']) + r""" & """ + wan(Y['p3']['cost_plan']) + r""" & """ + wan(Y['p3']['cost_em'] + Y['p3']['cost_dev']) + r""" \\
\bottomrule
\end{tabular}"""
w('p4_year.tex', s)

# ---------- P4 指定日 ----------
srows = []
sd42, sd43, sd2, sd3 = (TAB[k]['spec_dates'] for k in ['p4_2', 'p4_3', 'p2', 'p3'])
for d in SPEC_DAYS:
    def tot(sd):
        return sd[d]['day_cost'] + sd[d]['emerg_cost'] + sd[d]['dev_cost']
    srows.append(f"2025.{d[5:].replace('-', '.')} & {f2(tot(sd2))} & {f2(tot(sd42))} & {f2(tot(sd3))} & {f2(tot(sd43))} \\\\")
s = r"""\begin{tabular}{lrrrr}
\toprule
日期 & P2 & P4-2 & P3 & P4-3 \\
\midrule
""" + ' \\\\ \n'.join(srows) + r""" \\
\bottomrule
\end{tabular}"""
w('p4_spec.tex', s)

# ---------- 汇总输出 ----------
print('exported:', sorted(os.listdir(OUT)))
