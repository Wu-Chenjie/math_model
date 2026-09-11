"""Freeze current deliverables and build a compact handoff archive."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from datetime import datetime,timezone
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def included(p):
    rel=p.relative_to(ROOT)
    if '__pycache__'in rel.parts or p.name=='manifest.json':return False
    if rel.parts[0]=='results'and (p.name.startswith(('paperpage','题面','contact','manuscript'))):return False
    return p.suffix not in ['.aux','.toc','.out']
files=[p for p in ROOT.rglob('*')if p.is_file()and included(p)]
versions={k:importlib.metadata.version(k)for k in ['numpy','scipy','matplotlib']}
for program in ['g++','pandoc','xelatex']:
    r=subprocess.run([program,'--version'],capture_output=True,text=True);versions[program]=r.stdout.splitlines()[0]
manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'platform':platform.platform(),
          'versions':versions,'frozen_options':{'problem3_points':7,'problem4_spacing':950,'problem4_points':31,'early_clear_radius':35,'error_half_angle':1.005,'optical_cell_max_side':28},
          'evidence':{'main_cases':400,'paired_main_and_ablation_rows':1600,'stress_cases':1000,'original_kernel_cases':60,'local_HTTP_cases':6,'official_formal_cases':0},
          'sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p)for p in sorted(files)}}
original=ROOT.parent/'26B-team-v1.0.0'
manifest['original_simulator_sha256']={str(p.relative_to(original)).replace('\\','/'):sha(p)for p in sorted(original.rglob('*.py'))}
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
out=ROOT.parent/'B题_完整交接包.zip'
with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=6) as z:
    for p in files+[ROOT/'manifest.json']:z.write(p,str(Path('B题成果')/p.relative_to(ROOT)))
    # Include the small original simulator dependency, excluding old runs/cache.
    for p in original.rglob('*'):
        if p.is_file()and p.suffix in ['.py','.md','.json']and not any(q in ['__pycache__','runs']for q in p.relative_to(original).parts):
            if p.name=='team.json':continue  # Never package team identifiers.
            z.write(p,str(Path('26B-team-v1.0.0')/p.relative_to(original)))
print(f'Frozen {len(files)} files; archive {out.name}: {out.stat().st_size} bytes')
