"""Execute independent executable reviews and bind their evidence to current files."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TESTS = [
    ('review/check_nextgen_scenarios.py', 'review/nextgen-scenario-checks.json'),
    ('review/check_nextgen_control.py', 'review/nextgen-control-checks.json'),
    ('review/check_origin_math.py', 'review/origin-math-checks.json'),
    ('review/check_experiment_protocol.py', 'review/protocol-comparison-checks.json'),
    ('review/check_adoption_matched_M1.py', 'review/adoption-matched-M1-checks.json'),
    ('review/check_certificate_guards.py', 'review/certificate-guard-checks.json'),
    ('review/check_output_pipeline.py', 'review/output-pipeline-checks.json'),
    ('review/check_finalization_guards.py', 'review/finalization-guard-checks.json'),
    ('review/check_output_finisher.py', 'review/output-finisher-checks.json'),
    ('review/test_nextgen_physics.py', None),
]


def hashes():
    paths = list((ROOT/'src').glob('*.py'))+list((ROOT/'tools').glob('*.py'))
    paths += [ROOT/p for p, _ in TESTS]+[ROOT/'review/check_nextgen_physics.py',
        ROOT/'artifacts/data.npz', ROOT/'artifacts/forecast-selection.json', ROOT/'artifacts/experiment-protocol.json']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def certificate_is_current(value):
    if value.get('status') != 'PASS' or value.get('bound_hashes') != hashes(): return False
    records = value.get('records', [])
    if len(records) != len(TESTS): return False
    for record, (script, expected_report) in zip(records, TESTS):
        if record.get('command', [None])[-1] != script or record.get('exit_code') != 0: return False
        log = ROOT/record.get('log', '__missing__')
        if not log.is_file() or hashlib.sha256(log.read_bytes()).hexdigest() != record.get('log_sha256'): return False
        if expected_report:
            path = ROOT/expected_report
            if record.get('report') != expected_report or not path.is_file(): return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != record.get('report_sha256'): return False
            result = json.loads(path.read_text())
            if result.get('status') not in ('PASS', 'PASS_WITHIN_SCOPE') or result.get('independent') is not True: return False
    return True


def main():
    bound = hashes(); records = []; started = time.perf_counter()
    logs = ROOT/'artifacts/model-check-logs'; logs.mkdir(parents=True, exist_ok=True)
    for script, report in TESTS:
        command = [sys.executable, script]; before = time.perf_counter()
        log_path = logs/(Path(script).stem+'.log')
        with log_path.open('w') as log:
            proc = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        item = {'command': command, 'exit_code': proc.returncode, 'runtime_seconds': time.perf_counter()-before,
                'log': str(log_path.relative_to(ROOT)), 'log_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest()}
        if report and (ROOT/report).exists():
            item.update(report=report, report_sha256=hashlib.sha256((ROOT/report).read_bytes()).hexdigest())
            value = json.loads((ROOT/report).read_text())
            if value.get('status') not in ('PASS', 'PASS_WITHIN_SCOPE') or value.get('independent') is not True: item['exit_code'] = 1
        elif report:
            item['exit_code'] = 1; item['error'] = 'Required independent report missing'
        records.append(item); print(json.dumps(item, ensure_ascii=False), flush=True)
    report = {'status': 'PASS' if bound == hashes() and all(r['exit_code'] == 0 for r in records) else 'FAIL',
              'bound_hashes': bound, 'records': records, 'runtime_seconds': time.perf_counter()-started,
              'scope': 'Independent executable information, small mathematical/control, protocol and physical-falsification checks. No annual-cost or paper-layout acceptance is implied.'}
    if not certificate_is_current(report): report['status'] = 'FAIL'
    (ROOT/'artifacts/model-check-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__': main()
