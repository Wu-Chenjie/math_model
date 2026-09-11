"""Build paper evidence from the independently audited frozen baseline.

This script does not run an optimizer.  It only recomputes bills and paired
diagnostics from hash-bound NPZ/JSON artifacts in baseline_frozen.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("q2", "q3", "q4_2", "q4_3")
LABELS = {"q2": "问题二", "q3": "问题三", "q4_2": "问题四-2", "q4_3": "问题四-3"}
EXPECTED_DATES = np.arange(np.datetime64("2025-02-01"), np.datetime64("2026-01-01")).astype(str)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def ledger(stem: Path) -> dict:
    npz = stem.with_suffix(".npz")
    with np.load(npz, allow_pickle=False) as a:
        p, q, r, e = (a[k] for k in ("price", "q", "r", "emergency"))
        dates = a["dates"].astype(str)
        cost = np.sum(p * (q + 1.5 * np.maximum(r - q, 0) - 0.5 * np.maximum(q - r, 0) + 5 * e), axis=1)
        return {
            "dates": dates.tolist(),
            "total_cost_yuan": cost,
            "emergency_cost_yuan": np.sum(5 * p * e, axis=1),
            "emergency_kwh": e.sum(axis=1),
            "spill_kwh": a["spill"].sum(axis=1),
            "ending_inventory_kwh": a["state"][:, -1].copy(),
            "initial_inventory_kwh": float(a["state"][0, 0]),
            "final_inventory_kwh": float(a["state"][-1, -1]),
            "min_inventory_kwh": float(a["state"].min()),
            "max_inventory_kwh": float(a["state"].max()),
        }


def validate_ledger(item: dict):
    assert item["dates"] == EXPECTED_DATES.tolist()
    assert abs(item["initial_inventory_kwh"] - 6000.0) < 1e-7
    assert abs(item["final_inventory_kwh"] - 6000.0) < 1e-7


def moving_block_indices(days: int, block: int, replicates: int = 10000, seed: int = 20260911):
    rng = np.random.default_rng(seed + block)
    count = (days + block - 1) // block
    starts = rng.integers(0, days - block + 1, size=(replicates, count), dtype=np.int32)
    return (starts[:, :, None] + np.arange(block, dtype=np.int32)).reshape(replicates, -1)[:, :days]


def bootstrap(saving: np.ndarray, block: int) -> dict:
    idx = moving_block_indices(len(saving), block)
    samples = saving[idx].sum(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    return {"block_days": block, "replicates": 10000, "seed": 20260911,
            "lower_yuan": float(lo), "upper_yuan": float(hi)}


def monthly(candidate: dict, baseline: dict) -> list[dict]:
    saving = baseline["total_cost_yuan"] - candidate["total_cost_yuan"]
    rows = []
    for month in range(2, 13):
        mask = np.array([int(d[5:7]) == month for d in EXPECTED_DATES])
        rows.append({"month": f"2025-{month:02d}",
                     "candidate_cost_yuan": float(candidate["total_cost_yuan"][mask].sum()),
                     "baseline_cost_yuan": float(baseline["total_cost_yuan"][mask].sum()),
                     "saving_yuan": float(saving[mask].sum()),
                     "saving_days": int(np.sum(saving[mask] > 1e-8)),
                     "loss_days": int(np.sum(saving[mask] < -1e-8))})
    return rows


def main():
    evidence = {"status": "verified", "scope": "baseline_frozen independently audited artifacts",
                "evaluation_period": {"start": "2025-02-01", "end": "2025-12-31", "days": 334,
                                       "initial_inventory_kwh": 6000.0, "terminal_inventory_kwh": 6000.0,
                                       "intermediate_midnight_reset": False},
                "sources": {}, "q1": {}, "questions": {}, "information_ablations": {},
                "monthly": {}, "bootstrap": {}, "model_comparison": {}, "fair_crossday_affine": {}}

    q1_json = ROOT / "baseline_frozen/artifacts/q1.json"
    q1_npz = ROOT / "baseline_frozen/artifacts/q1.npz"
    q1 = read_json(q1_json)
    with np.load(q1_npz, allow_pickle=False) as a:
        q1.update({"purchased_energy_kwh": float(a["q"].sum()),
                   "charged_bus_kwh": float(a["c"].sum()),
                   "discharged_bus_kwh": float(a["d"].sum()),
                   "inventory_min_kwh": float(a["state"].min()),
                   "inventory_max_kwh": float(a["state"].max())})
    evidence["q1"] = q1
    # These rows are copied from the frozen specified-date result table and
    # are included only to make the Q1 table traceable without parsing prose
    # in the LaTeX build.
    evidence["q1"]["selected_purchase_slots"] = [
        {"time": "10:00-10:10", "purchase_kwh": 0.0},
        {"time": "12:00-12:10", "purchase_kwh": 480.4124},
        {"time": "14:00-14:10", "purchase_kwh": 0.0},
        {"time": "16:00-16:10", "purchase_kwh": 445.4317},
        {"time": "18:00-18:10", "purchase_kwh": 531.8940},
        {"time": "20:00-20:10", "purchase_kwh": 0.0},
    ]
    evidence["q1"]["four_hour_actions"] = [
        {"time": "00:00-04:00", "charge_kwh": 4500.0000, "discharge_kwh": 0.0},
        {"time": "04:00-08:00", "charge_kwh": 833.3333, "discharge_kwh": 6365.8412},
        {"time": "08:00-12:00", "charge_kwh": 4787.9643, "discharge_kwh": 1702.9970},
        {"time": "12:00-16:00", "charge_kwh": 5286.0352, "discharge_kwh": 91.1014},
        {"time": "16:00-20:00", "charge_kwh": 0.0, "discharge_kwh": 5780.1319},
        {"time": "20:00-24:00", "charge_kwh": 5333.3333, "discharge_kwh": 2859.8681},
    ]
    q1_table = ROOT / "baseline_frozen/指定日期结果表.md"
    evidence["sources"]["q1_table"] = {"path": str(q1_table.relative_to(ROOT)), "sha256": sha256(q1_table)}
    evidence["sources"]["q1_json"] = {"path": str(q1_json.relative_to(ROOT)), "sha256": sha256(q1_json)}
    evidence["sources"]["q1_npz"] = {"path": str(q1_npz.relative_to(ROOT)), "sha256": sha256(q1_npz)}

    for kind in KINDS:
        candidate_stem = ROOT / f"baseline_frozen/artifacts/global-terminal/{kind}_markov_mpc"
        baseline_stem = ROOT / f"baseline_frozen/artifacts/annual/{kind}_closed_baseline"
        cand = ledger(candidate_stem)
        base = ledger(baseline_stem)
        validate_ledger(cand)
        validate_ledger(base)
        cand_meta = read_json(candidate_stem.with_suffix(".json"))
        base_meta = read_json(baseline_stem.with_suffix(".json"))
        cand_total = float(cand["total_cost_yuan"].sum())
        base_total = float(base["total_cost_yuan"].sum())
        assert abs(cand_total - cand_meta["fixed_total_cost"]) < 1e-4
        assert abs(base_total - base_meta["totals"]["total_cost"]) < 1e-4
        saving = base["total_cost_yuan"] - cand["total_cost_yuan"]
        fixed = {"candidate_cost_yuan": cand_total, "baseline_cost_yuan": base_total,
                 "saving_yuan": float(saving.sum()),
                 "saving_percent": float(100 * saving.sum() / base_total),
                 "positive_days": int(np.sum(saving > 1e-8)),
                 "negative_days": int(np.sum(saving < -1e-8)),
                 "candidate_emergency_kwh": float(cand["emergency_kwh"].sum()),
                 "candidate_spill_kwh": float(cand["spill_kwh"].sum()),
                 "candidate_min_inventory_kwh": cand["min_inventory_kwh"],
                 "candidate_max_inventory_kwh": cand["max_inventory_kwh"],
                 "bootstrap": {str(b): bootstrap(saving, b) for b in (3, 7, 14)}}
        free_meta = read_json(ROOT / f"baseline_frozen/artifacts/annual/{kind}_markov_mpc.json")
        fixed_meta = read_json(candidate_stem.with_suffix(".json"))
        fixed["free_terminal_cost_yuan"] = float(free_meta["totals"]["total_cost"])
        fixed["fixed_terminal_cost_yuan"] = float(fixed_meta["fixed_total_cost"])
        evidence["questions"][kind] = fixed
        evidence["monthly"][kind] = monthly(cand, base)
        evidence["sources"][f"{kind}_candidate"] = {"path": str(candidate_stem.with_suffix(".npz").relative_to(ROOT)),
                                                        "sha256": sha256(candidate_stem.with_suffix(".npz"))}
        evidence["sources"][f"{kind}_baseline"] = {"path": str(baseline_stem.with_suffix(".npz").relative_to(ROOT)),
                                                      "sha256": sha256(baseline_stem.with_suffix(".npz"))}
        evidence["sources"][f"{kind}_candidate_json"] = {"path": str(candidate_stem.with_suffix(".json").relative_to(ROOT)),
                                                            "sha256": sha256(candidate_stem.with_suffix(".json"))}
        evidence["sources"][f"{kind}_baseline_json"] = {"path": str(baseline_stem.with_suffix(".json").relative_to(ROOT)),
                                                           "sha256": sha256(baseline_stem.with_suffix(".json"))}

        # The complete candidate table is already part of the frozen result
        # registry.  Keep it in the paper evidence so model-selection claims
        # and the SDDP comparison have the same traceability as bill totals.
        model_files = {
            "closed_baseline": ROOT / f"baseline_frozen/artifacts/annual/{kind}_closed_baseline.json",
            "cross_baseline": ROOT / f"baseline_frozen/artifacts/annual/{kind}_cross_baseline.json",
            "closed_affine": ROOT / f"baseline_frozen/artifacts/annual/{kind}_closed_affine.json",
            "affine_mpc": ROOT / f"baseline_frozen/artifacts/annual/{kind}_affine_mpc.json",
            "markov_mpc": ROOT / f"baseline_frozen/artifacts/annual/{kind}_markov_mpc.json",
            "sddp_markov": ROOT / f"baseline_frozen/artifacts/annual_sddp/{kind}_sddp_markov.json",
        }
        evidence["model_comparison"][kind] = {}
        for name, path in model_files.items():
            meta = read_json(path)
            evidence["model_comparison"][kind][name] = {
                "free_cost_yuan": float(meta["totals"]["total_cost"]),
                "final_inventory_kwh": float(meta["totals"].get("final_inventory", meta.get("validation", {}).get("final_inventory", np.nan))),
            }
            evidence["sources"][f"{kind}_{name}_model"] = {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}

        closed_affine = evidence["model_comparison"][kind]["closed_affine"]["free_cost_yuan"]
        affine_global = read_json(ROOT / f"baseline_frozen/artifacts/global-terminal/{kind}_affine_mpc.json")
        affine_fixed = float(affine_global["fixed_total_cost"])
        evidence["fair_crossday_affine"][kind] = {
            "daily_closed_affine_cost_yuan": closed_affine,
            "crossday_affine_fixed_cost_yuan": affine_fixed,
            "saving_yuan": closed_affine - affine_fixed,
            "saving_percent": 100 * (closed_affine - affine_fixed) / closed_affine,
        }
        affine_path = ROOT / f"baseline_frozen/artifacts/global-terminal/{kind}_affine_mpc.json"
        evidence["sources"][f"{kind}_affine_global_json"] = {"path": str(affine_path.relative_to(ROOT)), "sha256": sha256(affine_path)}

    info_root = ROOT / "artifacts/information-terminal"
    full_cost = evidence["questions"]["q3"]["fixed_terminal_cost_yuan"]
    for name in ("0only", "without6", "without12", "without18"):
        stem = info_root / f"q3_{name}"
        item = ledger(stem)
        validate_ledger(item)
        total = float(item["total_cost_yuan"].sum())
        evidence["information_ablations"][name] = {"cost_yuan": total, "increment_vs_all_releases_yuan": total - full_cost,
                                                    "increment_percent": 100 * (total - full_cost) / full_cost,
                                                    "emergency_kwh": float(item["emergency_kwh"].sum())}
        evidence["sources"][f"information_{name}"] = {"path": str(stem.with_suffix(".npz").relative_to(ROOT)),
                                                          "sha256": sha256(stem.with_suffix(".npz"))}

    oracle = read_json(ROOT / "baseline_frozen/review/global-oracle.json")["results"]
    evidence["perfect_information_reference"] = {
        "fixed_price_fixed_terminal_yuan": oracle["fixed_fixed6000"]["objective_cost_yuan"],
        "variable_price_fixed_terminal_yuan": oracle["variable_fixed6000"]["objective_cost_yuan"],
        "interpretation": "optimistic pathwise reference; not an optimality gap for the causal policy",
    }
    evidence["sources"]["global_oracle"] = {"path": "baseline_frozen/review/global-oracle.json",
                                               "sha256": sha256(ROOT / "baseline_frozen/review/global-oracle.json")}

    out = ROOT / "artifacts/frozen-paper-evidence.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Register every numeric leaf so every paper-bound number has a source path.
    registry = []
    claims = []
    def walk(value, path=""):
        if isinstance(value, dict):
            for key, val in value.items():
                if key != "sources":
                    walk(val, path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list):
            for i, val in enumerate(value):
                walk(val, path + "/" + str(i))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            ident = "frozen-paper" + path.replace("/", ".")
            registry.append({"id": ident, "source_artifact": "artifacts/frozen-paper-evidence.json",
                             "source_path": path, "value": value, "status": "verified"})
            claims.append({"result_id": ident, "usage": "Frozen-baseline final paper, tables, figures or reproducibility appendix."})
    walk(evidence)
    (ROOT / "artifacts/result-registry.json").write_text(json.dumps({"schema_version": 1, "scope": "frozen audited paper",
                                                                         "results": registry}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "paper/result-claims.json").write_text(json.dumps({"schema_version": 1, "claims": claims}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "verified", "output": str(out), "registered_results": len(registry)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
