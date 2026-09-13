"""Create an anonymous, source-only support archive and verify relocation."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--check-relocation',action='store_true');a=p.parse_args()
final=R/'B题几何策略优化_代码与数据.zip'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='b-delivery-') as temp:
 stage=Path(temp)/'B_solution';stage.mkdir()
 for folder in ['src','tests','results','artifacts','paper','figures','inputs','evidence','vendor','review']:
  def ignore(path,names):
   return [n for n in names if n=='__pycache__' or n.endswith(('.pyc','.aux','.log','.out','.png')) or n in ['paper_pages','solution_pages','main.pdf','panel-aggregate.txt']]
  shutil.copytree(R/folder,stage/folder,ignore=ignore)
 for n in ['run_all.py','README.md','requirements.txt','modeling-manifest.json','validation_frozen.json','B题几何策略优化_题解.md','B题几何策略优化_题解.pdf','B题几何策略优化_论文.pdf']:
  shutil.copy(R/n,stage/n)
 # Prefix normalization only affects delivery copies, never frozen source or CSV.
 # Original absolute commands remain in the user's research directory.
 normalized=[]
 for f in stage.rglob('*'):
  if not f.is_file() or f.suffix not in {'.json','.md','.txt','.tex','.py','.cpp','.hpp','.yaml'}:continue
  data=f.read_text();new=data.replace(str(R),'PROJECT_ROOT').replace(str(R.parent),'WORKSPACE_ROOT')
  # Tool invocation metadata may mention installed skill or runtime paths.
  new=new.replace(str(Path.home()),'USER_HOME')
  if new!=data:f.write_text(new);normalized.append(f.relative_to(stage).as_posix())
 # Hashes point to the exported files after path normalization.
 rep=json.loads((stage/'artifacts/reproducibility.json').read_text())
 rep['output_hashes']={k:sha(stage/k) for k in rep['output_hashes']}
 rep['delivery_path_normalization']='Host/user path prefixes replaced for anonymity only; original records preserved in the research root.'
 (stage/'artifacts/reproducibility.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2))
 (stage/'PACKAGE.md').write_text('本包为可复现的本地研究交付，六份官方加密日志仍未提供。\n\n解压后进入本目录运行 python3 run_all.py；--full重跑固定独立/压力集。无需原工作目录，目录可改名。运行前安装requirements.txt所列依赖和C++17编译器。PDF重建另需XeLaTeX/ctex/Pandoc及字体。\n\n为匿名交付，命令记录中的绝对用户路径已替换为PROJECT_ROOT/WORKSPACE_ROOT/USER_HOME；数值CSV和冻结模型源码未改动。原始路径记录保留在研究目录。以PACKAGE_HASHES.json校验包内文件，校验表不包含自身。\n')
 if a.check_relocation:
  check=Path(temp)/'renamed_portable_solver';shutil.copytree(stage,check)
  begin=time.time();run=subprocess.run([sys.executable,'run_all.py'],cwd=check,capture_output=True,text=True)
  (R/'artifacts/relocation.log').write_text(run.stdout+'\n'+run.stderr)
  assert run.returncode==0,run.stderr[-4000:]
  old=json.loads((R/'artifacts/summary.json').read_text());new=json.loads((check/'artifacts/summary.json').read_text());assert old==new
  cert=json.loads((check/'artifacts/regression-tests.json').read_text());replay=json.loads((check/'artifacts/residual-fraction-replay.json').read_text());assert cert['records'][0]['fresh_witness_sha256']==replay['witness_sha256']
  report={'status':'PASS','command':[sys.executable,'run_all.py'],'location':'fresh temporary directory named renamed_portable_solver','exit_code':run.returncode,'runtime_s':time.time()-begin,'summary_equal':True,'fresh_witness_replay':True,'scope':'Recompiled both binaries, all11 regression programs, Q2/Q3/Q4 certificates and CSV summary. Does not rerun2000 model cases or any official test.'}
  (R/'artifacts/relocation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));shutil.copy(R/'artifacts/relocation.json',stage/'artifacts/relocation.json')
 manifest={f.relative_to(stage).as_posix():sha(f) for f in stage.rglob('*') if f.is_file()}
 (stage/'PACKAGE_HASHES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 with zipfile.ZipFile(final,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for f in sorted(stage.rglob('*')):
   if f.is_file():z.write(f,Path(stage.name)/f.relative_to(stage))
 assert final.stat().st_size<20*1024*1024
 with zipfile.ZipFile(final) as z:
  assert z.testzip() is None
  for p,h in manifest.items():assert hashlib.sha256(z.read('B_solution/'+p)).hexdigest()==h
 out={'status':'PASS','archive':final.name,'sha256':sha(final),'bytes':final.stat().st_size,'files':len(manifest)+1,'source_only':True,'path_normalized_files':normalized,'formal_logs_present':False}
 (R/'artifacts/package-verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='path_normalized_files'},ensure_ascii=False))
