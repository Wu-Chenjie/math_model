import hashlib,json,platform,subprocess,importlib.metadata
from pathlib import Path
from datetime import datetime,timezone
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def include(p):
 r=p.relative_to(ROOT)
 return not any(x in ['__pycache__','qa']for x in r.parts)and p.name!='manifest.json'and p.suffix not in ['.aux','.toc','.log','.out']
files=[p for p in ROOT.rglob('*')if p.is_file()and include(p)]
versions={k:importlib.metadata.version(k)for k in ['numpy','scipy','matplotlib']}
for exe in ['g++','pandoc','xelatex']:
 q=subprocess.run([exe,'--version'],capture_output=True,text=True);versions[exe]=q.stdout.splitlines()[0]
old={n:json.loads((ROOT.parent/n/'manifest.json').read_text(encoding='utf-8'))for n in ['B题成果','B题优化','B题深化']}
m={'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'platform':platform.platform(),'versions':versions,
 'configuration':{'default_method':5,'second_station':[750,300],'layout_points':21,'known16_rule':'between completed nodes','exact_proxy_dp_limit':12,'optional_position_error_m':.4},
 'evidence':{'nominal_strategy_rows':8880,'position_diagnostic_rows':320,'robust_complete_runs':160,'original_mock_cases':66,'official_formal_cases':0,'positive_margin_leaves':21996,'fixed_site_lower_bound':15},
 'sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p)for p in sorted(files)},'previous_manifest_hashes':{n:sha(ROOT.parent/n/'manifest.json')for n in old}}
(ROOT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
original=ROOT.parent/'26B-team-v1.0.0';target=ROOT.parent/'B题_第四轮鲁棒优化交接包.zip'
with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=6)as z:
 for p in files+[ROOT/'manifest.json']:z.write(p,str(Path('B题鲁棒优化')/p.relative_to(ROOT)))
 for name,manifest in old.items():
  for rel in list(manifest['sha256'])+['manifest.json']:z.write(ROOT.parent/name/rel,str(Path(name)/rel))
 for p in original.rglob('*'):
  if p.is_file()and p.suffix in ['.py','.md','.json']and p.name!='team.json'and not any(x in ['__pycache__','runs']for x in p.relative_to(original).parts):z.write(p,str(Path('26B-team-v1.0.0')/p.relative_to(original)))
print('Frozen files',len(files),'archive bytes',target.stat().st_size)
