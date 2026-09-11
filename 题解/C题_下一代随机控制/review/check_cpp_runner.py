#!/usr/bin/env python3
"""Isolated CPP queue/acceptance guards; no real task execution or resumption."""
from pathlib import Path
from contextlib import contextmanager
import tempfile,hashlib,json,sys,os,fcntl,subprocess,time,signal
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'cpp'),str(ROOT/'src')]
import certify_cpp_backend as cert,run_cpp_registered as driver,run_case as backend

def put(root,path,value):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value) if isinstance(value,(dict,list)) else value)
    return cert.sha(p)
def edit(root,path,fn):
    v=json.loads((root/path).read_text());fn(v);put(root,path,v)

@contextmanager
def environment(root):
    old=cert.ROOT,driver.ROOT,backend.ROOT,backend.CPP
    cert.ROOT=driver.ROOT=backend.ROOT=root;backend.CPP=root/'cpp'
    try:yield
    finally:cert.ROOT,driver.ROOT,backend.ROOT,backend.CPP=old

def setup(root):
    for path in ('src/control.py','tools/run_incremental_experiments.py','tools/run_cpp_registered.py','tools/certify_cpp_backend.py','tools/verify_cpp_closed_loop.py','review/check_nextgen_physics.py','review/check_cpp_runner.py'):
        put(root,path,'# inert source fixture')
    for path in ('data.npz','forecast-selection.json','development-forecast-selection.json','experiment-protocol.json'):put(root,'artifacts/'+path,{})
    for name in ('native.py','native_feedback.py','native_enhanced.py','kernels.cpp','libmicrogrid.dylib'):put(root,'cpp/'+name,'inert core '+name)
    for name in ('build.json','adapter-sources.json'):put(root,'cpp/'+name,{'fixture':True})
    src=cert.current_hashes(list((root/'src').glob('*.py')))
    paths=list((root/'src').glob('*.py'))+[root/'tools/run_incremental_experiments.py']+[root/'artifacts'/n for n in ('data.npz','forecast-selection.json','development-forecast-selection.json','experiment-protocol.json')]
    put(root,'artifacts/frozen-development-selection.json',{'status':'frozen','source_hashes':src,'integrity_hashes':cert.current_hashes(paths),'protocol_sha256':cert.sha(root/'artifacts/experiment-protocol.json'),'annual_configurations':[{}]})
    native=backend.backend_hashes();rows=[]
    for kind,identity in sorted(cert.CASES):
        hashes={};arrays={'q':np.zeros((7,144)),'r':np.zeros((7,144)),'c':np.zeros((7,144)),'d':np.zeros((7,144)),'emergency':np.zeros((7,144)),'spill':np.zeros((7,144)),'price':np.ones((7,144)),'projection':np.zeros((7,144)),'releases':np.zeros((7,4,144)),'state':np.full((7,145),6000.),'days':np.arange(24,31),'dates':np.arange(np.datetime64('2025-01-25'),np.datetime64('2025-02-01')).astype(str)}
        for folder in ('development','cpp-development'):
            stem=root/f'artifacts/{folder}/{kind}_{identity}';stem.parent.mkdir(parents=True,exist_ok=True)
            np.savez(stem.with_suffix('.npz'),**arrays)
            metrics={'kind':kind,'configuration':{'start_day':24,'end_day':30},'implementation':{'name':'cpp-kernels-compatible-reductions-v1','backend_hashes':native}}
            put(root,str(stem.with_suffix('.json').relative_to(root)),metrics)
            for suffix in ('.npz','.json'):
                p=stem.with_suffix(suffix);hashes[str(p.relative_to(root))]=cert.sha(p)
        rows.append({'kind':kind,'configuration_id':identity,'status':'PASS','cost_difference_yuan':0.,'exact_arrays':{k:True for k in arrays},'physical':{'passed':True,'errors':[],'checks':{'inert':{'passed':True}}},'input_hashes':hashes})
    put(root,cert.EVIDENCE[0],{'status':'PASS','backend_hashes':native,'results':rows})
    math_hashes={f'cpp/{name}':cert.sha(root/'cpp'/name) for name in ('native_feedback.py','native_enhanced.py','kernels.cpp','libmicrogrid.dylib')}
    put(root,cert.EVIDENCE[1],{'status':'PASS','independent':True,'unresolved':[],'reviewed_artifact_hashes':math_hashes})
    sample={'LP_exact':{'obj':True},'output_exact':{'q':True}}
    put(root,cert.EVIDENCE[2],{'status':'PASS_WITHIN_SCOPE','independent':True,'issues':[],'source_hashes':src,'captured_cases':[sample]*4,'synthetic_cases':[sample]*32})
    ast=[{'class':c,'reference':'src/control.py','adapter':'cpp/native_feedback.py','class_AST_exact':True,'reference_sha256':cert.sha(root/'src/control.py'),'adapter_sha256':cert.sha(root/'cpp/native_feedback.py')} for c in ('MarkovDP','WeightedMarkovDP','EnhancedMarkovDP')]
    put(root,cert.EVIDENCE[3],{'status':'PASS_WITHIN_SCOPE','independent':True,'cases':ast})
    put(root,cert.EVIDENCE[4],{'status':'PASS_WITHIN_SCOPE','independent':True,'issues':[],'cases':[{'fixture':True}],'source_hashes':src})
    value={'status':'PASS_COMPATIBLE_BACKEND','environment_fingerprint':cert.environment_fingerprint(),'backend_hashes':native,'metadata_hashes':cert.metadata_hashes(),'source_hashes':cert.source_hashes(),
           'frozen_selection_sha256':cert.sha(root/'artifacts/frozen-development-selection.json'),'evidence_hashes':{path:cert.sha(root/path) for path in cert.EVIDENCE}}
    put(root,'artifacts/cpp-migration/acceptance.json',value)

