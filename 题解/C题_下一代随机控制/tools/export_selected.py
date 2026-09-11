"""Export only the adopted fixed-terminal policy using the verified table layout."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
from current_evidence import require_formal_current, require_baseline_current

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nextgen_scenarios import Config


def main():
    started=time.perf_counter();decision_path=ROOT/'artifacts/model-adoption.json'
    decision=json.loads(decision_path.read_text());assert decision['status']=='PASS'
    require_formal_current(ROOT);require_baseline_current(ROOT)
    config=Config(**decision['adopted_configuration']);selection={};bound={}
    (ROOT/'artifacts/annual').mkdir(exist_ok=True)
    for kind in ('q2','q3','q4_2','q4_3'):
        selection[kind]=config.identity()
        for suffix in ('.npz','.json'):
            source=ROOT/f'artifacts/formal/{kind}_{config.identity()}{suffix}'
            bound[str(source.relative_to(ROOT))]=hashlib.sha256(source.read_bytes()).hexdigest()
            shutil.copy2(source,ROOT/f'artifacts/annual/{kind}_{config.identity()}{suffix}')
    for suffix in ('.npz','.json'):
        source=ROOT.parent/'C题_下一代基线复现'/f'artifacts/q1{suffix}'
        shutil.copy2(source,ROOT/f'artifacts/q1{suffix}')
        bound['../C题_下一代基线复现/artifacts/q1'+suffix]=hashlib.sha256(source.read_bytes()).hexdigest()
    payload={'selected':selection,'role':'Export aliases from the prespecified adoption decision; this is not parameter selection.',
             'adoption_sha256':hashlib.sha256(decision_path.read_bytes()).hexdigest(),'formal_sources':bound}
    (ROOT/'artifacts/export-selection.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    result=subprocess.run([sys.executable,'tools/export_workbook_payload.py'],cwd=ROOT)
    if result.returncode:raise SystemExit(result.returncode)
    (ROOT/'artifacts/export-selected-execution.json').write_text(json.dumps({'status':'complete',
        'command':sys.argv,'exit_code':0,'runtime_seconds':time.perf_counter()-started,
        'adopted_configuration':decision['adopted_configuration'],'source_hashes':bound},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
