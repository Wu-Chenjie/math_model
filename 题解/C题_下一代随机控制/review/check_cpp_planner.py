#!/usr/bin/env python3
"""Independent original-v-native LP assembly checks; HiGHS is never called."""
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import copy,hashlib,json,sys,tempfile,subprocess,shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cpp'),str(ROOT/'src')]
import control,nextgen_control as reference,native_planner as candidate,native
from nextgen_scenarios import Config
OUT=ROOT/'artifacts/cpp-migration'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def arrays_equal(a,b):return bool(np.array_equal(np.asarray(a),np.asarray(b),equal_nan=True))
def delta(a,b):
    a,b=np.asarray(a),np.asarray(b)
    if a.shape!=b.shape:return None
    ok=np.isfinite(a)&np.isfinite(b)
    return float(np.max(np.abs(a[ok]-b[ok]),initial=0))

def captured_call(function,bundle,config,args,solution=None):
    old=control.lp_solve,reference.lp_solve,candidate.lp_solve;captured={}
    def fake(obj,A,b,bounds,*a,**k):
        csr=A.tocsr();x=solution if solution is not None else np.sin(np.arange(len(obj))*.013)
        assert len(x)==len(obj)
        captured.update(obj=np.asarray(obj),rhs=np.asarray(b),bounds=np.asarray([[np.nan if lo is None else lo,np.nan if hi is None else hi] for lo,hi in bounds]),
            indptr=csr.indptr,indices=csr.indices,values=csr.data,shape=np.asarray(csr.shape))
        return SimpleNamespace(x=x,fun=float(obj@x),violation=float(max(0,np.max(csr@x-b))))
    try:
        control.lp_solve=reference.lp_solve=candidate.lp_solve=fake
        result=function(bundle,args['asof'],args['inventory'],config,base=args.get('base'),adjust=args['adjust'],
            tail_price=args['tail_price'],terminal=args.get('terminal'),tail_cuts=args.get('tail_cuts'))
        return captured,result
    finally:control.lp_solve,reference.lp_solve,candidate.lp_solve=old

def compare(name,bundle,config,args,solution=None,stored=None):
    a,ar=captured_call(reference.affine_plan,bundle,config,args,solution)
    b,br=captured_call(candidate.affine_plan,bundle,config,args,solution)
    checks={k:arrays_equal(a[k],b[k]) for k in a}
    diffs={k:delta(a[k],b[k]) for k in a}
    outputs={k:arrays_equal(ar[k],br[k]) if isinstance(ar[k],(np.ndarray,float,int)) else ar[k]==br[k]
        for k in ar if k!='runtime_seconds'}
    frozen={} if stored is None else {k:arrays_equal(a[k],stored[k]) for k in a}
    assert all(checks.values()) and all(outputs.values()) and all(frozen.values()),(name,checks,outputs,frozen,diffs)
    return {'case':name,'LP_exact':checks,'output_exact':outputs,'saved_LP_exact':frozen,'max_abs_differences':diffs,
            'dimensions':a['shape'].tolist(),'nnz':len(a['values'])},ar

def historical_cases():
    rows=[]
    for folder in sorted(OUT.glob('q4_3_*h_*')):
        info=json.loads((folder/'profile.json').read_text())
        for name,digest in info['fixtures'].items():assert sha(folder/name)==digest,'Captured fixture changed: '+name
        bundle=copy.deepcopy(info['scenario_metadata'])
        with np.load(folder/'scenario-bundle.npz',allow_pickle=False) as z:
            for key in z:
                if '__' in key:
                    group,name=key.split('__',1);bundle.setdefault(group,{})[name]=z[key]
                else:bundle[key]=z[key]
        with np.load(folder/'linear-program.npz',allow_pickle=False) as z:stored=dict(z)
        cfg=Config(**info['configuration']);args={'asof':info['origin_slot'],'inventory':info['inventory'],'adjust':True,'tail_price':info['tail_price']}
        row,result=compare(folder.name,bundle,cfg,args,stored['solution'],stored)
        with np.load(folder/'contract-result.npz',allow_pickle=False) as z:
            row['saved_contract_exact']={k:arrays_equal(result[k],z[k]) for k in z}
        assert all(row['saved_contract_exact'].values());rows.append(row)
    assert len(rows)==4;return rows

def synthetic_cases():
    rng=np.random.default_rng(20260912);rows=[]
    for flavor in ('legacy_uniform','legacy_weighted','state2','state4'):
        for adjust in (False,True):
            for edge,T,shift,terminal,cuts in [('one_slot',1,0,None,None),('nonmidnight_terminal',108,36,6000.,None),
                ('cross_midnight_base',216,36,None,None),('midnight_tail_cuts',252,36,None,[[0.,0.],[500.,-.2],[-900.,.1]])]:
                S=3;F=4 if flavor=='state4' else 2
                weights=np.full(S,1/S) if flavor=='legacy_uniform' else np.array([.2,.3,.5])
                bundle={'net':rng.normal(300,100,(S,T)),'prices':rng.uniform(.3,1.4,(S,T)),'weights':weights,
                    'states':rng.normal(0,20,(S,T,F)),'seed':np.array([5.,3.,.1,.02]),'forecast':{'price':rng.uniform(.2,1.3,T)},
                    'history_net_error':rng.normal(0,30,(4,T)),'history_price_error':rng.normal(0,.1,(4,T))}
                cfg=Config(upper='state' if flavor.startswith('state') else 'legacy',alpha=.2 if flavor=='legacy_uniform' else .1)
                args={'asof':24*144+shift,'inventory':5432.,'adjust':adjust,'tail_price':.24,'terminal':terminal,'tail_cuts':cuts,
                    'base':rng.uniform(0,400,min(T,144-shift)) if shift else None}
                row,_=compare(f'{flavor}_{adjust}_{edge}',bundle,cfg,args);rows.append(row)
    return rows

