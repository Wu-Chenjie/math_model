import json
from analyze_joint import ROOT,paired
result={'baseline':'previous default two-step DP','final_method':39,'iid':paired('iid2_baseline.csv','iid2_final.csv',1710001,200,39),'stress':{}}
for k,start in enumerate([1720001,1730001,1740001,1750001,1760001],1):result['stress'][k]=paired(f'stress2_{k}_0.csv',f'stress2_{k}_39.csv',start,40,39)
(ROOT/'results/summary_stage2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
