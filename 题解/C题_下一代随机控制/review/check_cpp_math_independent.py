"""Independent bounded C++ migration review; no annual controller replay."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import ast,hashlib,json
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'review/cpp-numeric-snapshot/cpp'
sys.path[:0]=[str(SNAP),str(ROOT/'src')]
import control
import nextgen_control as ref
import native
import native_feedback as compat
import native_enhanced as enhanced

rng=np.random.default_rng(2026091141)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def body(path,name):
 tree=ast.parse(Path(path).read_text())
 return ast.dump(next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name),include_attributes=False)
def diff(a,b):return float(np.max(np.abs(np.asarray(a)-np.asarray(b)),initial=0))

def explicit_lp(g,v,E,a,p):
 # Independent explicit charge/discharge, inventory, emergency and PL epigraph.
 # x=(c,d,E_next,e,theta), grid PL is convex.
 slopes=np.diff(v)/np.diff(g); intercept=v[:-1]-slopes*g[:-1]
 Aub=[[1,-1,0,-1,0]];bub=[-a]
 for slope,b in zip(slopes,intercept):Aub.append([0,0,slope,0,-1]);bub.append(-b)
 result=linprog([0,0,0,5*p,1],A_ub=Aub,b_ub=bub,A_eq=[[-.9,1/.9,1,0,0]],b_eq=[E],
  bounds=[(0,5000/6),(0,5000/6),(g[0],g[-1]),(0,None),(None,None)],method='highs')
 assert result.success,result.message
 return float(result.fun)

def main():
 report={'reviewer_id':'/root/independent_review','independent':True,'scope':'bounded_Cpp_PL_and_feedback_math_parity_only',
  'annual_optimization_executed':False,'native_snapshot_build':json.loads((SNAP/'build.json').read_text()),
  'numpy_version':np.__version__,'checks':{},'unresolved':[]}
 assert body(ROOT/'src/control.py','MarkovDP')==body(SNAP/'native_feedback.py','MarkovDP')
 assert body(ROOT/'src/nextgen_control.py','WeightedMarkovDP')==body(SNAP/'native_feedback.py','WeightedMarkovDP')
 assert body(ROOT/'src/nextgen_control.py','EnhancedMarkovDP')==body(SNAP/'native_enhanced.py','EnhancedMarkovDP')
 report['checks']['compatibility_class_ast_identical_except_imported_convolution']=True
 conv=[]; lp_gaps=[]
 for G in [2,17,161,321,641]:
  g=np.linspace(1200,10800,G)
  for case in range(14):
   if case%5==0:v=np.zeros(G)
   elif case%5==1:v=-.333333333333*g
   elif case%5==2:v=1000*np.abs(g-6000)
   elif case%5==3:v=np.maximum.reduce([np.zeros(G),-1000+.2*g,3000-.5*g])
   else:v=np.r_[0,np.cumsum(np.sort(rng.uniform(-2,2,G-1))*np.diff(g))]
   a=[0.,-5000/6,5000/6,float(rng.normal(0,1200))][case%4]
   p=[0.,.001,.7,1.25][case%4]
   py=control.inf_convolution(g,v,a,p);cpp=native.inf_convolution(g,v,a,p)
   conv.append({'G':G,'case':case,'bit_equal':bool(np.array_equal(py,cpp)),'max_error':diff(py,cpp)})
   # Verify selected grid nodes against an independent explicit LP, not merged slopes.
   if G in [17,161] and case<8:
    for i in [0,G//2,G-1]:lp_gaps.append(abs(cpp[i]-explicit_lp(g,v,g[i],a,p)))
 report['checks']['convolution']={'cases':len(conv),'all_bit_equal':all(x['bit_equal'] for x in conv),
  'max_error':max(x['max_error'] for x in conv),'records':conv,
  'independent_explicit_LP_cases':len(lp_gaps),'independent_LP_max_error':max(lp_gaps)}
 dp=[]
 for case in range(14):
  S=[1,2,7,14][case%4];T=[1,5,36,144,576][case%5];G=[41,161,321][case%3]
  B=3 if case%2==0 else 5
  net=np.zeros((S,T)) if case%4==0 else rng.normal(200,170,(S,T))
  prices=np.full((S,T),.4) if case%3==0 else rng.uniform(.001,1.4,(S,T))
  q=rng.uniform(0,500,T);w=np.full(S,1/S) if case%2==0 else rng.dirichlet(np.ones(S))
  terminal=6000. if case%4==0 else None
  cuts=[[0.,0.],[-1000.,.2]] if case%4==1 else None
  args=(net,prices,q,w,.35,G,B,terminal,cuts)
  a=ref.WeightedMarkovDP(*args);b=compat.WeightedMarkovDP(*args);raw=native.WeightedMarkovDP(*args)
  av=a.legacy if a.legacy is not None else a;bv=b.legacy if b.legacy is not None else b;rv=raw.legacy if raw.legacy is not None else raw
  equal={k:bool(np.array_equal(getattr(av,k),getattr(bv,k))) for k in ['cuts','future','price','initial_values']}
  raw_errors={k:diff(getattr(av,k),getattr(rv,k)) for k in ['cuts','future','price','initial_values']}
  acts=[];rawacts=[];objgaps=[]
  for j in sorted(set([0,T//2,T-1])):
   for E in [1200.,6000.,10800.,float(rng.uniform(1200,10800))]:
    for n in [float(net[0,j]),0.,1200.]:
     x=a.action(j,E,n,q[j]);y=b.action(j,E,n,q[j]);z=raw.action(j,E,n,q[j])
     acts.append(abs(x-y));rawacts.append(abs(x-z))
     k=int(np.sum(n>av.cuts[j]));p=av.price[j,k]
     objective=lambda u:5*p*max(0,n-q[j]+max(.9*(u-E),(u-E)/.9))+np.interp(u,av.grid,av.future[j,k])
     objgaps.append(abs(objective(x)-objective(z)))
  dp.append({'case':case,'S':S,'T':T,'G':G,'B':B,'terminal':terminal,'cuts':cuts,
   'compatibility_bit_equal':equal,'compatibility_max_action_gap':max(acts),
   'experimental_cpp_full_dp_errors':raw_errors,'experimental_cpp_max_action_gap':max(rawacts),
   'experimental_cpp_reference_objective_gap':max(objgaps)})
 report['checks']['M0']=dp
 # M1 reference class and compatibility class use identical state law/BLAS order.
 from types import SimpleNamespace
 m1=[]
 def states(en,ep,seeds,alpha,variable):
  count,steps=en.shape;seeds=np.broadcast_to(seeds,(count,4));x=np.empty((count,steps,4 if variable else 2))
  zn=seeds[:,1].copy();lastp=seeds[:,2].copy();zp=seeds[:,3].copy()
  for j in range(steps):
   zn=(1-alpha)*zn+alpha*en[:,j];x[:,j,:2]=np.c_[en[:,j],zn]
   if variable:
    x[:,j,2:]=np.c_[lastp,zp];lastp=ep[:,j];zp=(1-alpha)*zp+alpha*lastp
  return x
 for case in range(4):
  variable=case%2==1;S=5;T=9 if case<2 else 36;G=41 if case<2 else 161
  alpha=.2;rn=rng.normal(0,150,(8,T));rp=rng.normal(0,.06,(8,T));seeds=rng.normal(size=(8,4))*[100,30,.04,.02]
  seed=np.array([20.,10.,.02,.01]);fn=np.linspace(100,300,T);fp=np.full(T,.5)
  net=fn+rn[:S];prices=np.maximum(.001,fp+rp[:S]) if variable else np.tile(fp,(S,1))
  w=rng.dirichlet(np.ones(S));hx=states(rn,rp,seeds,alpha,variable)
  sx=states(net-fn,prices-fp,seed,alpha,variable)
  bundle={'net':net,'prices':prices,'states':sx,'weights':w,'forecast':{'price':fp},
   'history_states':hx,'history_net_error':rn,'history_price_error':rp,'origins':np.arange(8)*144+1008}
  cfg=SimpleNamespace(grid=G,alpha=alpha,ridge=1e-4,innovation_count=5)
  q=np.maximum(fn,0);terminal=6000. if case>=2 else None
  a=ref.EnhancedMarkovDP(bundle,q,4000,cfg,.3,terminal)
  b=enhanced.EnhancedMarkovDP(bundle,q,4000,cfg,.3,terminal)
  equal={k:bool(np.array_equal(getattr(a,k),getattr(b,k))) for k in ['future','price','initial_values']}
  gaps=[]
  for j in [0,T//2,T-1]:
   for E in [1200.,6000.,10800.]:
    gaps.append(abs(a.action(j,E,net[0,j],q[j],sx[0,j])-b.action(j,E,net[0,j],q[j],sx[0,j])))
  m1.append({'case':case,'variable_price':variable,'T':T,'G':G,'bit_equal':equal,'max_action_gap':max(gaps)})
 report['checks']['M1']=m1
 report['checks']['compatible_M1_all_arrays_and_actions_equal']=all(all(x['bit_equal'].values()) and x['max_action_gap']==0 for x in m1)
 report['checks']['compatible_M0_all_arrays_and_actions_equal']=all(all(x['compatibility_bit_equal'].values()) and x['compatibility_max_action_gap']==0 for x in dp)
 # Near-flat argmin is discontinuous: arbitrarily close convex values do not bound action error.
 eps=1e-12;lo,hi=6000-5000/(6*.9),6000+.9*5000/6
 report['checks']['analytic_tie_counterexample']={'feasible_interval':[lo,hi],
  'first_cost':'identically zero with smallest-candidate argmin',
  'second_cost':'epsilon * (hi-E_next)/(hi-lo)',
  'sup_objective_difference':eps,'argmin_action_difference_kwh':hi-lo,
  'implication':'Value/objective agreement does not certify deterministic policy agreement.'}
 if not report['checks']['convolution']['all_bit_equal']:report['unresolved'].append('compatibility convolution bit mismatch')
 if max(lp_gaps)>1e-5:report['unresolved'].append('explicit LP economic mismatch')
 if not report['checks']['compatible_M0_all_arrays_and_actions_equal']:report['unresolved'].append('compatibility M0 policy mismatch')
 if not report['checks']['compatible_M1_all_arrays_and_actions_equal']:report['unresolved'].append('compatibility M1 policy mismatch')
 report['status']='PASS' if not report['unresolved'] else 'FAIL'
 report['decision']='bounded_checks_only_not_permission_to_resume_experiments'
 report['replacement_gate']={'experimental_full_cpp_M0':'REJECTED_AS_STRICT_POLICY_EQUIVALENT','compatible_cpp_convolution_feedback':'BOUNDED_SYNTHETIC_CHECKS_PASS_REAL_CLOSED_LOOP_GATE_SEPARATE','resume_authorization':False}
 snapshot_paths=[p for p in SNAP.parent.rglob('*') if p.is_file()]
 live_paths=[ROOT/p.relative_to(SNAP.parent) for p in snapshot_paths]
 for saved,live in zip(snapshot_paths,live_paths):assert sha(saved)==sha(live),('Live source changed after snapshot',str(live))
 report['current_cpp_matches_reviewed_snapshot']=True
 paths=[*snapshot_paths,*live_paths,ROOT/'review/C++数值兼容与严格替换门槛.md',ROOT/'src/control.py',ROOT/'src/nextgen_control.py',ROOT/'src/nextgen_scenarios.py',Path(__file__)]
 report['reviewed_artifact_hashes']={str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file()}
 (ROOT/'review/cpp-math-independent.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'conv_bit_equal':report['checks']['convolution']['all_bit_equal'],
  'LP_error':max(lp_gaps),'M0_equal':report['checks']['compatible_M0_all_arrays_and_actions_equal'],
  'experimental_fullM0_max_action_difference':max(x['experimental_cpp_max_action_gap'] for x in dp)},ensure_ascii=False))
 if report['unresolved']:raise SystemExit(1)
if __name__=='__main__':main()
