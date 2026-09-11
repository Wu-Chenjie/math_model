"""Independent full-horizon perfect-information LP, not an executable policy.

Run from the project directory: python3 review/check-global-oracle.py
Four LPs use all 48,096 actual ten-minute intervals, no daily closure, no
emergency energy, no regularization term, and explicit free spill variables.
"""
from pathlib import Path
import hashlib, json, platform, sys, time
import numpy as np
from scipy.sparse import eye, diags, hstack, vstack, csr_matrix

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor'))
import highspy

ETA=.9; M=5000./6.; EMIN=1200.; EMAX=10800.; INITIAL=6000.
OUTPUT=ROOT/'review'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def matrices(T):
    I=eye(T,format='csr'); Z=csr_matrix((T,T))
    D=I-diags(np.ones(T-1),-1,shape=(T,T),format='csr')
    # Column blocks q, c, d, next E, spill.
    return vstack([hstack([I,-I,I,Z,-I]),hstack([Z,-ETA*I,I/ETA,D,Z])],format='csr')

def one_case(A,net,price,terminal,label):
    begin=time.perf_counter();T=len(net);N=5*T
    objective=np.r_[price,np.zeros(4*T)]
    lo=np.r_[np.zeros(3*T),np.full(T,EMIN),np.zeros(T)]
    hi=np.r_[np.full(T,np.inf),np.full(2*T,M),np.full(T,EMAX),np.full(T,np.inf)]
    if terminal is not None:lo[4*T-1]=hi[4*T-1]=terminal
    rhs=np.r_[net,np.r_[INITIAL,np.zeros(T-1)]]
    problem=highspy.HighsLp();problem.num_col_=N;problem.num_row_=2*T
    problem.col_cost_=objective;problem.col_lower_=lo;problem.col_upper_=hi
    problem.row_lower_=rhs;problem.row_upper_=rhs
    problem.a_matrix_.format_=highspy.MatrixFormat.kRowwise
    problem.a_matrix_.start_=A.indptr;problem.a_matrix_.index_=A.indices;problem.a_matrix_.value_=A.data
    solver=highspy.Highs()
    options={'output_flag':False,'threads':1,'solver':'ipm',
             'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8,
             'ipm_optimality_tolerance':1e-10}
    for key,value in options.items():
        assert solver.setOptionValue(key,value)==highspy.HighsStatus.kOk
    assert solver.passModel(problem)==highspy.HighsStatus.kOk
    status=solver.run();model_status=solver.getModelStatus()
    assert status==highspy.HighsStatus.kOk,status
    assert model_status==highspy.HighsModelStatus.kOptimal,solver.modelStatusToString(model_status)
    sol=solver.getSolution();info=solver.getInfo()
    assert sol.value_valid and sol.dual_valid
    x=np.asarray(sol.col_value);y=np.asarray(sol.row_dual);z=np.asarray(sol.col_dual)
    q,c,d,E,spill=np.split(x,5)
    cost=float(price@q);raw_objective=float(solver.getObjectiveValue())
    finite=np.isfinite(hi)
    # Solver reduced-cost dual objective, with infeasible infinite-bound signs
    # reported separately. An independently repaired certificate follows.
    raw_dual=float(rhs@y+np.sum(lo*np.maximum(z,0))+
                   np.sum(hi[finite]*np.minimum(z[finite],0)))
    stationarity=float(abs(objective-A.T@y-z).max())
    infinite_sign_violation=float(max(0,-z[~finite].min()))

    # For unbounded-above q and spill, dual feasibility is exactly 0<=y_bus<=p.
    # All other columns have finite bounds and need no reduced-cost sign limit.
    # Clipping these rows constructs a feasible dual directly, independently
    # recomputing every reduced cost rather than relying on the solver report.
    certificate_y=y.copy();certificate_y[:T]=np.clip(certificate_y[:T],0,price)
    certificate_z=objective-A.T@certificate_y
    assert certificate_z[~finite].min()>=-1e-12
    dual_bound=float(rhs@certificate_y+np.sum(lo*np.maximum(certificate_z,0))+
                     np.sum(hi[finite]*np.minimum(certificate_z[finite],0)))
    gap=cost-dual_bound
    relative_gap=gap/max(1,abs(cost))
    eq_residual=float(abs(A@x-rhs).max())
    bounds_residual=float(max(0,np.max(lo-x),np.max(x[finite]-hi[finite])))

    # Any simultaneous charge/discharge is removed while keeping E and q.
    # Extra bus supply is sent to the explicit free spill variable.
    simultaneous_before=float(np.minimum(c,d).max())
    remove=np.minimum(c,d/(ETA*ETA))
    canonical_c=c-remove;canonical_d=d-ETA*ETA*remove
    canonical_spill=spill+(1-ETA*ETA)*remove
    state=np.r_[INITIAL,E]
    balance_error=float(abs(q+canonical_d-canonical_c-canonical_spill-net).max())
    soc_error=float(abs(np.diff(state)-ETA*canonical_c+canonical_d/ETA).max())
    power=max(canonical_c.max(),canonical_d.max())*6
    simultaneous_after=float(np.minimum(canonical_c,canonical_d).max())
    midnight=state[np.arange(144,T+1,144)]
    end_error=0. if terminal is None else abs(float(state[-1])-terminal)
    checks={'matrix_equality_max_abs':eq_residual,'variable_bound_violation':bounds_residual,
            'economic_objective_recompute_error':abs(cost-raw_objective),
            'dual_stationarity_max_abs':stationarity,'raw_infinite_bound_sign_violation':infinite_sign_violation,
            'dual_certificate_repair_max_abs':float(abs(certificate_y-y).max()),
            'dual_certificate_unbounded_column_violation':float(max(0,-certificate_z[~finite].min())),
            'primal_minus_repaired_dual':gap,'relative_primal_dual_gap':relative_gap,
            'canonical_bus_balance_max_abs':balance_error,'canonical_soc_recurrence_max_abs':soc_error,
            'canonical_soc_min':float(state.min()),'canonical_soc_max':float(state.max()),
            'canonical_power_max_kw':float(power),'simultaneous_before':simultaneous_before,
            'simultaneous_after':simultaneous_after,'terminal_error':end_error}
    assert max(eq_residual,bounds_residual,balance_error,soc_error,end_error)<1e-5,checks
    assert state.min()>=EMIN-1e-5 and state.max()<=EMAX+1e-5 and power<=5000+1e-5
    assert min(q.min(),canonical_c.min(),canonical_d.min(),canonical_spill.min())>=-1e-5
    assert abs(gap)<max(.01,abs(cost)*1e-8) and stationarity<1e-6,checks
    result={'label':label,'status':solver.modelStatusToString(model_status),'terminal_constraint':terminal,
            'objective_cost_yuan':cost,'solver_objective_yuan':raw_objective,
            'raw_dual_objective_yuan':raw_dual,'repaired_dual_lower_bound_yuan':dual_bound,
            'initial_inventory_kwh':INITIAL,'final_inventory_kwh':float(state[-1]),
            'ordinary_purchase_kwh':float(q.sum()),'spill_kwh':float(canonical_spill.sum()),
            'charge_bus_kwh':float(canonical_c.sum()),'discharge_bus_kwh':float(canonical_d.sum()),
            'midnight_inventories_kwh':midnight.tolist(),
            'checks':checks,'iterations':{'ipm':int(info.ipm_iteration_count),
                                         'crossover':int(info.crossover_iteration_count),
                                         'simplex':int(info.simplex_iteration_count)},
            'runtime_seconds':time.perf_counter()-begin,'solver_options':options,
            'solver_report':{'max_primal_infeasibility':float(info.max_primal_infeasibility),
                             'max_dual_infeasibility':float(info.max_dual_infeasibility)}}
    arrays={'q':q,'c':canonical_c,'d':canonical_d,'state':state,'spill':canonical_spill}
    return result,arrays