def acceptance_cases():
    cases=[]
    for case in ('control','status_shell','empty_evidence','stale_source','stale_input','stale_protocol','stale_metadata','changed_numpy_version','changed_numpy_cpu_features','changed_numpy_binary','changed_highs_binary','changed_python_platform','stale_closed_loop_array','missing_closed_loop_case','missing_closed_loop_array','false_exact_flag','empty_math_binding','planner_failed','runner_empty'):
        with tempfile.TemporaryDirectory() as td,environment(Path(td)):
            root=Path(td);setup(root)
            if case=='status_shell':put(root,'artifacts/cpp-migration/acceptance.json',{'status':'PASS_COMPATIBLE_BACKEND'})
            elif case=='empty_evidence':edit(root,'artifacts/cpp-migration/acceptance.json',lambda x:x.update(evidence_hashes={}))
            elif case=='stale_source':put(root,'src/control.py','# changed')
            elif case=='stale_input':put(root,'artifacts/data.npz','changed')
            elif case=='stale_protocol':put(root,'artifacts/experiment-protocol.json',{'changed':True})
            elif case=='stale_metadata':put(root,'cpp/build.json',{'changed':True})
            elif case=='changed_numpy_version':edit(root,'artifacts/cpp-migration/acceptance.json',lambda x:x['environment_fingerprint'].update(numpy_version='changed'))
            elif case=='changed_numpy_cpu_features':edit(root,'artifacts/cpp-migration/acceptance.json',lambda x:x['environment_fingerprint'].update(numpy_cpu_features={}))
            elif case=='changed_numpy_binary':
                edit(root,'artifacts/cpp-migration/acceptance.json',lambda x:x['environment_fingerprint']['binary_sha256'].update({x['environment_fingerprint']['numpy_core']:'changed'}))
            elif case=='changed_highs_binary':
                edit(root,'artifacts/cpp-migration/acceptance.json',lambda x:x['environment_fingerprint']['binary_sha256'].update({x['environment_fingerprint']['highs_core']:'changed'}))
            elif case=='changed_python_platform':edit(root,'artifacts/cpp-migration/acceptance.json',lambda x:x['environment_fingerprint'].update(platform='changed'))
            elif case=='stale_closed_loop_array':next((root/'artifacts/cpp-development').glob('*.npz')).write_bytes(b'changed')
            elif case=='missing_closed_loop_case':edit(root,cert.EVIDENCE[0],lambda x:x['results'].pop())
            elif case=='missing_closed_loop_array':
                rows=json.loads((root/cert.EVIDENCE[0]).read_text())
                row=rows['results'][0];row['exact_arrays'].pop('c')
                for relative in list(row['input_hashes']):
                    if relative.endswith('.npz'):
                        path=root/relative
                        with np.load(path,allow_pickle=False) as z:arrays={k:z[k] for k in z if k!='c'}
                        np.savez(path,**arrays);row['input_hashes'][relative]=cert.sha(path)
                put(root,cert.EVIDENCE[0],rows)
            elif case=='false_exact_flag':edit(root,cert.EVIDENCE[0],lambda x:x['results'][0]['exact_arrays'].update(q=False))
            elif case=='empty_math_binding':edit(root,cert.EVIDENCE[1],lambda x:x.update(reviewed_artifact_hashes={}))
            elif case=='planner_failed':edit(root,cert.EVIDENCE[2],lambda x:x.update(status='FAIL'))
            elif case=='runner_empty':edit(root,cert.EVIDENCE[4],lambda x:x.update(cases=[]))
            try:cert.require_acceptance();accepted=True;error=None
            except (AssertionError,KeyError,FileNotFoundError,ValueError) as e:accepted=False;error=str(e)
            cases.append({'case':case,'accepted':accepted,'error':error})
    return cases

