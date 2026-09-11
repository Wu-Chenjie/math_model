#!/usr/bin/env python3
"""Bounded, isolated output-finisher guards. No actual exporter/optimizer runs."""
from pathlib import Path
import tempfile,sys,json,hashlib,fcntl,os,subprocess,time,signal
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import finish_registered_outputs as finisher
sys.path.insert(0,str(ROOT/'review'))
from check_finalization_guards import setup as evidence_setup, sha
class DispatchBoundary(BaseException):pass
class RetryBoundary(BaseException):pass

def put(root,name,value):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value) if isinstance(value,dict) else value)
def fixture(root,state=None):
    if not (root/'artifacts/formal-validation.json').exists():
        evidence_setup(root)
        frozen=json.loads((root/'artifacts/frozen-development-selection.json').read_text())
        frozen.update(challenger={},incumbent={});put(root,'artifacts/frozen-development-selection.json',frozen)
        formal=json.loads((root/'artifacts/formal-validation.json').read_text())
        formal['frozen_selection_sha256']=sha(root/'artifacts/frozen-development-selection.json');put(root,'artifacts/formal-validation.json',formal)
        put(root,'artifacts/model-check-validation.json',{'status':'PASS','fixture_current':True})
        paths={'baseline_reproduction':'artifacts/baseline-reproduction-check.json',
               'formal_physics':'artifacts/formal-validation.json','model_information_and_mathematics':'artifacts/model-check-validation.json'}
        put(root,'artifacts/model-adoption.json',{'status':'PASS','pending':[],'challenger':{},'incumbent':{},
            'economic_gate_pass':False,'decision':'retain_incumbent','adopted_configuration':{},
            'selection_sha256':sha(root/'artifacts/frozen-development-selection.json'),
            'question_results':[{'kind':k} for k in ('q2','q3','q4_2','q4_3')],
            'verification_gates':{k:{'status':'PASS','sha256':sha(root/v)} for k,v in paths.items()}})
    put(root,'artifacts/pipeline-execution.json',state or {'status':'complete','stage':'computed_results_ready','pid':os.getpid()})
def locked(path):
    with path.open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);return False
        except BlockingIOError:return True

def dispatch_checks():
    old=finisher.ROOT,finisher.subprocess.run,finisher.time.sleep,finisher.certificate_is_current,finisher.time.monotonic,finisher.os.kill
    rows=[]
    try:
        for case in ('control','transient_json_recovered','failed_pipeline','duplicate_finisher','producer_changed_before_lock','truncated_json','corrupt_after_known_pid_died','stale_model_certificate','stale_adoption_binding','adoption_status_shell','stale_formal_source','failed_child'):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td)/'project';root.mkdir();fixture(root);finisher.ROOT=root;seen=[];ticks=[];clock=[0.];kill_calls=[]
                finisher.certificate_is_current=lambda v:v.get('fixture_current') is True
                finisher.time.monotonic=lambda:clock[0]
                finisher.os.kill=old[5]
                if case=='failed_pipeline':fixture(root,{'status':'failed','error':'fixture failure'})
                if case in ('truncated_json','transient_json_recovered'):put(root,'artifacts/pipeline-execution.json','{')
                if case=='corrupt_after_known_pid_died':
                    fixture(root,{'status':'running','stage':'annual','pid':12345})
                    def mock_kill(pid,sig):
                        kill_calls.append((pid,sig))
                        if len(kill_calls)>1:raise ProcessLookupError
                    finisher.os.kill=mock_kill
                if case=='stale_model_certificate':put(root,'artifacts/model-check-validation.json',{'status':'PASS','fixture_current':False})
                if case=='stale_adoption_binding':
                    value=json.loads((root/'artifacts/model-adoption.json').read_text());value['verification_gates']['formal_physics']['sha256']='stale';put(root,'artifacts/model-adoption.json',value)
                if case=='adoption_status_shell':put(root,'artifacts/model-adoption.json',{'status':'PASS'})
                if case=='stale_formal_source':next((root/'artifacts/formal').glob('*.npz')).write_text('changed trajectory')
                def intercept(*a,**k):
                    seen.append({'command':a[0],'pipeline_locked':locked(root/'artifacts/pipeline.lock'),
                        'own_locked':locked(root/'artifacts/output-continuation.lock'),'pass_fds':list(k.get('pass_fds',()))})
                    if case=='failed_child':return subprocess.CompletedProcess(a[0],7)
                    raise DispatchBoundary
                def bounded_sleep(seconds):
                    ticks.append(seconds);clock[0]+=20.
                    if case=='corrupt_after_known_pid_died':put(root,'artifacts/pipeline-execution.json','{')
                    if case=='transient_json_recovered':fixture(root)
                    if len(ticks)>=4:raise RetryBoundary
                finisher.subprocess.run=intercept;finisher.time.sleep=bounded_sleep
                held=None
                if case=='duplicate_finisher':
                    held=(root/'artifacts/output-continuation.lock').open('a');fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
                original_ready=finisher.ready;calls=[]
                if case=='producer_changed_before_lock':
                    def change_after_read(value):
                        answer=original_ready(value);calls.append(1)
                        if len(calls)==1:fixture(root,{'status':'failed','error':'changed between locks'})
                        return answer
                    finisher.ready=change_after_read
                outcome='returned'
                try:finisher.main()
                except DispatchBoundary:outcome='dispatch_boundary'
                except RetryBoundary:outcome='unbounded_retry_boundary'
                except (RuntimeError,FileNotFoundError,AssertionError,KeyError) as e:outcome='rejected:'+str(e)
                finally:
                    finisher.ready=original_ready
                    if held:held.close()
                saved=root/'artifacts/output-continuation-execution.json'
                stored=json.loads(saved.read_text()) if saved.exists() else {}
                rows.append({'case':case,'outcome':outcome,'dispatches':seen,'sleep_calls':len(ticks),'stored_status':stored.get('status')})
    finally:finisher.ROOT,finisher.subprocess.run,finisher.time.sleep,finisher.certificate_is_current,finisher.time.monotonic,finisher.os.kill=old
    return rows