def main():
    start=time.perf_counter();source=sha(__file__);data_path=ROOT/'artifacts/data.npz';input_hash=sha(data_path)
    data=dict(np.load(data_path));net=((data['load'][31:]-data['pv'][31:])/6).ravel()
    T=len(net);assert T==48096
    prices={'fixed':np.tile(data['day_price'],334),'variable':data['price'][31:].ravel()}
    assert all(p.min()>0 and len(p)==T for p in prices.values())
    A=matrices(T);results={};trajectories={}
    for kind,price in prices.items():
        for name,terminal in [('free',None),('fixed6000',6000.)]:
            label=f'{kind}_{name}';print('Solving '+label,flush=True)
            result,arrays=one_case(A,net,price,terminal,label)
            results[label]=result
            trajectories.update({f'{label}_{k}':v for k,v in arrays.items()})
            print(json.dumps({'label':label,'cost':result['objective_cost_yuan'],
                              'gap':result['checks']['primal_minus_repaired_dual'],
                              'seconds':result['runtime_seconds']}),flush=True)
    for kind in prices:
        assert results[f'{kind}_free']['objective_cost_yuan']<=results[f'{kind}_fixed6000']['objective_cost_yuan']+1e-5
    archive=OUTPUT/'global-oracle-trajectories.npz'
    np.savez_compressed(archive,**trajectories)
    assert source==sha(__file__) and input_hash==sha(data_path)
    report={'schema_version':1,'reviewer_id':'/root/independent_review','independent':True,
            'scope':'Full-horizon perfect-information optimistic reference, not a causal policy or SDDP gap.',
            'passed':True,'evaluation':{'start_date':str(data['dates'][31]),'end_date':str(data['dates'][-1]),
                                       'days':334,'ten_minute_intervals':T,'initial_inventory_kwh':INITIAL,
                                       'daily_closure':False,'emergency_purchase_allowed':False,
                                       'free_spill':True,'turnover_regularizer':0.,
                                       'eta_each_direction':ETA,'power_kw':5000,'soc_bounds_kwh':[EMIN,EMAX]},
            'lower_bound_argument':'For any feasible causal strategy with identical initial and true terminal conditions, use perfect-information ordinary purchase q_oracle=r+emergency with its battery and spill. phi(q,r)>=r and 5*emergency>=emergency, so positive-price cost cannot increase. Removing nonanticipativity therefore gives a lower bound. The free-terminal bound must not be presented as a same-terminal gap for a fixed-terminal policy.',
            'dual_certificate':'Clip the bus-balance row dual to [0,price], recompute z=c-A^T y, and evaluate b^T y + sum(z_positive*lower) + sum(z_negative*finite_upper). All infinite-upper columns are q and spill and have nonnegative reduced costs after repair. Numerical tolerances are explicitly reported; this is not exact rational arithmetic.',
            'results':results,'source_sha256':source,'data_npz_sha256':input_hash,
            'trajectory_file':str(archive.relative_to(ROOT)),'trajectory_sha256':sha(archive),
            'execution':{'command':'python3 review/check-global-oracle.py','exit_code':0,
                         'runtime_seconds':time.perf_counter()-start,'python':sys.version,
                         'numpy':np.__version__,'highs':highspy.Highs().version(),'platform':platform.platform(),
                         'deterministic_reason':'Four deterministic sparse LPs; no sampling or random seed.'}}
    (OUTPUT/'global-oracle.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':True,'total_seconds':report['execution']['runtime_seconds']}),flush=True)

if __name__=='__main__':main()
