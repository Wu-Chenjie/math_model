#!/usr/bin/env python3
"""Certificate failure-mode fixtures in isolated directories; no model runs."""
from pathlib import Path
import tempfile,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import certify_model_checks as certificate


def run():
    original=certificate.ROOT,certificate.TESTS;cases=[];issues=[]
    try:
        for name,script,expected in [
            ('missing_required_report','pass\n','FAIL'),
            ('report_without_explicit_success',"from pathlib import Path\nPath('review/report.json').write_text('{}')\n",'FAIL'),
            ('failed_report_despite_zero_exit',"from pathlib import Path\nPath('review/report.json').write_text('{\"status\":\"FAIL\"}')\n",'FAIL'),
            ('explicit_success_report',"from pathlib import Path\nPath('review/report.json').write_text('{\"status\":\"PASS\",\"independent\":true}')\n",'PASS')]:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);certificate.ROOT=root;certificate.TESTS=[('review/fixture.py','review/report.json')]
                for folder in ('review','artifacts','src','tools'):(root/folder).mkdir()
                (root/'review/fixture.py').write_text(script);(root/'review/check_nextgen_physics.py').write_text('#fixture\n')
                for filename in ('data.npz','forecast-selection.json','experiment-protocol.json'):(root/'artifacts'/filename).write_text('{}')
                try:certificate.main()
                except SystemExit:pass
                result=json.loads((root/'artifacts/model-check-validation.json').read_text())
                if name=='explicit_success_report' and result['status']=='PASS':
                    assert certificate.certificate_is_current(result)
                    shortened={**result,'records':[]}
                    assert not certificate.certificate_is_current(shortened)
                    report_path=root/'review/report.json';original_report=report_path.read_bytes()
                    report_path.write_text('{"status":"PASS","independent":true,"changed":true}')
                    assert not certificate.certificate_is_current(result)
                    report_path.write_bytes(original_report)
                    log=root/result['records'][0]['log'];log.write_text('changed log')
                    assert not certificate.certificate_is_current(result)
                cases.append({'name':name,'expected':expected,'actual':result['status'],'matched':result['status']==expected})
                if result['status']!=expected:issues.append(name)
    finally:certificate.ROOT,certificate.TESTS=original
    report={'reviewer_id':'/root/upgrade_code_review','independent':True,'status':'PASS' if not issues else 'CHANGES_REQUESTED',
            'scope':'Certificate-control fixtures only: temporary harmless scripts, no real review or valid project acceptance manufactured.',
            'cases':cases,'issues':issues,'source_sha256':hashlib.sha256((ROOT/'tools/certify_model_checks.py').read_bytes()).hexdigest()}
    (ROOT/'review/certificate-guard-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
    return 1 if issues else 0
if __name__=='__main__':sys.exit(run())
