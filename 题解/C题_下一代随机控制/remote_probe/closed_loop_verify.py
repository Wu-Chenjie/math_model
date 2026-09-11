"""Cross-platform January replay; no tuning and no formal-year jobs."""
from pathlib import Path
import concurrent.futures, hashlib, json, os, sys
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
ROOT=Path(__file__).resolve().parent/'closed_loop'
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
from nextgen_run import run_case

def one(cid):
    freeze=json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text(encoding='utf-8'))
    config=next(c for c in freeze['annual_configurations'] if hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:16]==cid)
    out=ROOT/f'artifacts/remote-validation/q4_3_{cid}'
    return run_case('q4_3',config,24,31,out)

def main():
    manifest=json.loads((ROOT/'transfer-manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    cases=['7a7d9f1f5f762810','c4458f2f6fb06e54']
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
        for result in pool.map(one,cases):print(json.dumps(result,ensure_ascii=True),flush=True)
    for name,digest in manifest.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    print('REPLAY_COMPLETE_PENDING_INDEPENDENT_LOCAL_AUDIT',flush=True)
if __name__=='__main__':main()
