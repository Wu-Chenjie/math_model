# 论文—代码—证据映射

| 论证 | 数学定位 | 当前代码 | 数值/核验 |
|---|---|---|---|
| 合同费用 | 两仿射式最大值，凸PWL | model-source/dispatch.py settlement；control.py affine_plan | theorem-check.md、代码独立审查 |
| 单向动作与可达性 | 库存增量消元、真实终点交集 | control.py execute | q2-new-analysis.json /validation |
| 固定72h | b=min(a+432,T*) | nextgen_run.py simulate | paper-configuration.json |
| 融合0.75 | 官方覆盖内凸组合，历史残差同口径 | nextgen_scenarios.py ScenarioFactory.forecast | remote-reported-summary.json /candidate |
| 成熟等权场景 | h+H<=a；时间覆盖 | nextgen_scenarios.py ScenarioFactory.build | new-control-theory.md |
| 因果仿射LP | 合同用截止前误差；受限策略类 | control.py features/affine_plan | new-convex-audit.md |
| M0库存反馈 | 三箱、伪计数、凸Bellman | control.py MarkovDP/inf_convolution | theorem-check.md |
| 四机制年度费用 | 同年度候选比较 | nextgen_run.py +远端summary | annual-comparison.json，Q2复算，其他三项报告值 |
| Q2分项、月差与MBB | 配对轨迹统计；不是显著性/泛化保证 | src/build_evidence.py | q2-new-analysis.json |
| Q2指定日期 | 当段量和四小时累计 | src/build_evidence.py、q2_emergency.py | q2-specified.json、q2-emergency.json |

精确数值到JSON Pointer的逐项映射见 artifacts/result-registry.json；正文用途见 paper/result-claims.json。
