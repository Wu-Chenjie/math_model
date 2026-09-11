"""Paired, alternating-order feedback builds on legal January LP fixtures."""
from pathlib import Path
import sys,json,time,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'cpp'),str(ROOT/'src')]
from nextgen_control import WeightedMarkovDP as Reference
from native_feedback import WeightedMarkovDP as Compatible
from run_case import backend_hashes

def main():
    rows=[];hashes={}
    for folder in sorted((ROOT/'artifacts/cpp-migration').glob('q4_3_*h_*')):
        profile=json.loads((folder/'profile.json').read_text());config=profile['configuration']
        with np.load(folder/'scenario-bundle.npz') as z:net=z['net'];prices=z['prices'];weights=z['weights']
        with np.load(folder/'contract-result.npz') as z:q=z['r']
        args=(net,prices,q,weights,profile['tail_price'],config['grid'],config['bins'],profile['terminal'],None)
        timing={'reference':[],'compatible':[]}
        for repetition in range(4):
            objects={}
            for name,cls in ([('reference',Reference),('compatible',Compatible)] if repetition%2==0 else [('compatible',Compatible),('reference',Reference)]):
                start=time.perf_counter();objects[name]=cls(*args);elapsed=time.perf_counter()-start
                if repetition:timing[name].append(elapsed)
            a,b=[x.legacy if x.legacy is not None else x for x in objects.values()]
            for attr in ['future','price','initial_values','cuts']:assert np.array_equal(getattr(a,attr),getattr(b,attr))
        python=float(np.median(timing['reference']));cpp=float(np.median(timing['compatible']))
        rows.append({'fixture':folder.name,'reference_seconds':python,'compatible_seconds':cpp,'feedback_speedup':python/cpp,'measurements':timing})
        for name in ['profile.json','scenario-bundle.npz','contract-result.npz']:
            p=folder/name;hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    report={'status':'PASS','scope':'Feedback build only, same machine, warm-up excluded, alternating order. Not an annual/end-to-end speedup claim.','rows':rows,'median_feedback_speedup':float(np.median([r['feedback_speedup'] for r in rows])),'backend_hashes':backend_hashes(),'fixture_hashes':hashes}
    (ROOT/'artifacts/cpp-migration/compatible-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()
