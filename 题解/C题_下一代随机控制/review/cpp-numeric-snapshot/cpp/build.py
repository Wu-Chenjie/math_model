"""Build the native kernels; numerical optimization flags are deliberately strict."""
from pathlib import Path
import subprocess,json,hashlib,platform
R=Path(__file__).resolve().parent
command=['clang++','-std=c++17','-O3','-ffp-contract=off','-fno-fast-math','-dynamiclib',str(R/'kernels.cpp'),'-o',str(R/'libmicrogrid.dylib')]
subprocess.run(command,check=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(R/'build.json').write_text(json.dumps({'command':command,'compiler':subprocess.check_output(['clang++','--version'],text=True),'platform':platform.platform(),'source_sha256':sha(R/'kernels.cpp'),'binary_sha256':sha(R/'libmicrogrid.dylib')},indent=2)+'\n')
print(R/'libmicrogrid.dylib')
