"""Summarize the actual trained scalar lower-envelope shape, not the unknown optimum."""
from pathlib import Path
import json
from collections import Counter
from control import prune_cuts
ROOT=Path(__file__).resolve().parents[1]
def main():
    models=[]
    for path in sorted((ROOT/'artifacts/tails').glob('*.json')):
        if '_D' in path.stem or path.stem.endswith('_14'):continue
        m=json.loads(path.read_text());assert m['iterations']==500
        cuts=prune_cuts(m['root_cuts'])
        models.append({'model':path.stem,'active_root_cut_count':len(cuts),'active_slopes':[float(b) for a,b in cuts]})
    assert len(models)==44
    result={'scope':'44 monthly three-day auxiliary lower envelopes on inventory1200..10800, after500iterations. This describes computed lower approximations, not exact value-function shape.',
      'models':models,'count':len(models),'active_cut_count_distribution':dict(Counter(str(m['active_root_cut_count']) for m in models)),
      'single_segment_models':sum(m['active_root_cut_count']==1 for m in models)}
    result['minimum_active_cuts']=min(m['active_root_cut_count'] for m in models)
    result['maximum_active_cuts']=max(m['active_root_cut_count'] for m in models)
    (ROOT/'artifacts/tail-shape-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='models'})
if __name__=='__main__':main()
