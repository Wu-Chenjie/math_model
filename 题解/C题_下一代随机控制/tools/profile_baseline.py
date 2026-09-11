"""Profile unchanged baseline on January only; not an upgrade experiment."""
from pathlib import Path
import cProfile,pstats,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'C题_下一代基线复现'
sys.path.insert(0,str(BASE/'src'))
from run import simulate
data=dict(np.load(BASE/'artifacts/data.npz'))
selection=json.loads((BASE/'artifacts/forecast-selection.json').read_text())
p=cProfile.Profile();start=time.perf_counter()
p.enable();arrays,metrics=simulate(data,selection,[24,25],'q2','markov_mpc');p.disable()
p.dump_stats(ROOT/'artifacts/baseline-profile.prof')
stats=pstats.Stats(p)
rows=[{'file':key[0],'line':key[1],'function':key[2],'primitive_calls':v[0],'calls':v[1],'self_seconds':v[2],'cumulative_seconds':v[3]} for key,v in stats.stats.items()]
rows.sort(key=lambda r:r['cumulative_seconds'],reverse=True)
record={'purpose':'January-only performance profile of unchanged code; no model selection or upgrade results','days':[24,25],'runtime_seconds':time.perf_counter()-start,'profiled_cost':metrics['totals']['total_cost'],'functions':rows[:35]}
(ROOT/'artifacts/baseline-profile.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
