#!/usr/bin/env python3
"""Isolated falsification of pre-review gates; never creates final review decisions."""
from pathlib import Path
import tempfile,sys,json,hashlib,base64
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import finalize_project as finalizer
import build_paper as builder

class ReviewBoundary(Exception):pass
class CompileBoundary(Exception):pass

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(root,path,value):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(value,bytes):p.write_bytes(value)
    else:p.write_text(json.dumps(value) if isinstance(value,(dict,list)) else value)
    return sha(p)
def get(root,path):return json.loads((root/path).read_text())
def edit(root,path,fn):
    value=get(root,path);fn(value);put(root,path,value)

def pdf_bytes():
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents 4 0 R >>',
             b'<< /Length 0 >>\nstream\n\nendstream']
    out=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(out));out+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(out);out+=b'xref\n0 5\n0000000000 65535 f \n'
    for offset in offsets[1:]:out+=f'{offset:010d} 00000 n \n'.encode()
    out+=f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode();return out

def setup(root):
    config={};ident=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
    freeze=put(root,'artifacts/frozen-development-selection.json',{'status':'frozen','annual_configurations':[config]})
    put(root,'artifacts/model-check-validation.json',{'status':'PASS'})
    checker=put(root,'tools/check_baseline_reproduction.py','# inert baseline comparator fixture')
    frozen_digest=put(root,'baseline_frozen/src/run.py','# frozen code fixture')
    rerun_digest=put(root,'../C题_下一代基线复现/src/run.py','# frozen code fixture')
    put(root,'artifacts/baseline-freeze.json',{'file_hashes':{'src/run.py':frozen_digest}})
    gates=('frozen_snapshot_integrity','unchanged:src','unchanged:inputs','unchanged:vendor','rerun_independent_production_audit','rerun_workbook_readback')
    put(root,'artifacts/baseline-reproduction-check.json',{'status':'PASS','independent':True,
        'cases':[{'name':name,'status':'PASS'} for name in gates],'counts':{'PASS':len(gates)},
        'execution':{'checker_sha256':checker},'evidence_hashes':{'baseline_frozen/src/run.py':frozen_digest,
            '../C题_下一代基线复现/src/run.py':rerun_digest}})
    data=put(root,'artifacts/data.npz','inert source bytes');auditor=put(root,'review/check_nextgen_physics.py','# inert validator fixture\n')
    records=[]
    for kind in ('q2','q3','q4_2','q4_3'):
        stem=f'artifacts/formal/{kind}_{ident}'
        hashes={'trajectory':put(root,stem+'.npz','inert trajectory bytes '+kind),'metrics':put(root,stem+'.json',{'kind':kind}),'data':data}
        report=f'review/formal-physics/{kind}_{ident}.json'
        digest=put(root,report,{'status':'PASS','passed':True,'errors':[],
            'checks':{'fixture_check':{'passed':True}},'input_hashes':hashes,'independent_validator_sha256':auditor})
        records.append({'kind':kind,'configuration_id':ident,'status':'PASS','checks':1,'report':report,'report_sha256':digest,'input_hashes':hashes})
    put(root,'artifacts/formal-validation.json',{'status':'PASS','pending':[],'failures':[],
        'frozen_selection_sha256':freeze,'auditor_sha256':auditor,'records':records})
    put(root,'artifacts/model-adoption.json',{'status':'PASS','selection_sha256':freeze})
    put(root,'artifacts/incremental-comparisons.json',{'status':'complete','selection_sha256':freeze})
    pdffile='output/pdf/fixture.pdf';pdfsha=put(root,pdffile,pdf_bytes())
    tex={'paper/main.tex':put(root,'paper/main.tex','text')}
    for name in ('abstract','results','discussion','appendix'):
        path=f'paper/generated/{name}.tex';tex[path]=put(root,path,'text '+name)
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==')
    render={'tmp/pdfs/final/pages/page-1.png':put(root,'tmp/pdfs/final/pages/page-1.png',png)}
    outputs={}
    for name in ('新旧模型结构','挑战模型逐日累计配对差','全年节省与配对区间','跨日库存与日内范围','固定时域收益与计算量'):
        for ext in ('png','svg'):
            path=f'figures/{name}.{ext}';outputs[path]=put(root,path,png if ext=='png' else '<svg/>')
    source={'artifacts/source.json':put(root,'artifacts/source.json',{'fixture':1})}
    put(root,'artifacts/figure-execution.json',{'status':'computed','execution':{'exit_code':0},'source_hashes':source,'outputs':outputs})
    source.update({'artifacts/formal-validation.json':sha(root/'artifacts/formal-validation.json'),'artifacts/data.npz':data})
    put(root,'artifacts/paper-results.json',{'status':'verified','source_hashes':source})
    put(root,'artifacts/paper-results-execution.json',{'status':'complete','exit_code':0,'source_hashes':source,
        'generated':{p:h for p,h in tex.items() if '/generated/' in p}})
    checks=[]
    for name in ('result1','result2','result3','result4-2','result4-3'):
        path=f'计算结果/{name}.xlsx';checks.append({'file':path,'status':'pass','sha256':put(root,path,'inert workbook')})
    put(root,'artifacts/pdf-build.json',{'pdf':pdffile,'pdf_sha256':pdfsha,'rendered_pages':render,'source_hashes':tex,
        'figure_hashes':{p:h for p,h in outputs.items() if p.endswith('.png')},'exit_code':0})
    put(root,'review/pdf-automated-qa.json',{'status':'PASS','pdf_sha256':pdfsha,'pages':[{'page':1}]})
    put(root,'review/pdf-visual-review.json',{'status':'PASS','pdf_sha256':pdfsha,'unresolved':[],'inspected_pages':render})
    workbook_sources={
        'artifacts/workbook-payload.json':put(root,'artifacts/workbook-payload.json',{'fixture':1}),
        'artifacts/export-selection.json':put(root,'artifacts/export-selection.json',{'fixture':1}),
        'artifacts/model-adoption.json':sha(root/'artifacts/model-adoption.json'),'artifacts/data.npz':data}
    for kind in ('q1','q2','q3','q4_2','q4_3'):
        for ext in ('npz','json'):
            source=f'../C题_下一代基线复现/artifacts/q1.{ext}' if kind=='q1' else f'artifacts/formal/{kind}_{ident}.{ext}'
            if kind=='q1':put(root,source,'inert q1 bytes')
            alias=f'artifacts/{kind}.{ext}'
            workbook_sources[alias]=put(root,alias,(root/source).read_bytes());workbook_sources[source]=sha(root/source)
    put(root,'artifacts/workbook-validation.json',{'execution':{'exit_code':0},'checks':checks,'source_hashes':workbook_sources})
    return ident

