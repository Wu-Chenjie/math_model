import json
from analyze_joint import ROOT,paired
result={'baseline':'previous default two-step DP','final_method':56,'iid':paired('iid3_baseline.csv','iid3_final.csv',1910001,200,56),'stress':{}}
for k,start in enumerate([1920001,1930001,1940001,1950001,1960001],1):result['stress'][k]=paired(f'stress3_{k}_0.csv',f'stress3_{k}_56.csv',start,40,56)
(ROOT/'results/summary_stage3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