def orphan_lock_check():
    # Start a sacrificial controller that replaces its first dispatch with an inert child.
    # Only that fixture controller is SIGKILLed; no real pipeline process is touched.
    child='''from pathlib import Path
import sys,fcntl,time,os,json
r=Path(sys.argv[1]);(r/'child-ready').write_text(str(os.getpid()))
for _ in range(400):
 if (r/'probe').exists():break
 time.sleep(.01)
with (r/'artifacts/pipeline.lock').open('a') as f:
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True
 except BlockingIOError:acquired=False
(r/'child-result').write_text(json.dumps({'acquired_after_parent_exit':acquired}))
'''
    controller='''from pathlib import Path
import sys,subprocess
sys.path.insert(0,sys.argv[1]);import finish_registered_outputs as f
f.ROOT=Path(sys.argv[2]);f.certificate_is_current=lambda v:v.get('fixture_current') is True;real=subprocess.run
child=sys.argv[3]
def inert(command,**kwargs):return real([sys.executable,'-c',child,str(f.ROOT)],**kwargs)
f.subprocess.run=inert
f.main()
'''
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'project';root.mkdir();fixture(root)
        parent=subprocess.Popen([sys.executable,'-c',controller,str(ROOT/'tools'),str(root),child],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(300):
                if (root/'child-ready').exists():break
                if parent.poll() is not None:raise AssertionError('fixture controller ended before dispatch: '+parent.stderr.read().decode())
                time.sleep(.01)
            assert (root/'child-ready').exists(),'inert child did not start'
            parent.kill();parent.wait(timeout=3);put(root,'probe','now')
            for _ in range(300):
                if (root/'child-result').exists():break
                time.sleep(.01)
            assert (root/'child-result').exists(),'inert child did not report'
            return {'case':'orphan_child_lock',**json.loads((root/'child-result').read_text())}
        finally:
            if parent.poll() is None:parent.kill();parent.wait(timeout=3)

def run():
    cases=dispatch_checks();cases.append(orphan_lock_check());issues=[]
    for c in cases:
        if c['case'] in ('control','transient_json_recovered'):
            if c['outcome']!='dispatch_boundary' or not c['dispatches'][0]['pipeline_locked'] or not c['dispatches'][0]['own_locked']:issues.append('control_locks')
        elif c['case']=='orphan_child_lock':
            if c['acquired_after_parent_exit']:issues.append('orphan_child_loses_pipeline_lock')
        elif c['case']=='truncated_json':
            if c['outcome']=='unbounded_retry_boundary':issues.append('corrupt_producer_state_unbounded_retry')
        elif c['case']=='failed_child':
            if not c['outcome'].startswith('rejected:') or len(c['dispatches'])!=1:issues.append(c['case'])
        elif not c['outcome'].startswith('rejected:') or c['dispatches']:issues.append(c['case'])
        if c['case'] not in ('control','transient_json_recovered','duplicate_finisher','orphan_child_lock') and c.get('stored_status')!='failed':issues.append(c['case']+'_not_failed_closed')
    report={'status':'CHANGES_REQUESTED' if issues else 'PASS_WITHIN_SCOPE','independent':True,'reviewer_id':'/root/upgrade_code_review',
        'scope':'Temporary full baseline/formal/adoption evidence fixtures; only certificate authenticator isolated; all production subprocess calls intercepted. One inert fixture controller is killed to test lock inheritance. No annual job, export, compiler or final review is run.',
        'cases':cases,'issues':issues,'source_sha256':hashlib.sha256((ROOT/'tools/finish_registered_outputs.py').read_bytes()).hexdigest()}
    (ROOT/'review/output-finisher-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));return bool(issues)
if __name__=='__main__':sys.exit(run())