def mutate(root,case,ident):
    if case=='control':return
    if case=='duplicate_workbooks':edit(root,'artifacts/workbook-validation.json',lambda x:x.update(checks=[x['checks'][0]]*5))
    elif case=='empty_rendered_pages':
        edit(root,'artifacts/pdf-build.json',lambda x:x.update(rendered_pages={}))
        edit(root,'review/pdf-visual-review.json',lambda x:x.update(inspected_pages={}))
    elif case=='missing_tex_bindings':edit(root,'artifacts/pdf-build.json',lambda x:x.update(source_hashes={}))
    elif case=='failed_build':edit(root,'artifacts/pdf-build.json',lambda x:x.update(exit_code=1))
    elif case=='baseline_status_shell':put(root,'artifacts/baseline-reproduction-check.json',{'status':'PASS'})
    elif case=='baseline_empty_cases':edit(root,'artifacts/baseline-reproduction-check.json',lambda x:x.update(cases=[],counts={}))
    elif case=='baseline_missing_required_gate':
        edit(root,'artifacts/baseline-reproduction-check.json',lambda x:(x['cases'].pop(),x.update(counts={'PASS':5})))
    elif case=='baseline_empty_evidence':edit(root,'artifacts/baseline-reproduction-check.json',lambda x:x.update(evidence_hashes={}))
    elif case=='baseline_wrong_counts':edit(root,'artifacts/baseline-reproduction-check.json',lambda x:x.update(counts={'PASS':99}))
    elif case=='stale_baseline_checker':put(root,'tools/check_baseline_reproduction.py','# changed comparator')
    elif case=='stale_baseline_frozen':put(root,'baseline_frozen/src/run.py','# changed frozen code')
    elif case=='stale_baseline_rerun':put(root,'../C题_下一代基线复现/src/run.py','# changed replay code')
    elif case=='workbook_missing_source_bindings':edit(root,'artifacts/workbook-validation.json',lambda x:x.update(source_hashes={}))
    elif case=='workbook_changed_payload':put(root,'artifacts/workbook-payload.json',{'fixture':2})
    elif case=='workbook_changed_alias':put(root,'artifacts/q2.npz','changed alias')
    elif case=='workbook_changed_q1_source':put(root,'../C题_下一代基线复现/artifacts/q1.npz','changed q1 source')
    elif case=='stale_formal_trajectory':put(root,f'artifacts/formal/q2_{ident}.npz','changed after validation')
    elif case=='stale_formal_metrics':put(root,f'artifacts/formal/q2_{ident}.json',{'changed':1})
    elif case=='stale_formal_data':put(root,'artifacts/data.npz','changed data')
    elif case=='stale_formal_auditor':put(root,'review/check_nextgen_physics.py','# changed validator')
    elif case=='stale_formal_report':edit(root,f'review/formal-physics/q2_{ident}.json',lambda x:x.update(errors=['changed']))
    elif case=='failed_formal_subcheck':
        path=f'review/formal-physics/q2_{ident}.json';edit(root,path,lambda x:x['checks']['fixture_check'].update(passed=False))
        edit(root,'artifacts/formal-validation.json',lambda x:x['records'][0].update(report_sha256=sha(root/path)))
    elif case=='missing_formal_coverage':edit(root,'artifacts/formal-validation.json',lambda x:x['records'].pop())
    elif case=='duplicate_formal_coverage':edit(root,'artifacts/formal-validation.json',lambda x:x['records'].__setitem__(1,x['records'][0]))
    elif case=='stale_paper_source':put(root,'artifacts/source.json',{'fixture':2})
    elif case=='changed_generated_tex':put(root,'paper/generated/abstract.tex','changed generated text')
    elif case=='changed_figure':put(root,'figures/新旧模型结构.png',b'changed png')
    elif case=='wrong_figure_build_binding':edit(root,'artifacts/pdf-build.json',lambda x:x.update(figure_hashes={}))
    elif case=='missing_figure_output':edit(root,'artifacts/figure-execution.json',lambda x:x['outputs'].pop('figures/新旧模型结构.svg'))
    elif case=='wrong_pdf_pagecount':edit(root,'review/pdf-automated-qa.json',lambda x:x.update(pages=[{'page':1},{'page':2}]))
    elif case=='nonconsecutive_qa_pages':edit(root,'review/pdf-automated-qa.json',lambda x:x.update(pages=[{'page':2}]))
    elif case=='unregistered_render_page':put(root,'tmp/pdfs/final/pages/page-2.png',b'extra render')
    else:raise ValueError(case)

