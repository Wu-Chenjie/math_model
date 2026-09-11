"""January-only staged development, then a frozen annual experiment register.

Every economic configuration actually evaluated in development is also registered
for a full annual replay. No annual metrics are read by the selection functions.
"""
from pathlib import Path
from dataclasses import asdict, replace
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nextgen_scenarios import Config, ScenarioFactory
from nextgen_run import KINDS, run_case, dump

PROTOCOL = {
    'version': 5, 'development_days': [24, 31], 'evaluation_days': [31, 365],
    'initial_kwh': 6000., 'final_kwh': 6000.,
    'physical_parameters': 'Unchanged control.execute and dispatch.settlement; original official input hashes preserved',
    'incumbent': 'Accepted legacy two-midnight M0 with the same true final6000; fixed48 is separately retained as the single-factor horizon reference.',
    'parameter_classes': {
        'physical': ['ETA=.9', 'capacity=12000', 'inventory=[1200,10800]', 'power=5000', 'settlement=original'],
        'numerical': {'SOC_grid': [161, 321, 641], 'grid_bill_convergence_tolerance': .0002, 'PAM_max_swaps': 20},
        'policy': {'H_hours': [48, 72, 96], 'gain_bound': [5., 10., 20.], 'tail_scales': [0., .5, 1., 2.]},
        'statistical': {'W': [14, 28, 56], 'S': [5, 7, 10, 14], 'alpha': [.1, .2, .3, .5], 'Markov_bins': [2, 3, 4, 5],
                        'fusion_weight': [0., .25, .5, .75, 1.], 'official_correction': [0., .4, .8],
                        'ridge': 1e-4, 'empirical_innovation_representatives': 10, 'state_kernel_bandwidth': 1.}},
    'selection': 'Staged one-factor January comparisons, equal weight to each question relative to its stage reference. Within0.1percent select the listed simpler configuration. No annual cost enters parameter selection.',
    'predictor_selection': 'Keep accepted historical forecast families. Select official PV fusion/correction by Jan15-24 next-six-hour MAE; retrospective development scores are not claimed to be unbiased held-out forecasts.',
    'grid_selection': 'Smallest grid whose January total bills in all four questions are within0.02percent of641; not the grid yielding minimum expense.',
    'representative_count_selection': 'In accordance with the latest requested7-10representatives, only7or10can be selected for the primary challenger.5and14remain full economic sensitivity configurations, registered for334days.',
    'M1_development_gate': 'Mean normalized saving at least0.1percent, no question worse than0.1percent, positive aggregate saving in both Jan25-27 and Jan28-31.',
    'M1_final_matched_gate': 'After final tail selection register both lower=M0 and lower=M1 with every other parameter identical, rerun the January M1 gate, and downgrade a failing M1 to M0. A final M1 challenger also requires direct annual matched-M0 mean saving>=0.1percent, no question worse, positive both half-period sums and positive seven-day bootstrap lower endpoint. Failure rejects the sole challenger; never pick another annual winner.',
    'annual_adoption_gate': 'One January-selected challenger only: normalized mean saving>=0.1percent, no question worse, positive aggregate saving in both Feb-Jun and Jul-Dec, and lower endpoint of paired7day block bootstrap total saving>0. If not met retain the frozen incumbent.0.1-0.3percent requires the predeclared state/conditional-probability theoretical role;>=0.3percent may justify adoption. No selecting a different annual winner.',
    'bootstrap': {'block_days': 7, 'replicates': 10000, 'seed': 20260911, 'interval': .95,
                  'interpretation': 'paired moving-block stability diagnostic on one seasonal year, not a distribution-free future-year confidence guarantee'},
    'gain_expansion_rule': 'If over5percent of active gains hit the bound in January, move to the next predeclared bound5/10/20 regardless of bill. If20 remains above5percent, add40 and80 sequentially as declared engineering checks; freeze before annual. Formal hits do not trigger expense-based retuning.',
    'final_gain_check': 'Repeat boundary enforcement after grid/feedback/tail choices. An expansion reruns January grid, M0/M1 and tail selection at the expanded bound. At80 any remaining binding is reported, not described as inactive regularization.',
    'freeze_integrity': 'Bind source, coordinator, input data, forecast selection and protocol. Refuse development after a freeze or formal start marker; annual verifies all bound hashes before execution.',
    'tail_interface': 'Fixed-H zero/linear are inventory-tail truncation heuristics with explicit causal q suffix completion. Existing SDDP compared with zero/linear/scaled tails in a separate common two-midnight block. No inventory-only SDDP at nonmidnight; no unimplemented contract bridge claimed.',
    'horizon_pool': 'Each H uses all its own complete mature blocks, identical generator settings; thus H changes legally available history too. Report requested/effective counts rather than claiming an isolated physical-lookahead effect.',
    'scope': 'All economic development configurations are registered for334days; forecast-only MAE fits are not unexecuted closed-loop policy results. Free-end sensitivity is separate.',
}


