"""Portable frozen reproduction entry point. Never starts official tests."""
from pathlib import Path
import subprocess,sys,argparse,shutil,json,time,os
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--paper',action='store_true');a=p.parse_args()
cc=os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++');assert cc,'C++17 compiler required'
(R/'bin').mkdir(exist_ok=True);records=[]
def run(cmd,cwd=R):
 begin=time.time()
 # Explicit UTF-8: subprocess text mode otherwise decodes child output with the host
 # locale (e.g. GBK on Chinese Windows) and crashes on UTF-8 tracebacks.
 out=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');rec={'command':cmd,'cwd':str(cwd.relative_to(R)) if cwd.is_relative_to(R) else str(cwd),'exit_code':out.returncode,'runtime_s':time.time()-begin,'stdout':out.stdout,'stderr':out.stderr};records.append(rec)
 # UTF-8 on write too: the default locale encoding (cp936 on Chinese Windows) would
 # produce a log that is not valid UTF-8 and breaks downstream readers.
 (R/'artifacts/reproduction-log.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 if out.returncode:raise RuntimeError(rec)
 print('PASS',cmd[0],cmd[-1],flush=True)
run([cc,'-O2','-std=c++17','src/robot.cpp','-o','robot.exe'])
run([cc,'-O2','-std=c++17','src/benchmark.cpp','-o','bin/benchmark_final'])
run([sys.executable,'src/build_overview_figure.py'])
run([sys.executable,'tests/run_checks.py'])
run([cc,'-O2','-std=c++17','tests/test_q3_radius.cpp','-o','bin/test_q3_radius']);run([str(R/'bin/test_q3_radius')]);run([sys.executable,'tests/q3_coverage_bound.py'])
run([sys.executable,'src/q2_full_domain_certificate.py','artifacts/q2-certificate.json'])
run([sys.executable,'src/q4_area_arc_certificate.py','artifacts/q4-lower-bound.json'])
if a.full:
 run([sys.executable,'src/run_experiments.py','--suite','iid'])
 run([sys.executable,'src/run_experiments.py','--suite','stress'])
run([sys.executable,'src/analyze_revision.py'])
if a.paper:
 run([sys.executable,'src/build_paper_assets.py'])
 for document in ['main.tex','AI工具使用详情.tex']:
  for _ in range(2):run(['xelatex','-interaction=nonstopmode','-halt-on-error',document],R/'paper')
 shutil.copy2(R/'paper/AI工具使用详情.pdf',R/'AI工具使用详情.pdf')
print('Core checks and frozen-data analysis completed; full simulations run only with --full.')
