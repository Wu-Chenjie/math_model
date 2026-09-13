"""Compile and run checks; the rational replay must consume this run's witness."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];records=[]
cc=os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
assert cc,'C++17 compiler required'
(R/'bin').mkdir(exist_ok=True);(R/'artifacts').mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
witness=R/'artifacts/residual-witness.json'
for name in ['test_geometry_revision','test_joint','test_controller','test_adaptive_optical','test_shortcut_controller','test_action_budget','test_scan_fee','test_discovery','test_variable_cover']:
 source=R/'tests'/f'{name}.cpp';binary=R/'bin'/name
 cmd=[cc,'-O2','-std=c++17',str(source),'-o',str(binary)];begin=time.time();out=subprocess.run(cmd,capture_output=True,text=True)
 if out.returncode:raise RuntimeError(out.stderr)
 run_cmd=[str(binary)];extra={}
 if name=='test_geometry_revision':
  witness.unlink(missing_ok=True)
  with tempfile.TemporaryDirectory(prefix='geometry-export-') as tmp:
   bad=subprocess.run([str(binary),str(Path(tmp)/'absent'/'witness.json')],cwd=tmp,capture_output=True,text=True)
   assert bad.returncode!=0 and 'PASS' not in bad.stdout
   run_cmd.append(str(witness));out=subprocess.run(run_cmd,cwd=tmp,capture_output=True,text=True)
  assert out.returncode==0 and witness.is_file() and witness.stat().st_mtime>=begin
  extra={'source_sha256':digest(source),'binary_sha256':digest(binary),'fresh_witness_sha256':digest(witness),'invalid_output_rejected':True,'execution_cwd':'fresh temporary directory'}
 else:out=subprocess.run(run_cmd,cwd=R,capture_output=True,text=True)
 records.append({'name':name,'compile_command':cmd,'command':run_cmd,'exit_code':out.returncode,'runtime_s':time.time()-begin,'stdout':out.stdout,'stderr':out.stderr,**extra})
 if out.returncode:raise RuntimeError(records[-1])
 print(name,'PASS',flush=True)
for name in ['replay_residual_fraction.py','test_bridge_deadline.py']:
 cmd=[sys.executable,str(R/'tests'/name)]
 if name.startswith('replay'):cmd.append(str(witness))
 begin=time.time();out=subprocess.run(cmd,cwd=R,capture_output=True,text=True)
 records.append({'name':name,'command':cmd,'exit_code':out.returncode,'runtime_s':time.time()-begin,'stdout':out.stdout,'stderr':out.stderr})
 if out.returncode:raise RuntimeError(records[-1])
 print(name,'PASS',flush=True)
assert json.loads((R/'artifacts/residual-fraction-replay.json').read_text())['witness_sha256']==records[0]['fresh_witness_sha256']
(R/'artifacts/regression-tests.json').write_text(json.dumps({'status':'PASS','records':records},ensure_ascii=False,indent=2))
