"""Run the independent physical/accounting auditor over every frozen candidate."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT/'review/check_nextgen_physics.py'
spec = importlib.util.spec_from_file_location('independent_physics', AUDITOR)
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main(phase):
    start = time.perf_counter()
    freeze_path = ROOT/'artifacts/frozen-development-selection.json'
    frozen = json.loads(freeze_path.read_text())
    data_path = ROOT/'artifacts/data.npz'; data = dict(np.load(data_path, allow_pickle=False))
    expected_sources = {Path(k).name: v for k, v in frozen['source_hashes'].items()}
    pending = []; failures = []; records = []
    for config in frozen['annual_configurations']:
        identity = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
        for kind in ('q2', 'q3', 'q4_2', 'q4_3'):
            stem = ROOT/f'artifacts/{phase}/{kind}_{identity}'
            npz, js = stem.with_suffix('.npz'), stem.with_suffix('.json')
            if not npz.exists() or not js.exists():
                pending.append(str(stem.relative_to(ROOT))); continue
            with np.load(npz, allow_pickle=False) as f: arrays = dict(f)
            metrics = json.loads(js.read_text())
            result = audit.audit_arrays(data, arrays, metrics, development=phase=='development')
            mismatches = [k for k, v in config.items() if metrics['configuration'].get(k) != v]
            if mismatches: result['errors'].append('configuration_mismatch:'+','.join(mismatches))
            if metrics['source_hashes'] != expected_sources: result['errors'].append('frozen_source_mismatch')
            if metrics['kind'] != kind: result['errors'].append('kind_mismatch')
            result['passed'] = not result['errors']
            result['status'] = 'PASS' if result['passed'] else 'FAIL'
            result['input_hashes'] = {'trajectory': sha(npz), 'metrics': sha(js), 'data': sha(data_path)}
            result['independent_validator_sha256'] = sha(AUDITOR)
            output = ROOT/f'review/{phase}-physics/{kind}_{identity}.json'; output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
            records.append({'kind': kind, 'configuration_id': identity, 'status': result['status'],
                            'checks': len(result['checks']), 'report': str(output.relative_to(ROOT)),
                            'report_sha256': sha(output), 'input_hashes': result['input_hashes']})
            if not result['passed']: failures.append({'kind': kind, 'configuration_id': identity, 'errors': result['errors']})
    status = 'FAIL' if failures else 'PENDING' if pending else 'PASS'
    report = {'status': status, 'records': records, 'failures': failures, 'pending': pending,
              'frozen_selection_sha256': sha(freeze_path), 'auditor_sha256': sha(AUDITOR),
              'execution': {'command': sys.argv, 'runtime_seconds': time.perf_counter()-start},
              'scope': 'Independent equations and actual bill, output consistency and recorded contract permissions. Behavioral information causality requires separate mutation tests.'}
    (ROOT/f'artifacts/{phase}-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': status, 'completed': len(records), 'pending': len(pending), 'failures': failures}, ensure_ascii=False))
    raise SystemExit(0 if status == 'PASS' else 1 if failures else 2)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--phase', choices=['development', 'formal'], default='formal')
    main(p.parse_args().phase)
