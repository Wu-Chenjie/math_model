"""Counterfactual validation and parameter sweeps, distinct from model selection."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import json,time,sys,argparse,hashlib
import numpy as np
import forecasting
from run import ROOT,simulate,dump

ORIGINAL_FORECAST=forecasting.forecast_as_of

def forecast_with_releases(allowed):
    def restricted(data,selection,asof,targets,official,variable):
        if not official:return ORIGINAL_FORECAST(data,selection,asof,targets,official,variable)
        pred=ORIGINAL_FORECAST(data,selection,asof,targets,False,variable)
        issue=max(i for i in range(max(0,(asof//144-1)*144),asof+1,36) if (i%144)//36 in allowed)
        d,k=divmod(issue//36,4);anchor=data['pv'].ravel()[issue-1] if issue else 0.
        mask=(targets+1<=issue+144)&(targets+1>=issue)
        pred['pv'][mask]=np.interp(targets[mask]+1,issue+np.arange(25)*6,np.r_[anchor,data['forecast'][d,k]])
        pred['net']=(pred['load']-pred['pv'])/6;pred['official_covered_slots']=int(mask.sum())
        return pred
    return restricted

def job(config):
    data=dict(np.load(ROOT/'artifacts/data.npz'));selection=json.loads((ROOT/'artifacts/forecast-selection.json').read_text())
    kind=config.get('kind','q3');start=config.get('start',72);stop=config.get('stop',79)
    days=list(range(start,stop));settings={'count':7,'horizon_days':2,'tail_scale':1.,'grid':321,'final':None}
    for k in list(settings):
        if k in config:settings[k]=config[k]
    if config.get('stress'):
        data['load'][start:stop]*=1.1;data['pv'][start:stop]*=.8
    forecasting.forecast_as_of=forecast_with_releases(config['releases']) if 'releases' in config else ORIGINAL_FORECAST
    a,m=simulate(data,selection,days,kind,'markov_mpc',**settings)
    m['validation_design']=config
    out=ROOT/'artifacts/experiments';out.mkdir(exist_ok=True)
    np.savez_compressed(out/(config['name']+'.npz'),**a);dump(out/(config['name']+'.json'),m)
    return {'name':config['name'],'total_cost':m['totals']['total_cost'],'runtime_seconds':m['runtime_seconds']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);parser.add_argument('--scope',choices=['short','annual-releases'],default='short');args=parser.parse_args()
    # These are matched finite seven-day subproblems, not annual savings estimates.
    configs=[{'name':'reference','kind':'q3'},{'name':'grid161','grid':161},{'name':'grid641','grid':641},
      {'name':'scenarios14','count':14},{'name':'horizon3','horizon_days':3},
      {'name':'tail_zero','tail_scale':0.},{'name':'tail_double','tail_scale':2.},
      {'name':'terminal6000','final':6000.},{'name':'stress_load_up_pv_down','stress':True},
      {'name':'pv_0only','releases':[0]},{'name':'pv_without6','releases':[0,2,3]},
      {'name':'pv_without12','releases':[0,1,3]},{'name':'pv_without18','releases':[0,1,2]},
      {'name':'variable_reference','kind':'q4_3'},{'name':'variable_stress','kind':'q4_3','stress':True}]
    if args.scope=='annual-releases':
        configs=[{'name':'annual_pv_'+name,'kind':'q3','start':31,'stop':365,'releases':releases} for name,releases in [('0only',[0]),('without6',[0,2,3]),('without12',[0,1,3]),('without18',[0,1,2])]]
    start=time.perf_counter();results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        fs=[pool.submit(job,c) for c in configs]
        for f in as_completed(fs):r=f.result();results.append(r);print(json.dumps(r),flush=True)
    dump(ROOT/f'artifacts/execution-experiments-{args.scope}.json',{'command':'python3 '+' '.join(sys.argv),'exit_code':0,'runtime_seconds':time.perf_counter()-start,
         'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results,
         'scope':'February–December continuous matched release ablations.' if args.scope=='annual-releases' else 'Prespecified seven-day March subproblems; common initial SOC6000 and free endpoint except the terminal comparison. Do not extrapolate their cost differences to annual totals.'})

if __name__=='__main__':main()
