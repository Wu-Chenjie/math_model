# 论文—代码—结果对应表

所有主结果统一固定真实初末6000 kWh，2025年2月1日至12月31日。`artifacts/result-registry.json`和`paper/result-claims.json`登记2246个有JSON字段来源的数值。下表解释结论用途，不能把不同基线数值互换。

|论文用途|实现|实际输出与独立核验|
|---|---|---|
|四机制主费用、16指定日期块、五工作簿|src/run.py、control.py、dispatch.py；revision/build_required_tables.py|revision/base-artifacts/q*.npz；计算结果/；review/restoration-evidence-audit.json|
|Q1最优账单、自由周期对照|src/run.py确定性LP；revision/q1_and_billing.py|artifacts/q1.json；revision/numeric-audit/q1-billing-audit.json|
|强跨日贪心主对照|revision/strong_baseline.py|revision/results/*_cross_baseline_fixed.npz；review/strong-baseline-three-blocks.json|
|主统计、月表、费用瀑布|revision/restore/build_primary_evidence.py|revision/restore/primary-evidence.json；tables/*-primary.tex；figures/*-primary.png|
|同仿射框架跨日消融、反馈消融|reference/scripts/register_results.py|reference/artifacts/result-claims.json；tables/mechanisms.tex|
|预报删减：权限保持不变|reference/scripts/run_supplement.py、register_results.py|reference/artifacts/ablation_fixed/；tables/ablation.tex|
|预测MAE/RMSE、初始化、增益去零列|revision/prediction-control/完整脚本|forecast-errors.json、gain-summary.json、verification.json|
|网格/场景/末值敏感性|相邻原模型实验入口、reference/scripts/register_results.py|reference/artifacts/result-claims.json sensitivity字段|
|另一退购解释|revision/q1_and_billing.py、billing_january_replan.py|numeric-audit/；重计费与重新优化分开|
|完美信息账单/对偶证书|review/check-global-oracle.py|相邻原模型review/global-oracle.json；tables/oracle.tex|
|三种时域的12条本地完整轨迹|相邻nextgen/src/nextgen_run.py|review/restoration-control-diagnostics.json annual字段；来源哈希逐条保存|
|融合矩与beta样本最优|review/restoration_control_diagnostics.py|同上moments字段；内部开发、不作留出/经济最优论断|
|Q2候选增量跨零区间|revision/restore/build_primary_evidence.py|revision/restore/q2-horizon-increment.json；主表不采用其增量作核心优势|

主模型原始生产、已执行消融、独立验证、本轮重算的作用不同。本轮命令`sh reproduce.sh check`是已有完整轨迹的重新核验与重新统计，并不声称重新训练或求解全部年度控制器。


## 本轮新增：容量与全年库存

|论证|论文入口|计算与证据入口|
|---|---|---|
|同功率、同初末库存的可用窗口费用|revision/storage-study/capacity-section.tex|run_capacity.py → results/ → verify_capacity.py → capacity-audit.json → build_storage_evidence.py|
|三容量费用与分项、7日块区间|revision/storage-study/capacity-appendix.tex|summary.csv、daily-costs.csv；tables/storage-capacity*.tex|
|全年十分钟段末库存|main.tex sec:annualinventory|inventory_figures.py → annual-inventory.npz/json → annual-inventory-heatmap.png|
|日内范围与366午夜边界|technical-appendix.tex app:annualinventory|同一库存NPZ → annual-inventory-envelope.png|
|零窗口日前解析退化|eq:zeroquantile|zero_window_quantile.py → zero-window-quantile.json；只验证同场景规划目标|

上表程序均位于revision/storage-study；主控制器副本与原main来源逐字节一致。新窗口在进程内设置边界，不改原源码。容量收益与固定容量的算法收益为不同对照。
