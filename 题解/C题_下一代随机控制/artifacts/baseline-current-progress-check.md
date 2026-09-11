# 基线严格复现核验

状态：**PENDING**。缺失证据不会视为通过。

计数：{'PASS': 306, 'PENDING': 59}

逐时数组绝对容差1e-6、相对容差1e-11；JSON数值绝对容差1e-5、相对容差1e-11。计费独立重算容差1e-4元，物理约束容差1e-5。

NPZ按实际数组内容比较；压缩文件哈希只作证据绑定。运行时间不要求重现。

## 未完成或不一致项

- PENDING：`artifacts/selection.json`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q3_affine_mpc.npz`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q3_affine_mpc.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/global-terminal/q3_affine_mpc`；trajectory, metrics or data missing
- PENDING：`artifacts/global-terminal/q3_markov_mpc.npz`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q3_markov_mpc.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/global-terminal/q3_markov_mpc`；trajectory, metrics or data missing
- PENDING：`artifacts/global-terminal/q4_2_affine_mpc.npz`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q4_2_affine_mpc.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/global-terminal/q4_2_affine_mpc`；trajectory, metrics or data missing
- PENDING：`artifacts/global-terminal/q4_2_markov_mpc.npz`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q4_2_markov_mpc.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/global-terminal/q4_2_markov_mpc`；trajectory, metrics or data missing
- PENDING：`artifacts/global-terminal/q4_3_affine_mpc.npz`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q4_3_affine_mpc.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/global-terminal/q4_3_affine_mpc`；trajectory, metrics or data missing
- PENDING：`artifacts/global-terminal/q4_3_markov_mpc.npz`；等待生成或见JSON细节
- PENDING：`artifacts/global-terminal/q4_3_markov_mpc.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/global-terminal/q4_3_markov_mpc`；trajectory, metrics or data missing
- PENDING：`artifacts/q2.npz`；等待生成或见JSON细节
- PENDING：`artifacts/q2.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/q2`；trajectory, metrics or data missing
- PENDING：`artifacts/q3.npz`；等待生成或见JSON细节
- PENDING：`artifacts/q3.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/q3`；trajectory, metrics or data missing
- PENDING：`artifacts/q4_2.npz`；等待生成或见JSON细节
- PENDING：`artifacts/q4_2.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/q4_2`；trajectory, metrics or data missing
- PENDING：`artifacts/q4_3.npz`；等待生成或见JSON细节
- PENDING：`artifacts/q4_3.json`；等待生成或见JSON细节
- PENDING：`independent:artifacts/q4_3`；trajectory, metrics or data missing
- PENDING：`artifacts/global-terminal.json`；等待生成或见JSON细节
- PENDING：`artifacts/workbook-payload.json`；等待生成或见JSON细节
- PENDING：`artifacts/handoff-tables.json`；等待生成或见JSON细节
- PENDING：`artifacts/summary.json`；等待生成或见JSON细节
- PENDING：`artifacts/figure-data.json`；等待生成或见JSON细节
- PENDING：`计算结果/q1_逐时完整策略.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q2_紧急购电.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q2_调整发布记录.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q2_费用汇总.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q2_逐时完整策略.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q3_紧急购电.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q3_调整发布记录.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q3_费用汇总.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q3_逐时完整策略.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_2_紧急购电.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_2_调整发布记录.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_2_费用汇总.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_2_逐时完整策略.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_3_紧急购电.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_3_调整发布记录.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_3_费用汇总.csv`；等待生成或见JSON细节
- PENDING：`计算结果/q4_3_逐时完整策略.csv`；等待生成或见JSON细节
- PENDING：`execution:artifacts/global-terminal.json`；等待生成或见JSON细节
- PENDING：`execution:artifacts/execution-selection.json`；等待生成或见JSON细节
- PENDING：`execution:artifacts/execution-finish.json`；等待生成或见JSON细节
- PENDING：`execution:artifacts/execution-export.json`；等待生成或见JSON细节
- PENDING：`rerun_independent_production_audit`；等待生成或见JSON细节
- PENDING：`rerun_workbook_readback`；等待生成或见JSON细节
