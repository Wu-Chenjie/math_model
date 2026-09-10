"""Compare algebraically equivalent affine LP economic objectives, no holdout tuning."""
import time,json
import numpy as np
from run_comparison import ROOT,BASE,dump
from forecasting import scenario_data
from controllers import affine_plan as original
from reduced_affine import affine_plan as reduced

def main():
    data=dict(np.load(BASE/'artifacts/data.npz'));fc=dict(np.load(BASE/'artifacts/forecasts.npz'))
    checks=[]
    for k in range(4):
        n,p,_=scenario_data(data,fc,30,k,True,True)
        ref=None
        for name,fn in [('original',original),('reduced',reduced)]:
            tic=time.perf_counter();s=fn(n,p,start=k*36)
            row={'release':k,'model':name,'runtime_seconds':time.perf_counter()-tic,'expected_cost':s['expected_cost'],
                 'eq_residual':s['eq_residual'],'ineq_violation':s['ineq_violation']}
            if name=='original':ref=s['expected_cost']
            else:
                row['economic_objective_difference']=s['expected_cost']-ref
                assert abs(row['economic_objective_difference'])<.05
            checks.append(row);print(json.dumps(row),flush=True)
    dump(ROOT/'artifacts/equivalent-reduction.json',{'status':'pass','checks':checks,
         'difference_note':'Original includes 1e-7 charge/discharge tie breaker; reduced solves economic objective directly.'})

if __name__=='__main__':main()
