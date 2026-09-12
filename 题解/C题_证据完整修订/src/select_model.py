"""Freeze model choice using January development results only."""
from pathlib import Path
import json,hashlib,time,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    started=time.perf_counter()
    result={'selection_period':[24,30],'evaluation_period':[31,364],'relative_tie_tolerance':.0001,
      'policy':'Choose minimum January development cost; within 0.01% prefer Markov feedback with linear tail. This script never reads annual costs.',
      'selected':{},'development_costs':{},'sddp_training_iterations_development':500,'sddp_training_iterations_evaluation':500}
    for kind in ['q2','q3','q4_2','q4_3']:
        vals={}
        for c in ['cross_baseline','affine_mpc','markov_mpc','sddp_mpc','sddp_markov']:
            phase='calibrate_sddp_v2' if c.startswith('sddp') else 'calibrate'
            m=json.loads((ROOT/f'artifacts/{phase}/{kind}_{c}.json').read_text())
            assert m['configuration']['start_day']==24 and m['configuration']['end_day']==30
            vals[c]=m['totals']['total_cost']
        chosen=min(vals,key=vals.get)
        if vals['markov_mpc']<=min(vals.values())*1.0001:chosen='markov_mpc'
        result['selected'][kind]=chosen;result['development_costs'][kind]=vals
    result['source_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').glob('*.py')}
    result['sddp_training_note']='Corrected development and annual auxiliary models both use500iterations, with finite-end1/2day truncation. Older development results remain archived.'
    (ROOT/'artifacts/selection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['selected'])
    (ROOT/'artifacts/execution-selection.json').write_text(json.dumps({'command':'python3 '+' '.join(sys.argv),'exit_code':0,'runtime_seconds':time.perf_counter()-started,'selected':result['selected'],'reads_annual_costs':False},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
