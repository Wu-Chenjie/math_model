"""Audit returned Windows reference-backend trajectories on the original Mac."""
from pathlib import Path
import hashlib, importlib.util, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/remote-validation'
spec=importlib.util.spec_from_file_location('independent_physics',ROOT/'review/check_nextgen_physics.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
data=dict(np.load(ROOT/'artifacts/data.npz',allow_pickle=False))
rows=[]
for cid in ['7a7d9f1f5f762810','c4458f2f6fb06e54']:
    old=ROOT/f'artifacts/development/q4_3_{cid}';new=OUT/f'q4_3_{cid}'
    a=dict(np.load(old.with_suffix('.npz'),allow_pickle=False));b=dict(np.load(new.with_suffix('.npz'),allow_pickle=False))
    m=json.loads(new.with_suffix('.json').read_text(encoding='utf-8'));ref=json.loads(old.with_suffix('.json').read_text())
    assert set(a)==set(b)
    diffs={};exact={}
    for key in a:
        if a[key].dtype.kind in 'fc':
            exact[key]=bool(np.array_equal(a[key],b[key],equal_nan=True))
            same_nan=bool(np.array_equal(np.isnan(a[key]),np.isnan(b[key])))
            diffs[key]=float(np.nanmax(np.abs(a[key]-b[key]))) if same_nan else None
        else:exact[key]=bool(np.array_equal(a[key],b[key]))
    physical=audit.audit_arrays(data,b,m,development=True)
    source_match=m['source_hashes']==ref['source_hashes']
    rows.append({'configuration_id':cid,'kind':'q4_3','exact_arrays':exact,'max_absolute_differences':diffs,'source_hashes_match':source_match,'cost_difference_yuan':m['totals']['total_cost']-ref['totals']['total_cost'],'remote_runtime_seconds':m['runtime_seconds'],'reference_runtime_seconds':ref['runtime_seconds'],'physical':physical,'files_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for stem in [old,new] for p in [stem.with_suffix('.npz'),stem.with_suffix('.json')]}})
result={'status':'PASS_EXACT_SHORT_REPLAY' if all(all(r['exact_arrays'].values()) and r['source_hashes_match'] and r['physical']['passed'] for r in rows) else 'REVIEW_REQUIRED','scope':'Two January25–31 Q4-3 closed-loop trajectories; does not certify annual replay or Windows C++ backend. Original Python reference backend.','results':rows}
(OUT/'closed-loop-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
