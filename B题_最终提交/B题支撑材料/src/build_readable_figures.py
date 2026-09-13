"""Regenerate the two remaining small-font figures at a legible effective size.

* fig: paired_results     -- saved by src/build_paper_assets.py at figsize=(10,3.5)
* fig: count_time_relation -- saved by supplement/count_time/src/build_count_report.py at (10,4.4)

Both are drawn on a ~25.4 cm canvas but included at <=14.2 cm, i.e. ~56 % scale, so a
10-11 pt base font lands at ~5.6 pt on the page. We redraw them on a 16.51 cm (6.5 in)
canvas with >=11 pt fonts, giving >=8 pt on the page.
"""
import json
from pathlib import Path

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def t_ppf(p, df):
    """Student-t quantile via bisection on the regularised incomplete beta function
    (avoids a scipy dependency for figure regeneration)."""
    def betainc(a, b, x, n=4000):
        # continued fraction (Lentz) for the regularised incomplete beta
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
        f, c, d = 1.0, 1.0, 0.0
        for i in range(n):
            m = i // 2
            if i == 0:
                num = 1.0
            elif i % 2 == 0:
                num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
            d = 1.0 + num * d
            d = 1e-30 if abs(d) < 1e-30 else d
            d = 1.0 / d
            c = 1.0 + num / c
            c = 1e-30 if abs(c) < 1e-30 else c
            f *= c * d
            if abs(1 - c * d) < 1e-14:
                break
        return front * (f - 1)

    def cdf(x):
        ib = betainc(df / 2.0, 0.5, df / (df + x * x)) / 2.0
        return 1 - ib if x > 0 else ib

    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


R = Path(__file__).resolve().parents[1]

from matplotlib import font_manager
available_fonts = {font.name for font in font_manager.fontManager.ttflist}
figure_font = next((name for name in ['Heiti TC', 'Microsoft YaHei',
    'Noto Sans CJK SC', 'SimHei', 'FandolHei'] if name in available_fonts), None)
if figure_font is None:
    import subprocess
    font_file = subprocess.check_output(['kpsewhich', 'FandolHei-Regular.otf'],
                                        text=True).strip()
    if not font_file:
        raise RuntimeError('Install a Chinese font or TeX Fandol fonts.')
    font_manager.fontManager.addfont(font_file)
    figure_font = font_manager.FontProperties(fname=font_file).get_name()

plt.rcParams.update({
    "font.family": figure_font,
    "font.size": 12,
    "axes.unicode_minus": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
})

# ---------------------------------------------------------------- paired_results
S = json.loads((R / "artifacts/summary.json").read_text(encoding="utf-8"))
fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.5))
for ax, q in zip(axes, ["3", "4"]):
    pairs = S["iid"][q]["vs56"]["pairs"]
    x = np.arange(1, len(pairs) + 1)
    y = np.array([v["saving_s"] for v in pairs])
    ax.scatter(x, y, s=6, c=np.where(y >= 0, "#187b7d", "#b64635"), alpha=.8)
    ax.axhline(0, color="#222", lw=.7)
    ax.set(xlabel="配对案例序号", ylabel="相对方法56节省（秒）", title="Q" + q)
    ax.title.set_fontsize(13)
    ax.xaxis.label.set_fontsize(12)
    ax.yaxis.label.set_fontsize(12)
    ax.tick_params(labelsize=11)
    ax.grid(alpha=.15)
fig.tight_layout(pad=0.6)
fig.savefig(R / "figures/paired_results.pdf")
fig.savefig(R / "figures/paired_results.png", dpi=200)
plt.close(fig)
print("paired_results regenerated")

# ------------------------------------------------------- count_time_relation
D = json.loads((R / "supplement/count_time/artifacts/count_time_results.json").read_text(encoding="utf-8"))
Q = D["Q"]
fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.0))
handles = []
for ax, q in zip(axes, ["3", "4"]):
    d = Q[q]
    f = d["models"]["affine_step16"]
    beta = np.array(f["coefficients"])
    cov = np.array(f["HC3_covariance"])
    x = np.linspace(10, 15.99, 150)
    g = np.column_stack([1 / x, np.ones(len(x)), np.zeros(len(x))])
    y = g @ beta
    margin = t_ppf(.975, 197) * np.sqrt(np.einsum("ij,jk,ik->i", g, cov, g))
    line, = ax.plot(x, y, color="#163e5d", lw=1.6, label="冻结公式")
    ax.fill_between(x, y - margin, y + margin, color="#163e5d", alpha=.13)
    point = d["predictions"][-1]
    ax.plot([16], [point["predicted_avg_s"]], marker="s", color="#163e5d", ms=5)
    a = d["training_groups"]
    old = ax.scatter([z["N"] - .05 for z in a], [z["avg_mean_s"] for z in a],
                     color="#8c979e", marker="x", s=22, label="原样本均值")
    b = d["validation_groups"]
    new = ax.errorbar([z["N"] + .05 for z in b], [z["avg_mean_s"] for z in b],
                      yerr=[[z["avg_mean_s"] - z["avg_mean_t95_s"][0] for z in b],
                            [z["avg_mean_t95_s"][1] - z["avg_mean_s"] for z in b]],
                      fmt="o", ms=3.5, capsize=2.5, color="#c06927",
                      label="新样本均值及95%区间")
    ax.set(xlabel="信号源数量 N", ylabel="单源平均清除时长（秒）",
           title="Q3：全向源" if q == "3" else "Q4：全向与定向混合",
           xticks=range(10, 17), xlim=(9.7, 16.3))
    ax.title.set_fontsize(12)
    ax.xaxis.label.set_fontsize(11)
    ax.yaxis.label.set_fontsize(11)
    ax.tick_params(labelsize=10.5)
    ax.grid(alpha=.16)
    handles = [line, old, new]
fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(.5, .005),
           frameon=False, fontsize=11)
fig.tight_layout(rect=(0, .10, 1, 1), pad=0.6)
fig.savefig(R / "supplement/count_time/figures/count_time_relation.pdf")
fig.savefig(R / "supplement/count_time/figures/count_time_relation.png", dpi=200)
fig.savefig(R / "figures/count_time_relation.pdf")
fig.savefig(R / "figures/count_time_relation.png", dpi=200)
plt.close(fig)
print("count_time_relation regenerated")
