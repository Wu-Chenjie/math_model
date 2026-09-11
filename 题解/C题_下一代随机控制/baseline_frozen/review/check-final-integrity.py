"""Independent consistency checks for the frozen handoff evidence.

Hash verification is an integrity check, not a substitute for numerical review.
Final review/repro/acceptance are deliberately outside their own hash closure.
"""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
def read(p): return json.loads((ROOT / p).read_text())
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
def check_hashes(items):
    for name, expected in items.items():
        assert sha(name) == expected, name
    return len(items)

def main():
    checks = {}
    registry = read('artifacts/result-registry.json')['results']
    assert len({r['id'] for r in registry}) == len(registry)
    for row in registry:
        obj = read(row['source_artifact'])
        for part in row['source_path'].split('/')[1:]:
            part = part.replace('~1', '/').replace('~0', '~')
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        assert row['status'] == 'verified' and row['value'] == obj, row['id']
    checks['registry_exact_source_values'] = {'passed': True, 'records': len(registry)}
    visual = read('artifacts/visual-qa.json')
    assert visual['status'] == 'pass'
    checks['visual_hashes'] = {k: check_hashes(visual[k]) for k in
                              ['preview_hashes', 'figure_hashes', 'workbook_hashes']}
    wb = read('artifacts/workbook-validation.json')
    assert wb['execution']['exit_code'] == 0
    assert len(wb['checks']) == 5 and all(c['status'] == 'pass' for c in wb['checks'])
    checks['workbook_hashes'] = check_hashes({c['file']: c['sha256'] for c in wb['checks']})
    versions = read('artifacts/source-version-records.json')['v1']
    checks['executed_source_archive'] = check_hashes({versions['directory']+'/'+name: value
                                                     for name, value in versions['files'].items()})
    repro = read('artifacts/reproducibility.json')
    checks['input_hashes'] = check_hashes(repro['input_hashes'])
    # Reviewer reruns and final findings are refreshed by the author's final
    # freeze; all production and documentation hashes must already be stable.
    frozen = {n: h for n, h in repro['output_hashes'].items()
              if not n.startswith('review/') and n not in
              ['modeling-manifest.json', 'artifacts/reproducibility.json', 'artifacts/acceptance.json']}
    checks['frozen_production_outputs'] = check_hashes(frozen)
    production = read('review/production-audit.json')
    assert production['passed'] is True and production['passed_cases'] == 36
    assert not production['pending_cases'] and not production['failed_cases']
    supplement = read('review/final-supplement.json')
    assert all(v.get('passed') is True for v in supplement['checks'].values())
    checks['independent_visual_inspection'] = {
        'passed': True,
        'scope': 'Four final scientific PNGs, plus three representative workbook preview ranges; not every cell visually inspected.',
        'files': {p: sha(p) for p in [
            'figures/年度方法比较.png', 'figures/午夜库存轨迹.png',
            'figures/SDDP训练与库存价值.png', 'figures/预报发布消融.png',
            'artifacts/previews/result4-2-充放电量.png',
            'artifacts/previews/result3-调整购电量-6点.png',
            'artifacts/previews/result1-口径说明.png']},
        'observations': [
            'Four figures have readable axes/legends, no visible clipping; close annual curves are accompanied by exact numeric differences in the handoff.',
            'Battery dates are visible and grouped per six rows; the six-hour revision view has correct ten-minute interval headers.',
            'Workbook SOC in kWh denotes energy inventory, as explicitly distinguished from the normalized SOC ratio in the model document.',
            'Workbook notes state the time, settlement, terminal, information and optimality conventions.']}
    result = {'schema_version': 1, 'reviewer_id': '/root/independent_review', 'independent': True,
              'passed': True, 'scope': 'frozen_evidence_consistency_and_sampled_visual_review',
              'checks': checks, 'audit_source_sha256': sha('review/check-final-integrity.py')}
    (ROOT/'review/final-integrity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'passed': True, 'registry_records': len(registry), 'production_hashes': len(frozen)}))

if __name__ == '__main__': main()
