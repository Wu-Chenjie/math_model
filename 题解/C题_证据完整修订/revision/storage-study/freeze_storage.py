"""Register executed storage evidence and close gates only against current independent QA."""
from pathlib import Path
import json,hashlib,argparse
P=Path(__file__).resolve().parents[2];S=P/'revision/storage-study'
def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--complete',action='store_true');args=ap.parse_args()
    audit=read(S/'capacity-audit.json');assert audit['status']=='PASS'
    exe=read(S/'execution.json');assert exe['exit_code']==0
    batch=read(S/'batch-status.json');assert len(batch)==8 and all(x['exit_code']==0 for x in batch)
    snap=read(S/'start-snapshot.json')
    unchanged={}
    for f,digest in snap['sha256'].items():
        path=Path(f);path=path if path.is_absolute() else P.parents[1]/path
        assert sha(path)==digest,f
        unchanged[f]=digest
    for f in ('control.py','run.py','forecasting.py','dispatch.py'):
        assert (P/'src'/f).read_bytes()==(P.parent/'C题_跨日随机控制/src'/f).read_bytes()
    reg=read(P/'artifacts/result-registry.json');claims=read(P/'paper/result-claims.json')
    prefix='revision.storage-study.'
    reg['results']=[r for r in reg['results'] if not r['id'].startswith(prefix)]
    claims['claims']=[c for c in claims['claims'] if not c['result_id'].startswith(prefix)]
    def walk(x,ptr,src):
        if isinstance(x,bool):return
        if isinstance(x,(int,float)):
            ident=src.replace('/','.')+':'+ptr
            reg['results'].append({'id':ident,'value':x,'source_artifact':src,'source_path':ptr,'status':'verified'})
            claims['claims'].append({'result_id':ident,'value':x})
        elif isinstance(x,dict):
            for k,v in x.items():
                if k in ['daily_cost_yuan','source_hashes','hashes','current_hashes','hash_observation_snapshot']:continue
                walk(v,ptr+'/'+k.replace('~','~0').replace('/','~1'),src)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,ptr+'/'+str(i),src)
    for src in ['revision/storage-study/capacity-audit.json','revision/storage-study/annual-inventory.json','revision/storage-study/paper-evidence.json','revision/storage-study/zero-window-quantile.json']:
        walk(read(P/src),'',src)
    reg['scope']='Verified primary results, prior diagnostics, full usable-capacity ablation and365-day inventory; remote aggregate-only results excluded'
    dump(P/'artifacts/result-registry.json',reg);dump(P/'paper/result-claims.json',claims)
    m=read(P/'modeling-manifest.json')
    m['project'].update({'stage':'storage_capacity_and_inventory_revision','status':'in_progress','scope':'Eight newly executed334-day usable-capacity cases plus four unchanged primary trajectories,365-day inventory, and prior validated paper evidence. No annual retuning or main-policy replacement.'})
    m['execution'].update({k:exe[k] for k in ['command','exit_code','runtime_seconds','environment']})
    m['execution'].update({'status':'completed','scope':exe['scope'],'additional_executions_file':'revision/storage-study/batch-status.json','figures':['figures/'+n+'.png' for n in ['reachable','q1','contracts-revision','storage-capacity','annual-inventory-heatmap','decomposition-primary','bootstrap-primary','annual-inventory-envelope']]})
    m['validation']['checks']=[c for c in m['validation']['checks'] if not c['name'].startswith('storage:')]
    m['validation']['checks'] += [{'name':'storage:'+n,'status':'pass','source':f} for n,f in [('12 trajectories physical and cash checks','revision/storage-study/capacity-audit.json'),('four default suffixes32 variables identical','revision/storage-study/capacity-audit.json'),('365-day inventory and366 midnight states','revision/storage-study/annual-inventory.json'),('zero-window analytic quantile check','revision/storage-study/zero-window-quantile.json'),('capacity nesting theory','review/storage-capacity-proof.md'),('inventory text and plot consistency','review/storage-inventory-consistency.md')]]
    m['validation']['sensitivity']=list(dict.fromkeys(m['validation']['sensitivity']+['revision/storage-study/capacity-audit.json']))
    m['pending']=['Current rendered PDF QA and independent storage text/table/figure review']
    outfiles=['artifacts/data-audit.json','artifacts/baseline-metrics.json','artifacts/metrics.json','artifacts/result-registry.json',*m['execution']['figures'],'revision/storage-study/capacity-audit.json','revision/storage-study/annual-inventory.json','revision/storage-study/paper-evidence.json','revision/storage-study/zero-window-quantile.json']
    repro=read(P/'artifacts/reproducibility.json')
    repro.update({k:exe[k] for k in ['command','runtime_seconds','exit_code','environment','scope']})
    repro['output_hashes']={f:sha(P/f) for f in outfiles}
    repro['additional_executions_file']='revision/storage-study/batch-status.json';repro['producer_log']='revision/storage-study/reproduce.log'
    repro['storage_seed']='SeedSequence([20260912,kind_index,pair_index])'
    repro['unchanged_source_input_and_workbook_hashes']=unchanged
    if args.complete:
        q=read(P/'review/pdf-qa.json');assert q['status']=='PASS'
        pdf=P/'output/pdf/基于跨日随机控制与价值反馈的微网购电和储能协同调度_证据完整修订.pdf'
        assert q['pdf_sha256']==sha(pdf) and q['body_and_references_pages']<=30
        f=read(P/'review/findings.json');assert f['decision']=='pass' and f['independent'] and not f.get('unresolved')
        assert f['hashes']['main.tex']==sha(P/'main.tex')
        assert 'storage' in f['scope'].lower()
        m['project']['status']='complete';m['pending']=[]
        m['review'].update({'status':'completed','independent':True,'reviewer_id':f['reviewer_id'],'findings_file':'review/findings.json'})
        m['validation']['checks'] += [{'name':'storage:final independent consistency review','status':'pass','source':'review/findings.json'},{'name':'storage:final PDF visual review','status':'pass','source':'review/pdf-qa.json'}]
        repro['output_hashes'][str(pdf.relative_to(P))]=sha(pdf)
    dump(P/'artifacts/reproducibility.json',repro);dump(P/'modeling-manifest.json',m)
    print(m['project']['status'],len(reg['results']),'registered numerical fields')
if __name__=='__main__':main()
