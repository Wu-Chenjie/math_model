"""Compute the declared numerical objective-perturbation bounds."""
from run_comparison import ROOT,dump
from controllers import M

def main():
    lam=1e-7;S=28;T=144
    dump(ROOT/'artifacts/tie-break-bound.json',{
        'status':'computed','scope':'Per-subproblem bound in exact arithmetic, plus solver tolerance; not a closed-loop annual bound',
        'lambda':lam,'maximum_scenarios':S,'maximum_slots':T,'bus_energy_limit_kwh':M,
        'affine_economic_suboptimality_bound_yuan':lam*2*S*T*M,
        'mpc_economic_suboptimality_bound_yuan':lam*2*T*M})

if __name__=='__main__':main()
