"""Deterministic kernel/feedback parity and local microbenchmarks, not annual claims."""
from pathlib import Path
import sys,time,json,hashlib
import numpy as np
R=Path(__file__).resolve().parent;ROOT=R.parent
sys.path[:0]=[str(R),str(ROOT/'src')]
import native
import native_feedback as compatible
import control
import nextgen_control as ref
rng=np.random.default_rng(20260911);records=[]

def error(a,b):return float(np.max(np.abs(np.asarray(a)-np.asarray(b)),initial=0))

for G in [2,17,161,321,641]:
 g=np.linspace(1200,10800,G)
 for i in range(60):
  slopes=np.sort(rng.normal(size=G-1));v=np.r_[rng.normal(),np.cumsum(slopes*np.diff(g))]
  a=float(rng.uniform(-3000,3000));p=float(rng.uniform(.001,2))
  expected=control.inf_convolution(g,v,a,p);actual=native.inf_convolution(g,v,a,p)
  gap=error(expected,actual);assert gap<1e-7,(G,i,gap)
  records.append({'type':'convolution','G':G,'max_error':gap})

for case in range(24):
 S=[1,2,7,10,14,7][case%6];T=[1,36,144,432][case%4];G=[161,321,641][case%3];B=[2,3,4,5][case%4]
 net=rng.normal(250,220,(S,T));prices=rng.uniform(.2,1.3,(S,T));q=rng.uniform(0,450,T)
 weights=np.full(S,1/S) if case%2==0 else rng.dirichlet(np.ones(S)*2)
 if case%2==0:B=3
 terminal=6000 if case%3==0 else None;cuts=[[0.,0.],[-1000.,.2]] if case%3==1 else None
 args=(net,prices,q,weights,.3,G,B,terminal,cuts)
 start=time.perf_counter();a=ref.WeightedMarkovDP(*args);python=time.perf_counter()-start
 start=time.perf_counter();b=native.WeightedMarkovDP(*args);cpp=time.perf_counter()-start
 av=a.legacy if a.legacy is not None else a;bv=b.legacy if b.legacy is not None else b
 gaps={key:error(getattr(av,key),getattr(bv,key)) for key in ['cuts','future','price','initial_values']}
 assert max(gaps.values())<2e-6,(case,gaps)
 action_gap=0.;objective_gap=0.
 for j in sorted(set([0,T//2,T-1])):
  for E in [1200.,6000.,10800.,float(rng.uniform(1200,10800))]:
   for n in [net[0,j],0.,1200.]:
    x=a.action(j,E,n,q[j]);y=b.action(j,E,n,q[j]);action_gap=max(action_gap,abs(x-y))
    k=int(np.sum(n>av.cuts[j]));future=av.future[j,k];p=av.price[j,k]
    val=lambda z:5*p*max(0,n-q[j]+max(.9*(z-E),(z-E)/.9))+np.interp(z,av.grid,future)
    objective_gap=max(objective_gap,abs(val(x)-val(y)))
 assert objective_gap<2e-6,(case,action_gap,objective_gap)
 c=compatible.WeightedMarkovDP(*args);cv=c.legacy if c.legacy is not None else c
 for key in ['cuts','future','price','initial_values']:
  assert np.array_equal(getattr(av,key),getattr(cv,key)), ('compatible',case,key,error(getattr(av,key),getattr(cv,key)))
 records.append({'type':'Markov','case':case,'S':S,'T':T,'G':G,'B':B,'errors':gaps,'action_max_difference':action_gap,'reference_action_objective_gap':objective_gap,'python_seconds':python,'cpp_seconds':cpp,'speedup':python/cpp})
report={'status':'PASS','full_native_DP_policy_equivalence':False,'compatible_DP_exact_arrays':True,'scope':'Kernel values and same-reference greedy objective; nonunique optimal actions are reported separately. Full closed-loop and independent review still required.','records':records,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*') if p.is_file() and p.suffix in ['.py','.cpp','.dylib']}}
(ROOT/'artifacts/cpp-migration/kernel-equivalence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'PASS','cases':len(records),'max_action_difference':max(r.get('action_max_difference',0) for r in records),'median_DP_speedup':float(np.median([r['speedup'] for r in records if 'speedup' in r]))}))
