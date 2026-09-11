"""Verify the native backend against completed January trajectories, never retune."""
from pathlib import Path
import concurrent.futures,hashlib,importlib.util,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cpp'),str(ROOT/'src')]
from run_case import run_case,backend_hashes
CASES=[('q3','7a7d9f1f5f762810'),('q4_3','c4458f2f6fb06e54'),('q4_3','592bc8462bb5cae5'),('q2','d21be844de2de2b1'),('q4_2','c4458f2f6fb06e54')]

def one(case):
    kind,identity=case;reference=ROOT/f'artifacts/development/{kind}_{identity}'
    old=json.loads(reference.with_suffix('.json').read_text())
    freeze=json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text())
    config=next(c for c in freeze['annual_configurations'] if hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:16]==identity)
    output=ROOT/f'artifacts/cpp-development/{kind}_{identity}'
    run_case(kind,config,24,31,output)
    with np.load(reference.with_suffix('.npz'),allow_pickle=False) as f:a=dict(f)
    with np.load(output.with_suffix('.npz'),allow_pickle=False) as f:b=dict(f)
    assert set(a)==set(b)
    checks={k:bool(np.array_equal(a[k],b[k],equal_nan=True)) if a[k].dtype.kind in 'fc' else bool(np.array_equal(a[k],b[k])) for k in a}
    metrics=json.loads(output.with_suffix('.json').read_text())
    spec=importlib.util.spec_from_file_location('independent_cpp_audit',ROOT/'review/check_nextgen_physics.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    with np.load(ROOT/'artifacts/data.npz',allow_pickle=False) as f:data=dict(f)
    physical=audit.audit_arrays(data,b,metrics,development=True)
    paths=[reference.with_suffix(s) for s in ['.npz','.json']]+[output.with_suffix(s) for s in ['.npz','.json']]
    result={'kind':kind,'configuration_id':identity,'status':'PASS' if all(checks.values()) and physical['passed'] else 'FAIL','exact_arrays':checks,'cost_difference_yuan':metrics['totals']['total_cost']-old['totals']['total_cost'],'physical':physical,'input_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    print(json.dumps({k:result[k] for k in ['kind','configuration_id','status','cost_difference_yuan']}),flush=True)
    return result

def main():
    before=backend_hashes()
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,CASES))
    assert before==backend_hashes()
    report={'status':'PASS' if all(r['status']=='PASS' for r in results) else 'FAIL','scope':'Five complete Jan25–31 sequential trajectories covering all tasks, legacy and conditional M0, joint M1, H72/96 and actual terminal6000. No formal-year optimization was run.','backend_hashes':before,'results':results}
    (ROOT/'artifacts/cpp-migration/closed-loop-equivalence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    assert report['status']=='PASS'
if __name__=='__main__':main()
