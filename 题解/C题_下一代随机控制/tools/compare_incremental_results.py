"""Paired actual bills and prespecified seven-day moving-block bootstrap."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nextgen_scenarios import Config


def daily_ledger(stem):
    with np.load(Path(stem).with_suffix('.npz'), allow_pickle=False) as a:
        p, q, r, e = (a[k] for k in ('price', 'q', 'r', 'emergency'))
        return {'dates': a['dates'].tolist(), 'total_cost': np.sum(p*(q+1.5*np.maximum(r-q, 0)-.5*np.maximum(q-r, 0)+5*e), axis=1),
                'emergency_cost': np.sum(5*p*e, axis=1), 'emergency_kwh': e.sum(1),
                'spill_kwh': a['spill'].sum(1), 'ending_inventory_kwh': a['state'][:, -1].copy(),
                'min_soc': float(a['state'].min()/12000), 'max_soc': float(a['state'].max()/12000),
                'initial': float(a['state'][0, 0]), 'final': float(a['state'][-1, -1])}


def block_indices(days=334, replicates=10000, block=7, seed=20260911):
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, days-block+1, size=(replicates, (days+block-1)//block), dtype=np.int32)
    return (starts[:, :, None]+np.arange(block, dtype=np.int32)).reshape(replicates, -1)[:, :days]


def pair(candidate, baseline, indices):
    assert candidate['dates'] == baseline['dates'] and len(candidate['dates']) == 334
    expected_dates = np.arange(np.datetime64('2025-02-01'), np.datetime64('2026-01-01')).astype(str).tolist()
    assert candidate['dates'] == expected_dates
    assert max(abs(candidate[k]-baseline[k]) for k in ('initial', 'final')) < 1e-5
    assert max(abs(candidate[k]-6000.) for k in ('initial', 'final')) < 1e-5
    saving = baseline['total_cost']-candidate['total_cost']
    samples = saving[indices].sum(1); lo, hi = np.quantile(samples, [.025, .975])
    total_base = float(baseline['total_cost'].sum()); total = float(candidate['total_cost'].sum())
    rows = []
    for i, date in enumerate(candidate['dates']):
        rows.append({'date': date, 'baseline_cost_yuan': baseline['total_cost'][i],
                     'candidate_cost_yuan': candidate['total_cost'][i], 'saving_yuan': saving[i],
                     'baseline_emergency_kwh': baseline['emergency_kwh'][i], 'candidate_emergency_kwh': candidate['emergency_kwh'][i],
                     'baseline_spill_kwh': baseline['spill_kwh'][i], 'candidate_spill_kwh': candidate['spill_kwh'][i],
                     'baseline_ending_inventory_kwh': baseline['ending_inventory_kwh'][i], 'candidate_ending_inventory_kwh': candidate['ending_inventory_kwh'][i]})
    return {'total_cost_yuan': total, 'baseline_cost_yuan': total_base, 'saving_yuan': total_base-total,
            'saving_percent': 100*(total_base-total)/total_base, 'bootstrap_95_lower_yuan': float(lo),
            'bootstrap_95_upper_yuan': float(hi), 'positive_days': int(np.sum(saving > 1e-6)),
            'negative_days': int(np.sum(saving < -1e-6)), 'emergency_cost_yuan': float(candidate['emergency_cost'].sum()),
            'emergency_kwh': float(candidate['emergency_kwh'].sum()), 'spill_kwh': float(candidate['spill_kwh'].sum()),
            'min_soc': candidate['min_soc'], 'max_soc': candidate['max_soc'],
            'first_half_saving_yuan': float(sum(s for s, d in zip(saving, candidate['dates']) if d < '2025-07-01')),
            'second_half_saving_yuan': float(sum(s for s, d in zip(saving, candidate['dates']) if d >= '2025-07-01'))}, rows, saving


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def scenario_diagnostics(metrics):
    d = metrics['decisions']
    return {'candidate_blocks_mean': float(np.mean([x['effective_window'] for x in d])),
            'candidate_blocks_min': min(x['effective_window'] for x in d),
            'representatives_mean': float(np.mean([x['effective_scenarios'] for x in d])),
            'candidate_ESS_mean': float(np.mean([x['weight_ess'] for x in d])),
            'transport_distance_mean': float(np.mean([x['transport_distance'] for x in d])),
            'net_tail95_retention_fraction': float(np.mean([x['tail95_representative_retained'] for x in d])),
            'gain_binding_fraction': sum(x['gain_bound_hit_count'] for x in d)/max(1, sum(x['gain_active_count'] for x in d))}


def main(allow_partial=False):
    frozen = json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text())
    configurations = [Config(**c) for c in frozen['annual_configurations']]
    incumbent = Config(**frozen['incumbent']); indices = block_indices()
    summaries = []; pending = []
    for config in configurations:
        for kind in ('q2', 'q3', 'q4_2', 'q4_3'):
            stem = ROOT/f'artifacts/formal/{kind}_{config.identity()}'
            fixed48 = ROOT/f'artifacts/formal/{kind}_{Config().identity()}'
            legacy = ROOT/f'baseline_frozen/artifacts/global-terminal/{kind}_markov_mpc'
            if not stem.with_suffix('.npz').exists() or not fixed48.with_suffix('.npz').exists():
                pending.append({'kind': kind, 'configuration': config.identity()}); continue
            candidate = daily_ledger(stem)
            metrics = json.loads(stem.with_suffix('.json').read_text())
            for label, baseline_path in [('legacy_matched_terminal', legacy), ('fixed48_reference', fixed48)]:
                result, rows, difference = pair(candidate, daily_ledger(baseline_path), indices)
                result.update({'kind': kind, 'configuration_id': config.identity(), 'comparison': label,
                               'runtime_seconds': metrics['runtime_seconds'], **metrics['timing'], **scenario_diagnostics(metrics)})
                summaries.append(result)
                write_csv(ROOT/f'计算结果/逐日配对/{kind}_{config.identity()}_vs_{label}.csv', rows)
    if summaries: write_csv(ROOT/'计算结果/增量消融汇总.csv', summaries)
    stage_summaries = []
    for index, stage in enumerate(frozen['stages']):
        configs = [Config(**c) for c in stage['configurations']]
        if len(configs) < 2: continue
        for config in configs[1:]:
            for kind in ('q2', 'q3', 'q4_2', 'q4_3'):
                candidate_path = ROOT/f'artifacts/formal/{kind}_{config.identity()}'
                base_path = ROOT/f'artifacts/formal/{kind}_{configs[0].identity()}'
                if not candidate_path.with_suffix('.npz').exists() or not base_path.with_suffix('.npz').exists(): continue
                result, rows, _ = pair(daily_ledger(candidate_path), daily_ledger(base_path), indices)
                stage_summaries.append({'stage_index': index, 'stage': stage['name'], 'kind': kind,
                    'reference_configuration': configs[0].identity(), 'candidate_configuration': config.identity(), **result})
                write_csv(ROOT/f"计算结果/阶段逐日配对/{index:02d}_{kind}_{config.identity()}.csv", rows)
    if stage_summaries: write_csv(ROOT/'计算结果/阶段同口径消融.csv', stage_summaries)
    report = {'status': 'PENDING' if pending else 'complete', 'summaries': summaries, 'pending': pending,
              'stage_comparisons': stage_summaries,
              'bootstrap': {'block': 7, 'replicates': 10000, 'seed': 20260911, 'interval': 'percentile95',
                            'scope': 'paired serial-dependence diagnostic for this seasonal single year; not a guarantee about future years'},
              'baseline_verification': 'Frozen legacy results used only as a named reference; final claims require the independent full reproduction gate PASS',
              'selection_sha256': hashlib.sha256((ROOT/'artifacts/frozen-development-selection.json').read_bytes()).hexdigest()}
    (ROOT/'artifacts/incremental-comparisons.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': report['status'], 'comparisons': len(summaries), 'pending': len(pending)}, ensure_ascii=False))
    if pending and not allow_partial: raise SystemExit(2)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--allow-partial', action='store_true'); args = p.parse_args(); main(args.allow_partial)
