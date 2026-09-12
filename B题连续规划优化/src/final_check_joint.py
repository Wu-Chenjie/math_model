import csv,json,hashlib,math
from pathlib import Path
from analyze_joint import ROOT,paired
for stage,start,method in [(1,1510001,38),(2,1710001,39),(3,1910001,56)]:
    suffix='' if stage==1 else str(stage)
    filename='summary.json' if stage==1 else f'summary_stage{stage}.json'
    result=json.loads((ROOT/'results'/filename).read_text(encoding='utf-8'))
    actual=paired(f'iid{suffix}_baseline.csv',f'iid{suffix}_final.csv',start,200,method)
    assert json.loads(json.dumps(actual))==result['iid']
    for k in range(1,6):
        prefix=f'stress{k}' if stage==1 else f'stress{stage}_{k}'
        check=paired(f'{prefix}_0.csv',f'{prefix}_{method}.csv',start+10000*k,40,method)
        assert json.loads(json.dumps(check))==result['stress'][str(k)]
for file in (ROOT/'baseline/src').iterdir():
    if file.is_file():assert file.read_bytes()==(ROOT.parent/'B题动态规划/src'/file.name).read_bytes(),file
for file in (ROOT/'baseline/review').iterdir():
    if file.is_file():assert file.read_bytes()==(ROOT.parent/'B题动态规划/review'/file.name).read_bytes(),file
data=json.loads((ROOT/'results/summary_stage3.json').read_text(encoding='utf-8'))
assert data['iid']['4']['saving_percent']>10
assert 100*(1-data['iid']['4']['new_single_s']/data['iid']['4']['baseline_single_s'])>10
for name,count in [('joint',26),('baseline',10)]:
    rows=json.loads((ROOT/f'results/original_mock_{name}_depth2.json').read_text())
    assert len(rows)==count
    for r in rows:
        if r['layer']=='local_HTTP':assert r['total']==r['cleared']
        else:assert r['jammer_total']==r['cleared_count']
doc=(ROOT/'最终结果.md').read_text(encoding='utf-8');readme=(ROOT/'README.md').read_text(encoding='utf-8')
for p in ['3','4']:
    for key in ['baseline_single_s','new_single_s','saving_percent']:
        value=f"{data['iid'][p][key]:.2f}";assert value in doc and value in readme
bound=(133*5344+16*107*77+16*1520)/5+516*6+1840*3+32
assert abs(bound-182027.2)<1e-6 and bound<360000
assert 354574.4<360000
files={}
for file in sorted(ROOT.rglob('*')):
    if not file.is_file() or '__pycache__' in file.parts or file.name=='manifest.json':continue
    files[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
summary={'three_stage_paired_runs':4800,'q4_total_improvement_pct':data['iid']['4']['saving_percent'],'q4_single_improvement_pct':100*(1-data['iid']['4']['new_single_s']/data['iid']['4']['baseline_single_s']),
         'q3_total_improvement_pct':data['iid']['3']['saving_percent'],'original_sources_unchanged':True,'default_mock_runs':26,'baseline_mock_runs':10,'report_matches_data':True}
(ROOT/'manifest.json').write_text(json.dumps({'verification':summary,'sha256':files},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
