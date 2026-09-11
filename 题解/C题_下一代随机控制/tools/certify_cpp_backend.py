"""Fail-closed acceptance for compatible native kernels, never full-native M0."""
from pathlib import Path
import hashlib,json,sys,platform,importlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cpp'),str(ROOT/'src')]
from run_case import backend_hashes
EVIDENCE=('artifacts/cpp-migration/closed-loop-equivalence.json','review/cpp-math-independent.json',
          'artifacts/cpp-migration/independent-planner-checks.json','artifacts/cpp-migration/feedback-reference-ast-checks.json',
          'review/cpp-runner-checks.json')
CASES={('q3','7a7d9f1f5f762810'),('q4_3','c4458f2f6fb06e54'),('q4_3','592bc8462bb5cae5'),('q2','d21be844de2de2b1'),('q4_2','c4458f2f6fb06e54')}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def current_hashes(paths):return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}
def source_hashes():
    paths=list((ROOT/'src').glob('*.py'))+[ROOT/'tools'/n for n in ('run_incremental_experiments.py','run_cpp_registered.py','certify_cpp_backend.py','verify_cpp_closed_loop.py')]
    paths += [ROOT/'review/check_nextgen_physics.py',ROOT/'review/check_cpp_runner.py']
    paths += [ROOT/'artifacts'/n for n in ('data.npz','forecast-selection.json','development-forecast-selection.json','experiment-protocol.json')]
    return current_hashes(paths)
def metadata_hashes():return current_hashes([ROOT/'cpp/build.json',ROOT/'cpp/adapter-sources.json'])

def environment_fingerprint():
    # Match the modules actually loaded by the retained numerical execution path.
    import control
    highspy=control.highspy
    highscore=importlib.import_module('highspy._core')
    numpycore=importlib.import_module('numpy._core._multiarray_umath')
    vendor=Path(control.__file__).resolve().parents[1]/'vendor'
    assert Path(highscore.__file__).resolve().is_relative_to(vendor.resolve()), 'HiGHS is not the retained vendored runtime'
    np_root=Path(np.__file__).resolve().parent
    paths=[Path(sys.executable).resolve(),Path(numpycore.__file__).resolve(),Path(highscore.__file__).resolve()]
    # Include NumPy extension modules and bundled BLAS/LAPACK shared objects.
    for directory in (np_root,np_root.parent/'numpy.libs',np_root.parent/'.dylibs'):
        if directory.is_dir():paths.extend(p.resolve() for p in directory.rglob('*') if p.is_file() and p.suffix in ('.so','.dylib'))
    highspy_root=Path(highspy.__file__).resolve().parent
    paths.extend(p.resolve() for p in highspy_root.rglob('*') if p.is_file() and p.suffix in ('.so','.dylib'))
    version='.'.join(str(getattr(highspy,'HIGHS_VERSION_'+part)) for part in ('MAJOR','MINOR','PATCH'))
    return {'python_version':sys.version,'python_executable':str(Path(sys.executable).resolve()),
            'platform':platform.platform(),'machine':platform.machine(),'numpy_version':np.__version__,
            'numpy_core':str(Path(numpycore.__file__).resolve()),'numpy_cpu_features':getattr(numpycore,'__cpu_features__',{}),'numpy_configuration':getattr(np.__config__,'CONFIG',{}),
            'highs_version':version,'highs_core':str(Path(highscore.__file__).resolve()),
            'binary_sha256':{str(path):sha(path) for path in sorted(set(paths))}}


def require_frozen():
    frozen=read(ROOT/'artifacts/frozen-development-selection.json')
    src=current_hashes(list((ROOT/'src').glob('*.py')))
    assert frozen.get('status')=='frozen' and src and frozen.get('source_hashes')==src,'Frozen source changed'
    paths=list((ROOT/'src').glob('*.py'))+[ROOT/'tools/run_incremental_experiments.py']
    paths += [ROOT/'artifacts'/n for n in ('data.npz','forecast-selection.json','development-forecast-selection.json','experiment-protocol.json')]
    assert frozen.get('integrity_hashes')==current_hashes(paths),'Frozen input/coordinator/protocol changed'
    assert frozen.get('protocol_sha256')==sha(ROOT/'artifacts/experiment-protocol.json')
    configs=frozen.get('annual_configurations',[])
    assert configs and len({json.dumps(c,sort_keys=True) for c in configs})==len(configs),'Empty or duplicate annual register'
    return frozen

def check_bound(hashes):
    assert hashes,'Empty bound evidence'
    for path,digest in hashes.items():assert sha(ROOT/path)==digest,'Stale evidence: '+path