class NativeDispatch(BaseException):pass

def boundary_checks():
    saved=native.lib;rows=[]
    def trap(*a):raise NativeDispatch
    native.lib=SimpleNamespace(mg_expression=trap)
    try:
        for name,changes in [('control',{}),('zero_scenarios',{'S':0}),('zero_times',{'T':0}),('zero_features',{'F':0}),
            ('negative_origin',{'asof':-1}),('negative_intercept',{'intercept':-1}),('negative_gain',{'gain':-1}),
            ('column_overflow',{'N':2}),('int32_column_overflow',{'intercept':2**31}),('numpy_int64_origin_overflow',{'asof':np.int64(2**63-1)})]:
            kw=dict(which='E',S=1,T=2,F=2,asof=3456,N=30,intercept=4,gain=10);kw.update(changes)
            kw.update(energy=np.zeros((kw['S'],kw['T'],kw['F'])),previous=np.zeros((kw['S'],kw['T'],kw['F'])),base=None)
            try:native.expression(**kw);outcome='returned'
            except NativeDispatch:outcome='native_dispatched'
            except (ValueError,TypeError,OverflowError) as e:outcome='rejected:'+str(e)
            rows.append({'case':name,'outcome':outcome})
    finally:native.lib=saved
    return rows

def binding_checks():
    rows=[]
    for mutation in ('control','stale_kernel','stale_binary','stale_reference','stale_adapter','empty_adapter_binding','missing_reference_binding','loaded_binary_replaced'):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);cpp=root/'cpp';cpp.mkdir();(root/'src').mkdir()
            for name in ('native.py','native_planner.py','native_feedback.py','native_enhanced.py','adapter-sources.json','generate_adapters.py','build.json','kernels.cpp','libmicrogrid.dylib'):
                shutil.copy2(ROOT/'cpp'/name,cpp/name)
            for name in ('control.py','nextgen_control.py'):shutil.copy2(ROOT/'src'/name,root/'src'/name)
            if mutation=='stale_kernel':(cpp/'kernels.cpp').write_text((cpp/'kernels.cpp').read_text()+'\n// stale\n')
            elif mutation=='stale_binary':
                with (cpp/'libmicrogrid.dylib').open('ab') as f:f.write(b'changed')
            elif mutation=='stale_reference':(root/'src/control.py').write_text((root/'src/control.py').read_text()+'\n# stale\n')
            elif mutation=='stale_adapter':(cpp/'native_planner.py').write_text((cpp/'native_planner.py').read_text()+'\n# stale\n')
            elif mutation=='empty_adapter_binding':(cpp/'adapter-sources.json').write_text('{}')
            elif mutation=='missing_reference_binding':
                bindings=json.loads((cpp/'adapter-sources.json').read_text());bindings.pop('src/control.py')
                (cpp/'adapter-sources.json').write_text(json.dumps(bindings))
                (root/'src/control.py').write_text((root/'src/control.py').read_text()+'\n# stale\n')
            # Existing originals supply dependencies. Binding paths must still refer to copied adapter's own project.
            code='''import sys,json,hashlib
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[2]]
import native_planner,native
if sys.argv[3]=='loaded_binary_replaced':
 root=Path(sys.argv[1]);library=root/'libmicrogrid.dylib';fresh=library.with_suffix('.swap')
 fresh.write_bytes(library.read_bytes()+b'fixture replacement');fresh.replace(library)
 record=json.loads((root/'build.json').read_text());record['binary_sha256']=hashlib.sha256(library.read_bytes()).hexdigest()
 (root/'build.json').write_text(json.dumps(record));native.validate_artifacts()
print('IMPORTED')
'''
            proc=subprocess.run([sys.executable,'-c',code,str(cpp),str(ROOT/'src'),mutation],capture_output=True,text=True)
            rows.append({'case':mutation,'imported':proc.returncode==0,'error':proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else None})
    return rows

def main():
    source_paths=[ROOT/'cpp'/n for n in ('native.py','native_planner.py','native_feedback.py','native_enhanced.py','kernels.cpp','libmicrogrid.dylib','adapter-sources.json','build.json','run_case.py')]+[ROOT/'src/control.py',ROOT/'src/nextgen_control.py',Path(__file__)]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    historical=historical_cases();synthetic=synthetic_cases();boundaries=boundary_checks();bindings=binding_checks()
    issues=[r['case'] for r in boundaries if (r['outcome']=='native_dispatched')!=(r['case']=='control')]
    issues += [r['case'] for r in bindings if r['imported']!=(r['case']=='control')]
    report={'status':'CHANGES_REQUESTED' if issues else 'PASS_WITHIN_SCOPE','independent':True,'reviewer_id':'/root/upgrade_code_review',
        'scope':'Four original January LPs with cached solutions plus 32 algebraic boundary cases. No solver called; synthetic solutions are arbitrary vectors for algebraic identity, not feasible policy claims. ctypes boundary probes stop before the native call; hash mutations use temporary copies.',
        'captured_cases':historical,'synthetic_cases':synthetic,'input_guards':boundaries,'import_binding':bindings,'issues':issues,
        'source_hashes':hashes}
    assert hashes=={str(p.relative_to(ROOT)):sha(p) for p in source_paths},'Native/reference source changed during review'
    (OUT/'independent-planner-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'captured_cases':len(historical),'synthetic_cases':len(synthetic),'input_guards':boundaries,'import_binding':bindings,'issues':issues},ensure_ascii=False))
    return bool(issues)
if __name__=='__main__':sys.exit(main())