def source_signature():
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted((ROOT/'src').glob('*.py'))}
    return files


def integrity_signature():
    paths = list((ROOT/'src').glob('*.py')) + [Path(__file__), ROOT/'artifacts/data.npz',
        ROOT/'artifacts/forecast-selection.json', ROOT/'artifacts/development-forecast-selection.json',
        ROOT/'artifacts/experiment-protocol.json']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def require_unfrozen_development():
    for path in [ROOT/'artifacts/frozen-development-selection.json', ROOT/'artifacts/formal-start.json',
                 ROOT/'artifacts/execution-formal.json']:
        if path.exists(): raise RuntimeError(f'Refuse to overwrite frozen development: {path.name}')
    if (ROOT/'artifacts/formal').exists() and any((ROOT/'artifacts/formal').iterdir()):
        raise RuntimeError('Formal artifacts already exist; development is closed')


def preregister():
    p = ROOT/'artifacts/experiment-protocol.json'
    if p.exists():
        old = json.loads(p.read_text()); assert old['protocol'] == PROTOCOL, 'Protocol changed; version and audit it explicitly'
        return old
    value = {'created_utc': datetime.now(timezone.utc).isoformat(), 'protocol': PROTOCOL,
             'source_hashes_at_registration': source_signature(),
             'baseline_reproduction': 'still running; user explicitly authorized incremental implementation before completion'}
    dump(p, value); return value


def execute_group(configurations, phase, workers):
    start, stop = (24, 31) if phase == 'development' else (31, 365)
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for config in configurations:
            for kind in KINDS:
                stem = ROOT/f'artifacts/{phase}/{kind}_{config.identity()}'
                existing = stem.with_suffix('.json')
                if existing.exists() and stem.with_suffix('.npz').exists():
                    value = json.loads(existing.read_text())
                    assert value['source_hashes'] == {Path(k).name: v for k, v in source_signature().items()}, 'Refuse stale source-version result reuse'
                    results.append({'kind': kind, 'configuration': asdict(config), 'output': str(stem), 'cost': value['totals']['total_cost']})
                    continue
                future = pool.submit(run_case, kind, asdict(config), start, stop, str(stem)); futures[future] = stem
        for future in as_completed(futures):
            result = future.result(); results.append(result)
            print(json.dumps({'phase': phase, 'kind': result['kind'], 'configuration': result['configuration'], 'cost': result['cost']}, ensure_ascii=False), flush=True)
    return results


def matrix(configurations):
    # Deliberately hard-coded January directory: never select using formal bills.
    return np.array([[json.loads((ROOT/f'artifacts/development/{kind}_{c.identity()}.json').read_text())['totals']['total_cost'] for kind in KINDS] for c in configurations])


def choose(configurations):
    costs = matrix(configurations); scores = (costs/costs[0]).mean(1)
    eligible = np.flatnonzero(scores <= scores.min()+.001)
    index = int(eligible[0])
    return configurations[index], {'scores': scores.tolist(), 'costs': costs.tolist(), 'chosen_index': index}


