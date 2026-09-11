"""Read-only Excel intake. Run with bundled Python (openpyxl, numpy)."""
from pathlib import Path
import json, hashlib, shutil, datetime, platform
import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / 'C题'

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')

def rows(path, sheet=0):
    w = openpyxl.load_workbook(path, read_only=True, data_only=True)
    s = w.worksheets[sheet] if isinstance(sheet, int) else w[sheet]
    out = list(s.values)
    w.close()
    return out

def main():
    inputs = ROOT/'inputs'
    for p in SOURCE.rglob('*'):
        if p.is_file() and p.suffix in ['.xlsx','.pdf']:
            dest=inputs/p.relative_to(SOURCE); dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest)
    a1=rows(inputs/'附件/附件1.xlsx')
    a2l=rows(inputs/'附件/附件2.xlsx','小区负载')
    a2v=rows(inputs/'附件/附件2.xlsx','光伏发电实际功率')
    a3=rows(inputs/'附件/附件3.xlsx')
    a4=rows(inputs/'附件/附件4.xlsx')
    dates=[r[0].date().isoformat() for r in a2l[1:]]
    load=np.array([r[1:] for r in a2l[1:]],float)
    pv=np.array([r[1:] for r in a2v[1:]],float)
    price=np.array([r[1:] for r in a4[1:]],float)
    forecasts=np.array([r[2:] for r in a3[1:]],float).reshape(365,4,24)
    day=np.array([r[1:] for r in a1[1:]],float)
    assert dates==[(datetime.date(2025,1,1)+datetime.timedelta(days=i)).isoformat() for i in range(365)]
    assert [r[0] for r in a2l[1:]]==[r[0] for r in a2v[1:]]==[r[0] for r in a4[1:]]
    def minute(x):
        if isinstance(x,datetime.time): return x.hour*60+x.minute
        if x=='0:00+1': return 1440
        h,m=str(x).split(':'); return int(h)*60+int(m)
    time_axes=[list(a2l[0][1:]),list(a2v[0][1:]),list(a4[0][1:]),[r[0] for r in a1[1:]]]
    assert all([minute(t) for t in axis]==list(range(10,1441,10)) for axis in time_axes)
    for i,r in enumerate(a3[1:]):
        if i%4==0: assert str(r[0])==f'2025-{a2l[1+i//4][0].month}-{a2l[1+i//4][0].day}'
        assert r[1]==['0:00','6:00','12:00','18:00'][i%4]
    np.savez_compressed(ROOT/'artifacts/data.npz',load=load,pv=pv,price=price,forecast=forecasts,
                        day_price=day[:,0],day_load=day[:,1],day_pv=day[:,2],dates=np.array(dates))
    stats={}
    for name,x in [('load',load),('pv',pv),('price',price),('forecast',forecasts),('q1',day)]:
        stats[name]={'shape':list(x.shape),'count':int(x.size),'missing':int(np.isnan(x).sum()),
                     'min':float(x.min()),'max':float(x.max()),'negative':int((x<0).sum()),
                     'quantiles':np.quantile(x,[0,.01,.5,.99,1]).tolist()}
        assert np.isfinite(x).all() and (x>=0).all()
    def corr_daily(x):
        return [float(np.corrcoef(x[:-lag].ravel(),x[lag:].ravel())[0,1]) for lag in [1,7]]
    stats['lag_correlations']={n:corr_daily(x) for n,x in [('load',load),('pv',pv),('price',price)]}
    stats['daily_load_energy_range']=[float(load.sum(1).min()/6),float(load.sum(1).max()/6)]
    stats['daily_pv_energy_range']=[float(pv.sum(1).min()/6),float(pv.sum(1).max()/6)]
    audit={'status':'completed','stats':stats,'date_range':[dates[0],dates[-1]],'evaluation_days':334,
           'checks':[{'name':n,'status':'pass'} for n in ['finite_nonnegative_values','365_unique_consecutive_days',
                    '144_aligned_samples_per_day','forecast_4_releases_24_leads','source_copies_hashed']],
           'issues':[{'type':'time_label_mismatch','evidence':'Inputs 00:10..24:00; template 00:10-00:20..next-day00:10.',
                      'resolution':'Treat input as right endpoint / interval mean of preceding 10min; correct output copy headers.'}],
           'units':{'load':'kW','pv':'kW','forecast':'kW','price':'CNY/kWh','time_step_hours':1/6},
           'data_policy':'No deletion or imputation. Repeated zero night PV is structural, not missing. Mixed Excel time/text types normalized to minutes.',
           'coverage':'January is calibration; February-December strictly prequential. Raw future data only for scoring.'}
    dump(ROOT/'artifacts/data-audit.json',audit)
    m=json.loads((ROOT/'modeling-manifest.json').read_text())
    paths=sorted(p.relative_to(ROOT).as_posix() for p in inputs.rglob('*') if p.is_file())
    m['source'].update(statement_files=['inputs/C题.pdf'],data_files=[p for p in paths if p.endswith('.xlsx')],
        input_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
        official_rules={'status':'verified','url':'https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html',
                        'version':'2026 revision; modeling handoff only, no competition submission claimed','reason':None})
    m['source']['official_statement_url']='https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html'
    m['project']['stage']='modeling'
    dump(ROOT/'modeling-manifest.json',m)
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__': main()
