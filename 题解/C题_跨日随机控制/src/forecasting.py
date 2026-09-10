"""Absolute-time, as-of forecasts and fully matured multiday residual blocks."""
import numpy as np

FAMILIES=('lag1','lag7','mean7','trend7')

def base_forecast(data,key,asof,targets,family):
    day=asof//144; td=targets//144; tt=targets%144; x=data[key]
    if day<1: raise ValueError('No preceding complete day')
    if family=='mean7': return x[max(0,day-7):day].mean(0)[tt]
    lag=1 if family=='lag1' else 7
    hd=np.minimum(td-lag,day-1);hd=np.maximum(0,hd)
    if family=='trend7':
        older=np.maximum(0,np.minimum(td-14,day-1))
        return np.maximum(0,2*x[hd,tt]-x[older,tt])
    return x[hd,tt].copy()

def select_families(data):
    out={}
    for key in ['load','pv','price']:
        scores={f:float(np.mean([np.abs(base_forecast(data,key,d*144,np.arange(d*144,(d+1)*144),f)-data[key][d]).mean() for d in range(14,31)])) for f in FAMILIES}
        out[key]={'selected':min(scores,key=scores.get),'january_mae':scores}
    return out

def forecast_as_of(data,selection,asof,targets,official,variable):
    """Only completed days, already observed intraday values, latest release."""
    pred={k:base_forecast(data,k,asof,targets,selection[k]['selected']) for k in ['load','pv','price']}
    day,t=divmod(asof,144)
    # A conservative observed-error correction, with a six-hour fading memory.
    # Coefficient 0.8 is a declared shrinkage, unchanged across annual runs.
    if t:
        past=np.arange(max(day*144,asof-36),asof)
        fade=np.exp(-(targets-asof)/36.)
        for k in ['load','pv','price']:
            err=data[k].ravel()[past]-base_forecast(data,k,day*144,past,selection[k]['selected'])
            pred[k]=np.maximum(0,pred[k]+.8*err.mean()*fade)
    official_covered=0
    if official:
        issue=(asof//36)*36; d,k=divmod(issue//36,4)
        anchor=data['pv'].ravel()[issue-1] if issue else 0.
        endpoints=np.arange(25)*6+issue
        mask=(targets+1<=issue+144)&(targets+1>=issue)
        pred['pv'][mask]=np.interp(targets[mask]+1,endpoints,np.r_[anchor,data['forecast'][d,k]])
        official_covered=int(mask.sum())
    if not variable: pred['price']=data['day_price'][targets%144]
    pred['price']=np.maximum(.001,pred['price'])
    pred['net']=(pred['load']-pred['pv'])/6
    pred['official_covered_slots']=official_covered
    return pred

def scenarios(data,selection,asof,end,official,variable,window=28,count=7):
    targets=np.arange(asof,end);T=len(targets); day,t=divmod(asof,144)
    # A block must be mature at the current decision time, including its last target.
    eligible=[h for h in range(max(7,day-window-3),day) if h*144+t+T<=asof]
    eligible=eligible[-window:]
    if not eligible: raise ValueError('No fully mature historical blocks')
    if count and len(eligible)>count:
        eligible=[eligible[j] for j in np.linspace(0,len(eligible)-1,count).round().astype(int)]
    current=forecast_as_of(data,selection,asof,targets,official,variable)
    ns=[];ps=[]
    for h in eligible:
        issue=h*144+t; ht=np.arange(issue,issue+T)
        old=forecast_as_of(data,selection,issue,ht,official,variable)
        actual=(data['load'].ravel()[ht]-data['pv'].ravel()[ht])/6
        ns.append(current['net']+actual-old['net'])
        ps.append(np.maximum(.001,current['price']+data['price'].ravel()[ht]-old['price']) if variable else current['price'])
    return np.array(ns),np.array(ps),{'as_of':asof,'end':end,'history_days':eligible,
        'latest_training_target_exclusive':max(eligible)*144+t+T,
        'official_covered_slots':current['official_covered_slots']}