def select_forecast():
    data = dict(np.load(ROOT/'artifacts/data.npz'))
    # Mechanically deny access to February--December during statistical selection.
    for name in ('load', 'pv', 'price'): data[name][31:] = np.nan
    data['forecast'][31:] = np.nan
    selection = json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
    rows = []
    # Prefer the unchanged forecast if prediction errors tie; no cost-based tuning.
    settings = [(1., 0.)]+[(w, g) for w in [0., .25, .5, .75, 1.] for g in [0., .4, .8] if (w, g) != (1., 0.)]
    for weight, gain in settings:
        factory = ScenarioFactory(data, selection, True, False, fusion_weight=weight, official_correction=gain)
        errors = []
        for day in range(14, 24):
            for phase in (0, 36, 72, 108):
                a = day*144+phase; f = factory.forecast(a, 36)
                errors.extend(np.abs(f['pv']-data['pv'].ravel()[a:a+36]).tolist())
        rows.append({'fusion_weight': weight, 'official_correction': gain, 'january_pv_mae_kw': float(np.mean(errors))})
    best = min(range(len(rows)), key=lambda i: rows[i]['january_pv_mae_kw'])
    dump(ROOT/'artifacts/development-forecast-selection.json', {'rows': rows, 'selected': rows[best], 'data_cutoff_exclusive': 31*144})
    return rows[best]