def finalization_case(case):
    old=finalizer.ROOT,finalizer.read,finalizer.certificate_is_current
    try:
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'project';root.mkdir();ident=setup(root);mutate(root,case,ident);finalizer.ROOT=root
            # Only the certificate authenticator is isolated. Formal freshness is real.
            finalizer.certificate_is_current=lambda _:True
            def guarded_read(path):
                if path.startswith('review/final-'):raise ReviewBoundary
                return old[1](path)
            finalizer.read=guarded_read
            try:finalizer.main();raise AssertionError('Must never reach successful finalization')
            except ReviewBoundary:return {'case':case,'pre_review_gate_accepted':True}
            except (AssertionError,KeyError,FileNotFoundError,ValueError) as error:
                return {'case':case,'pre_review_gate_accepted':False,'rejection':str(error)}
    finally:finalizer.ROOT,finalizer.read,finalizer.certificate_is_current=old

def compilation_case(case):
    old=builder.ROOT,builder.subprocess.run
    try:
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'project';root.mkdir();ident=setup(root);mutate(root,case,ident);builder.ROOT=root
            def stop(*a,**k):raise CompileBoundary
            builder.subprocess.run=stop
            try:builder.main();raise AssertionError('Must never finish compilation')
            except CompileBoundary:return {'case':'compile_'+case,'compile_dispatched':True}
            except (AssertionError,KeyError,FileNotFoundError,ValueError) as error:
                return {'case':'compile_'+case,'compile_dispatched':False,'rejection':str(error)}
    finally:builder.ROOT,builder.subprocess.run=old

def run():
    names=('control','baseline_status_shell','baseline_empty_cases','baseline_missing_required_gate','baseline_empty_evidence','baseline_wrong_counts','stale_baseline_checker','stale_baseline_frozen','stale_baseline_rerun','workbook_missing_source_bindings','workbook_changed_payload','workbook_changed_alias','workbook_changed_q1_source','duplicate_workbooks','empty_rendered_pages','missing_tex_bindings','stale_formal_trajectory',
        'stale_formal_metrics','stale_formal_data','stale_formal_auditor','stale_formal_report','failed_formal_subcheck',
        'missing_formal_coverage','duplicate_formal_coverage','failed_build','stale_paper_source','changed_generated_tex',
        'changed_figure','wrong_figure_build_binding','missing_figure_output','wrong_pdf_pagecount','nonconsecutive_qa_pages','unregistered_render_page')
    cases=[finalization_case(case) for case in names]
    cases.extend(compilation_case(case) for case in ('control','baseline_status_shell','stale_baseline_frozen','stale_baseline_rerun','stale_paper_source','changed_generated_tex','changed_figure','stale_formal_trajectory'))
    issues=[]
    for c in cases:
        accepted=c.get('pre_review_gate_accepted',c.get('compile_dispatched'))
        if accepted!=(c['case'] in ('control','compile_control')):issues.append(c['case'])
    result={'status':'CHANGES_REQUESTED' if issues else 'PASS_WITHIN_SCOPE','independent':True,'reviewer_id':'/root/upgrade_code_review',
        'scope':'Temporary records with exact four-task coverage, inert hashed ledger payloads and a real one-page PDF. Baseline/formal helpers and pdfinfo run unmodified; only model certificate authenticator is isolated. Both legal controls must reach hard boundaries. No final review file/decision, optimizer or real compiler invocation is created.',
        'cases':cases,'issues':issues,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/finalize_project.py',ROOT/'tools/build_paper.py',ROOT/'tools/current_evidence.py')}}
    (ROOT/'review/finalization-guard-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False));return bool(issues)
if __name__=='__main__':sys.exit(run())