def require_evidence():
    require_frozen();backend=backend_hashes();proofs={name:read(ROOT/name) for name in EVIDENCE}
    for path,p in proofs.items():
        assert p.get('status') in ('PASS','PASS_WITHIN_SCOPE'), 'CPP evidence has not passed: '+path
        if 'closed-loop' not in path:assert p.get('independent') is True,'Review is not independent: '+path
    closed=proofs[EVIDENCE[0]];assert closed.get('backend_hashes')==backend,'Closed-loop backend changed'
    rows=closed.get('results',[]);assert len(rows)==5 and {(r['kind'],r['configuration_id']) for r in rows}==CASES,'Incomplete closed-loop settings'
    for row in rows:
        assert row.get('status')=='PASS' and row.get('cost_difference_yuan')==0
        kind,identity=row['kind'],row['configuration_id']
        required={f'artifacts/{folder}/{kind}_{identity}{suffix}' for folder in ('development','cpp-development') for suffix in ('.npz','.json')}
        assert set(row.get('input_hashes',{}))==required,'Closed-loop input coverage incomplete';check_bound(row['input_hashes'])
        stems=[ROOT/f'artifacts/{folder}/{kind}_{identity}' for folder in ('development','cpp-development')]
        with np.load(stems[0].with_suffix('.npz'),allow_pickle=False) as old,np.load(stems[1].with_suffix('.npz'),allow_pickle=False) as new:
            required_arrays={'q','r','c','d','emergency','spill','price','projection','state','releases','days','dates'}
            assert set(old)==set(new)==set(row.get('exact_arrays',{}))==required_arrays, 'Closed-loop array coverage incomplete'
            assert all(v is True for v in row['exact_arrays'].values())
            for key in old:
                assert np.array_equal(old[key],new[key],equal_nan=True) if old[key].dtype.kind in 'fc' else np.array_equal(old[key],new[key]),'Closed-loop arrays differ: '+key
            assert np.array_equal(new['days'],np.arange(24,31)) and np.array_equal(new['dates'],np.arange(np.datetime64('2025-01-25'),np.datetime64('2025-02-01')).astype(str))
            assert new['state'].shape==(7,145) and new['state'][0,0]==6000. and abs(new['state'][-1,-1]-6000.)<1e-5
        metrics=read(stems[1].with_suffix('.json'))
        assert metrics['kind']==kind and metrics['configuration']['start_day']==24 and metrics['configuration']['end_day']==30
        assert metrics['implementation']['name']=='cpp-kernels-compatible-reductions-v1' and metrics['implementation']['backend_hashes']==backend
        physical=row.get('physical',{});assert physical.get('passed') is True and not physical.get('errors')
        assert physical.get('checks') and all(c.get('passed') is True for c in physical['checks'].values())
    math=proofs[EVIDENCE[1]];assert math.get('unresolved')==[];check_bound(math.get('reviewed_artifact_hashes',{}))
    for name in ('native_feedback.py','native_enhanced.py','kernels.cpp','libmicrogrid.dylib'):
        assert sha(ROOT/'cpp'/name) in [h for p,h in math['reviewed_artifact_hashes'].items() if Path(p).name==name],'Math review uses different numerical core: '+name
    planner=proofs[EVIDENCE[2]];assert planner.get('issues')==[];check_bound(planner.get('source_hashes',{}))
    assert len(planner.get('captured_cases',[]))==4 and len(planner.get('synthetic_cases',[]))>=32
    for row in planner['captured_cases']+planner['synthetic_cases']:
        assert row.get('LP_exact') and row.get('output_exact')
        assert all(row['LP_exact'].values()) and all(row['output_exact'].values())
    ast=proofs[EVIDENCE[3]];rows=ast.get('cases',[])
    assert len(rows)==3 and {r['class'] for r in rows}=={'MarkovDP','WeightedMarkovDP','EnhancedMarkovDP'}
    for row in rows:
        assert row['class_AST_exact'] is True
        assert sha(ROOT/row['reference'])==row['reference_sha256'] and sha(ROOT/row['adapter'])==row['adapter_sha256']
    runner=proofs[EVIDENCE[4]];assert runner.get('issues')==[] and runner.get('cases');check_bound(runner.get('source_hashes',{}))
    return {name:sha(ROOT/name) for name in EVIDENCE}

def require_acceptance():
    value=read(ROOT/'artifacts/cpp-migration/acceptance.json')
    assert value.get('status')=='PASS_COMPATIBLE_BACKEND'
    assert value.get('environment_fingerprint')==environment_fingerprint(), 'Numerical runtime environment changed'
    assert value.get('backend_hashes')==backend_hashes() and value.get('metadata_hashes')==metadata_hashes(),'Native backend/metadata changed'
    assert value.get('frozen_selection_sha256')==sha(ROOT/'artifacts/frozen-development-selection.json')
    assert value.get('source_hashes')==source_hashes(),'CPP acceptance source/input changed'
    assert value.get('evidence_hashes')==require_evidence(),'CPP acceptance evidence changed or incomplete'
    return value

def main():
    evidence=require_evidence()
    value={'status':'PASS_COMPATIBLE_BACKEND','environment_fingerprint':environment_fingerprint(),'backend_hashes':backend_hashes(),'metadata_hashes':metadata_hashes(),
           'frozen_selection_sha256':sha(ROOT/'artifacts/frozen-development-selection.json'),'source_hashes':source_hashes(),'evidence_hashes':evidence,
           'scope':'Compatible native CSR/convolution implementation of frozen policies; does not certify full-native Markov reduction or authorize resuming the stopped Python processes.'}
    target=ROOT/'artifacts/cpp-migration/acceptance.json';temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(target)
    print(value['status'])
if __name__=='__main__':main()
