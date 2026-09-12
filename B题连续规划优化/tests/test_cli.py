import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=subprocess.run([sys.executable,str(root/'src/bridge.py'),'--help'],capture_output=True,text=True)
assert p.returncode==0,p.stderr
assert '--planner-depth' in p.stdout,'planner-depth switch missing from bridge'
assert '--strategy' in p.stdout,'baseline/joint strategy switch missing'
for depth in [-1,4]:
    p=subprocess.run([str(root/'robot.exe'),'3','35','0',str(depth)],input='',capture_output=True,text=True)
    assert p.returncode!=0 and 'planner depth' in p.stderr,p.stderr
print('PASS CLI: planner-depth discoverable, invalid depths rejected before sensor I/O')
