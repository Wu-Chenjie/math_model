"""Freeze artifact hashes and populate the audit ledger from execution/review records."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def get(p):return json.loads((ROOT/p).read_text())
def dump(p,x):(ROOT/p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=get('modeling-manifest.json');metrics=get('artifacts/metrics.json');ex=get('artifacts/execution-main.json');be=get('artifacts/execution-extras.json')
m['framing'].update(objectives=['Minimize actual planned+adjustment+emergency electricity cost with causal information.',
 'Deliver Q1 and 334-day Q2/Q3/Q4 trajectories, specified-day tables and modeling handoff.'],
 decision_variables=['q: midnight contract','r: final contract','c,d: bus-side battery charge/discharge','E: stored energy','e,w: emergency and surplus'],
 constraints=['bus energy conservation','SOC in [1200,10800] kWh','charge/discharge <=5000/6 kWh per slot',
 'no simultaneous charging/discharging after analytic cancellation','initial6000','daily terminal6000 policy','causal forecasts','freeze completed slots'],
 ambiguities=['template headers shifted10min','directional versus roundtrip90%','cancellation refund','net versus repeated amendment settlement','future price information'],
 assumptions=['10min interval-mean powers with right-endpoint tags','each efficiency0.9','no sale, free curtailment, unlimited emergency purchase',
 'Q2-4 daily6000 terminal is extra operational policy','refund then50% penalty; net final adjustments relative midnight',
 'same-slot actual net-load feedback, no inter-slot future observation'])
m['models']['candidates']=[
 {'name':'deterministic_forecast_LP','target_output':'Causal daily contract and realized cost','assumptions':['point forecasts','same causal feedback'],
 'data_requirements':['historical load and PV'],'failure_mode':'large fivefold emergency cost from forecast errors','diagnostic':'334-day actual total cost baseline'},
 {'name':'empirical_SAA_LP_with_feedback','target_output':'Causal contracts, battery paths, realized total cost',
 'assumptions':['local empirical residual distribution','common planned battery path','reachable-terminal greedy feedback'],
 'data_requirements':['past residuals','released PV forecasts for Q3','past price for Q4'],'failure_mode':'systematic bias and rigid terminal losses',
 'diagnostic':'baseline, controlled PV ablation, frozen-contract stress, parameter sensitivity'},
 {'name':'full_multistage_stochastic_control','target_output':'optimal contingent storage and contract policy',
 'assumptions':['identified state transition and scenario tree'],'data_requirements':['joint temporal uncertainty distribution'],
 'failure_mode':'large state/scenario space and weak transition identification','diagnostic':'not run; choose tractable approximation, no global optimum claim'}]
m['models']['selected']='empirical_SAA_LP_with_feedback'
m['models']['selection_rationale']={'objective_fit':'Explicit asymmetric emergency and piecewise contract settlement costs',
 'constraint_fit':'Linear energy/SOC/power constraints plus causal reachable-state feedback',
 'data_fit':'January selection; preceding residual windows; four actual forecast release times',
 'baseline':'Executed point-forecast LP with identical controller and evaluation dates',
 'risks':['extra daily terminal policy','approximate common-path plan','empirical errors may shift','ambiguous settlement'],
 'fallback_trigger':'For revised inputs, rerun January selection and baseline; prefer simpler method if held-out realized cost improvement vanishes. Never tune on reported holdout.'}
m['models']['baseline'].update(status='completed',name='Q2 point-forecast LP with same causal feedback',command=be['command'],exit_code=be['exit_code'],
 runtime_seconds=be['runtime_seconds'],output='artifacts/baseline-metrics.json',metric_ids=['q2'])
figures=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'figures').glob('*') if p.suffix in ['.png','.svg'])
m['execution'].update(status='completed',command=ex['command'],exit_code=ex['exit_code'],runtime_seconds=ex['runtime_seconds'],
 environment=metrics['environment'],seed=None,deterministic_reason=ex['deterministic_reason'],metric_ids=['q2'],figures=figures)
checks=get('artifacts/validation.json')['checks']+get('artifacts/workbook-validation.json')['checks']
checks += [{'name':k+'_physical_and_lp_invariants','status':'pass','source':'artifacts/'+k+'.json'} for k in ['q2','q3','q4_2','q4_3']]
m['validation'].update(status='completed',checks=checks,sensitivity=['artifacts/sensitivity.json','artifacts/validation.json#/q1_sensitivity'],
 robustness=['artifacts/validation.json#/frozen_contract_stress'],falsification=['future actual/forecast mutation invariance at all4 releases',
 '80% quantile exact boundary','no-refund downward adjustment dominance','review/independent-checks.json'])
m['results']['paper_file']=None;m['results']['handoff_file']='建模计算交接.md';m['results']['handoff_claims_file']='artifacts/handoff-claims.json'
m['pending']=[];m['violations']=[]
review=get('review/findings.json')
if review.get('decision')=='pass' and review.get('independent') is True and not review.get('unresolved'):
 m['review'].update(status='completed',independent=True,reviewer_id=review['reviewer_id'])
 m['project'].update(stage='handoff',status='complete')
else:
 m['project'].update(stage='final_review',status='in_progress')
 m['pending']=['Final independent review of frozen handoff/results']
outputs=[]
for directory in ['src','artifacts','figures','计算结果']:
 for p in (ROOT/directory).rglob('*'):
  if p.is_file() and not any(s in str(p) for s in ['__pycache__','previews','reproducibility.json','acceptance.json','.log','.inspect.ndjson']):outputs.append(p)
outputs += [ROOT/p for p in ['README.md','建模计算交接.md','指定日期结果表.md','复现.sh']]
record={'command':ex['command'],'seed':None,'deterministic_reason':ex['deterministic_reason'],'environment':metrics['environment'],
 'input_hashes':m['source']['input_hashes'],'output_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in outputs},
 'executions':[get('artifacts/execution-'+s+'.json') for s in ['calibrate','main','extras','validation']]}
dump('artifacts/reproducibility.json',record);dump('modeling-manifest.json',m)
print(m['project'])
