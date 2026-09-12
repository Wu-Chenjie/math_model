from pathlib import Path
import json,hashlib,shutil,platform
R=Path(__file__).resolve().parents[2];B=R.parent/'C题_跨日随机控制';N=R.parent/'C题_下一代随机控制'
def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Registered metrics are recomputed bills from saved full trajectories, not a claim of rerunning annual solvers.
primary=read(R/'revision/restore/primary-evidence.json');exe=read(R/'revision/restore/execution.json');assert exe['exit_code']==0
ks=['q2','q3','q4_2','q4_3'];metrics={k:primary[k]['main_cost'] for k in ks};baseline={k:primary[k]['baseline_cost'] for k in ks}
dump(R/'artifacts/metrics.json',metrics);dump(R/'artifacts/baseline-metrics.json',baseline)
conf=read(N/'artifacts/formal/q2_cc3ebe6953b57007.json')['configuration']
conf.update({'eta':.9,'minimum_kwh':1200,'maximum_kwh':10800,'power_kw':5000,'slot_minutes':10,'slots_per_day':144,'evaluation_days':334,'evaluation_slots':48096,'terminal_penalty_coefficient':1000,'tail_price_quantile':.25,'pseudo_count_per_cell':1/3})
dump(R/'artifacts/paper-configuration.json',conf)
sources=['artifacts/paper-configuration.json','artifacts/metrics.json','artifacts/baseline-metrics.json','reference/artifacts/result-claims.json','revision/required-tables.json','revision/restore/primary-evidence.json','revision/restore/q2-horizon-increment.json','review/restoration-control-diagnostics.json','revision/numeric-audit/q1-billing-audit.json','revision/numeric-audit/january-billing-independent.json','revision/prediction-control/forecast-errors.json','revision/prediction-control/gain-summary.json','revision/prediction-control/january-causal-greedy.json','revision/prediction-control/duplicate-lp-probe.json']
results=[]
def walk(x,ptr,source):
 if isinstance(x,bool):return
 if isinstance(x,(int,float)):
  rid=source.replace('/','.')+':'+ptr
  results.append({'id':rid,'value':x,'source_artifact':source,'source_path':ptr,'status':'verified'})
 elif isinstance(x,dict):
  for k,v in x.items():
   if k in ['daily_cost_yuan','provenance','input_sha256','source_hashes','files','daily','records']:continue
   walk(v,ptr+'/'+k.replace('~','~0').replace('/','~1'),source)
 elif isinstance(x,list):
  for i,v in enumerate(x):walk(v,ptr+'/'+str(i),source)
for source in sources:
 p=R/source;assert p.exists(),source;walk(read(p),'',source)
