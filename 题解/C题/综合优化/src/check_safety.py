"""Stress the terminal-reachable safety projection, not economic robustness."""
import json,time
import numpy as np
from run_comparison import ROOT,dump
from controllers import feasible,execute_target,ETA,M

def main():
    tick=time.perf_counter();rng=np.random.default_rng(20260910);N=20000
    max_balance=max_state=max_power=max_terminal=0.
    for i in range(N):
        t=int(rng.integers(0,144));remaining=144-t
        lo=max(1200.,6000-remaining*ETA*M);hi=min(10800.,6000+remaining*M/ETA)
        E=float(rng.uniform(lo,hi));target=float(rng.uniform(-100000,100000))
        q=float(rng.uniform(0,6000));net=float(rng.uniform(-10000,20000))
        c,d,x,e,w,proj=execute_target(E,target,q,net,t)
        max_balance=max(max_balance,abs(q+d+e-c-w-net));max_state=max(max_state,abs(x-E-ETA*c+d/ETA))
        max_power=max(max_power,c*6,d*6)
        assert 1200-1e-8<=x<=10800+1e-8
        assert c<=M+1e-8 and d<=M+1e-8 and min(c,d)<1e-8
        R=143-t
        assert 6000-R*ETA*M-1e-8<=x<=6000+R*M/ETA+1e-8
        if t==143:max_terminal=max(max_terminal,abs(x-6000))
    result={'status':'pass','seed':20260910,'cases':N,'net_energy_test_range_kwh':[-10000,20000],
            'requested_soc_range_kwh':[-100000,100000],'max_balance_error':max_balance,
            'max_soc_recurrence_error':max_state,'max_power_kw':max_power,'max_terminal_error':max_terminal,
            'scope':'Conditional on initially terminal-reachable SOC; feasibility stress only. Emergency supply is unlimited. No economic worst-case guarantee.',
            'runtime_seconds':time.perf_counter()-tick}
    dump(ROOT/'artifacts/robustness.json',result);print(json.dumps(result))

if __name__=='__main__':main()
