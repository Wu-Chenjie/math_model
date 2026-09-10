"""All figure values and derived statements come from executed JSON/NPZ artifacts."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'Songti SC','font.size':11,'axes.titlesize':12,'axes.labelsize':11,
                     'legend.fontsize':9,'xtick.labelsize':10,'ytick.labelsize':10,'axes.unicode_minus':False,
                     'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':120,'savefig.dpi':220,
                     'svg.fonttype':'none'})
colors=['#2A5674','#D98042','#398576','#8B6192']
def load(name):return json.loads((ROOT/'artifacts'/name).read_text())
def save(fig,name):
    for ext in ['png','svg']:fig.savefig(FIG/(name+'.'+ext),bbox_inches='tight',facecolor='white')
    plt.close(fig)
def main():
    q=load('q1.json');data=dict(np.load(ROOT/'artifacts/data.npz'));m=load('metrics.json');v=load('validation.json');ab=load('ablations.json')
    t=np.arange(144)/6
    fig,axs=plt.subplots(3,1,figsize=(8,7.3),sharex=True,constrained_layout=True)
    axs[0].plot(t,data['day_load']/1000,label='小区负载',color=colors[0]);axs[0].plot(t,data['day_pv']/1000,label='光伏发电',color=colors[1])
    axs[0].step(t,np.array(q['q'])*6/1000,where='post',label='计划购电功率',color=colors[2],lw=1.2);axs[0].set_ylabel('功率 / MW');axs[0].legend(ncol=3,loc='upper left')
    axs[1].step(np.arange(145)/6,np.array(q['state'])/1000,where='post',color=colors[0]);axs[1].axhline(1.2,ls=':',color='gray');axs[1].axhline(10.8,ls=':',color='gray');axs[1].set_ylabel('储电量 / MWh')
    axs[2].step(np.arange(145)/6,np.r_[data['day_price'],data['day_price'][-1]],where='post',color=colors[3]);axs[2].set_ylabel('电价 / (元/kWh)');axs[2].set_xlabel('时刻 / h');axs[2].set_xticks(np.arange(0,25,3));axs[2].set_xlim(0,24)
    for ax in axs:ax.grid(axis='y',alpha=.18)
    save(fig,'01_问题1最优计划')
    monthly={}
    fig,ax=plt.subplots(figsize=(8,4.5),constrained_layout=True)
    for color,key,label in zip(colors,['q2','q3','q4_2','q4_3'],['问题2 固定电价','问题3 固定电价+日内调整','问题4-2 波动电价','问题4-3 波动电价+日内调整']):
        ds=load(key+'.json')['daily'];vals=[sum(r['total_cost'] for r in ds if int(r['date'][5:7])==month) for month in range(2,13)];monthly[key]=vals
        ax.plot(range(2,13),np.array(vals)/1e4,'o-',ms=4,color=color,label=label)
    ax.set_xticks(range(2,13));ax.set_xlabel('2025年月');ax.set_ylabel('月总费用 / 万元');ax.grid(axis='y',alpha=.2);ax.legend(ncol=2)
    save(fig,'02_月度费用比较')
    keys=['q3_0only','q3_6only','q3_12only','q3_18only'];vals=[ab[k]['total_cost'] for k in keys]+[v['controlled_pv_value']['q3_keep_midnight_pv']['total_cost'],m['q3']['total_cost']]
    labels=['只在0点制定计划','只增加6点调整','只增加12点调整','只增加18点调整','三次调整，光伏始终用0点预报','三次调整，使用各次新光伏预报']
    savings=(np.array(vals[0])-vals)/1e4
    fig,ax=plt.subplots(figsize=(9,4.5),constrained_layout=True);ax.barh(labels[::-1],savings[::-1],color=[colors[2]]+['#668397']*5)
    for j,x in enumerate(savings[::-1]):ax.text(x+.5,j,f'{x:.2f}',va='center',fontsize=10)
    ax.set_xlabel('相对仅0点计划的累计节省 / 万元');ax.set_xlim(0,float(max(savings))*1.18);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    save(fig,'03_日内调整与新增预报价值')
    fig,axs=plt.subplots(2,2,figsize=(9,6),sharex=True,constrained_layout=True)
    a=dict(np.load(ROOT/'artifacts/q3.npz'))
    for ax,date in zip(axs.flat,['2025-03-20','2025-06-21','2025-09-23','2025-12-21']):
        i=int(np.where(a['dates']==date)[0][0]);day=int(a['days'][i]);net=(data['load'][day]-data['pv'][day])/1000
        ax.plot(t,net,color=colors[0],lw=1.2,label='实际净负载');ax.step(t,a['r'][i]*6/1000,where='post',color=colors[2],lw=1.1,label='最终合同购电')
        ax.fill_between(t,0,a['emergency'][i]*6/1000,color=colors[1],alpha=.6,label='紧急购电')
        ax.set_title(date);ax.axhline(0,lw=.5,color='gray');ax.set_xticks([0,6,12,18,24]);ax.grid(axis='y',alpha=.15);ax.set_ylabel('功率 / MW')
    axs[0,0].legend(ncol=3,fontsize=8,loc='upper center');axs[1,0].set_xlabel('时刻 / h');axs[1,1].set_xlabel('时刻 / h')
    save(fig,'04_指定日最终购电策略')
    d={'q1_saving_percent':100*(q['no_storage_cost']-q['daily_cost'])/q['no_storage_cost'],
       'q2_vs_deterministic_saving':ab['q2_deterministic']['total_cost']-m['q2']['total_cost'],
       'q2_vs_deterministic_percent':100*(ab['q2_deterministic']['total_cost']-m['q2']['total_cost'])/ab['q2_deterministic']['total_cost'],
       'q3_full_update_saving':ab['q3_0only']['total_cost']-m['q3']['total_cost'],
       'q3_full_update_percent':100*(ab['q3_0only']['total_cost']-m['q3']['total_cost'])/ab['q3_0only']['total_cost'],
       'q3_pv_only_saving':v['controlled_pv_value']['q3_keep_midnight_pv']['total_cost']-m['q3']['total_cost'],
       'q4_full_update_saving':ab['q4_3_0only']['total_cost']-m['q4_3']['total_cost'],
       'q4_pv_only_saving':v['controlled_pv_value']['q4_3_keep_midnight_pv']['total_cost']-m['q4_3']['total_cost'],
       'refund_interpretation_cost_difference':ab['q3_no_refund']['total_cost']-m['q3']['total_cost'],
       'monthly_cost':monthly,'figure_sources':{'01':'q1.json,data.npz','02':'q2.json,q3.json,q4_2.json,q4_3.json',
           '03':'ablations.json,validation.json,metrics.json','04':'q3.npz,data.npz'}}
    (ROOT/'artifacts/derived-results.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:x for k,x in d.items() if isinstance(x,float)}))

if __name__=='__main__':main()
