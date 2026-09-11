#!/usr/bin/env python3
"""Time unchanged January contract LPs; no closed-loop replay or solver retuning."""
from pathlib import Path
from dataclasses import asdict,replace
import argparse,hashlib,json,sys,time,platform
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import control
import nextgen_control as planner
from nextgen_scenarios import Config,ScenarioFactory,weighted_quantile
OUT=ROOT/'artifacts/cpp-migration'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def profile(config,kind,asof):
    start=time.perf_counter()
    data=dict(np.load(ROOT/'artifacts/data.npz',allow_pickle=False))
    selection=json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
    official,variable={'q2':(False,False),'q3':(True,False),'q4_2':(False,True),'q4_3':(True,True)}[kind]
    assert 144<asof and asof+6*config.horizon_hours<=31*144,'Only January origins and targets allowed'
    factory=ScenarioFactory(data,selection,official,variable,config.alpha,config.fusion_weight,config.official_correction)
    factory_seconds=time.perf_counter()-start
    before=time.perf_counter();bundle=factory.build(asof,asof+6*config.horizon_hours,config);scenario_seconds=time.perf_counter()-before
    prices,weights=bundle['prices'],bundle['weights'];last=prices[:,-min(144,prices.shape[1]):]
    tail=config.tail_scale*float(weighted_quantile(last.ravel(),[.25],np.repeat(weights,last.shape[1]))[0])/control.ETA
    ident=f'{kind}_{config.upper}_{config.horizon_hours}h_{config.identity()}';root=OUT/ident;root.mkdir(exist_ok=True)
    clocks={};capture={};orig_highs=control.highspy.Highs;orig_lp=control.lp_solve;orig_newlp=planner.lp_solve
    class TimedHighs:
        def __init__(self,*a,**k):self.inner=orig_highs(*a,**k)
        def __getattr__(self,name):return getattr(self.inner,name)
        def setOptionValue(self,name,value):
            clocks.setdefault('solver_options',{})[name]=value
            return self.inner.setOptionValue(name,value)
        def passModel(self,*a,**k):
            t=time.perf_counter();answer=self.inner.passModel(*a,**k);clocks['highs_pass_model_seconds']=time.perf_counter()-t;return answer
        def run(self,*a,**k):
            t=time.perf_counter();answer=self.inner.run(*a,**k);clocks['highs_run_seconds']=time.perf_counter()-t
            info=self.inner.getInfo();clocks['highs_runtime_reported_seconds']=self.inner.getRunTime()
            clocks['solver_info']={name:getattr(info,name) for name in ('ipm_iteration_count','simplex_iteration_count','crossover_iteration_count','max_primal_infeasibility','max_dual_infeasibility') if hasattr(info,name)}
            clocks['solver_version']=self.inner.version();return answer
    plan_start=None
    def timed_lp(obj,A,b,bounds,solver='ipm'):
        clocks['pre_solver_features_sparse_assembly_seconds']=time.perf_counter()-plan_start
        capture.update(obj=obj,A=A,b=b,bounds=bounds)
        t=time.perf_counter();answer=orig_lp(obj,A,b,bounds,solver);clocks['lp_wrapper_seconds']=time.perf_counter()-t
        capture['solution']=answer.x;clocks['lp_objective']=answer.fun;clocks['lp_violation']=answer.violation
        return answer
    try:
        control.highspy.Highs=TimedHighs;control.lp_solve=timed_lp;planner.lp_solve=timed_lp
        plan_start=time.perf_counter()
        answer=planner.affine_plan(bundle,asof,6000.,config,base=None,adjust=official,tail_price=tail,terminal=None,tail_cuts=None)
        clocks['planning_total_seconds']=time.perf_counter()-plan_start
    finally:control.highspy.Highs=orig_highs;control.lp_solve=orig_lp;planner.lp_solve=orig_newlp
    clocks['post_solver_result_reconstruction_seconds']=clocks['planning_total_seconds']-clocks['pre_solver_features_sparse_assembly_seconds']-clocks['lp_wrapper_seconds']
    clocks['lp_wrapper_other_seconds']=clocks['lp_wrapper_seconds']-clocks['highs_run_seconds']-clocks['highs_pass_model_seconds']
    A=capture['A'].tocsr();bounds=np.array([[np.nan if lo is None else lo,np.nan if hi is None else hi] for lo,hi in capture['bounds']])
    np.savez_compressed(root/'linear-program.npz',obj=capture['obj'],rhs=capture['b'],bounds=bounds,indptr=A.indptr,indices=A.indices,values=A.data,shape=np.asarray(A.shape),solution=capture['solution'])
    arrays={};metadata={}
    for name,value in bundle.items():
        if isinstance(value,np.ndarray):arrays[name]=value
        elif isinstance(value,dict):
            metadata[name]={}
            for key,item in value.items():
                if isinstance(item,np.ndarray):arrays[name+'__'+key]=item
                else:metadata[name][key]=item
        else:metadata[name]=value
    np.savez_compressed(root/'scenario-bundle.npz',**arrays)
    np.savez_compressed(root/'contract-result.npz',**{k:v for k,v in answer.items() if isinstance(v,np.ndarray)})
    S,T=bundle['net'].shape;total=clocks['planning_total_seconds'];assembly=clocks['pre_solver_features_sparse_assembly_seconds']
    info={'status':'measured','kind':kind,'configuration':asdict(config),'origin_slot':asof,'origin_date':str(data['dates'][asof//144]),'inventory':6000.,'tail_price':tail,'terminal':None,
          'scenario_metadata':metadata,'factory_init_seconds':factory_seconds,'scenario_generation_seconds':scenario_seconds,
          'lp_size':{'scenarios':S,'delivery_slots':T,'variables':A.shape[1],'inequality_rows':A.shape[0],'nonzeros':A.nnz,'csr_bytes':A.indptr.nbytes+A.indices.nbytes+A.data.nbytes},
          'timing':clocks,'diagnostics':{'objective_recompute_gap':answer['objective_gap'],'gain_max_abs':answer['gain_max_abs']},
          'migration_bound':{'pre_solver_assembly_fraction':assembly/total,'highs_run_fraction':clocks['highs_run_seconds']/total,
                             'max_contract_speedup_if_pre_solver_work_free':total/(total-assembly),
                             'max_contract_speedup_if_all_non_highs_work_free':total/clocks['highs_run_seconds'],
                             'scope':'Amdahl limits for this measured LP only; unchanged solver and LP. No annual speedup prediction.'},
          'fixtures':{p.name:sha(p) for p in root.glob('*.npz')}}
    write(root/'profile.json',info);print(json.dumps({'case':ident,'size':info['lp_size'],'timing':clocks,'migration_bound':info['migration_bound']},ensure_ascii=False),flush=True)
    return info

def main():
    p=argparse.ArgumentParser();p.add_argument('--horizons',type=int,nargs='+',default=[72,96]);p.add_argument('--kind',choices=['q2','q3','q4_2','q4_3'],default='q4_3');p.add_argument('--case',choices=['challenger','legacy'],default='challenger');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    paths=[ROOT/'src'/name for name in ('control.py','nextgen_control.py','nextgen_scenarios.py','forecasting.py')]+[ROOT/'artifacts/data.npz',ROOT/'artifacts/forecast-selection.json',ROOT/'artifacts/frozen-development-selection.json']
    hashes={str(path.relative_to(ROOT)):sha(path) for path in paths};frozen=json.loads((ROOT/'artifacts/frozen-development-selection.json').read_text())
    base=Config(**frozen['challenger']) if a.case=='challenger' else Config()
    results=[]
    for horizon in a.horizons:
        print(json.dumps({'starting':a.case,'horizon_hours':horizon,'kind':a.kind,'legal_origin':'2025-01-25 00:00'},ensure_ascii=False),flush=True)
        results.append(profile(replace(base,horizon_hours=horizon),a.kind,24*144))
        assert hashes=={str(path.relative_to(ROOT)):sha(path) for path in paths},'Source/input changed during profiling'
        write(OUT/f'profile-{a.case}.json',{'status':'MEASURED_WITHIN_SCOPE','independent':True,'reviewer_id':'/root/upgrade_code_review','source_hashes':hashes,'environment':{'python':sys.version,'platform':platform.platform()},'scope':'January origin; unchanged original Python equations and HiGHS options, no feedback construction or closed-loop annual replay. Timing proxies only; fixture writes occur after timings.','results':results})
if __name__=='__main__':main()
