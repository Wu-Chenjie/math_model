"""Portable CPU benchmark using exact January LPs; no annual experiment runs."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,platform,sys,time
import numpy as np
import scipy
from scipy.sparse import csr_matrix
import highspy
ROOT=Path(__file__).resolve().parent

def one(name):
    path=ROOT/'fixtures'/name/'linear-program.npz'
    with np.load(path,allow_pickle=False) as a:
        objective=a['obj'];rhs=a['rhs'];bounds=a['bounds'];expected=a['solution'];
        A=csr_matrix((a['values'],a['indices'],a['indptr']),shape=tuple(a['shape']))
    bounds=bounds.copy();bounds[:,0]=np.where(np.isnan(bounds[:,0]),-np.inf,bounds[:,0]);bounds[:,1]=np.where(np.isnan(bounds[:,1]),np.inf,bounds[:,1])
    lp=highspy.HighsLp();lp.num_col_=len(objective);lp.num_row_=len(rhs)
    lp.col_cost_=objective;lp.col_lower_=bounds[:,0];lp.col_upper_=bounds[:,1]
    lp.row_lower_=np.full(len(rhs),-np.inf);lp.row_upper_=rhs
    lp.a_matrix_.format_=highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_=A.indptr;lp.a_matrix_.index_=A.indices;lp.a_matrix_.value_=A.data
    h=highspy.Highs();h.setOptionValue('output_flag',False);h.setOptionValue('threads',1);h.setOptionValue('solver','ipm')
    start=time.perf_counter();h.passModel(lp);loaded=time.perf_counter();h.run();finished=time.perf_counter()
    x=np.asarray(h.getSolution().col_value)
    if h.getModelStatus()!=highspy.HighsModelStatus.kOptimal:raise RuntimeError(h.modelStatusToString(h.getModelStatus()))
    residual=max(0.,float(np.max(A@x-rhs)),float(np.max(bounds[:,0]-x)),float(np.max(x-bounds[:,1])))
    return {'fixture':name,'solver_seconds':finished-loaded,'pass_model_seconds':loaded-start,
        'objective':float(objective@x),'reference_objective':float(objective@expected),
        'objective_difference':float(objective@x-objective@expected),'primal_violation':residual,
        'solution_max_abs_difference':float(np.max(np.abs(x-expected))),
        'solution_exact':bool(np.array_equal(x,expected)),
        'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main(workers):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for relative,digest in manifest['files'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,'Fixture/source changed: '+relative
    names=sorted(p.name for p in (ROOT/'fixtures').iterdir() if p.is_dir())
    serial=[]
    for name in names:
        one(name) # Warm-up is excluded.
        serial.extend(one(name) for _ in range(3))
    tasks=names*2
    started=time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        parallel=list(pool.map(one,tasks))
    elapsed=time.perf_counter()-started
    report={'status':'MEASURED_NOT_ANNUAL_VALIDATION','machine':platform.platform(),'architecture':platform.machine(),
        'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'highs':highspy.Highs().version(),
        'workers':workers,'serial':serial,'parallel':parallel,'eight_LP_batch_seconds_including_process_startup':elapsed,
        'all_primal_violations_below_1e_5':all(x['primal_violation']<1e-5 for x in serial+parallel),
        'max_objective_difference':max(abs(x['objective_difference']) for x in serial+parallel),
        'scope':'Same IPM and threads=1. Different optima/floating results must be reviewed before transferring frozen policies. This benchmark does not measure full closed-loop throughput.'}
    output=ROOT/f'benchmark-{platform.machine()}-{workers}workers.json'
    output.write_text(json.dumps(report,indent=2)+'\n');print(output)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);a=p.parse_args();assert a.workers>0;main(a.workers)
