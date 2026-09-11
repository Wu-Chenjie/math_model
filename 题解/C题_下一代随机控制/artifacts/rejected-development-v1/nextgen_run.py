"""Incremental chronological replay with the frozen original meter/executor."""
from pathlib import Path
from dataclasses import asdict
import argparse
import hashlib
import json
import time
import numpy as np
from control import ETA, execute, prune_cuts
from dispatch import settlement
from nextgen_scenarios import Config, ScenarioFactory, weighted_quantile
from nextgen_control import affine_plan, WeightedMarkovDP, EnhancedMarkovDP

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'q2': (False, False), 'q3': (True, False), 'q4_2': (False, True), 'q4_3': (True, True)}


def dump(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def simulate(data, selection, days, kind, config, initial=6000., progress=None):
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.py'))}
    official, variable = KINDS[kind]; days = list(days); count = len(days)
    arrays = {k: np.zeros((count, 144)) for k in ['q', 'r', 'c', 'd', 'emergency', 'spill', 'price', 'projection']}
    arrays['state'] = np.zeros((count, 145)); arrays['releases'] = np.full((count, 4, 144), np.nan)
    factory = ScenarioFactory(data, selection, official, variable, config.alpha,
                              config.fusion_weight, config.official_correction)
    started = time.perf_counter(); E = float(initial); evaluation_end = (days[-1]+1)*144
    decisions = []; daily = []; lp_violation = objective_gap = 0.; tails = {}
    planning_seconds = feedback_seconds = scenario_seconds = 0.
    for i, day in enumerate(days):
        arrays['state'][i, 0] = E
        actual = (data['load'][day]-data['pv'][day])/6
        scoring_price = data['price'][day] if variable else data['day_price']
        arrays['price'][i] = scoring_price
        for t in range(144):
            now = day*144+t
            if t % 36 == 0:
                end = min(now+6*config.horizon_hours if config.horizon_mode == 'fixed'
                          else (day+config.horizon_hours//24)*144, evaluation_end)
                stage_started = time.perf_counter(); bundle = factory.build(now, end, config)
                scenario_seconds += time.perf_counter()-stage_started
                net, prices, weights = (bundle[k] for k in ('net', 'prices', 'weights'))
                base = None if t == 0 else np.r_[arrays['q'][i, t:], np.zeros(end-(day+1)*144)]
                terminal = config.final if end == evaluation_end else None
                lam = 0.; cuts = None; cutoff = tail_days = None
                if end < evaluation_end:
                    if config.tail == 'linear':
                        last_prices = prices[:, -min(144, end-now):]
                        lam = config.tail_scale*float(weighted_quantile(last_prices.ravel(), [.25],
                            np.repeat(weights, last_prices.shape[1]))[0])/ETA
                    elif config.tail == 'sddp':
                        if end % 144: raise ValueError('Existing SDDP tail is valid only at midnight')
                        cutoff = 14 if day < 31 else day-int(str(data['dates'][day])[8:10])+1
                        tail_days = min(3, (evaluation_end-end)//144)
                        suffix = '' if tail_days == 3 else '_D'+str(tail_days)
                        path = ROOT.parent/'C题_下一代基线复现'/f'artifacts/tails/{kind}_{cutoff}{suffix}.json'
                        if path not in tails: tails[path] = json.loads(path.read_text())
                        assert tails[path]['configuration']['cutoff_day_exclusive']*144 <= now
                        cuts = prune_cuts(tails[path]['root_cuts'])
                    elif config.tail != 'zero': raise ValueError(config.tail)
                plan = affine_plan(bundle, now, E, config, base, official, lam, terminal, cuts)
                planning_seconds += plan['runtime_seconds']
                lp_violation = max(lp_violation, plan['lp_violation']); objective_gap = max(objective_gap, plan['objective_gap'])
                if t == 0:
                    arrays['q'][i] = np.maximum(plan['q'][:144], 0); arrays['r'][i] = arrays['q'][i]
                    arrays['releases'][i, 0] = arrays['q'][i]
                elif official:
                    arrays['r'][i, t:] = np.maximum(plan['r'][:144-t], 0)
                    arrays['releases'][i, t//36, t:] = arrays['r'][i, t:]
                effective = plan['r'].copy(); locked = 36 if official else 144-t
                effective[:locked] = arrays['r'][i, t:t+locked]
                stage_started = time.perf_counter()
                if config.lower == 'M0':
                    dp = WeightedMarkovDP(net, prices, effective, weights, lam, config.grid, config.bins, terminal, cuts)
                elif config.lower == 'M1':
                    dp = EnhancedMarkovDP(bundle, effective, now, config, lam, terminal, cuts)
                else: raise ValueError(config.lower)
                feedback_seconds += time.perf_counter()-stage_started
                active = t; zn, ep, zp = bundle['seed'][1:]
                record = {**bundle['meta'], 'date': str(data['dates'][day]), 'release': t//36,
                          'inventory': E, 'tail_price': lam, 'tail_model_cutoff': cutoff,
                          'tail_model_days': tail_days, 'tail_cut_count': len(cuts) if cuts else 0,
                          'contract_information_cutoff': now, 'current_delivery_observation_in_contract': False,
                          'gain_active_count': plan['gain_active_count'], 'gain_bound_hit_count': plan['gain_bound_hit_count'],
                          'gain_max_abs': plan['gain_max_abs'], 'lp_violation': plan['lp_violation'],
                          'objective_recompute_gap': plan['objective_gap'], 'solver_seconds': plan['runtime_seconds'],
                          'partial_contract_completion': plan['future_partial_contract_completion'],
                          'contract_information_cutoffs': plan['contract_information_cutoffs']}
                if config.lower == 'M1': record['enhanced_markov'] = dp.diagnostics()
                decisions.append(record)
            j = t-active
            error = actual[t]-bundle['forecast']['net'][j]; zn = (1-config.alpha)*zn+config.alpha*error
            state = np.array([error, zn, ep, zp]) if variable else np.array([error, zn])
            target = dp.action(j, E, actual[t], arrays['r'][i, t], state)
            E, c, discharge, emergency, spill, projection = execute(E, target, arrays['r'][i, t], actual[t], evaluation_end-now-1, final=config.final)
            for name, value in [('c', c), ('d', discharge), ('emergency', emergency), ('spill', spill), ('projection', projection)]:
                arrays[name][i, t] = value
            arrays['state'][i, t+1] = E
            # Price is disclosed only after the battery action has been committed.
            ep = data['price'][day, t]-bundle['forecast']['price'][j]
            zp = (1-config.alpha)*zp+config.alpha*ep
        cost = settlement(arrays['q'][i], arrays['r'][i], arrays['emergency'][i], scoring_price)
        daily.append({'date': str(data['dates'][day]), **cost,
                      'emergency_energy': float(arrays['emergency'][i].sum()),
                      'spill_energy': float(arrays['spill'][i].sum()), 'ending_inventory': E,
                      'projection_count': int(np.sum(arrays['projection'][i] > 1e-6))})
        if progress and ((i+1) % 7 == 0 or i+1 == count):
            dump(progress, {'kind': kind, 'configuration_id': config.identity(), 'completed_days': i+1,
                            'requested_days': count, 'last_date': str(data['dates'][day]),
                            'elapsed_seconds': time.perf_counter()-started, 'status': 'running'})
    balance = arrays['r']+arrays['emergency']+arrays['d']-arrays['c']-arrays['spill']-(data['load'][days]-data['pv'][days])/6
    validation = {'balance_max_abs': float(np.abs(balance).max()),
        'soc_recurrence_max_abs': float(np.abs(np.diff(arrays['state'], axis=1)-ETA*arrays['c']+arrays['d']/ETA).max()),
        'midnight_jump_max_abs': float(np.abs(arrays['state'][1:, 0]-arrays['state'][:-1, -1]).max(initial=0)),
        'soc_min': float(arrays['state'].min()), 'soc_max': float(arrays['state'].max()),
        'power_max_kw': float(6*max(arrays['c'].max(), arrays['d'].max())),
        'simultaneous_max': float(np.minimum(arrays['c'], arrays['d']).max()),
        'initial_inventory': initial, 'final_inventory': E, 'lp_violation_max': lp_violation,
        'lp_objective_recompute_gap': objective_gap}
    assert validation['balance_max_abs'] < 1e-5 and validation['soc_recurrence_max_abs'] < 1e-5
    assert validation['midnight_jump_max_abs'] < 1e-5 and validation['soc_min'] >= 1200-1e-5 and validation['soc_max'] <= 10800+1e-5
    assert config.final is None or abs(E-config.final) < 1e-5
    arrays['days'] = np.array(days); arrays['dates'] = data['dates'][days]
    keys = ['planned_cost', 'increase_cost', 'reduction_net_cost', 'emergency_cost', 'total_cost', 'emergency_energy', 'spill_energy', 'projection_count']
    metrics = {'kind': kind, 'candidate': config.identity(),
               'configuration': {**asdict(config), 'initial': initial, 'closed_daily': False, 'start_day': days[0], 'end_day': days[-1]},
               'totals': {k: float(sum(row[k] for row in daily)) for k in keys},
               'validation': validation, 'daily': daily, 'decisions': decisions,
               'runtime_seconds': time.perf_counter()-started,
               'timing': {'planning_seconds': planning_seconds, 'feedback_build_seconds': feedback_seconds, 'scenario_seconds': scenario_seconds},
               'source_hashes': source_hashes}
    assert source_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.py'))}, 'Source changed during replay; do not certify this run'
    return arrays, metrics


def run_case(kind, configuration, start, stop, output):
    config = Config(**configuration); data = dict(np.load(ROOT/'artifacts/data.npz'))
    selection = json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    arrays, metrics = simulate(data, selection, range(start, stop), kind, config, progress=output.with_suffix('.progress.json'))
    np.savez_compressed(output.with_suffix('.npz'), **arrays); dump(output.with_suffix('.json'), metrics)
    dump(output.with_suffix('.progress.json'), {'status': 'complete', 'completed_days': stop-start})
    return {'kind': kind, 'configuration': configuration, 'output': str(output), 'cost': metrics['totals']['total_cost'], 'runtime_seconds': metrics['runtime_seconds']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--kind', default='q2'); p.add_argument('--config', default='{}')
    p.add_argument('--start', type=int, default=24); p.add_argument('--stop', type=int, default=31)
    p.add_argument('--output', default=str(ROOT/'artifacts/development/single'))
    args = p.parse_args(); print(json.dumps(run_case(args.kind, json.loads(args.config), args.start, args.stop, args.output), ensure_ascii=False))
