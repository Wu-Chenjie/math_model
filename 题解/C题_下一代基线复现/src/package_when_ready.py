"""Assemble completed numerical runs and export the five requested result templates."""
from pathlib import Path
import subprocess,time,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[1]
NODE=Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
PYTHON=Path('/Users/wuchenjie/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
MARKER=Path('/Users/wuchenjie/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.904.11930/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs')
def run(args):
    started=time.perf_counter();print('START',args,flush=True)
    subprocess.run(args,cwd=ROOT,check=True)
    return {'command':args,'exit_code':0,'runtime_seconds':time.perf_counter()-started}
def main():
    assert len(json.loads((ROOT/'artifacts/execution-annual.json').read_text())['results'])==20
    assert len(json.loads((ROOT/'artifacts/execution-annual_sddp.json').read_text())['results'])==4
    payload=ROOT/'artifacts/workbook-payload.json';expected_payload=hashlib.sha256(payload.read_bytes()).hexdigest()
    logs=[run([str(NODE),str(MARKER),'--operation-kind','create','--expected-output-count','5','--output-format','xlsx'])]
    logs.append(run([str(NODE),'src/build_workbooks.mjs']))
    logs.append(run([str(PYTHON),'src/verify_workbooks.py']))
    while True:
        try:
            m=json.loads((ROOT/'artifacts/global-terminal.json').read_text())
            if len(m['results'])==8 and m['execution']['exit_code']==0:break
        except (OSError,ValueError,KeyError):pass
        time.sleep(10)
    logs.append(run([sys.executable,'src/finish.py']));logs.append(run([sys.executable,'src/export_results.py']))
    assert hashlib.sha256(payload.read_bytes()).hexdigest()==expected_payload,'Workbook payload changed after early export; rebuild the workbooks and reconcile.'
    logs.append(run([str(PYTHON),'src/verify_workbooks.py']))
    (ROOT/'artifacts/execution-package.json').write_text(json.dumps({'results':logs,'exit_code':0,'runtime_seconds':sum(x['runtime_seconds'] for x in logs)},ensure_ascii=False,indent=2)+'\n')
    print('EXPORTED AND NUMERICALLY CHECKED; visual and independent final review required.',flush=True)
if __name__=='__main__':main()
