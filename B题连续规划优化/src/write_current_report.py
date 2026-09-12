"""Verify independent results, original simulator traces and write the handoff."""
import hashlib
import json
from pathlib import Path
from pair_analysis import read_rows, summarize

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'


def main():
    iid=json.loads((RESULTS/'independent_summary.json').read_text(encoding='utf-8'))
    stress=json.loads((RESULTS/'stress_summary.json').read_text(encoding='utf-8'))
    baseline=ROOT.parent/'B题联合优化'
    frozen=json.loads((baseline/'manifest.json').read_text(encoding='utf-8'))['sha256']
    for name,digest in frozen.items():
        if name.startswith('src/'):
            assert hashlib.sha256((baseline/name).read_bytes()).hexdigest()==digest, name
    old=json.loads((RESULTS/'original_mock_previous_depth2.json').read_text(encoding='utf-8'))
    new=json.loads((RESULTS/'original_mock_joint_depth2.json').read_text(encoding='utf-8'))
    assert len(old)==len(new)==26
    for a,b in zip(old,new):
        assert (a['layer'],a['problem'],a['seed'])==(b['layer'],b['problem'],b['seed'])
        if a['layer']=='original_kernel':
            for field in ('jammer_total','cleared_count','measure_count','clear_count','clear_miss_count'):
                assert a[field]==b[field]
            assert b['cleared_count']==b['jammer_total']
            assert b['total_locate_clear_time_s']<=a['total_locate_clear_time_s']+1e-4
        else:
            assert a['total']==a['cleared']==b['total']==b['cleared']
            assert b['virtual_time_s']<=a['virtual_time_s']+1e-4
    http_actions=0
    for problem in (3,4):
        for seed in (1620001,1620002,1620003):
            def trace(strategy):
                file=RESULTS/f'LOCAL_HTTP_{strategy}_D2_P{problem}_{seed}.jsonl'
                return [json.loads(line) for line in file.read_text(encoding='utf-8').splitlines()]
            a,b=trace('previous'),trace('joint')
            assert len(a)==len(b)
            for x,y in zip(a,b):
                assert x['path']==y['path']
                if x['path'] not in ('/measure','/clear'):continue
                http_actions+=1
                assert x['request']['channel']==y['request']['channel']
                if x['path']=='/measure':assert x['request']['position']==y['request']['position']
                for field in ('measure_result','svd_deg','clear_result'):
                    assert x['response'].get(field)==y['response'].get(field)
    development={}
    dev_base=read_rows([RESULTS/'dev56.csv'])
    files=[*sorted(RESULTS.glob('dev58_[abcd].csv')),RESULTS/'dev60.csv',*sorted(RESULTS.glob('dev_search_*.csv')),RESULTS/'dev66.csv',*sorted(RESULTS.glob('dev_continuous_*.csv')),*sorted(RESULTS.glob('dev_bins_*.csv')),*sorted(RESULTS.glob('dev_portfolio_*.csv')),RESULTS/'dev78.csv']
    import csv
    variants={}
    for file in files:
        with file.open(newline='',encoding='utf-8') as stream:
            for row in csv.DictReader(stream):
                method=int(row['method']);key=tuple(int(row[k]) for k in ('problem','seed','stress'))
                for k in ('time_s','avg_s','runtime_s'):row[k]=float(row[k])
                assert key not in variants.setdefault(method,{})
                variants[method][key]=row
    for method,rows in sorted(variants.items()):
        assert rows.keys()==dev_base.keys(),method
        development[method]={}
        for problem in (3,4):
            keys=sorted(k for k in rows if k[0]==problem)
            development[method][problem]=summarize([dev_base[k] for k in keys],[rows[k] for k in keys])
    (RESULTS/'development_summary.json').write_text(json.dumps(development,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# B题本轮改进结果','',
        '结论：只获得很小的正收益，未达到新增10%。默认方法78仅在原方法56外增加“保证清除的沿线提前停车”，其它试验方法均未采用。','',
        '## 独立验证：每问200例','',
        '同一批新案例，种子2310001—2310200。比较基线是上一轮最佳method56，不是更早的两步DP方法0。以下为本地模拟，不是官方正式成绩。','',
        '|问题|原总均时/s|新总均时/s|节省/s|总均时下降|原单源均时/s|新单源均时/s|全清除|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for p in (3,4):
        r=iid['groups'][f'p{p}_stress0']
        lines.append(f"|{p}|{r['baseline_total_s']:.6f}|{r['candidate_total_s']:.6f}|{r['saving_s_mean']:.6f}|{r['total_gain_pct']:.6f}%|{r['baseline_single_s']:.6f}|{r['candidate_single_s']:.6f}|200/200|")
    lines+=['','配对节省时间的95%正态近似区间：','']
    for p in (3,4):
        r=iid['groups'][f'p{p}_stress0'];lo,hi=r['saving_s_ci95']
        lines.append(f"- Q{p}：[{lo:.6f}, {hi:.6f}]秒；{r['wins']}局更快，{r['ties']}局持平，{r['losses']}局变慢（0.0001秒容差）；最大CPU耗时{r['cpu_max_s']:.3f}秒。")
    lines+=['','浮点累计舍入可产生1—3微秒的差异；无变慢指超过上述容差的变慢。几何论证针对未逐步取整的路程，不能声称逐微秒严格改善。',
        '','## 为什么可以保持原控制器行为','',
        '执行适配器保存真实物理位置与原计划路标。所有测向命令原样发送。只有原清除位置能够以至少0.0001米余量覆盖整个保守多边形时，才在“当前物理位置→原清除位置”线段上二分找到最早可保证清除的位置。实际发送清除命令、等待真实返回；不伪造成功。其它清除命令原样发送。',
        '',
        '控制器继续使用原计划路标，因此未来测向坐标不因这项改动改变。对同一测量噪声实现且清除几何确定的名义位置模型，清除结果与后续控制器分支不变。',
        '',
        '记累计实际路程为L，原计划路程为L₀，实际位置为x，计划路标为a。每个动作后验证 `L + |x−a| ≤ L₀`（浮点容差1e−5米）。提前停车点在线段上，下一次移向原路标时由三角不等式保持该不变量。它是固定路标控制器的执行路程上界，不是全任务最优性证明。',
        '',
        '适配器仅支持从原点启动的新会话，不能中途接管。非零位置误差模式自动禁用快捷清除；需要重新计入位置误差后才能扩展保证。',
        '', '## 压力测试','',
        '五组分别为边界外向、共线端点、重合/近重合、相关角误差、分区端点误差；每组每问40例，种子与开发/IID不重叠。',
        '', '|组别|Q3总均时下降|Q4总均时下降|清除结果|','|---|---:|---:|---|']
    for k in range(1,6):
        a=stress['groups'][f'p3_stress{k}'];b=stress['groups'][f'p4_stress{k}']
        lines.append(f"|{k}|{a['total_gain_pct']:.6f}%|{b['total_gain_pct']:.6f}%|两问均40/40|")
    lines+=['','## 未采用的开发试验','',
        '每项每问40例，使用同一开发集。不能将这些反复使用的开发数据称为独立验证。59是修正入口方向的终端实现，未进行完整开发对照；58保留原入口顺序作为历史负结果。',
        '', '|方法|变化|Q3总均时变化（正为改善）|Q4总均时变化|','|---|---|---:|---:|']
    descriptions={58:'连续域DP叶端费用校准（历史入口顺序）',60:'可变宽度覆盖，典型78→62点',61:'原覆盖+期望搜索时间排序',62:'可变覆盖+搜索排序',63:'原覆盖+10%覆盖点先验混合',64:'可变覆盖+10%混合',65:'可变覆盖+30%混合',66:'DP剩余动作预算校准',67:'连续候选点80次预算',68:'连续候选点+Q3取63假设',69:'连续候选点160次预算',70:'4°预测分箱',71:'3°预测分箱',72:'6°预测分箱',73:'8°预测分箱',74:'可变覆盖，预测收益5%/5秒门槛',75:'覆盖+排序，10%/10秒门槛',76:'覆盖20%/20秒门槛',77:'覆盖仅要求预测费用更低',78:'冻结方法56+保证清除提前停车'}
    for method,groups in development.items():
        lines.append(f"|{method}|{descriptions[method]}|{groups[3]['total_gain_pct']:+.6f}%|{groups[4]['total_gain_pct']:+.6f}%|")
    lines+=['','连续候选搜索是确定性局部模式搜索，不是完整ADVT或POMCPOW实现。2°/3°等分箱仅是有限观测模型敏感性试验，不等于有界噪声的概率模型。连续域叶端保留几何域，但条件粒子权重仍是近似；未采用其增大的CPU开销来换取不存在的收益。',
        '', '## 验证记录','',
        '- IID与压力共800个配对案例、1600次策略运行，全部清除；动作计数与DP计数一致；时间差与执行路程差/5一致。',
        '- 12个C++完整逐动作对照案例，涵盖两问及五类压力；测向位置、角度、清除响应保持一致。',
        f'- 原模拟器两策略各26次（20次内核+6次本地HTTP），全部清除；六对HTTP日志共核对{http_actions}个动作。',
        '- 旧成果src哈希逐项与其冻结manifest一致；最终编译的method56与旧CSV十行复现一致，method78十行开发回放一致（不比较CPU时间）。',
        '- 独立源码审查确认当前method78及默认接入无关键或重要问题，并核对了路程不变量的适用条件。该次审查未独立重跑最终基准或复核统计总数，统计核验由本轮主执行完成。',
        '- 传输测试在并行工作期间曾出现一次“静默子进程退出时间”超出1秒；未改测试阈值或传输逻辑。隔离重跑约0.241秒通过，随后完整9项通过。不能将该单次波动归因于已确认的具体原因。',
        '', '## 文件与复现','',
        '- `src/shortcut_sensor.hpp`：本轮默认唯一启用的新优化。',
        '- `validation_frozen.json`：验证前冻结的策略与样本。',
        '- `results/independent_summary.json`、`stress_summary.json`：配对统计；原始CSV和HTTP日志同目录。',
        '- `results/development_summary.json`：含负结果的完整开发对照。',
        '- `run_all.ps1`：重建与验证；`-Full`重新运行冻结的1600次策略测试。',
        '', '## 文献关联','',
        '把清除点视为可访问区域，而非必须到达的固定中心，受[Peng、Wei、Isler，ICRA 2023，Stochastic Traveling Salesperson Problem with Neighborhoods for Object Detection](https://arxiv.org/html/2407.06366v1)的建模方式启发。本轮沿线提前停车和路程不变量为此项目的具体推导，未移植该文近似比。',
        '', '继续冲击两位数提升需要新的结构性改进；本轮结果不支持声称已经找到或接近全局最优方案。','']
    (ROOT/'最终结果.md').write_text('\n'.join(lines),encoding='utf-8')
    manifest=dict(baseline_method=56,default_method=78,verification=dict(iid_paired_cases=400,stress_paired_cases=400,original_mock_runs=52,http_action_pairs=http_actions,baseline_sources_unchanged=True),sha256={})
    for folder in ('src','tests','review'):
        for file in sorted((ROOT/folder).rglob('*')):
            if file.is_file() and file.suffix in ('.hpp','.cpp','.py','.md'):
                manifest['sha256'][file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    for file in sorted(RESULTS.iterdir()):
        if file.is_file() and file.suffix in ('.csv','.json','.jsonl'):
            manifest['sha256'][file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    for name in ('robot.exe','benchmark.exe','README.md','run_all.ps1','最终结果.md','validation_frozen.json'):
        file=ROOT/name
        manifest['sha256'][name]=hashlib.sha256(file.read_bytes()).hexdigest()
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS report: 800 paired cases,52 original runs,{http_actions} matched HTTP actions; baseline unchanged')


if __name__=='__main__':main()