def dispatch_cases():
    cases=[]
    with tempfile.TemporaryDirectory() as td,environment(Path(td)):
        root=Path(td);setup(root)
        old_pool=driver.concurrent.futures.ProcessPoolExecutor
        class ForbiddenPool:
            def __init__(self,*a,**k):raise AssertionError('Unexpected optimizer pool dispatch')
        driver.concurrent.futures.ProcessPoolExecutor=ForbiddenPool
        try:
            driver.main(1,False);cases.append({'case':'default_dry_run','passed':not (root/'artifacts/cpp-execution.json').exists()})
            with (root/'artifacts/cpp-pipeline.lock').open('a') as f:
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                try:driver.main(1,True);rejected=False
                except BlockingIOError:rejected=True
                cases.append({'case':'duplicate_writer','passed':rejected})
        finally:driver.concurrent.futures.ProcessPoolExecutor=old_pool
    return cases

def orphan_pool_case():
    # Spawn a real worker, with only its numerical work/audit replaced by inert
    # functions. The production work() obtains DupFd and owns its lifetime.
    code='''from pathlib import Path
import sys,os,fcntl,json,time,concurrent.futures,multiprocessing
from multiprocessing.reduction import DupFd
sys.path[:0]=[sys.argv[1],sys.argv[2],sys.argv[3]]
import run_cpp_registered as runner
R=Path(sys.argv[4])
def inert_run(*args):
 (R/'worker-ready').write_text(str(os.getpid()))
 for _ in range(500):
  if (R/'probe').exists():break
  time.sleep(.01)
 with (R/'artifacts/cpp-pipeline.lock').open('a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True
  except BlockingIOError:acquired=False
 (R/'worker-result').write_text(json.dumps({'lock_acquired_after_parent_exit':acquired}))
def init():
 runner.ROOT=R;runner.epoch=lambda:{};runner.run_case=inert_run;runner.audit=lambda *a:{}
if __name__=='__main__':
 with (R/'artifacts/cpp-pipeline.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with concurrent.futures.ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'),initializer=init) as pool:
   pool.submit(runner.work,'q2',{},str(R/'unused'),DupFd(lock.fileno()),{}).result()
'''
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);(root/'artifacts').mkdir();script=root/'inert_controller.py';script.write_text(code)
        process=subprocess.Popen([sys.executable,str(script),str(ROOT/'tools'),str(ROOT/'cpp'),str(ROOT/'src'),str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        worker=None
        try:
            for _ in range(600):
                if (root/'worker-ready').exists():break
                if process.poll() is not None:raise AssertionError('Fixture controller ended: '+process.stderr.read().decode())
                time.sleep(.01)
            assert (root/'worker-ready').exists(),'Fixture worker failed to start'
            worker=int((root/'worker-ready').read_text());process.kill();process.wait(timeout=3);(root/'probe').write_text('probe')
            for _ in range(300):
                if (root/'worker-result').exists():break
                time.sleep(.01)
            value=json.loads((root/'worker-result').read_text())
            return {'case':'spawn_pool_orphan_lock','passed':not value['lock_acquired_after_parent_exit'],**value}
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)
            if worker:
                try:os.kill(worker,signal.SIGTERM)
                except ProcessLookupError:pass

def main():
    accept=acceptance_cases();other=dispatch_cases()+[orphan_pool_case()]
    issues=[r['case'] for r in accept if r['accepted']!=(r['case']=='control')]+[r['case'] for r in other if not r['passed']]
    report={'status':'CHANGES_REQUESTED' if issues else 'PASS_WITHIN_SCOPE','independent':True,'reviewer_id':'/root/upgrade_code_review','issues':issues,'cases':accept+other,
            'scope':'Temporary inert acceptance records test structure/freshness, not genuine model approval. Actual spawned worker uses production DupFd lifetime while numerics/audit are inert. Only own temporary parent/worker are terminated; no original PID resumed or annual optimization invoked.',
            'source_hashes':{str(p.relative_to(ROOT)):cert.sha(p) for p in (ROOT/'tools/run_cpp_registered.py',ROOT/'tools/certify_cpp_backend.py',Path(__file__))}}
    (ROOT/'review/cpp-runner-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));return bool(issues)
if __name__=='__main__':sys.exit(main())
