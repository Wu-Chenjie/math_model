"""Close the artifact ledger only after executed and independently reviewed gates.

This tool does not supply reviewer decisions or visual inspection. Those records
must be authored after examining the completed artifacts and bind current hashes.
"""
from pathlib import Path
import hashlib
import json
import platform
import shlex
import sys
import subprocess
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from certify_model_checks import certificate_is_current
from current_evidence import require_formal_current, require_paper_sources_current, require_baseline_current


def read(relative):
    return json.loads((ROOT/relative).read_text())


def sha(relative):
    return hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()


def write(relative, value):
    path=ROOT/relative;temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n');temporary.replace(path)


def main():
    baseline=read('artifacts/baseline-reproduction-check.json')
    formal=read('artifacts/formal-validation.json')
    model=read('artifacts/model-check-validation.json')
    adoption=read('artifacts/model-adoption.json')
    comparisons=read('artifacts/incremental-comparisons.json')
    paper=read('artifacts/paper-results.json')
    build=read('artifacts/pdf-build.json')
    automated=read('review/pdf-automated-qa.json')
    visual=read('review/pdf-visual-review.json')
    workbooks=read('artifacts/workbook-validation.json')
    for name,value in [('baseline',baseline),('formal',formal),('model',model),('adoption',adoption),('automated PDF',automated),('visual PDF',visual)]:
        assert value['status']=='PASS', name+' has not passed'
    assert certificate_is_current(model), 'Independent model certificate is stale'
    require_baseline_current(ROOT,baseline)
    assert comparisons['status']=='complete' and paper['status']=='verified'
    require_formal_current(ROOT,formal)
    require_paper_sources_current(ROOT,paper)
    assert workbooks.get('execution',{}).get('exit_code')==0, 'Workbook readback has not passed'
    assert len(workbooks.get('checks',[]))==5 and all(c.get('status')=='pass' for c in workbooks['checks']), 'Five workbook readbacks required'
    expected_workbooks={f'计算结果/{name}.xlsx' for name in ('result1','result2','result3','result4-2','result4-3')}
    assert {c['file'] for c in workbooks['checks']}==expected_workbooks, 'Exact five unique workbooks required'
    for check in workbooks['checks']:assert sha(check['file'])==check['sha256'], 'Workbook changed after readback'
    workbook_sources=workbooks.get('source_hashes',{})
    required_workbook_sources={'artifacts/workbook-payload.json','artifacts/export-selection.json','artifacts/model-adoption.json','artifacts/data.npz',
        *[f'artifacts/{kind}.{ext}' for kind in ('q1','q2','q3','q4_2','q4_3') for ext in ('npz','json')]}
    assert required_workbook_sources.issubset(workbook_sources), 'Workbook readback sources not bound'
    for path,digest in workbook_sources.items():assert sha(path)==digest, 'Workbook source changed: '+path
    assert build.get('exit_code')==0, 'PDF compilation failed'
    pdf=build['pdf'];assert sha(pdf)==build['pdf_sha256']==automated['pdf_sha256']==visual['pdf_sha256']
    assert visual.get('unresolved')==[], 'Unresolved visual defects'
    rendered=build['rendered_pages']
    expected_sources={'paper/main.tex',*[f'paper/generated/{n}.tex' for n in ('abstract','results','discussion','appendix')]}
    assert set(build['source_hashes'])==expected_sources, 'Complete current TeX source set required'
    pages=automated.get('pages',[])
    assert pages and [p['page'] for p in pages]==list(range(1,len(pages)+1))
    info=subprocess.run(['/opt/homebrew/bin/pdfinfo',str(ROOT/pdf)],capture_output=True,text=True,check=True)
    match=re.search(r'^Pages:\s+(\d+)',info.stdout,re.M)
    assert match and int(match[1])==len(pages), 'Actual PDF page count differs from QA record'
    assert rendered and len(rendered)==len(pages), 'Nonempty render for every checked PDF page required'
    actual_rendered={str(p.relative_to(ROOT)) for p in (ROOT/'tmp/pdfs/final/pages').glob('page-*.png')}
    assert set(rendered)==actual_rendered, 'Rendered page file set changed'
    assert sorted(int(Path(p).stem.split('-')[-1]) for p in rendered)==list(range(1,len(pages)+1)), 'Rendered page numbers missing or duplicated'
    assert visual.get('inspected_pages')==rendered, 'Every current rendered page must be visually inspected'
    expected_figures={p:d for p,d in read('artifacts/figure-execution.json')['outputs'].items() if p.endswith('.png')}
    assert build.get('figure_hashes')==expected_figures, 'PDF was compiled with different figures'
    for path,digest in {**build['source_hashes'],**expected_figures,**rendered}.items():assert sha(path)==digest,path
    selection='artifacts/frozen-development-selection.json'
    assert sha(selection)==adoption['selection_sha256']==comparisons['selection_sha256']==formal['frozen_selection_sha256']
    required_bindings=['paper/main.tex',pdf,'artifacts/paper-results.json',selection,
                       'artifacts/formal-validation.json','artifacts/model-adoption.json',
                       'src/nextgen_scenarios.py','src/nextgen_control.py','src/nextgen_run.py']
    reviewers=[]
    for role in ('math','code','judge'):
        path=f'review/final-{role}-review.json';report=read(path)
        assert report.get('independent') is True and report.get('decision')=='pass', path
        assert report.get('reviewer_id') and report.get('unresolved')==[], path
        for artifact in required_bindings:
            assert report.get('bound_hashes',{}).get(artifact)==sha(artifact),path+' stale: '+artifact
        reviewers.append({'role':role,'reviewer_id':report['reviewer_id'],'report':path,'sha256':sha(path)})
    assert len({r['reviewer_id'] for r in reviewers})==3, 'Three distinct final reviewers required'
    pipeline=read('artifacts/pipeline-execution.json')
    assert pipeline['status']=='complete'
    record=next(r for r in pipeline['records'] if r['stage']=='registered_334day_replays')
    assert record['exit_code']==0
    execution=read('artifacts/execution-formal.json');assert execution['status']=='complete'
    baseline_execution=read('artifacts/baseline-reproduction-execution.json')
    assert baseline_execution.get('records') and all(r['exit_code']==0 for r in baseline_execution['records'])
    executed_scripts={r['command'][1] for r in baseline_execution['records']}
    assert {'src/prepare_data.py','src/run.py','src/validate.py','src/check_terminal.py','src/select_model.py','review/check-production.py','src/finish.py','src/export_results.py'}.issubset(executed_scripts)
    for path,digest in paper['source_hashes'].items():assert sha(path)==digest,'Paper source changed: '+path
    command=shlex.join(record['command']);metrics=read('artifacts/metrics.json')
    baseline_metrics=read('artifacts/baseline-metrics.json');assert set(metrics)==set(baseline_metrics)
    manifest=read('modeling-manifest.json');config=paper['selected_configuration']
    inputs=manifest['source']['input_hashes']
    for path,digest in inputs.items():assert sha(path)==digest,path
    selected=('legacy_affine_M0' if adoption['decision']=='retain_incumbent' else
              'conditional_affine_M1' if config['lower']=='M1' else 'conditional_affine_M0')
    figures=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'figures').glob('*.png'))]
    manifest['project'].update(stage='completed',status='complete')
    manifest['models']['selected']=selected
    manifest['models']['baseline'].update(status='completed',command='python3 tools/reproduce_baseline.py',exit_code=0,
        runtime_seconds=baseline_execution['elapsed_seconds'],metric_ids=list(metrics))
    environment={'python':sys.version,'platform':platform.platform(),
        'execution_record':'artifacts/pipeline-execution.json','frozen_source_record':selection,
        'runtime_scope':'Wall time of the full registered annual replay command; simultaneous local processes may affect timing.'}
    manifest['execution'].update(status='completed',command=command,exit_code=0,runtime_seconds=record['runtime_seconds'],
        environment=environment,seed=20260911,deterministic_reason='Optimization, scenario selection and regression are deterministic; the seed controls moving-block bootstrap.',
        metric_ids=list(metrics),figures=figures)
    checks=[('baseline_reproduction','artifacts/baseline-reproduction-check.json'),
            ('independent_physical_billing_and_permissions','artifacts/formal-validation.json'),
            ('independent_model_and_information_checks','artifacts/model-check-validation.json'),
            ('frozen_adoption_gate','artifacts/model-adoption.json'),
            ('workbook_readback','artifacts/workbook-validation.json'),
            ('pdf_automated','review/pdf-automated-qa.json'),('pdf_visual','review/pdf-visual-review.json')]
    manifest['validation'].update(status='completed',checks=[{'name':n,'status':'pass','evidence':p} for n,p in checks],
        sensitivity=[{'evidence':'artifacts/incremental-comparisons.json','scope':'All registered horizon, scenario, forecast, grid, state and tail comparisons, including negative results.'}],
        robustness=[{'evidence':'artifacts/incremental-comparisons.json','scope':'Paired daily costs, two calendar subperiods and shared 7-day moving-block bootstrap; single-year diagnostic only.'}],
        falsification=[{'evidence':'artifacts/model-check-validation.json','scope':'Hidden-future perturbations, explicit small LP comparisons, physical mutation fixtures, stale-evidence guards.'}])
    combined_id='; '.join(r['reviewer_id'] for r in reviewers)
    findings={'schema_version':1,'reviewer_id':combined_id,'independent':True,'decision':'pass',
          'unresolved':[],'reports':reviewers,'note':'Aggregate of three separately authored, hash-bound reviews; this tool does not generate their decisions.'}
    manifest['review'].update(status='completed',independent=True,reviewer_id=combined_id)
    manifest['pending']=[]
    outputs=['artifacts/data-audit.json','artifacts/baseline-metrics.json','artifacts/metrics.json',
        'artifacts/result-registry.json','paper/result-claims.json','artifacts/paper-results.json',pdf,
        *figures,*[p for _,p in checks]]
    output_hashes={p:sha(p) for p in outputs}
    output_hashes['review/findings.json']=hashlib.sha256((json.dumps(findings,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
    reproducibility={'schema_version':1,'command':command,'seed':20260911,
        'deterministic_reason':manifest['execution']['deterministic_reason'],'runtime':environment,
        'input_hashes':inputs,'output_hashes':output_hashes,
        'one_key_command':'./复现.sh --workers 8','fresh_annual_replay_command':'./复现.sh --workers 8 --rerun-year',
        'finalized_utc':datetime.now(timezone.utc).isoformat()}
    write('review/findings.json',findings)
    write('artifacts/reproducibility.json',reproducibility)
    write('modeling-manifest.json',manifest)
    print('Artifact ledger closed from executed evidence. Run the skill project validator next.')


if __name__=='__main__':main()
