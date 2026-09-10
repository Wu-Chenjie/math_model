"""Snapshot existing verified inputs and explicitly record inherited assumptions."""
from pathlib import Path
import shutil,json,hashlib
from run_comparison import ROOT,BASE,CANDIDATES,dump

def main():
    old=json.loads((BASE/'modeling-manifest.json').read_text())
    for path in (BASE/'inputs').rglob('*'):
        if path.is_file():
            dst=ROOT/'inputs'/path.relative_to(BASE/'inputs');dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,dst)
    cache=ROOT/'inputs/prepared';cache.mkdir(exist_ok=True)
    for name in ['data.npz','forecasts.npz','data-audit.json','forecast-selection.json','controller-selection.json']:
        shutil.copy2(BASE/'artifacts'/name,cache/name)
    deps=ROOT/'inputs/baseline-code';deps.mkdir(exist_ok=True)
    for name in ['forecasting.py','dispatch.py','prepare_data.py']:
        shutil.copy2(BASE/'src'/name,deps/name)
    m=json.loads((ROOT/'modeling-manifest.json').read_text())
    m['project'].update(stage='modeling',status='in_progress')
    m['source']=old['source'];m['source']['data_files']=[p.relative_to(ROOT).as_posix() for p in (ROOT/'inputs').rglob('*') if p.is_file() and p.suffix!='.pdf']
    m['source']['input_hashes']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'inputs').rglob('*') if p.is_file()}
    m['framing']=old['framing'];m['framing']['objectives']=['Compare causal hierarchical controllers under common data/fees/information; select by January or previous-days costs only.']
    m['framing']['assumptions']+=['Current actual price is not used by new controllers; past and released price forecasts only.',
                                 'Finite-dimensional affine policy / approximate Markov state / common-open-loop scenario MPC are restricted classes.']
    m['models']['candidates']=[{'name':name,'target_output':'Causal contracts, battery actions and 334-day realized costs',
        'assumptions':[upper,lower,'daily terminal6000','same-slot net-load feedback'],
        'data_requirements':['verified original inputs','January-selected forecasts','preceding28day residuals'],
        'failure_mode':'forecast or policy approximation fails outside training scenarios',
        'diagnostic':'causal annual replay, feasibility, leakage, grid and monthly checks'} for name,(upper,lower) in CANDIDATES.items()]
    m['pending']=['annual candidate replay','selection and validation','independent review']
    dump(ROOT/'modeling-manifest.json',m)
    audit=json.loads((BASE/'artifacts/data-audit.json').read_text())
    audit['incremental_source']='Byte-identical copies from accepted baseline; input hashes re-evaluated.'
    audit['evaluation_boundary']='Same fixed 2025 data previously examined; incremental chronological replay, not a newly acquired external holdout.'
    audit['checks'].append({'name':'snapshot_hash_matches_parent_sources','status':'pass'})
    for p in (BASE/'inputs').rglob('*'):
        if p.is_file():assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((ROOT/'inputs'/p.relative_to(BASE/'inputs')).read_bytes()).digest()
    dump(ROOT/'artifacts/data-audit.json',audit)
    print('Snapshot verified')

if __name__=='__main__':main()
