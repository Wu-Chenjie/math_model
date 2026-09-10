"""Readable full trajectories and specified-date tables for causal aggregators."""
import csv,json
import numpy as np
from run_comparison import ROOT,KINDS,dump

def interval(t,end=None):
    clock=lambda x:f'{x//6:02d}:{x%6*10:02d}'
    return clock(t)+'-'+clock(t+1 if end is None else end)

def table(header,rows):
    fmt=lambda x:f'{x:,.4f}' if isinstance(x,float) else str(x)
    return '\n'.join(['| '+' | '.join(header)+' |','|'+'|'.join(['---']*len(header))+'|']+
                     ['| '+' | '.join(map(fmt,r))+' |' for r in rows])

def main():
    result={};out=ROOT/'计算结果/综合策略';out.mkdir(exist_ok=True)
    chosen={'2025-03-20','2025-06-21','2025-09-23','2025-12-21'}
    text=['# 综合策略指定日期表',
          '本表与“1月选定后固定”的主xlsx分开。adaptive为过去28日选择单一专家，convex为过去28日优化的日内固定凸权重。两者均使用此前已结束日的信息，不以当天最低已实现费用决定动作。原始逐时数据与合同发布快照位于计算结果/综合策略。电量单位kWh，费用单位元。']
    for policy,label in [('adaptive','历史选择'),('convex','凸组合')]:
        result[policy]={}
        for kind in KINDS:
            a=dict(np.load(ROOT/f'artifacts/{kind}_{policy}.npz'))
            q,r,p,e=[a[k] for k in ['q','r','price','emergency']]
            bill=p*(q+1.5*np.maximum(r-q,0)-.5*np.maximum(q-r,0))
            total=(bill+5*p*e).sum(axis=1)
            totals={'total_cost':float(total.sum()),'contract_cost':float(bill.sum()),
                    'emergency_cost':float((5*p*e).sum()),'emergency_energy':float(e.sum())}
            summary=json.loads((ROOT/'artifacts/comparisons.json').read_text())[kind]['comparisons'][policy+'28']
            assert abs(totals['total_cost']-summary['total_cost'])<1e-4
            selected={};stem=f'{kind}_{label}'
            with (out/f'{stem}_逐时完整策略.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(['日期','时间段','计划购电_kWh','最终合同购电_kWh','充电_kWh','放电_kWh','紧急购电_kWh','弃电_kWh','电价_元每kWh','时段初SOC_kWh','时段末SOC_kWh'])
                for i,date in enumerate(a['dates']):
                    for t in range(144):
                        w.writerow([str(date),interval(t)]+[float(a[k][i,t]) for k in ['q','r','c','d','emergency','spill','price']]+[float(a['state'][i,t]),float(a['state'][i,t+1])])
            with (out/f'{stem}_发布记录.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(['日期','发布时间','交易时间段','合同购电_kWh'])
                for i,date in enumerate(a['dates']):
                    for k in range(4):
                        for t in range(k*36,144):
                            if np.isfinite(a['releases'][i,k,t]):w.writerow([str(date),f'{k*6:02d}:00',interval(t),float(a['releases'][i,k,t])])
            with (out/f'{stem}_费用汇总.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(['日期','合同费用_元','紧急费用_元','总费用_元','紧急电量_kWh'])
                for i,date in enumerate(a['dates']):w.writerow([str(date),float(bill[i].sum()),float((5*p[i]*e[i]).sum()),float(total[i]),float(e[i].sum())])
            for i,date in enumerate(a['dates']):
                date=str(date)
                if date not in chosen:continue
                purchases=[[interval(t),float(q[i,t]),float(r[i,t])] for t in [60,72,84,96,108,120]]
                battery=[[interval(t,t+24),float(a['c'][i,t:t+24].sum()),float(a['d'][i,t:t+24].sum())] for t in range(0,144,24)]
                emergency=[];start=None
                for t in range(145):
                    active=t<144 and e[i,t]>1e-6
                    if active and start is None:start=t
                    if not active and start is not None:emergency.append([interval(start,t),float(e[i,start:t].sum())]);start=None
                daily={'total_cost':float(total[i]),'contract_cost':float(bill[i].sum()),
                       'emergency_cost':float((5*p[i]*e[i]).sum()),'emergency_energy':float(e[i].sum()),
                       'planned_purchase_energy':float(q[i].sum()),'final_contract_energy':float(r[i].sum()),
                       'actual_purchase_energy':float((r[i]+e[i]).sum())}
                selected[date]={'purchase':purchases,'battery':battery,'emergency':emergency,'daily':daily,
                                'initial_soc':float(a['state'][i,0]),'terminal_soc':float(a['state'][i,-1])}
                text += [f'## {kind} {label} {date}',table(['时间段','0点计划q','最终合同r'],purchases),
                         table(['项目','数值'],list(daily.items())),table(['时间段','充电量','放电量'],battery),
                         table(['紧急购电时间段','紧急购电量'],emergency or [['无',0.]]),'日初、日末SOC均为6000kWh。']
            result[policy][kind]={'totals':totals,'selected':selected}
    dump(ROOT/'artifacts/aggregate-handoff-tables.json',result)
    (ROOT/'综合策略指定日期表.md').write_text('\n\n'.join(text)+'\n')
    print('Exported both causal aggregators as full CSVs and specified-date tables.')

if __name__=='__main__':main()
