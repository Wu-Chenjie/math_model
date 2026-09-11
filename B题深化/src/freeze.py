"""Freeze the optimization handoff while leaving the original archive unchanged."""
import hashlib,importlib.metadata,json,platform,subprocess
from pathlib import Path
from datetime import datetime,timezone
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def include(p):
 rel=p.relative_to(ROOT)
 return '__pycache__'not in rel.parts and p.name!='manifest.json'and not(p.name.startswith(('paperpage','contact'))or p.suffix in ['.aux','.toc','.out','.log'])
files=[p for p in ROOT.rglob('*')if p.is_file()and include(p)]
versions={k:importlib.metadata.version(k)for k in ['numpy','scipy','matplotlib']}
for exe in ['g++','pandoc','xelatex']:
 r=subprocess.run([exe,'--version'],capture_output=True,text=True);versions[exe]=r.stdout.splitlines()[0]
manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'platform':platform.platform(),'versions':versions,
 'frozen_options':{'grid_h':999,'shiftA':'1/6','shiftB':'11/12','include_origin':False,'routing':'joint_multistart_2opt','opportunistic_baseline_m':50,'early_m':35},
 'evidence':{'paired_rows':2400,'stress_cases':1000,'original_mock_cases':66,'official_formal_cases':0,'q2_rational_nodes':166},
 'sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p)for p in sorted(files)}}
old=ROOT.parent/'B题成果';original=ROOT.parent/'26B-team-v1.0.0'
manifest['baseline_manifest_sha256']=sha(old/'manifest.json')
manifest['original_simulator_sha256']={str(p.relative_to(original)).replace('\\','/'):sha(p)for p in sorted(original.rglob('*.py'))}
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
out=ROOT.parent/'B题_优化交接包.zip'
with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=6)as z:
 for p in files+[ROOT/'manifest.json']:z.write(p,str(Path('B题优化')/p.relative_to(ROOT)))
 baseline=json.loads((old/'manifest.json').read_text(encoding='utf-8'))
 for name in list(baseline['sha256'])+['manifest.json']:
  z.write(old/name,str(Path('B题成果')/name))
 for p in original.rglob('*'):
  if p.is_file()and p.suffix in ['.py','.md','.json']and p.name!='team.json'and not any(x in ['__pycache__','runs']for x in p.relative_to(original).parts):z.write(p,str(Path('26B-team-v1.0.0')/p.relative_to(original)))
print('Frozen',len(files),'files; archive bytes',out.stat().st_size)
