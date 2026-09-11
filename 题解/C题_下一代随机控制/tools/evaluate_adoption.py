"""Apply the preregistered annual gate to the single January-selected challenger.

This module cannot select among annual winners. All four questions are paired
with the accepted, fixed-terminal legacy policy; shared bootstrap indices retain
the within-date dependence between their bills.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
from compare_incremental_results import daily_ledger, block_indices, pair
from certify_model_checks import certificate_is_current

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nextgen_scenarios import Config


def gate(question_results, joint_daily_saving, indices, theoretical_role):
    samples = np.asarray(joint_daily_saving)[indices].sum(1)
    lo, hi = np.quantile(samples, [.025, .975])
    mean_percent = float(np.mean([r['saving_percent'] for r in question_results]))
    first = sum(r['first_half_saving_yuan'] for r in question_results)
    second = sum(r['second_half_saving_yuan'] for r in question_results)
    checks = {
        'normalized_mean_saving_at_least_0_1_percent': mean_percent >= .1,
        'no_question_more_expensive': all(r['saving_yuan'] >= 0 for r in question_results),
        'positive_Feb_Jun_aggregate': first > 0,
        'positive_Jul_Dec_aggregate': second > 0,
        'positive_joint_bootstrap_lower_endpoint': lo > 0,
        'small_gain_has_predeclared_theoretical_role': mean_percent >= .3 or bool(theoretical_role),
    }
    checks = {k: bool(v) for k, v in checks.items()}
    return {'economic_gate_pass': bool(all(checks.values())), 'checks': checks,
            'mean_question_saving_percent': mean_percent,
            'joint_saving_yuan': float(np.sum(joint_daily_saving)),
            'joint_bootstrap95_yuan': [float(lo), float(hi)],
            'joint_first_period_saving_yuan': float(first),
            'joint_second_period_saving_yuan': float(second),
            'theoretical_role': theoretical_role,
            'joint_scope': 'Sum across four alternative task settings for stability screening; not one physical microgrid annual bill.'}


def main():
    freeze_path = ROOT/'artifacts/frozen-development-selection.json'
    frozen = json.loads(freeze_path.read_text())
    challenger = Config(**frozen['challenger']); incumbent = Config(**frozen['incumbent'])
    pending = []; questions = []; differences = []; indices = block_indices()
    for kind in ('q2', 'q3', 'q4_2', 'q4_3'):
        stem = ROOT/f'artifacts/formal/{kind}_{challenger.identity()}'
        reference = ROOT/f'baseline_frozen/artifacts/global-terminal/{kind}_markov_mpc'
        if not stem.with_suffix('.npz').exists():
            pending.append(str(stem.relative_to(ROOT))); continue
        result, _, difference = pair(daily_ledger(stem), daily_ledger(reference), indices)
        questions.append({'kind': kind, **result}); differences.append(difference)
    roles = []
    if challenger.scenario_method == 'conditional': roles.append('Condition the empirical joint trajectory measure on the observed error state.')
    if challenger.upper == 'state': roles.append('Use a common causal error-state definition in contract and inventory feedback.')
    if challenger.lower == 'M1': roles.append('Represent persistent joint errors by an empirical-innovation projected Markov operator.')
    report = {'status': 'PENDING', 'challenger': frozen['challenger'], 'incumbent': frozen['incumbent'],
              'selection_sha256': hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
              'question_results': questions, 'pending': pending,
              'selection_rule': 'Evaluate this frozen challenger only; never substitute a different annual winner.'}
    if not pending:
        report.update(gate(questions, np.sum(differences, axis=0), indices, roles))
        if challenger.lower == 'M1':
            matched = Config(**frozen['final_matched_M0'])
            assert {k: v for k, v in frozen['challenger'].items() if k != 'lower'} == {k: v for k, v in frozen['final_matched_M0'].items() if k != 'lower'}
            assert matched.lower == 'M0' and frozen['final_M1_development_pass']
            direct_questions = []; direct_differences = []
            for kind in ('q2', 'q3', 'q4_2', 'q4_3'):
                result, _, difference = pair(daily_ledger(ROOT/f'artifacts/formal/{kind}_{challenger.identity()}'),
                    daily_ledger(ROOT/f'artifacts/formal/{kind}_{matched.identity()}'), indices)
                direct_questions.append({'kind': kind, **result}); direct_differences.append(difference)
            direct = gate(direct_questions, np.sum(direct_differences, axis=0), indices,
                          ['Empirical continuous-state feedback is the only module changed in this contrast.'])
            direct['question_results'] = direct_questions
            report['M1_direct_matched_M0_gate'] = direct
            report['economic_gate_pass'] = report['economic_gate_pass'] and direct['economic_gate_pass']
        requirements = {'baseline_reproduction': ROOT/'artifacts/baseline-reproduction-check.json',
                        'formal_physics': ROOT/'artifacts/formal-validation.json',
                        'model_information_and_mathematics': ROOT/'artifacts/model-check-validation.json'}
        evidence = {}
        for name, path in requirements.items():
            value = json.loads(path.read_text()) if path.exists() else {}
            evidence[name] = {'status': value.get('status', 'PENDING'),
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
            if name == 'baseline_reproduction' and value:
                freeze = ROOT/'artifacts/baseline-freeze.json'
                baseline_hashes = json.loads(freeze.read_text())['file_hashes'] if freeze.exists() else {}
                for kind in ('q2', 'q3', 'q4_2', 'q4_3'):
                    relative = f'artifacts/global-terminal/{kind}_markov_mpc.npz'
                    reference = ROOT/'baseline_frozen'/relative
                    if not reference.is_file() or hashlib.sha256(reference.read_bytes()).hexdigest() != baseline_hashes.get(relative):
                        evidence[name]['status'] = 'STALE_BASELINE_REFERENCE'
            if name == 'formal_physics' and value:
                current = value.get('frozen_selection_sha256') == report['selection_sha256']
                expected = {(kind, Config(**c).identity()) for c in frozen['annual_configurations'] for kind in ('q2', 'q3', 'q4_2', 'q4_3')}
                records = value.get('records', [])
                found = [(r['kind'], r['configuration_id']) for r in records]
                current = current and len(found) == len(expected) and set(found) == expected
                current = current and all(r.get('status') == 'PASS' and r.get('checks', 0) > 0 for r in records)
                for record in records:
                    validation_path = ROOT/record['report']
                    current = current and validation_path.exists() and hashlib.sha256(validation_path.read_bytes()).hexdigest() == record['report_sha256']
                    for field, suffix in [('trajectory', '.npz'), ('metrics', '.json')]:
                        output = ROOT/f"artifacts/formal/{record['kind']}_{record['configuration_id']}{suffix}"
                        current = current and output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() == record['input_hashes'][field]
                if not current: evidence[name]['status'] = 'STALE'
            if name == 'model_information_and_mathematics' and value:
                if not certificate_is_current(value): evidence[name]['status'] = 'STALE_OR_INCOMPLETE'
        verified = all(v['status'] == 'PASS' for v in evidence.values())
        report['verification_gates'] = evidence
        report['status'] = 'PASS' if verified else 'PENDING'
        report['decision'] = ('adopt_challenger' if report['economic_gate_pass'] else 'retain_incumbent') if verified else 'await_verification'
        report['adopted_configuration'] = (frozen['challenger'] if report['economic_gate_pass'] else frozen['incumbent']) if verified else None
    output = ROOT/'artifacts/model-adoption.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': report['status'], 'decision': report.get('decision'), 'pending': pending}, ensure_ascii=False))
    if report['status'] != 'PASS': raise SystemExit(2)


if __name__ == '__main__': main()
