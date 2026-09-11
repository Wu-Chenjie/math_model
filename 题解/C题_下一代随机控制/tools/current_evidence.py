"""Read-only freshness and exact-coverage checks for downstream result consumers."""
from pathlib import Path
import hashlib,json
from collections import Counter
KINDS=('q2','q3','q4_2','q4_3')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def require_baseline_current(root,value=None):
    root=Path(root);value=read(root/'artifacts/baseline-reproduction-check.json') if value is None else value
    assert value.get('status')=='PASS' and value.get('independent') is True
    cases=value.get('cases',[]);assert cases and all(c.get('status')=='PASS' for c in cases)
    assert value.get('counts')==dict(Counter(c['status'] for c in cases))
    assert value.get('execution',{}).get('checker_sha256')==sha(root/'tools/check_baseline_reproduction.py')
    frozen=read(root/'artifacts/baseline-freeze.json')['file_hashes'];assert frozen
    evidence=value.get('evidence_hashes',{});assert evidence
    for path,digest in frozen.items():assert evidence.get('baseline_frozen/'+path)==digest
    for path,digest in evidence.items():assert sha(root/path)==digest, 'Baseline evidence changed: '+path
    required={'frozen_snapshot_integrity','unchanged:src','unchanged:inputs','unchanged:vendor','rerun_independent_production_audit','rerun_workbook_readback'}
    assert required.issubset({c['name'] for c in cases}), 'Baseline gate coverage incomplete'
    return value

def require_formal_current(root,value=None):
    root=Path(root);freeze_path=root/'artifacts/frozen-development-selection.json';frozen=read(freeze_path)
    assert frozen.get('status')=='frozen' and frozen.get('annual_configurations'), 'Missing frozen configuration register'
    value=read(root/'artifacts/formal-validation.json') if value is None else value
    assert value.get('status')=='PASS' and not value.get('pending') and not value.get('failures')
    assert value.get('frozen_selection_sha256')==sha(freeze_path), 'Formal validation uses stale freeze'
    expected={(kind,hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:16]) for c in frozen['annual_configurations'] for kind in KINDS}
    records=value.get('records',[]);found=[(r['kind'],r['configuration_id']) for r in records]
    assert len(found)==len(expected) and set(found)==expected, 'Formal validation lacks exact, unique coverage'
    data_hash=sha(root/'artifacts/data.npz');auditor_hash=sha(root/'review/check_nextgen_physics.py')
    assert value.get('auditor_sha256')==auditor_hash, 'Formal validator changed'
    for r in records:
        assert r.get('status')=='PASS' and r.get('checks',0)>0
        path=root/r['report'];assert sha(path)==r['report_sha256'], 'Individual report changed'
        detail=read(path);assert detail.get('status')=='PASS' and detail.get('passed') is True and not detail.get('errors')
        checks=detail.get('checks',{});assert len(checks)==r['checks'] and all(c.get('passed') is True for c in checks.values())
        assert detail.get('independent_validator_sha256')==auditor_hash
        assert detail.get('input_hashes')==r['input_hashes'] and r['input_hashes'].get('data')==data_hash
        for field,suffix in [('trajectory','.npz'),('metrics','.json')]:
            path=root/f"artifacts/formal/{r['kind']}_{r['configuration_id']}{suffix}"
            assert sha(path)==r['input_hashes'][field], 'Formal output changed after validation: '+str(path)
    return value

def require_paper_sources_current(root,proof=None):
    root=Path(root);proof=read(root/'artifacts/paper-results.json') if proof is None else proof
    assert proof.get('status')=='verified' and proof.get('source_hashes'), 'Paper has no bound source evidence'
    for path,digest in proof['source_hashes'].items():assert sha(root/path)==digest,'Paper source changed: '+path
    execution=read(root/'artifacts/paper-results-execution.json')
    assert execution.get('status')=='complete' and execution.get('exit_code')==0
    assert execution.get('source_hashes')==proof['source_hashes']
    expected={f'paper/generated/{name}.tex' for name in ('abstract','results','discussion','appendix')}
    generated=execution.get('generated',{});assert set(generated)==expected,'Generated paper sections not bound completely'
    for path,digest in generated.items():assert sha(root/path)==digest,'Generated paper section changed: '+path
    require_formal_current(root)
    require_baseline_current(root)
    require_figures_current(root)
    return proof

def require_figures_current(root):
    root=Path(root);record=read(root/'artifacts/figure-execution.json')
    assert record.get('status')=='computed' and record.get('execution',{}).get('exit_code')==0
    assert record.get('source_hashes') and record.get('outputs')
    for path,digest in {**record['source_hashes'],**record['outputs']}.items():assert sha(root/path)==digest, 'Figure evidence changed: '+path
    expected={f'figures/{name}.{ext}' for name in ('新旧模型结构','挑战模型逐日累计配对差','全年节省与配对区间','跨日库存与日内范围','固定时域收益与计算量') for ext in ('png','svg')}
    assert set(record['outputs'])==expected, 'Scientific figure set incomplete'
    return record