def development(workers):
    require_unfrozen_development(); preregister(); all_configs = {}; stages = []
    def stage(name, configs, select=True):
        configs = list(dict((c.identity(), c) for c in configs).values())
        execute_group(configs, 'development', workers)
        all_configs.update({c.identity(): c for c in configs})
        selected, evidence = choose(configs)
        stages.append({'name': name, 'configurations': [asdict(c) for c in configs], **evidence, 'selecting': select})
        dump(ROOT/'artifacts/development-stage-log.json', {'stages': stages, 'status': 'running'})
        return selected
    incumbent = Config(horizon_mode='legacy')
    stage('legacy_matched_terminal', [incumbent], select=False)
    chosen = stage('fixed_horizon_only', [replace(incumbent, horizon_mode='fixed', horizon_hours=h) for h in [48, 72, 96]])
    horizon_selected = chosen
    forecast = select_forecast()
    chosen = stage('forecast_fusion_only', [chosen, replace(chosen, fusion_weight=forecast['fusion_weight'], official_correction=forecast['official_correction'])])
    chosen = stage('trajectory_measure', [replace(chosen, scenario_method=m) for m in ['legacy', 'medoids', 'conditional']])
    # Even if the conditional module loses, its W/S sensitivity is still evaluated.
    conditional_reference = replace(chosen, scenario_method='conditional')
    conditional_reference = stage('conditional_window', [replace(conditional_reference, window=w) for w in [14, 28, 56]])
    stage('representative_count_sensitivity', [replace(conditional_reference, scenarios=s) for s in [7, 10, 5, 14]], select=False)
    conditional_reference = stage('representative_count_main_selection', [replace(conditional_reference, scenarios=s) for s in [7, 10]])
    conditional_reference = stage('state_smoothing', [replace(conditional_reference, alpha=a) for a in [.2, .1, .3, .5]])
    chosen = stage('conditional_module_acceptance', [chosen, conditional_reference])
    chosen = stage('shared_state_contract_features', [replace(chosen, upper=u) for u in ['legacy', 'state']])
    chosen = stage('gain_regularization', [replace(chosen, gain_bound=g) for g in [5., 10., 20.]])
    def hit_ratio(c):
        records = [json.loads((ROOT/f'artifacts/development/{k}_{c.identity()}.json').read_text())['decisions'] for k in KINDS]
        denominator = sum(d['gain_active_count'] for rows in records for d in rows)
        return sum(d['gain_bound_hit_count'] for rows in records for d in rows)/max(denominator, 1)
    expansions = []
    for bound in [10., 20., 40., 80.]:
        if hit_ratio(chosen) <= .05 or bound <= chosen.gain_bound: continue
        candidate = replace(chosen, gain_bound=bound); stage('gain_boundary_expansion', [chosen, candidate], select=False)
        expansions.append({'from': chosen.gain_bound, 'to': bound, 'trigger_hit_ratio': hit_ratio(chosen)})
        chosen = candidate
    grids = [replace(chosen, grid=g) for g in [161, 321, 641]]
    stage('inventory_grid_convergence', grids, select=False); costs = matrix(grids)
    candidates = np.flatnonzero(np.max(np.abs(costs/costs[-1]-1), axis=1) <= .0002)
    chosen = grids[int(candidates[0])]
    stage('discrete_state_count_sensitivity', [replace(chosen, bins=k) for k in [3, 2, 4, 5]], select=False)
    M0 = replace(chosen, bins=3, lower='M0'); M1 = replace(M0, lower='M1')
    stage('continuous_state_feedback', [M0, M1], select=False)
    costs = matrix([M0, M1]); savings = 1-costs[1]/costs[0]
    halves = []
    for sl in [slice(0, 3), slice(3, 7)]:
        difference = 0.
        for kind in KINDS:
            a = json.loads((ROOT/f'artifacts/development/{kind}_{M0.identity()}.json').read_text())['daily']
            b = json.loads((ROOT/f'artifacts/development/{kind}_{M1.identity()}.json').read_text())['daily']
            difference += sum(v['total_cost'] for v in a[sl])-sum(v['total_cost'] for v in b[sl])
        halves.append(difference)
    m1_pass = bool(savings.mean() >= .001 and savings.min() >= -.001 and min(halves) > 0)
    chosen = M1 if m1_pass else M0
    chosen = stage('fixed_horizon_inventory_tail', [replace(chosen, tail='linear', tail_scale=s) for s in [1., 0., .5, 2.]])
    # The terminal heuristic can change gain binding. Recheck the actual final
    # challenger before freezing, and repeat affected January choices if needed.
    while True:
        final_M0, final_M1 = replace(chosen, lower='M0'), replace(chosen, lower='M1')
        stage('final_matched_feedback', [final_M0, final_M1], select=False)
        final_costs = matrix([final_M0, final_M1]); final_savings = 1-final_costs[1]/final_costs[0]
        final_halves = []
        for sl in [slice(0, 3), slice(3, 7)]:
            difference = 0.
            for kind in KINDS:
                a = json.loads((ROOT/f'artifacts/development/{kind}_{final_M0.identity()}.json').read_text())['daily']
                b = json.loads((ROOT/f'artifacts/development/{kind}_{final_M1.identity()}.json').read_text())['daily']
                difference += sum(v['total_cost'] for v in a[sl])-sum(v['total_cost'] for v in b[sl])
            final_halves.append(difference)
        final_m1_pass = bool(final_savings.mean() >= .001 and final_savings.min() >= -.001 and min(final_halves) > 0)
        if chosen.lower == 'M1' and not final_m1_pass: chosen = final_M0
        if hit_ratio(chosen) <= .05 or chosen.gain_bound >= 80: break
        bound = next(b for b in [10., 20., 40., 80.] if b > chosen.gain_bound)
        expanded = replace(chosen, gain_bound=bound)
        stage('final_gain_boundary_expansion', [chosen, expanded], select=False)
        expansions.append({'from': chosen.gain_bound, 'to': bound, 'trigger_hit_ratio': hit_ratio(chosen), 'phase': 'final'})
        grids = [replace(expanded, grid=g, bins=3, lower='M0', tail_scale=1.) for g in [161, 321, 641]]
        stage('expanded_inventory_grid_convergence', grids, select=False); costs = matrix(grids)
        eligible = np.flatnonzero(np.max(np.abs(costs/costs[-1]-1), axis=1) <= .0002)
        M0 = grids[int(eligible[0])]; M1 = replace(M0, lower='M1')
        stage('expanded_continuous_state_feedback', [M0, M1], select=False)
        costs = matrix([M0, M1]); savings = 1-costs[1]/costs[0]; halves = []
        for sl in [slice(0, 3), slice(3, 7)]:
            difference = 0.
            for kind in KINDS:
                a = json.loads((ROOT/f'artifacts/development/{kind}_{M0.identity()}.json').read_text())['daily']
                b = json.loads((ROOT/f'artifacts/development/{kind}_{M1.identity()}.json').read_text())['daily']
                difference += sum(v['total_cost'] for v in a[sl])-sum(v['total_cost'] for v in b[sl])
            halves.append(difference)
        m1_pass = bool(savings.mean() >= .001 and savings.min() >= -.001 and min(halves) > 0)
        chosen = M1 if m1_pass else M0
        chosen = stage('expanded_fixed_horizon_inventory_tail', [replace(chosen, tail_scale=s) for s in [1., 0., .5, 2.]])
    # Old SDDP has only a verified midnight interface. Hold that interface common.
    tail_reference = replace(M0, horizon_mode='legacy', horizon_hours=48)
    stage('matched_midnight_tail_diagnostic', [replace(tail_reference, tail='linear', tail_scale=s) for s in [1., 0., .5, 2.]]+[replace(tail_reference, tail='sddp')], select=False)
    all_configs[incumbent.identity()] = incumbent
    record = {'status': 'frozen', 'frozen_utc': datetime.now(timezone.utc).isoformat(),
              'protocol_sha256': hashlib.sha256((ROOT/'artifacts/experiment-protocol.json').read_bytes()).hexdigest(),
              'source_hashes': source_signature(), 'incumbent': asdict(incumbent),
              'integrity_hashes': integrity_signature(),
              'horizon_selected': asdict(horizon_selected), 'challenger': asdict(chosen),
              'M0': asdict(M0), 'M1': asdict(M1), 'M1_development_pass': m1_pass,
              'final_matched_M0': asdict(final_M0), 'final_matched_M1': asdict(final_M1),
              'final_M1_development_pass': final_m1_pass,
              'final_M1_question_savings': final_savings.tolist(), 'final_M1_half_savings_yuan': final_halves,
              'M1_question_savings': savings.tolist(), 'M1_half_savings_yuan': halves,
              'gain_expansions': expansions, 'gain_hit_ratio_at_freeze': hit_ratio(chosen),
              'annual_configurations': [asdict(c) for c in all_configs.values()],
              'stages': stages, 'selection_data': 'January only; annual outputs never read by this function'}
    dump(ROOT/'artifacts/frozen-development-selection.json', record)
    dump(ROOT/'artifacts/development-stage-log.json', {'stages': stages, 'status': 'complete'})
    print(json.dumps({'development': 'frozen', 'annual_configurations': len(all_configs), 'challenger': asdict(chosen)}, ensure_ascii=False), flush=True)


