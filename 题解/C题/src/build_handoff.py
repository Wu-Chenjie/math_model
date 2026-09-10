"""Fill handoff from executed artifacts, then register every numerical source block."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def get(name):return json.loads((ROOT/'artifacts'/name).read_text())
def tab(header,rows):
    def fmt(v):return f'{v:,.4f}' if isinstance(v,float) else str(v)
    return '\n'.join(['| '+' | '.join(header)+' |','|'+'|'.join(['---']*len(header))+'|']+
                     ['| '+' | '.join(fmt(v) for v in r)+' |' for r in rows])
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    q=get('q1.json');m=get('metrics.json');a=get('ablations.json');v=get('validation.json');d=get('derived-results.json');s=get('sensitivity.json');o=get('oracle.json')
    summary={'q1':{k:q[k] for k in ['daily_energy','daily_cost','no_storage_cost']},'comparisons':d,
             'main':{k:m[k] for k in ['q2','q3','q4_2','q4_3']},
             'feasibility':{k:get(k+'.json')['validation'] for k in ['q2','q3','q4_2','q4_3']}}
    dump(ROOT/'artifacts/handoff-summary.json',summary)
    results=[f"问题1：全天购电 **{q['daily_energy']:,.4f} kWh**，费用 **{q['daily_cost']:,.4f} 元**。不使用储能的同口径费用为{q['no_storage_cost']:,.4f}元，下降{d['q1_saving_percent']:.4f}%。首末SOC均为6000 kWh。这里的最优性针对第4节离散确定性模型及其假设，数值周转正则不计入报告费用。",
      tab(['方案（334天）','计划电量/kWh','最终合同电量/kWh','紧急电量/kWh','总费用/元'],
          [[key,m[key]['planned_energy'],m[key]['adjusted_energy'],m[key]['emergency_energy'],m[key]['total_cost']] for key in ['q2','q3','q4_2','q4_3']]),
      tab(['方案','计划费/元','增购费/元','退购净费用/元','紧急费/元'],
          [[key]+[m[key][f] for f in ['planned_cost','increase_cost','reduction_net_cost','emergency_cost']] for key in ['q2','q3','q4_2','q4_3']]),
      f"问题2点预测基准的实际总费用为{a['q2_deterministic']['total_cost']:,.4f}元。主策略节省{d['q2_vs_deterministic_saving']:,.4f}元（{d['q2_vs_deterministic_percent']:.4f}%）。比较采用相同的正式日期、结算规则与实时控制。",
      tab(['问题3对照','总费用/元','紧急电量/kWh'],
          [[key,a[key]['total_cost'],a[key]['emergency_energy']] for key in ['q3_0only','q3_6only','q3_12only','q3_18only','q3_no_refund']]+
          [['相同三次更新、光伏始终用0点预报',v['controlled_pv_value']['q3_keep_midnight_pv']['total_cost'],v['controlled_pv_value']['q3_keep_midnight_pv']['emergency_energy']],
           ['完整三次更新',m['q3']['total_cost'],m['q3']['emergency_energy']]]),
      f"固定电价下全部日内更新累计节省{d['q3_full_update_saving']:,.4f}元（{d['q3_full_update_percent']:.4f}%）；保持其他更新完全相同后，新增光伏预报的条件贡献为{d['q3_pv_only_saving']:,.4f}元。波动电价下两种差值分别为{d['q4_full_update_saving']:,.4f}元、{d['q4_pv_only_saving']:,.4f}元。因此在本数据及主结算口径下，支持引入日内预报进行调整，但不把全部调整收益归因于光伏信息。",
      f"若按不退款另罚解释，问题3总费用变为{a['q3_no_refund']['total_cost']:,.4f}元，较主口径增加{d['refund_interpretation_cost_difference']:,.4f}元，且模型不退购。",
      f"实际未来完全已知、仍每日循环SOC的乐观费用参考：固定价{o['fixed']['total_cost']:,.4f}元，波动价{o['variable']['total_cost']:,.4f}元。主策略与该参考之间的差距不能称为已知随机最优性间隙。",
      tab(['预测对象（2–12月0点）','MAE','RMSE'],[[key,list(values.values())[0],values['rmse']] for key,values in v['prediction_accuracy'].items()]),
      '上表负载、光伏单位为kW，价格单位为元/kWh。这里的光伏是问题2历史模型；官方预报的同预测区间比较如下。',
      tab(['发布时刻/h','最新官方预报MAE/kW','0点预报对相同剩余时段MAE/kW'],[[x['release_hour'],x['latest_mae_kw'],x['midnight_same_horizon_mae_kw']] for x in v['pv_release_accuracy']]),
      '图1见`figures/01_问题1最优计划.png`，图2为月费比较，图3专门区分预报与重规划收益，图4给出指定日期曲线。详细指定日数字以`指定日期结果表.md`为准。']
    validations=[tab(['方案','平衡最大误差/kWh','SOC递推最大误差/kWh','SOC最小/kWh','SOC最大/kWh','终端误差/kWh','最大功率/kW'],
        [[key]+[summary['feasibility'][key][f] for f in ['energy_balance_max_abs','soc_recurrence_max_abs','soc_min','soc_max','terminal_max_abs','power_max_kw']] for key in summary['feasibility']]),
      '上表四位小数的0代表数值误差在展示精度以下；原始科学计数结果保留在各方案JSON。全部主轨迹同时充放电量为数值零。LP求解检查包括原始/对偶残差与对偶目标核对。',
      '因果反例测试：分别在第101天的0/6/12/18点，将该时刻之后实际负载、光伏、电价和未发布预报大幅改写；当时普通/官方两种情景矩阵均完全不变。另通过80%分位点测试、解析互斥转换和不退款退购被支配测试。独立agent另以135条极端路径验证终端控制可行性，并独立重算全部4套正式轨迹费用。',
      tab(['问题1敏感性','费用/元','购电量/kWh'],[[key,x['cost'],x['energy']] for key,x in v['q1_sensitivity'].items()]),
      'reference为主解释；roundtrip90取两个方向效率均为sqrt(0.9)；trapezoid_power将周期端点功率按梯形法积分、电价仍按本段价格。',
      tab(['问题4-3参数实验（每月1日，共11天）','总费用/元','紧急电量/kWh'],[[key,x['totals']['total_cost'],x['totals']['emergency_energy']] for key,x in s.items()]),
      '参数实验改变场景窗口14/56天、双向效率0.85/0.95、循环SOC目标4800/7200、最大功率4000/6000。终端实验同时将所测试日初值设为该循环目标，属于条件循环策略比较，不能当作改变1月1日题给初值的全年主结果。各敏感性只评价预先选定的每月1日，不是完整年度重算。',
      tab(['固定最终合同的压力测试','总费用/元','紧急电量/kWh','终端最大误差/kWh'],[[key,x['total_cost'],x['emergency_energy'],x['terminal_max_abs']] for key,x in v['frozen_contract_stress'].items()]),
      '压力测试保持原问题3的最终普通合同不变，仅对实际负载±5%、实际PV±10%施加偏移并重放实时电池控制；不允许再次调整合同。这是已给合同对系统性偏差的压力评估，不是用扰动后信息重新优化的方案。',
      tab(['方案','充电与紧急补购同时发生量/kWh'],[[key,m[key]['emergency_while_charging']] for key in ['q2','q3','q4_2','q4_3']]),
      '同时发生量定义为逐时min(充电量,紧急量)之和，不能作为严格因果归属。它主要提醒日终闭合仍会有恢复充电的成本。',
      f"主计算（含问题1与四套全年方案）的实测运行时间为{get('execution-main.json')['runtime_seconds']:.2f}秒；扩展比较{get('execution-extras.json')['runtime_seconds']:.2f}秒；正式验证与预报控制组{get('execution-validation.json')['runtime_seconds']:.2f}秒。时间为本机单次记录，会随机器及并行负载变化。"]
    template=(ROOT/'src/handoff_notes.md').read_text()
    (ROOT/'建模计算交接.md').write_text(template.replace('{{RESULTS}}','\n\n'.join(results)).replace('{{VALIDATION}}','\n\n'.join(validations)))
    sources=['q1.json','metrics.json','baseline-metrics.json','handoff-tables.json','handoff-summary.json','validation.json','sensitivity.json','derived-results.json','forecast-selection.json','controller-selection.json','oracle.json','ablations.json','data-audit.json','execution-main.json','execution-extras.json','execution-validation.json']
    registry={'schema_version':1,'results':[]};claims=[]
    for name in sources:
        obj=get(name)
        for key,value in obj.items():
            rid=name.removesuffix('.json')+'.'+key
            registry['results'].append({'id':rid,'value':value,'source_artifact':'artifacts/'+name,
               'source_path':'/'+key.replace('~','~0').replace('/','~1'),'status':'verified'})
            claims.append({'result_id':rid,'value':value,'usage':'建模计算交接.md / 指定日期结果表.md / figures'})
    dump(ROOT/'artifacts/result-registry.json',registry);dump(ROOT/'artifacts/handoff-claims.json',{'claims':claims})
    print('Handoff generated; registered',len(registry['results']),'numerical/source blocks.')
if __name__=='__main__':main()
