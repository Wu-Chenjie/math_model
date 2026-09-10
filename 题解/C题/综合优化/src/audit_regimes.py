"""Check that observed quantile regimes are nonempty on all used real data."""
import numpy as np
from run_comparison import ROOT,BASE,KINDS,dump
from forecasting import scenario_data

def main():
    data=dict(np.load(BASE/'artifacts/data.npz'));fc=dict(np.load(BASE/'artifacts/forecasts.npz'));out={}
    for name,(official,variable,updates) in KINDS.items():
        count=0;minimum=999;examples=[]
        for day in range(21,365):
            for k in [0,*updates]:
                n,_,_=scenario_data(data,fc,day,k,official,variable)
                cuts=np.quantile(n,[1/3,2/3],axis=0)
                labels=(n>cuts[0]).astype(int)+(n>cuts[1]).astype(int)
                counts=np.stack([(labels==j).sum(0) for j in range(3)])
                count+=int((counts==0).sum());minimum=min(minimum,int(counts.min()))
                if (counts==0).any() and len(examples)<3:examples.append([day,k])
        out[name]={'empty_regime_slot_count':count,'minimum_regime_samples':minimum,'examples':examples}
        assert count==0,'Empty deterministic regime requires a separately validated transition fallback'
    dump(ROOT/'artifacts/regime-audit.json',out);print(out)

if __name__=='__main__':main()
