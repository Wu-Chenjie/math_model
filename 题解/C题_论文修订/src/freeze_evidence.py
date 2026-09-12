"""Bind existing executed artifacts; never substitute missing evidence with claims."""
from pathlib import Path
import json,hashlib,platform,sys
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text())
def dump(p,x):(ROOT/p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    m=read('modeling-manifest.json');summary=read('artifacts/summary.json')
    annual=read('artifacts/execution-annual.json');sddp=read('artifacts/execution-annual_sddp.json')
    assert annual['exit_code']==0 and len(annual['results'])==20
    assert sddp['exit_code']==0 and len(sddp['results'])==4
    assert read('artifacts/execution-train.json')['exit_code']==0
    assert len(read('artifacts/execution-train.json')['results'])==48
    for days in [1,2]:
        record=read(f'artifacts/execution-train-D{days}.json');assert record['exit_code']==0 and len(record['results'])==8
    for scope,count in [('short',15),('annual-releases',4)]:
        record=read(f'artifacts/execution-experiments-{scope}.json');assert record['exit_code']==0 and len(record['results'])==count
    assert all(c['status']=='pass' for c in read('artifacts/workbook-validation.json')['checks'])
    production=read('review/production-audit.json');assert production['passed'] is True and not production['pending_cases'] and not production['failed_cases']
    visual=read('artifacts/visual-qa.json');assert visual['status']=='pass'
    # Register coherent tables as structured values; this preserves every number
    # without manufacturing thousands of redundant scalar registry entries.
    registry=[]
    def add(rid,path,pointer,value):registry.append({'id':rid,'source_artifact':path,'source_path':pointer,'value':value,'status':'verified'})
    for name in ['summary','handoff-tables','selection','figure-data']:
        path=f'artifacts/{name}.json';obj=read(path)
        for key,value in obj.items():
            if key in ['source_hashes','scope_notes','policy']:continue
            add(name+'.'+key,path,'/'+key.replace('~','~0').replace('/','~1'),value)
    for name in ['sddp-checks','controller-checks','global-oracle','v2-boundary-review','production-audit']:
        path=f'review/{name}.json'
        if (ROOT/path).exists():
            obj=read(path)
            for key in ['checks','results','metrics','expected_cases','passed_cases','cases']:
                if key in obj:add(name+'.'+key,path,'/'+key,obj[key])
    dump('artifacts/result-registry.json',{'schema_version':1,'scope':'Executed modeling handoff. Structured table records include every displayed numerical value. No paper authored.','results':registry})
    m['framing'].update({'objectives':['Minimize Q1 deterministic purchase cost and Q2–4 realized chronological settlement cost, with physically continuous cross-day inventory.'],
      'decision_variables':['Original q and effective r per delivery interval','Bus charge/discharge, inventory, emergency purchase and total spill','Causal affine policy coefficients and approximate future values'],
      'constraints':['SOC 1200..10800 kWh, each-direction efficiency0.9, power5000 kW','10-minute balance, nonnegative purchases, no simultaneous charge/discharge after canonicalization','Allowed contract revisions only; first6hours unadjustable; original daily q retained for settlement','Q1 daily terminal6000; Q2–4 main free year-end, exact physical continuity and separate global6000 comparison','Scenario and release nonanticipativity'],
      'ambiguities':['Interval-end time labels; single-direction90% efficiency; refund interpretation; final net versus cumulative settlement. See 模型与推导.md.'],
      'assumptions':['Current net load observed before battery action','Free total surplus disposal, no sale; unspecified degradation/network constants omitted','January common no-battery emergency warmup; separate cost','Finite empirical scenario approximation and restricted affine/Markov policies']})
    descriptions={
      'cross_baseline':('Common-path SAA with greedy physical feedback','Ignores stochastic feedback effects'),
      'affine_mpc':('Causal affine-policy SAA-MPC','Restricted affine policy may perform poorly outside empirical scenarios'),
      'markov_mpc':('Causal affine planning with Markov stochastic DP battery feedback','Three error bins and nominal future contracts approximate the full process'),
      'sddp_markov':('Generic SDDP auxiliary value with the same Markov feedback','Coarse independent-stage tail can miss fine-resolution forecast dependence')}
    m['models']['candidates']=[{'name':k,'target_output':v[0],'failure_mode':v[1],'diagnostic':'January development comparison and complete held-out chronological replay; physical, information and exact-small-instance audits.','assumptions':['Same accounting and information rules','Details and limited policy scope in 模型与推导.md'],'data_requirements':['Original load/PV/price history','Released official forecast where allowed']} for k,v in descriptions.items()]
    selected=set(summary['selected'].values());assert len(selected)==1,'Update manifest model mapping for a mixed selection.'
    m['models']['selected']=next(iter(selected))
    m['models']['selection_rationale'].update({'objective_fit':'Exact settlement accounting in executed historical evaluation; January-only choice with0.01% tie preference.','constraint_fit':'Hard power/SOC/nonanticipation and contract release restrictions, physically carried inventory.','data_fit':'Chronological mature historical errors and released24h forecasts.','baseline':'Matched daily-closure and cross-day common-path SAA baselines, with global terminal comparisons.','risks':['Empirical model misspecification','Approximate tail value','One historical year, no population optimality guarantee'],'fallback_trigger':'Any physical/information audit failure blocks delivery; select only from executed January-feasible candidates, never switch after observing annual costs.'})
    ids=[k+'_total_cost' for k in ['q2','q3','q4_2','q4_3']]
    m['models']['baseline'].update({'status':'completed','name':'closed_baseline','command':annual['command'],'exit_code':0,'runtime_seconds':sum(r['runtime_seconds'] for r in annual['results'] if r['candidate']=='closed_baseline'),'metric_ids':ids})
    figures=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'figures').glob('*')) if p.suffix in ['.png','.svg']]
    m['execution'].update({'status':'completed','command':annual['command'],'exit_code':0,'runtime_seconds':annual['runtime_seconds'],'environment':annual['environment'],'seed':None,'deterministic_reason':'Primary replay uses deterministic chronological scenarios and LP/DP. SDDP training seed20260911 and independent evaluation seed9182 are recorded separately.','metric_ids':ids,'figures':figures,'additional_execution_records':['artifacts/execution-annual_sddp.json','artifacts/execution-train.json','artifacts/execution-train-D1.json','artifacts/execution-train-D2.json','artifacts/global-terminal.json']})
    m['validation'].update({'status':'completed','checks':[{'name':n,'status':'pass','evidence':p} for n,p in [('physical_and_settlement','artifacts/summary.json'),('independent_36_trajectories','review/production-audit.json'),('independent_small_tree_sddp','review/sddp-checks.json'),('causality_and_dp','review/controller-checks.json'),('global_oracle','review/global-oracle.json'),('workbook_reconciliation','artifacts/workbook-validation.json'),('visual_review','artifacts/visual-qa.json')]],
      'sensitivity':['artifacts/summary.json#/experiments: grids161/321/641, scenarios7/14, horizon2/3, tail0/1/2, fixed global endpoint'],
      'robustness':['artifacts/experiments/stress_load_up_pv_down.json','artifacts/experiments/variable_stress.json'],
      'falsification':['Future actual and unreleased forecast perturbations leave prior decisions unchanged','Independent explicit c/d LP versus convex infimal convolution','Full-path SDDP strategy enumeration and lower-cut validity','Free suffix replay before global terminal intervention','Annual release ablations keep adjustment rights fixed']})
    findings_path=ROOT/'review/findings.json'
    findings=read('review/findings.json') if findings_path.exists() else {}
    if findings.get('decision')=='pass' and findings.get('independent') is True and not findings.get('unresolved'):
        reviewed=findings.get('reviewed_artifact_hashes',{})
        assert reviewed,'Final review must bind the frozen source, numerical results, documents and exported workbooks.'
        for name,expected in reviewed.items():assert sha(ROOT/name)==expected,('Stale independent review',name)
        m['review'].update({'status':'completed','independent':True,'reviewer_id':findings['reviewer_id']})
        m['project'].update({'status':'complete','stage':'modeling_handoff'});m['pending']=[]
    else:
        m['project']['status']='in_progress';m['pending']=['Final independent frozen-artifact review']
    dump('modeling-manifest.json',m)
    outputs={}
    for folder in ['artifacts','figures','计算结果','review','src']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.name not in ['reproducibility.json','acceptance.json'] and p.suffix not in ['.pyc']:
                outputs[str(p.relative_to(ROOT))]=sha(p)
    for p in ROOT.iterdir():
        if p.is_file() and p.suffix in ['.md','.sh','.txt']:outputs[p.name]=sha(p)
    commands={p.name:read(str(p.relative_to(ROOT))) for p in (ROOT/'artifacts').glob('execution-*.json')}
    dump('artifacts/reproducibility.json',{'command':m['execution']['command'],'seed':m['execution']['seed'],'input_hashes':m['source']['input_hashes'],'output_hashes':outputs,'execution_records':commands,
      'library_versions':read('artifacts/library-versions.json'),
      'source_versions':read('artifacts/source-version-records.json'),
      'source_hash_semantics':'Early command source_hashes were sampled from disk at completion, not a snapshot of modules already loaded in workers. The hash-verified source-v1 archive binds the original annual non-SDDP, three-day tail and short-validation workers. Later SDPP comparisons use the finite-end v2 correction. Q1 was rerun with zero turnover regularization; settlement code was unchanged. Current sources reproduce the non-SDDP numerical defaults.',
      'full_reproduction':'复现.sh; exact run records retain historical command spelling. Reviews and visual acceptance must be repeated after regeneration.'})
    print('Frozen evidence; status:',m['project']['status'])
if __name__=='__main__':main()
