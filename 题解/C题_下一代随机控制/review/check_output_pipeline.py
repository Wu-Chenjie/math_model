#!/usr/bin/env python3
"""Bounded first-dispatch checks of the reproduction wrapper; no actual job runs."""
from pathlib import Path
import tempfile,fcntl,sys,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import reproduce_project as reproduction


def run():
    original=reproduction.ROOT,reproduction.REPLAY,reproduction.run
    observed={};issues=[]
    class StopBeforeJob(Exception):pass
    try:
        with tempfile.TemporaryDirectory() as td:
            project=Path(td)/'new';replay=Path(td)/'replay';project.mkdir();(project/'artifacts').mkdir()
            for folder in ('src','review','vendor','inputs','paper'):(project/'baseline_frozen'/folder).mkdir(parents=True)
            (project/'baseline_frozen/src/run.py').write_text('# inert fixture\n')
            (project/'baseline_frozen/modeling-manifest.json').write_text('{"source":{},"project":{}}')
            reproduction.ROOT=project;reproduction.REPLAY=replay
            def intercept(*command,**kwargs):
                observed['first_command']=[str(v) for v in command]
                observed['replay_manifest_exists']=(replay/'modeling-manifest.json').is_file()
                # Probe the lock actually expected to protect parent dispatch.
                for filename in ('pipeline.lock','reproduce.lock','reproduction.lock','wrapper.lock'):
                    path=project/'artifacts'/filename
                    if not path.exists():continue
                    with path.open('a') as descriptor:
                        acquired=True
                        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        except BlockingIOError:acquired=False
                        observed[filename+'_held_through_dispatch']=not acquired
                raise StopBeforeJob
            reproduction.run=intercept
            try:reproduction.main(1,False)
            except StopBeforeJob:pass
            assert observed,'fixture never reached its intercepted first dispatch'
            if not observed['replay_manifest_exists']:issues.append('cold_replay_missing_manifest')
            if not any(v for k,v in observed.items() if k.endswith('_held_through_dispatch')):issues.append('no_parent_lock_held_during_baseline_dispatch')
    finally:reproduction.ROOT,reproduction.REPLAY,reproduction.run=original
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'lock'
        with path.open('a') as descriptor:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            inherited_code='import os,fcntl,sys; f=os.fdopen(int(sys.argv[1]),"a"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); print("inherited_ok")'
            child=subprocess.run([sys.executable,'-c',inherited_code,str(descriptor.fileno())],pass_fds=(descriptor.fileno(),),capture_output=True,text=True)
            observed['child_inherited_same_lock']=child.returncode==0
            separate_code='import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
            other=subprocess.run([sys.executable,'-c',separate_code,str(path)],capture_output=True,text=True)
            observed['separate_process_rejected_while_parent_holds']=other.returncode!=0 and 'BlockingIOError' in other.stderr
            if not observed['child_inherited_same_lock'] or not observed['separate_process_rejected_while_parent_holds']:issues.append('descriptor_lock_inheritance_failed')
    report={'reviewer_id':'/root/upgrade_code_review','independent':True,'status':'PASS' if not issues else 'CHANGES_REQUESTED',
            'scope':'Temporary cold-start fixture, stopped before the first real command. No optimizer, export, file overwrite or live dispatcher started.',
            'observed':observed,'issues':issues,'source_sha256':hashlib.sha256((ROOT/'tools/reproduce_project.py').read_bytes()).hexdigest()}
    (ROOT/'review/output-pipeline-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));return int(bool(issues))
if __name__=='__main__':sys.exit(run())
