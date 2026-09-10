"""Prequential forecasts: fit/choose on past observations only."""
import numpy as np

CANDIDATES=('lag1','lag7','mean7','trend7')

def predict(x,day,name):
    if day==0: raise ValueError('No history at day zero')
    if name=='lag1': return x[day-1].copy()
    if name=='lag7': return x[max(0,day-7)].copy()
    if name=='mean7': return x[max(0,day-7):day].mean(0)
    if name=='trend7':
        return np.maximum(0,2*x[max(0,day-7)]-x[max(0,day-14)])
    raise ValueError(name)

def make_forecasts(data):
    forecasts={}; selection={}
    for key in ['load','pv','price']:
        x=data[key]
        scores={name:float(np.mean([np.abs(predict(x,d,name)-x[d]).mean() for d in range(14,31)]))
                for name in CANDIDATES}
        chosen=min(scores,key=scores.get)
        selection[key]={'candidate_january_mae':scores,'selected':chosen,'selection_days':[14,30]}
        base=np.zeros_like(x)
        for d in range(1,365): base[d]=predict(x,d,chosen)
        by_release=np.repeat(base[:,None,:],4,axis=1)
        # A past-day regression maps the most recent 6-hour forecast error to remaining errors.
        # Each day is a full residual vector; lambda=0.25*sample variance stabilizes slope.
        for d in range(14,365):
            h=np.arange(max(7,d-28),d)
            for k in range(1,4):
                t=k*36
                err=x[h]-base[h]
                z=err[:,t-36:t].mean(1)
                zc=z-z.mean(); ec=err-err.mean(0)
                beta=(zc[:,None]*ec).mean(0)/(1.25*np.mean(zc**2)+1e-12)
                observed=(x[d,t-36:t]-base[d,t-36:t]).mean()
                by_release[d,k,t:]=np.maximum(0,base[d,t:]+err[:,t:].mean(0)+beta[t:]*(observed-z.mean()))
        forecasts[key]=by_release
    # Official forecasts report future hourly endpoints; interpolation uses a known release anchor.
    official=np.zeros((365,4,144))
    for d in range(365):
        for k in range(4):
            t=k*36
            anchor=(data['pv'][d,t-1] if t else data['pv'][d-1,-1] if d else 0.)
            vals=np.r_[anchor,data['forecast'][d,k]]
            official[d,k,t:]=np.interp(np.arange(1,145-t)/6,np.arange(25),vals)
    forecasts['official_pv']=official
    return forecasts,selection

def scenario_data(data,fc,day,release,official=False,variable_price=False,window=28,deterministic=False):
    """Only residuals from strictly earlier days enter a release's scenarios."""
    t=release*36
    hist=np.arange(max(14,day-window),day)
    if not len(hist): hist=np.arange(max(7,day-7),day)
    pv_key='official_pv' if official else 'pv'
    fnet=fc['load'][day,release]-fc[pv_key][day,release]
    errors=(data['load'][hist]-fc['load'][hist,release])-(data['pv'][hist]-fc[pv_key][hist,release])
    net=(fnet[None,:]+errors)[:,t:]/6
    if variable_price:
        prices=np.maximum(.001,(fc['price'][day,release]+data['price'][hist]-fc['price'][hist,release])[:,t:])
    else: prices=np.repeat(data['day_price'][None,t:],len(hist),axis=0)
    if deterministic:
        net=fnet[None,t:]/6
        prices=(fc['price'][day,release,t:][None,:] if variable_price else data['day_price'][None,t:])
        prices=np.maximum(.001,prices)
    return net,prices,hist
