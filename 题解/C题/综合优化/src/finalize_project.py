"""Freeze executed evidence. Acceptance depends on independent review + validator."""
from pathlib import Path
import json,hashlib,platform,sys
from run_comparison import ROOT,BASE,CANDIDATES,KINDS,dump

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    m=json.loads((ROOT/'modeling-manifest.json').read_text())
    ex=json.loads((ROOT/'artifacts/execution-annual.json').read_text())
    selection=json.loads((ROOT/'artifacts/selection.json').read_text())
    chosen={v['january_selected'] for v in selection.values()}
    assert len(chosen)==1,'Per-task selected models need explicit manifest aggregation if they differ'
    name=next(iter(chosen))
    m['project'].update(stage='handoff',status='in_progress')
    m['models']['selected']=name
    m['models']['additional_experiments']=[
        {'name':'common_saa_mpc','role':'late structural diagnostic; excluded from frozen six-expert selectors','record':'补充对照记录.md'},
        {'name':'common_sdp','role':'late structural diagnostic; excluded from frozen six-expert selectors','record':'补充对照记录.md'},
        {'name':'adaptive28','role':'past-only daily selection among the frozen six experts','record':'实验预声明.md'},
        {'name':'convex28','role':'late past-only daily convex aggregation; not an untouched external validation','record':'凸组合综合策略记录.md'}]
    m['models']['selection_rationale']={
        'objective_fit':'Actual planned, adjustment and fivefold emergency costs evaluated consistently',
        'constraint_fit':'Physical bounds, energy conservation, terminal reachability and causal contract releases',
        'data_fit':'January selection; historical residuals; incremental chronological replay on previously examined fixed data',
        'baseline':'Original baseline rerun with identical outputs; six controller combinations compared',
        'risks':['restricted strategy and information classes','historical distribution shift','daily6000 added policy',
                 'Q3 net amendment/refund interpretation','upper affine policy replaced by rolling lower controller'],
        'fallback_trigger':'Use original feasible policy if rolling historical comparison degrades; do not choose using current/future-day realized costs.'}
    m['models']['baseline'].update(status='completed',name='Original common-path SAA plus greedy',command=ex['command'],
        exit_code=0,runtime_seconds=sum(r['runtime_seconds'] for r in ex['results'] if r['candidate']=='baseline'),
        output='artifacts/baseline-metrics.json',metric_ids=list(KINDS),reason=None)
    env=ex['environment'];env['native_highs']='1.15.1';env['threads_per_native_highs_instance']=1
    m['execution'].update(status='completed',command=ex['command'],exit_code=ex['exit_code'],runtime_seconds=ex['runtime_seconds'],
        environment=env,seed=None,deterministic_reason=ex['deterministic_reason'],metric_ids=list(KINDS),
        figures=[p.relative_to(ROOT).as_posix() for p in (ROOT/'figures').glob('*') if p.suffix in ['.png','.svg']])
    annual=json.loads((ROOT/'artifacts/annual-validation.json').read_text())
    fals=json.loads((ROOT/'artifacts/falsification.json').read_text())
    safety=json.loads((ROOT/'artifacts/robustness.json').read_text())
    visual=json.loads((ROOT/'artifacts/visual-qa.json').read_text())
    wb=json.loads((ROOT/'artifacts/workbook-validation.json').read_text())
    for artifact in [annual,fals]:
        assert artifact['status']=='pass' and artifact['checks']
        assert all(c['status']=='pass' for c in artifact['checks'])
    assert safety['status']=='pass'
    assert visual['status']=='pass' and not visual['observed_issues']
    for path,digest in visual['inspected_image_hashes'].items():assert sha(ROOT/path)==digest
    checked={c['name'] for c in annual['checks']}
    assert {k+'_convex28' for k in KINDS}<=checked
    assert wb.get('checks') and all(c['status']=='pass' for c in wb['checks'])
    m['validation'].update(status='completed',checks=annual['checks']+fals['checks']+
        [{'name':'workbook_roundtrip','status':'pass','source':'artifacts/workbook-validation.json'},
         {'name':'visual_inspection','status':'pass','source':'artifacts/visual-qa.json'},
         {'name':'safety_projection_stress','status':'pass','source':'artifacts/robustness.json'}],
        sensitivity=['artifacts/grid-sensitivity.json'],robustness=['artifacts/robustness.json'],
        falsification=['artifacts/falsification.json','review/controller-small-checks.json'])
    findings_path=ROOT/'review/findings.json'
    if findings_path.is_file():
        findings=json.loads(findings_path.read_text())
        passed=findings.get('decision')=='pass' and not findings.get('unresolved') and findings.get('independent') is True
        if passed:
            reviewed=findings.get('reviewed_artifact_hashes',{})
            assert reviewed,'Final independent review must identify the actual reviewed artifact snapshot'
            for path,digest in reviewed.items():assert sha(ROOT/path)==digest,('Changed since review',path)
        m['review'].update(status='completed' if passed else 'pending',independent=findings.get('independent',False),
                           reviewer_id=findings.get('reviewer_id'))
    else:passed=False
    m['results'].update(handoff_file='综合建模计算交接.md')
    m['pending']=[] if passed else ['independent final review']
    m['project']['status']='complete' if passed else 'in_progress'
    # Snapshot copied input dependencies correspond byte-for-byte to externally
    # referenced parent cache/code, whose locations are documented explicitly.
    deps={}
    for relative,parent in [('inputs/prepared/data.npz',BASE/'artifacts/data.npz'),
                            ('inputs/prepared/forecasts.npz',BASE/'artifacts/forecasts.npz'),
                            ('inputs/baseline-code/forecasting.py',BASE/'src/forecasting.py'),
                            ('inputs/baseline-code/dispatch.py',BASE/'src/dispatch.py')]:
        assert sha(ROOT/relative)==sha(parent)
        deps[str(parent)]={'sha256':sha(parent),'project_snapshot':relative}
    files=[p for folder in ['src','artifacts','figures','计算结果','review'] for p in (ROOT/folder).rglob('*')
           if p.is_file() and p.suffix not in ['.pyc'] and p.name not in ['reproducibility.json','acceptance.json']]
    files +=[p for p in ROOT.glob('*.md')]+[p for p in ROOT.glob('*.sh')]
    outputs={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    repro={'command':ex['command'],'seed':None,'runtime_seconds':ex['runtime_seconds'],'environment':env,
           'deterministic_reason':ex['deterministic_reason'],'input_hashes':m['source']['input_hashes'],
           'output_hashes':outputs,'external_dependencies_with_verified_snapshots':deps,
           'source_note':'Grid logging names were corrected during annual execution; numerical annual branch unchanged. Alternative reduced affine kernel is not used for main trajectories.'}
    dump(ROOT/'artifacts/reproducibility.json',repro);dump(ROOT/'modeling-manifest.json',m)
    print(json.dumps({'status':m['project']['status'],'selected':name,'hashed_outputs':len(outputs)},ensure_ascii=False))

if __name__=='__main__':main()
