import csv, json, math, statistics as st
from pathlib import Path
R = Path(__file__).resolve().parents[1]
(R / "figures").mkdir(exist_ok=True)

def tcrit(df):
    table = {1:12.706,2:4.303,5:2.571,10:2.228,20:2.086,30:2.042,39:2.023,40:2.021,60:2.000,120:1.980}
    if df in table:
        return table[df]
    keys = sorted(table)
    for a, b in zip(keys, keys[1:]):
        if a < df < b:
            return table[a] + (table[b] - table[a]) * (df - a) / (b - a)
    return 1.96

def mean_ci(xs):
    m = st.mean(xs)
    if len(xs) < 2:
        return m, [m, m]
    se = st.pstdev(xs) / math.sqrt(len(xs) - 1)
    h = tcrit(len(xs) - 1) * se
    return m, [m - h, m + h]

def frozen_mu4(n):
    return -31.60 + 6206.85 / n - (513.96 / n if n == 16 else 0)

rows = []
for n in range(10, 17):
    for method in (78, 84):
        path = R / "results" / f"q4_n{n}_m{method}.csv"
        for r in csv.DictReader(path.open()):
            d = {k: (r[k] if k == "certificate" else float(r[k])) for k in r}
            rows.append(d)

groups = {}
for r in rows:
    groups.setdefault((int(r["method"]), int(r["n"])), []).append(r)

summary = {"problem": 4, "cases_per_cell": 40, "methods": [78, 84], "groups": {}}
for method in (78, 84):
    summary["groups"][str(method)] = {}
    for n in range(10, 17):
        g = groups[(method, n)]
        T = [x["time_s"] for x in g]
        tau = [x["avg_s"] for x in g]
        move = [x["move_m"] / 5 for x in g]
        meas = [x["measures"] for x in g]
        scans = [x["scans"] for x in g]
        miss = [x["miss"] for x in g]
        fb = [x["fallbacks"] for x in g]
        nd = [x["directional_n"] for x in g]
        skip = [x["skipped_discovery"] for x in g]
        tm, tci = mean_ci(T)
        am, aci = mean_ci(tau)
        cell = {
            "cases": len(g),
            "all_cleared": all(x["cleared"] == n for x in g),
            "total_mean_s": tm,
            "total_ci95_s": tci,
            "per_source_mean_s": am,
            "per_source_ci95_s": aci,
            "move_mean_s": st.mean(move),
            "measures_mean": st.mean(meas),
            "scans_mean": st.mean(scans),
            "miss_mean": st.mean(miss),
            "fallbacks_mean": st.mean(fb),
            "directional_mean": st.mean(nd),
            "skipped_discovery_mean": st.mean(skip),
            "frozen_mu4_s": frozen_mu4(n),
            "per_source_minus_frozen_s": am - frozen_mu4(n),
            "cpu_mean_s": st.mean(x["runtime_s"] for x in g),
            "cpu_max_s": max(x["runtime_s"] for x in g),
        }
        summary["groups"][str(method)][str(n)] = cell

# 78 vs 84 paired on same seeds
paired = {}
for n in range(10, 17):
    a = {int(x["seed"]): x for x in groups[(78, n)]}
    b = {int(x["seed"]): x for x in groups[(84, n)]}
    dT = [a[s]["time_s"] - b[s]["time_s"] for s in a]
    m, ci = mean_ci(dT)
    paired[str(n)] = {
        "saving_84_vs_78_mean_s": m,
        "saving_ci95_s": ci,
        "faster": sum(x > 1e-4 for x in dT),
        "slower": sum(x < -1e-4 for x in dT),
        "ties": sum(abs(x) <= 1e-4 for x in dT),
    }
summary["paired_84_vs_78"] = paired

# monotonicity of method 78 per-source means
tau78 = [summary["groups"]["78"][str(n)]["per_source_mean_s"] for n in range(10, 17)]
summary["method78_per_source_adjacent_drop"] = [tau78[i] - tau78[i + 1] for i in range(6)]
summary["method78_monotone_decreasing_means"] = all(x > 0 for x in summary["method78_per_source_adjacent_drop"])

(R / "artifacts" / "q4_by_count_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "Songti SC",
        "font.size": 11,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
    })
    ns = list(range(10, 17))
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    ax = axes[0]
    for method, color, label in ((78, "#1f4e79", "方法78 定额"), (84, "#c45911", "方法84 定额")):
        y = [summary["groups"][str(method)][str(n)]["per_source_mean_s"] for n in ns]
        lo = [summary["groups"][str(method)][str(n)]["per_source_ci95_s"][0] for n in ns]
        hi = [summary["groups"][str(method)][str(n)]["per_source_ci95_s"][1] for n in ns]
        ax.errorbar(ns, y, yerr=[[a - b for a, b in zip(y, lo)], [c - a for a, c in zip(y, hi)]],
                    fmt="o-", color=color, label=label, capsize=3)
    ax.plot(ns, [frozen_mu4(n) for n in ns], "k--", label="冻结 $\\mu_4(N)$")
    ax.set_xlabel("源数 $N$")
    ax.set_ylabel("每源均时 / 秒")
    ax.set_xticks(ns)
    ax.legend(frameon=False, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax = axes[1]
    for method, color, label in ((78, "#1f4e79", "方法78 定额"), (84, "#c45911", "方法84 定额")):
        y = [summary["groups"][str(method)][str(n)]["total_mean_s"] for n in ns]
        lo = [summary["groups"][str(method)][str(n)]["total_ci95_s"][0] for n in ns]
        hi = [summary["groups"][str(method)][str(n)]["total_ci95_s"][1] for n in ns]
        ax.errorbar(ns, y, yerr=[[a - b for a, b in zip(y, lo)], [c - a for a, c in zip(y, hi)]],
                    fmt="o-", color=color, label=label, capsize=3)
    ax.set_xlabel("源数 $N$")
    ax.set_ylabel("总局均时 / 秒")
    ax.set_xticks(ns)
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(R / "figures" / "q4_by_count.png", dpi=160)
    fig.savefig(R / "figures" / "q4_by_count.pdf")
    plt.close()
except Exception as e:
    summary["figure_error"] = str(e)
    (R / "artifacts" / "q4_by_count_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

print(json.dumps({n: summary["groups"]["78"][str(n)]["per_source_mean_s"] for n in range(10, 17)}, indent=2))
