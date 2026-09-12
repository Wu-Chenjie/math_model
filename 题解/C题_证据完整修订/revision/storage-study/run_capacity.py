"""Causal full-year usable-capacity ablation; process-local bounds, fixed 6000 endpoints."""
from pathlib import Path
import argparse,hashlib,json,sys,time,platform
import numpy as np
HERE=Path(__file__).resolve().parent
PAPER=HERE.parents[1]
BASE=PAPER.parent/'C题_跨日随机控制'
sys.path.insert(0,str(BASE/'src'))
import control
import run as production

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
class LockedInventory:
    """A zero-width feasible interval admits no battery action and no DP grid."""
    def __init__(self,*args,**kwargs):pass
    def action(self,j,E,net,q):return 6000.

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=list(production.KINDS),required=True);p.add_argument('--width',type=int,choices=[0,4800,9600],required=True);p.add_argument('--suffix-check',action='store_true');args=p.parse_args()
    start=time.perf_counter();width=args.width;lo=6000-width/2;hi=6000+width/2
    # Only these globals define physical bounds in affine_plan, MarkovDP and execute.
    # Separate OS processes prevent accidental contamination of concurrent cases.
    control.EMIN=lo;control.EMAX=hi
    assert production.affine_plan.__globals__ is control.__dict__
    assert production.execute.__globals__ is control.__dict__
    assert production.MarkovDP is control.MarkovDP
    if width==0:production.MarkovDP=LockedInventory
    data=dict(np.load(BASE/'artifacts/data.npz'));selection=json.loads((BASE/'artifacts/forecast-selection.json').read_text())
    initial=6000.;days=list(range(31,365))
    if args.suffix_check:
        assert width==9600
        ref=np.load(BASE/f'artifacts/global-terminal/{args.kind}_markov_mpc.npz')
        initial=float(ref['state'][-2,0]);days=[363,364]
    out=HERE/'results'/f'{args.kind}_W{width}'
    if args.suffix_check:out=out.with_name(out.name+'_suffix')
    calls=[0];original=production.scenarios
    def progress(*a,**kw):
        result=original(*a,**kw);calls[0]+=1
        if calls[0]%40==0:
            dump(out.with_suffix('.progress.json'),{'kind':args.kind,'width':width,'replanning_calls':calls[0],'elapsed_seconds':time.perf_counter()-start})
        return result
    production.scenarios=progress
    a,m=production.simulate(data,selection,days,args.kind,'markov_mpc',count=7,horizon_days=2,tail_scale=1.,grid=width//30+1 if width else 1,final=6000.,initial=initial)
    q,r,c,d,e,w,E,pr=[a[k] for k in ['q','r','c','d','emergency','spill','state','price']]
    assert E.min()>=lo-1e-5 and E.max()<=hi+1e-5
    assert abs(E[0,0]-initial)<1e-5 and abs(E[-1,-1]-6000)<1e-5
    assert np.max(abs(np.diff(E,axis=1)-.9*c+d/.9))<1e-5
    assert np.max(abs(r+e+d-c-w-(data['load'][days]-data['pv'][days])/6))<1e-5
    assert max(c.max(),d.max())<=5000/6+1e-5 and np.minimum(c,d).max()<1e-5
    daily=(pr*(r+.5*np.abs(r-q)+5*e)).sum(1)
    assert abs(daily.sum()-m['totals']['total_cost'])<1e-5
    if width==0:assert np.max(abs(E-6000))<1e-5 and max(c.max(),d.max())<1e-5
    m['capacity_experiment']={'usable_width_kwh':width,'emin_kwh':lo,'emax_kwh':hi,'initial_kwh':initial,'final_kwh':6000,'power_kw':5000,'grid_step_kwh':30 if width else None,'grid_nodes':width//30+1 if width else 1,'meaning':'operational window centered on the same inventory; not rated hardware-capacity sizing','suffix_check':args.suffix_check}
    m['execution']={'command':'python3 revision/storage-study/run_capacity.py '+' '.join(sys.argv[1:]),'exit_code':0,'runtime_seconds':time.perf_counter()-start,'environment':{'python':sys.version,'platform':platform.platform()},'source_hashes':{f:digest(BASE/'src'/f) for f in ['control.py','run.py','forecasting.py','dispatch.py']},'script_sha256':digest(Path(__file__)),'input_hashes':{f:digest(BASE/'artifacts'/f) for f in ['data.npz','forecast-selection.json']}}
    if args.suffix_check:
        m['reference_suffix_max_abs']={k:float(np.max(abs(a[k]-ref[k][-2:]))) for k in ['q','r','c','d','emergency','spill','state','price']}
        print('SUFFIX',m['reference_suffix_max_abs'],flush=True)
    np.savez_compressed(out.with_suffix('.npz'),**a);dump(out.with_suffix('.json'),m)
    print(json.dumps({'kind':args.kind,'width':width,'cost':m['totals']['total_cost'],'seconds':m['execution']['runtime_seconds']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
