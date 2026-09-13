"""Regenerate the two small-font figures at a legible effective size.

Included at 0.88 and 0.95 of a 14.20 cm text block, so a figure drawn at 22.86 cm
wide is scaled to ~55-59 %. Base 10 pt therefore renders at ~5.5 pt. We redraw both
figures at 16.51 cm (6.5 in) wide with explicit font sizes so that the *effective*
on-page size is >= 6 pt (labels/legends) and >= 7 pt (axis labels, titles).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle
from matplotlib.collections import PatchCollection

R = Path(__file__).resolve().parents[1]
S = json.loads((R / "artifacts/summary.json").read_text(encoding="utf-8"))
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

# ---- fig: cost_components -------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.6))
for ax, q in zip(axes, ["3", "4"]):
    d = S["iid"][q]["vs56"]["decomposition_s"]
    vals = list(d.values())
    ax.bar(["走路", "测向", "换频", "失败清除"], vals,
           color=["#187b7d" if v >= 0 else "#b64635" for v in vals])
    ax.axhline(0, color="#222", lw=.7)
    ax.set(ylabel="平均节省（秒）", title="Q" + q)
    ax.tick_params(axis="x", labelsize=12)
    ax.tick_params(axis="y", labelsize=11)
    ax.title.set_fontsize(13)
    ax.yaxis.label.set_fontsize(12)
    ax.grid(axis="y", alpha=.15)
fig.tight_layout(pad=0.6)
fig.savefig(R / "figures/cost_components.pdf")
fig.savefig(R / "figures/cost_components.png", dpi=200)
plt.close(fig)
print("cost_components regenerated")

# ---- fig: residual_geometry ----------------------------------------------
a = json.loads((R / "artifacts/residual-witness.json").read_text(encoding="utf-8"))
sites = np.array(a["sites"])
boxes = a["boxes"]
fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.9))
patches = [Rectangle((x0, y0), x1 - x0, y1 - y0) for x0, y0, x1, y1 in boxes]
axes[0].add_collection(PatchCollection(patches, facecolor="#dae7ec",
                                       edgecolor="#adbdc4", linewidth=.15))
axes[0].add_patch(Circle((0, 0), 1800, fill=False, color="#333", lw=1))
axes[0].scatter(sites[:, 0], sites[:, 1], s=14, color="#187b7d")
axes[0].set(xlim=(-2100, 2100), ylim=(-2100, 2100), xlabel="x (m)", ylabel="y (m)",
            title="连续覆盖认证分区")
axes[0].title.set_fontsize(13)
axes[0].xaxis.label.set_fontsize(12)
axes[0].yaxis.label.set_fontsize(12)
axes[0].tick_params(labelsize=11)
axes[0].set_aspect("equal")

old = np.array([995, 0])
q = sites[1]
axes[1].plot([old[0], q[0]], [old[1], q[1]], color="#187b7d")
axes[1].scatter([old[0]], [old[1]], label="静态点", marker="x", s=70, color="#b64635")
axes[1].scatter([q[0]], [q[1]], label="证书通过的替换点", s=55, color="#187b7d")
axes[1].set(xlim=(989, 999.5), ylim=(-3.4, 3.4), xlabel="x (m)", ylabel="y (m)",
            title="可行替换位移3.595米")
axes[1].title.set_fontsize(13)
axes[1].xaxis.label.set_fontsize(12)
axes[1].yaxis.label.set_fontsize(12)
axes[1].tick_params(labelsize=11)
# legend inside the axes: an outside legend would be clipped by the figure edge
axes[1].legend(loc="lower right", fontsize=11, framealpha=.95, borderpad=.35,
               handletextpad=.4)
axes[1].set_aspect("equal")
fig.tight_layout(pad=0.6)
fig.savefig(R / "figures/residual_geometry.pdf")
fig.savefig(R / "figures/residual_geometry.png", dpi=200)
plt.close(fig)
print("residual_geometry regenerated")
