"""Resume the frozen register with compatible C++ kernels only on explicit execution.

Completed Python results are verified and reused with their original provenance;
new results use cpp-formal. The old suspended Python pipeline is never resumed.
"""
from pathlib import Path
import argparse,concurrent.futures,fcntl,hashlib,importlib.util,json,subprocess,sys,os
from multiprocessing.reduction import DupFd
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cpp'),str(ROOT/'src')]
from run_case import run_case,backend_hashes
sys.path.insert(0,str(ROOT/'tools'))
import certify_cpp_backend as certification

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def task_id(config):return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]

def audit(stem,config,kind):
    spec=importlib.util.spec_from_file_location('cpp_independent_physics',ROOT/'review/check_nextgen_physics.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with np.load(stem.with_suffix('.npz'),allow_pickle=False) as f:arrays=dict(f)
    metrics=json.loads(stem.with_suffix('.json').read_text())
    with np.load(ROOT/'artifacts/data.npz',allow_pickle=False) as f:data=dict(f)
    assert metrics['kind']==kind and all(metrics['configuration'][k]==v for k,v in config.items())
    assert metrics['source_hashes']=={p.name:sha(p) for p in sorted((ROOT/'src').glob('*.py'))}
    if stem.parent.name=='cpp-formal':
        assert metrics.get('implementation',{}).get('name')=='cpp-kernels-compatible-reductions-v1', 'Incomplete native result lacks implementation proof'
        assert metrics['implementation']['backend_hashes']==backend_hashes()
    else:assert 'implementation' not in metrics, 'Original Python result has ambiguous implementation'
    result=module.audit_arrays(data,arrays,metrics,development=False)
    assert result['passed'],result['errors']
    result.update(source=str(stem.relative_to(ROOT)),trajectory_sha256=sha(stem.with_suffix('.npz')),
                  metrics_sha256=sha(stem.with_suffix('.json')),auditor_sha256=sha(ROOT/'review/check_nextgen_physics.py'),data_sha256=sha(ROOT/'artifacts/data.npz'))
    output=ROOT/f'review/cpp-formal-physics/{stem.name}.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return {'kind':kind,'configuration_id':task_id(config),'source':str(stem.relative_to(ROOT)),
            'implementation':metrics.get('implementation',{'name':'frozen-python'}),
            'audit':str(output.relative_to(ROOT)),'audit_sha256':sha(output),
            'trajectory_sha256':result['trajectory_sha256'],'metrics_sha256':result['metrics_sha256']}

def epoch():
    certification.require_frozen()
    return {'acceptance':sha(ROOT/'artifacts/cpp-migration/acceptance.json'),
            'selection':sha(ROOT/'artifacts/frozen-development-selection.json'),
            'sources':certification.source_hashes(),'environment':certification.environment_fingerprint(),'backend':backend_hashes(),'metadata':certification.metadata_hashes()}


def work(kind,config,stem,lock_token,expected_epoch):
    # One transferable duplicate per submission. Queued jobs whose parent died
    # before descriptor delivery fail at detach and cannot write any output.
    with os.fdopen(lock_token.detach(),'a') as inherited:
        path=ROOT/'artifacts/cpp-pipeline.lock'
        assert os.fstat(inherited.fileno()).st_ino==path.stat().st_ino, 'Replaced pipeline lock'
        fcntl.flock(inherited,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert epoch()==expected_epoch, 'CPP execution inputs changed before worker dispatch'
        run_case(kind,config,31,365,stem)
        result=audit(Path(stem),config,kind)
        assert epoch()==expected_epoch, 'CPP execution inputs changed during worker run'
        return result


def jobs_for(freeze):
    jobs=[]
    for config in freeze['annual_configurations']:
        for kind in ['q2','q3','q4_2','q4_3']:
            name=f'{kind}_{task_id(config)}'
            existing=next((ROOT/f'artifacts/{folder}/{name}' for folder in ['formal','cpp-formal']
                           if (ROOT/f'artifacts/{folder}/{name}.npz').exists() and (ROOT/f'artifacts/{folder}/{name}.json').exists()),None)
            jobs.append((kind,config,existing))
    return jobs


def require_old_paused():
    paused=json.loads((ROOT/'artifacts/cpp-migration-pause.json').read_text())
    assert paused.get('status')=='paused_by_user' and paused.get('pids'), 'Missing original-process pause record'
    assert len(set(paused['pids']))==len(paused['pids'])
    for pid in paused['pids']:
        assert isinstance(pid,int) and not isinstance(pid,bool) and pid>0
        p=subprocess.run(['ps','-p',str(pid),'-o','stat='],text=True,capture_output=True)
        assert p.returncode in (0,1), 'Cannot determine original process state'
        assert not p.stdout.strip() or p.stdout.strip().startswith(('T','Z')),f'Original process {pid} is active'


def main(workers,execute):
    assert isinstance(workers,int) and workers>0
    freeze_path=ROOT/'artifacts/frozen-development-selection.json'
    if not execute:
        jobs=jobs_for(json.loads(freeze_path.read_text()))
        print(json.dumps({'status':'paused_dry_run','registered':len(jobs),'existing_to_verify':sum(j[2] is not None for j in jobs),'remaining':sum(j[2] is None for j in jobs),'instruction':'Use --execute only when resuming is authorized. No experimental full-native M0 is selectable.'}));return
    # The stopped Python pipeline keeps its original lock. This distinct lock
    # protects isolated CPP outputs and is inherited by every running job.
    with (ROOT/'artifacts/cpp-pipeline.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        certification.require_acceptance();require_old_paused()
        freeze=certification.require_frozen();expected_epoch=epoch()
        jobs=jobs_for(freeze)  # Reuse decisions must be made under the writer lock.
        record={'status':'running','frozen_selection_sha256':sha(freeze_path),'backend_hashes':backend_hashes(),
                'acceptance_sha256':expected_epoch['acceptance'],'source_epoch':expected_epoch,'records':[],'pending':len(jobs)}
        target=ROOT/'artifacts/cpp-execution.json'
        def save():
            tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');tmp.replace(target)
        try:
            todo=[]
            for kind,config,existing in jobs:
                if existing is not None:record['records'].append(audit(existing,config,kind))
                else:todo.append((kind,config,str(ROOT/f'artifacts/cpp-formal/{kind}_{task_id(config)}')))
            record['pending']=len(todo);save()
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
                futures=[pool.submit(work,*args,DupFd(lock.fileno()),expected_epoch) for args in todo]
                for future in concurrent.futures.as_completed(futures):
                    record['records'].append(future.result());record['pending']-=1;save()
            assert epoch()==expected_epoch, 'CPP execution inputs changed before completion'
            expected={(kind,task_id(config)) for kind,config,_ in jobs}
            found=[(r['kind'],r['configuration_id']) for r in record['records']]
            assert len(found)==len(expected) and set(found)==expected and record['pending']==0
            record['status']='complete';save()
        except Exception as exc:
            record.update(status='failed',error=f'{type(exc).__name__}: {exc}');save();raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--execute',action='store_true')
    a=p.parse_args();assert a.workers>0;main(a.workers,a.execute)
