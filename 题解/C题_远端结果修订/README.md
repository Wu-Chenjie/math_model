> 本目录为历史候选诊断稿，不作为本轮提交主稿。当前完整证据版本见 `../C题_证据完整修订/`。

# 固定时域与预报融合：论文修订

参考风格：用户提供的《基于跨日随机控制与价值反馈的微网购电和储能协同调度_修订稿》。代码事实源：当前仓库main内容 c69529366ce888fd133e47b39583a6b2581067e2；核心代码原样复制在model-source。

主要交付：output/pdf/基于固定时域与预报融合的微网跨日随机调度.pdf；revised-main.tex；technical-appendix.tex；theory-audit.md；claim-code-map.md；theorem-check.md；code-consistency-review.md；final-review.md；writing-revisions.md。

实际采用结果配置：6cfbc0fe34fd0999，固定72h、28成熟历史日、7等权场景、alpha0.2、321库存点、legacy上层、M0三状态、linear末值、官方融合0.75。它属于年度比较后的统一候选，与一月最终挑战模型不是同一配置。

证据等级：Q2完整NPZ重新计算并独立审核；Q3、q4_2、q4_3当前只有同步的远端汇总，其四任务年度费用均可据源报告转述，但这三项未冒充本地逐段验证。完整文字与数学稿已交付，整体状态LIMITED，不是全部支撑材料齐全的可直接提交包。缺少的三机制原始JSON/NPZ、完整formal验证、指定日期表与新版完整工作簿需要同步缓存后补齐。未修改参考原稿及旧工作簿。

复算当前论文图表（需保留同级C题_下一代随机控制和C题_论文修订目录）：

```sh
python3 src/build_evidence.py
python3 src/q2_emergency.py
python3 src/write_paper.py
sh compile.sh
python3 src/freeze_revision.py
```

Python依赖numpy、scipy、matplotlib；统计种子20260912，3/7/14日移动块各10000次。LaTeX使用XeLaTeX、ctex、所附fvextra，mac字体。`compile.sh`使用本机已安装的XeLaTeX绝对路径，其他系统需调整该路径及字体设置。

完整模型复算入口是同级C题_下一代随机控制/src/nextgen_run.py，通过--config传入已登记配置、--start31 --stop365，并用--output指定独立结果路径。它读取同级artifacts/data.npz及forecast-selection.json，依赖原项目vendor中的HiGHS。仓库中完整的113项远端缓存尚不在本目录；本文未声称重新运行过这些实验。

可传给--config的原样配置保存在artifacts/replay-config.json，已经重新核对其ID为6cfbc0fe34fd0999；CLI参数须分别写为`--start 31 --stop 365`。不同平台的求解器版本和近退化动作应另行核验，年度汇总不替代跨平台逐段一致性证明。

每个图表都有职责：可达域解释物理约束；框架图解释信息时序；时域图解释72h改变；典型日图验证能量移位；年度比较图展示同任务费用；Q2瀑布图解释节省来源；Q2区间图展示时间波动。
