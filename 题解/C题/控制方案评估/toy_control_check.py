"""Illustrative counterexample only; these are NOT competition-data results."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye,diags,hstack

T=3;eta=.9;emin=1200.;initial=emin+100/eta
net=np.array([100.,100.,0.]);price=np.array([.4,1.4,.4]);contract=np.array([0.,0.,100/eta**2])
I=eye(T);Z=0*I;D=I-diags(np.ones(T-1),-1,shape=(T,T))
Aeq=hstack([-eta*I,I/eta,D,Z]).toarray();rhs=np.r_[initial,0.,0.]
Aub=hstack([I,-I,Z,-I]).toarray()
obj=np.r_[np.zeros(3*T),5*price]
bounds=[(0,5000/6)]*(2*T)+[(emin,10800)]*T+[(0,None)]*T
bounds[3*T-1]=(initial,initial)
sol=linprog(obj,A_ub=Aub,b_ub=contract-net,A_eq=Aeq,b_eq=rhs,bounds=bounds,method='highs')
assert sol.success
E=initial;greedy=[]
for q,n in zip(contract,net):
    surplus=q-n
    c=min(max(surplus,0),5000/6,(10800-E)/eta)
    b=min(max(-surplus,0),5000/6,eta*(E-emin))
    E+=eta*c-b/eta
    greedy.append(max(n+c-b-q,0))
assert abs(E-initial)<1e-8
result={'scope':'Artificial three-slot deterministic illustration; not annual performance.',
 'net_kwh':net.tolist(),'price_cny_per_kwh':price.tolist(),'fixed_contract_kwh':contract.tolist(),
 'initial_and_terminal_soc_kwh':initial,'greedy_emergency_kwh':greedy,
 'predictive_emergency_kwh':sol.x[3*T:].tolist(),
 'greedy_emergency_cost':float(5*price@greedy),'predictive_emergency_cost':float(sol.fun),
 'same_contract_cost':float(price@contract),
 'full_year_lower_mpc_solves_per_policy':334*144,'four_policies_solves':4*334*144}
assert abs(result['greedy_emergency_cost']-700)<1e-7
assert abs(result['predictive_emergency_cost']-200)<1e-7
Path(__file__).with_name('toy_control_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
