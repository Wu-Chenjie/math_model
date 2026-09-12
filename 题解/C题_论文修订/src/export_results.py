"""Prepare numerical handoff tables, detailed CSVs and an artifact-tool workbook payload."""
from pathlib import Path
import csv,json,shutil,sys,time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'计算结果'; OUT.mkdir(exist_ok=True)
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def clock(i):return f'{i//6:02d}:{(i%6)*10:02d}'
def interval(i,j=None):return clock(i)+'-'+clock(i+1 if j is None else j)
def writecsv(name,header,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)
def events(values,date):
    out=[];start=None
    for t in range(145):
        active=t<144 and values[t]>1e-6
        if active and start is None:start=t
        if not active and start is not None:
            out.append([date,interval(start,t),float(values[start:t].sum())]);start=None
    return out
def markdown_table(header,rows):
    def fmt(v):return f'{v:,.4f}' if isinstance(v,float) else str(v)
    return '\n'.join(['| '+' | '.join(header)+' |','|'+'|'.join(['---']*len(header))+'|']+
                     ['| '+' | '.join(fmt(v) for v in r)+' |' for r in rows])

def main():
    started=time.perf_counter()
    selection=json.loads((ROOT/'artifacts/selection.json').read_text())
    for kind,candidate in selection['selected'].items():
        phase='annual_sddp' if candidate.startswith('sddp') else 'annual'
        for ext in ['json','npz']:shutil.copy2(ROOT/f'artifacts/{phase}/{kind}_{candidate}.{ext}',ROOT/f'artifacts/{kind}.{ext}')
    data=dict(np.load(ROOT/'artifacts/data.npz'));q1=json.loads((ROOT/'artifacts/q1.json').read_text());q1.update({k:v.tolist() for k,v in dict(np.load(ROOT/'artifacts/q1.npz')).items()});q1['daily_energy']=float(sum(q1['q']));q1['daily_cost']=float(data['day_price']@np.array(q1['q']))
    labels=[interval(t) for t in range(144)]
    notes=[['项目','口径'],['官方原题','https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html'],
           ['时间轴','原输入00:10至24:00按前10分钟区间均值处理；输出时间段改正为00:00-00:10至23:50-24:00。'],
           ['单位','购电、充放电、SOC均为kWh；费用为元；充放电量在交流母线侧计量。'],
           ['储能效率','充电和放电各0.9；SOC=上一时段SOC+0.9充电量-放电量/0.9。'],
           ['年度边界','只输出2025年2月1日至12月31日。1月为校准，初始SOC6000，1月储能保持6000；主策略SOC跨日连续、年末库存自由；一次全局期末6000仅作对照。'],
           ['计划购电量','0点承诺量q；全天购电费列仅为计划成本Σp*q。'],
           ['调整购电量','当天逐次调整后最终执行量r，非增减差值；全天购电费为计划成本加调整净费用，未含紧急。'],
           ['费用汇总','总费用=计划成本+1.5p增购量-0.5p退购量+5p紧急量；已购电实物总量=r+紧急量。'],
           ['退购结算','主口径：退购部分原电费被50%违约费替代；相对0点基准逐时最终净额结算。若解释为不退款，必须改变目标函数并重算，本目录未将其作为已验证结果。'],
           ['弃电口径','弃电量为母线总富余弃置，可能包含已购买电能，不能直接视为光伏弃电量或用于计算纯光伏利用率。'],
           ['充放电量','问题2-4填写因果实时反馈后的实际充放电，非0点LP预计划。'],
           ['紧急购电量','连续非零10分钟段合并；未发生的日期填无、0。小于1e-6 kWh视为数值零。'],
           ['预测与信息','仅用过往日期数据与已发布的光伏预报；实际未来电价只用于事后结算。'],
           ['最优性边界','Q1确定性LP；Q2-4跨日因果仿射策略SAA计划+Markov随机动态规划反馈，SDDP作为末值备选，为经过验证的可行策略，不声称完整随机问题全局最优。']]
    payload={'labels':labels,'notes':notes,'q1':q1,'models':{}}
    tables={'q1':{'purchase':[[labels[t],float(q1['q'][t])] for t in [60,72,84,96,108,120]],
                  'energy':q1['daily_energy'],'cost':q1['daily_cost'],
                  'battery':[[interval(b,b+24),float(sum(q1['c'][b:b+24])),float(sum(q1['d'][b:b+24]))] for b in range(0,144,24)],
                  'soc':[q1['state'][0],q1['state'][-1]]},'models':{}}
    chosen=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    for key in ['q2','q3','q4_2','q4_3']:
        a=dict(np.load(ROOT/f'artifacts/{key}.npz'));m=json.loads((ROOT/f'artifacts/{key}.json').read_text())
        
        for i,row in enumerate(m['daily']):
            row['planned_energy']=float(a['q'][i].sum());row['adjusted_energy']=float(a['r'][i].sum())
        bat=[];emer=[];detail=[];releases=[];selected={}
        for i,date in enumerate(a['dates']):
            date=str(date)
            battery=[[date,interval(b,b+24),float(a['c'][i,b:b+24].sum()),float(a['d'][i,b:b+24].sum()),
                      '00:00' if b==0 else '24:00' if b==24 else None,
                      float(a['state'][i,0]) if b==0 else float(a['state'][i,-1]) if b==24 else None] for b in range(0,144,24)]
            ev=events(a['emergency'][i],date)
            bat+=battery;emer+=ev or [[date,'无',0.]]
            for t in range(144):
                detail.append([date,labels[t]]+[float(a[z][i,t]) for z in ['q','r','c','d','emergency','spill','price']]+
                              [float(a['state'][i,t]),float(a['state'][i,t+1])])
            for k in range(4):
                for t in range(k*36,144):
                    if np.isfinite(a['releases'][i,k,t]):releases.append([date,f'{k*6:02d}:00',labels[t],float(a['releases'][i,k,t])])
            if date in chosen:
                selected[date]={'purchase':[[labels[t],float(a['q'][i,t]),float(a['r'][i,t])] for t in [60,72,84,96,108,120]],
                                'daily':m['daily'][i],'battery':battery,'emergency':ev or [[date,'无',0.]]}
        payload['models'][key]={'dates':a['dates'].tolist(),'q':a['q'].tolist(),'r':a['r'].tolist(),
                              'battery':bat,'emergency':emer,'daily':m['daily']}
        tables['models'][key]={'totals':m['totals'],'selected':selected,'validation':m['validation']}
        writecsv(f'{key}_逐时完整策略.csv',['日期','时间段','计划购电_kWh','最终合同购电_kWh','充电_kWh','放电_kWh','紧急购电_kWh','弃电_kWh','电价_元每kWh','时段初SOC_kWh','时段末SOC_kWh'],detail)
        writecsv(f'{key}_调整发布记录.csv',['日期','发布时间','交易时间段','购电量_kWh'],releases)
        writecsv(f'{key}_费用汇总.csv',list(m['daily'][0]),[list(row.values()) for row in m['daily']])
        writecsv(f'{key}_紧急购电.csv',['日期','时间段','购电量_kWh'],emer)
    writecsv('q1_逐时完整策略.csv',['时间段','购电_kWh','充电_kWh','放电_kWh','时段初SOC_kWh','时段末SOC_kWh'],
             [[labels[t],q1['q'][t],q1['c'][t],q1['d'][t],q1['state'][t],q1['state'][t+1]] for t in range(144)])
    dump(ROOT/'artifacts/workbook-payload.json',payload);dump(ROOT/'artifacts/handoff-tables.json',tables)
    text=['# 指定日期结果表','\n全部数值由本地程序直接生成。单位：电量 kWh、费用元。计划量 q 与最终合同量 r 分列；实际从电网取电量另加紧急购电。',
          '\n## 问题1',markdown_table(['时间段','购电量'],tables['q1']['purchase']),
          f"\n全天购电量 {q1['daily_energy']:,.4f} kWh；全天购电费 {q1['daily_cost']:,.4f} 元；首末SOC均为6000 kWh。",
          markdown_table(['时间段','充电量','放电量'],tables['q1']['battery'])]
    for key,model in tables['models'].items():
        for date,s in model['selected'].items():
            text+=['\n## '+key+' '+date,markdown_table(['时间段','0点计划购电量q','最终合同购电量r'],s['purchase']),
                   markdown_table(['项目','数值'],[[k,v] for k,v in s['daily'].items() if k!='date']),
                   markdown_table(['日期','时间段','充电量','放电量','时刻','SOC'],[[('' if v is None else v) for v in r] for r in s['battery']]),
                   markdown_table(['日期','紧急购电时间段','紧急购电量'],s['emergency'])]
    (ROOT/'指定日期结果表.md').write_text('\n\n'.join(text)+'\n')
    dump(ROOT/'artifacts/execution-export.json',{'command':'python3 '+' '.join(sys.argv),'exit_code':0,'runtime_seconds':time.perf_counter()-started,'selected':selection['selected']})
    print('Exported CSVs, workbook payload and exact selected-day tables.')

if __name__=='__main__':main()
