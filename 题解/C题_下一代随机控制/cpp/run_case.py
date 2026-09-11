"""Explicit native backend runner. Outputs never overwrite frozen Python runs."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];CPP=ROOT/'cpp'
sys.path[:0]=[str(CPP),str(ROOT/'src')]

def backend_hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(CPP.iterdir()) if p.suffix in ('.py','.cpp','.dylib')}

def install():
    import native
    native.validate_artifacts()
    for relative,expected in json.loads((CPP/'adapter-sources.json').read_text()).items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Generated adapter has changed: '+relative)
    import nextgen_run as run
    from native_planner import affine_plan
    from native_feedback import WeightedMarkovDP
    from native_enhanced import EnhancedMarkovDP
    run.affine_plan=affine_plan;run.WeightedMarkovDP=WeightedMarkovDP;run.EnhancedMarkovDP=EnhancedMarkovDP
    return run

def run_case(kind,configuration,start,stop,output):
    run=install();before=backend_hashes();output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'artifacts/cpp-development') and not output.is_relative_to(ROOT/'artifacts/cpp-formal'):
        raise ValueError('Native outputs must use a separate cpp-development or cpp-formal directory')
    result=run.run_case(kind,configuration,start,stop,output)
    if before!=backend_hashes():raise RuntimeError('Native backend changed during computation')
    path=output.with_suffix('.json');metrics=json.loads(path.read_text())
    metrics['implementation']={'name':'cpp-kernels-compatible-reductions-v1','backend_hashes':before,
        'scope':'Native CSR expressions and PL convolution; original BLAS reduction order, tie selection, HiGHS options, information and physical executor retained.'}
    run.dump(path,metrics)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['q2','q3','q4_2','q4_3'],required=True)
    p.add_argument('--configuration-id',required=True);p.add_argument('--start',type=int,default=24);p.add_argument('--stop',type=int,default=31)
    a=p.parse_args();freeze=json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text())
    configs={hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()[:16]:c for c in freeze['annual_configurations']}
    if a.configuration_id not in configs:raise ValueError('Configuration is not in the frozen register')
    if not 0<=a.start<a.stop<=31:raise ValueError('This verification CLI is restricted to January; use the gated annual runner for formal evaluation')
    output=ROOT/f'artifacts/cpp-development/{a.kind}_{a.configuration_id}'
    print(json.dumps(run_case(a.kind,configs[a.configuration_id],a.start,a.stop,output)))
if __name__=='__main__':main()