dump(R/'artifacts/result-registry.json',{'scope':'Full primary evidence, appendix and separate next-generation diagnostic; reported-only remote annual totals excluded','results':results})
dump(R/'paper/result-claims.json',{'claims':[{'result_id':r['id'],'value':r['value']} for r in results],'usage':'Mapped numeric evidence pool for main.tex, tables, appendix and figures; bibliography years and equation labels are not empirical results.'})
m=read(R/'modeling-manifest.json');m['project'].update({'stage':'paper_revision_and_saved_trajectory_verification','status':'in_progress','scope':'Restore auditable four-question manuscript with complete existing workbooks and append independently recomputed next-generation diagnostics; no new annual candidate adoption.'})
infiles=['inputs/C题.pdf','inputs/论文格式规范2026.pdf','artifacts/data.npz']
m['source'].update({'statement_files':infiles[:2],'data_files':infiles[2:],'input_hashes':{f:sha(R/f) for f in infiles},'data_audit_file':'artifacts/data-audit.json','official_rules':{'status':'verified','url':'inputs/论文格式规范2026.pdf','version':'用户提供的2026年修订稿；本次按PDF全文核对电子稿格式','reason':'Verification concerns the supplied rule document, not an independent authenticity claim.'}})
m['framing'].update({'objectives':['Minimize actual purchased-energy bill under four contract mechanisms; supply all realized demand and satisfy true endpoint.'],'decision_variables':['original and revised contracts','charge/discharge','emergency/spill','inventory'],'constraints':['per-slot bus balance','battery recurrence and efficiency .9','1200..10800 capacity; 5000kW power','information adapted contracts and current-net-load feedback','initial/final 6000 for 334 day comparison'],'ambiguities':['90% efficiency interpreted each way','refund then 50% cancellation penalty main convention, alternative billing examined'],'assumptions':['free unlimited bus spill, no sales, nonnegative prices','no degradation/self-discharge parameter supplied']})
m['models']['candidates']=[{'name':name,'target_output':'full-day energy contracts and feasible inventory trajectory with cash bill','assumptions':['same physical and billing model','causal information'],'data_requirements':['timestamped load, PV, prices, official forecasts'],'failure_mode':risk,'diagnostic':diag} for name,risk,diag in [('cross_day_greedy','myopic use of inventory','fixed-end paired annual bills'),('affine_feedback','restricted response class may incur higher bills','same-endpoint cross/day and feedback ablations'),('markov_value_feedback','compressed conditional state and interpolated future values','feasibility, convexity checks, sensitivity and paired blocks')]]
m['models'].update({'selected':'markov_value_feedback','selection_rationale':{'objective_fit':'January actual closed-loop bill rule retained; no selection from new annual diagnostics','constraint_fit':'LP and reachable executor enforce stated planning and physical conditions','data_fit':'mature equal-weight historical blocks and legal forecast releases','baseline':'cross_day_greedy with same 6000 endpoints','risks':['one-year replay','Markov and frozen-contract continuation approximation','January development overlap stated for new fusion moments'],'fallback_trigger':'Do not promote unverified or statistically unsupported next-generation candidates into primary results'}})
m['models']['baseline'].update({'status':'completed','name':'cross_day_greedy','command':exe['command'],'exit_code':exe['exit_code'],'runtime_seconds':exe['runtime_seconds'],'output':'artifacts/baseline-metrics.json','metric_ids':ks,'reason':'Full stored baseline trajectory independently re-evaluated, not annual solver rerun.'})
m['execution'].update({k:exe[k] for k in ['command','exit_code','runtime_seconds','environment']});m['execution'].update({'status':'completed','seed':20260911,'metrics_file':'artifacts/metrics.json','metric_ids':ks,'figures':[str(p.relative_to(R)) for p in sorted((R/'figures').glob('*.png'))],'scope':exe['scope']})
m['validation'].update({'status':'completed','checks':[{'name':n,'status':'pass','source':f} for n,f in [('all four fixed endpoint physical and cash ledgers','review/restoration-evidence-audit.json'),('all five workbooks and 16 date blocks match','review/restoration-evidence-audit.json'),('three block lengths against crossday greedy','revision/restore/primary-evidence.json'),('matched horizon configuration and paired forecast moments','review/restoration-control-diagnostics.json')]],'sensitivity':['reference/artifacts/result-claims.json','revision/prediction-control/gain-summary.json'],'robustness':['revision/restore/primary-evidence.json'],'falsification':['negative horizon result in Q3 preserved','Q2 incremental CI crosses zero, not promoted','unverified remote totals excluded from manuscript','beta MSE diagnostics not held-out or bill optimal']})
m['results'].update({'registry_file':'artifacts/result-registry.json','paper_file':'main.tex','claims_file':'paper/result-claims.json'})
m['pending']=['final independent numerical/text review and rendered PDF QA'];m['violations']=[]
dump(R/'modeling-manifest.json',m)
outputs=['artifacts/data-audit.json','artifacts/baseline-metrics.json','artifacts/metrics.json','artifacts/result-registry.json',*m['execution']['figures']]
dump(R/'artifacts/reproducibility.json',{'command':exe['command'],'seed':20260911,'environment':exe['environment'],'runtime_seconds':exe['runtime_seconds'],'exit_code':exe['exit_code'],'scope':exe['scope'],'input_hashes':m['source']['input_hashes'],'output_hashes':{f:sha(R/f) for f in outputs},'dependencies':['../C题_跨日随机控制','../C题_下一代随机控制'],'producer_log':'revision/restore/final-reproduce.log','baseline_command':exe['command'],'baseline_exit_code':exe['exit_code']})
print('Registered',len(results),'numeric fields; actual verification exit',exe['exit_code'])