def annual(workers):
    preregister(); frozen = json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text())
    assert frozen['status'] == 'frozen' and frozen['source_hashes'] == source_signature()
    assert frozen['protocol_sha256'] == hashlib.sha256((ROOT/'artifacts/experiment-protocol.json').read_bytes()).hexdigest()
    assert frozen['integrity_hashes'] == integrity_signature(), 'Frozen implementation, input or selection changed'
    freeze_sha = hashlib.sha256((ROOT/'artifacts/frozen-development-selection.json').read_bytes()).hexdigest()
    marker = ROOT/'artifacts/formal-start.json'
    if marker.exists():
        assert json.loads(marker.read_text())['selection_sha256'] == freeze_sha
    else:
        dump(marker, {'started_utc': datetime.now(timezone.utc).isoformat(), 'selection_sha256': freeze_sha,
                      'integrity_hashes': frozen['integrity_hashes']})
    results = execute_group([Config(**v) for v in frozen['annual_configurations']], 'formal', workers)
    assert frozen['integrity_hashes'] == integrity_signature(), 'Bound files changed during formal evaluation'
    dump(ROOT/'artifacts/execution-formal.json', {'status': 'complete', 'results': results,
         'selection_sha256': hashlib.sha256((ROOT/'artifacts/frozen-development-selection.json').read_bytes()).hexdigest()})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--phase', choices=['register', 'development', 'annual'], default='development')
    p.add_argument('--workers', type=int, default=2); args = p.parse_args()
    if args.phase == 'register': preregister(); print('Protocol registered before economic development sweep.')
    elif args.phase == 'development': development(args.workers)
    else: annual(args.workers)
