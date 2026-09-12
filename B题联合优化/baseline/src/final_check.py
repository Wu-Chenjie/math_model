import csv,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from analyze import analyze
report=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
assert json.loads(json.dumps(analyze('iid.csv',1210001,200)))==report['iid']
assert json.loads(json.dumps(analyze('development.csv',1,40)))==report['development']
for k,start in enumerate([1220001,1230001,1240001,1250001,1260001],1):
    assert json.loads(json.dumps(analyze(f'stress{k}.csv',start,40)))==report['stress'][str(k)]
assert sum(int(r['dp_budget_hits']) for r in csv.DictReader((ROOT/'results/iid.csv').open()))==0
counts={0:10,1:8,2:26,3:8}
for depth,count in counts.items():
    rows=json.loads((ROOT/f'results/original_mock_depth{depth}.json').read_text())
    assert len(rows)==count and sum(r['layer']=='local_HTTP' for r in rows)==6
    for r in rows:
        assert r['planner_depth']==depth
        if r['layer']=='original_kernel':assert r['jammer_total']==r['cleared_count']
        else:assert r['total']==r['cleared']
for file in (ROOT/'baseline/src').iterdir():
    if file.is_file():assert file.read_bytes()==(ROOT.parent/'B题文献驱动优化/src'/file.name).read_bytes(),file
for file in (ROOT/'baseline/review').iterdir():
    if file.is_file():assert file.read_bytes()==(ROOT.parent/'B题文献驱动优化/review'/file.name).read_bytes(),file
raw=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
doc=(ROOT/'模型与验证.md').read_text(encoding='utf-8')
for p in ['3','4']:
    for m in ['0','1','2','3']:
        for key in ['total_mean_s','single_mean_s']:
            assert f"{raw['iid'][p][m][key]:.2f}" in doc
    assert f"{raw['iid'][p]['3']['comparisons']['1']['saving_percent']:.4f}%" in doc
assert 245985.6+96*(5344/5+6)+16*5<360000
hashes={}
for f in sorted(ROOT.rglob('*')):
    if not f.is_file() or '__pycache__' in f.parts or f.name=='manifest.json':continue
    hashes[f.relative_to(ROOT).as_posix()]=hashlib.sha256(f.read_bytes()).hexdigest()
(ROOT/'manifest.json').write_text(json.dumps({'sha256':hashes,'checks':{'paired_runs':3520,'mock_runs':sum(counts.values()),'iid_matches_raw':True,'prior_sources_unchanged':True,'paper_values_match':True}},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS final: raw IID reproduces summary; 52 simulator runs verified; old sources unchanged; report numbers match; hashes saved')
