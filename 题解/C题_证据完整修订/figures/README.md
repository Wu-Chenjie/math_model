# 当前论文图像索引

当前main.tex及其附录引用下列PNG；原有其他图像是保留的历史对照资产，不作为本稿主结果。

|图像|生成程序|论证职责|
|---|---|---|
|reachable.png|revision/base_figures.py|原物理容量与功率的单步可达域|
|q1.png|revision/base_figures.py|典型日的库存移能与电价|
|contracts-revision.png|revision/revision_figures.py|主策略指定日合同与应急电量|
|decomposition-primary.png|revision/restore/build_primary_evidence.py|对跨日贪心基线的现金费用分解|
|bootstrap-primary.png|revision/restore/build_primary_evidence.py|主策略对跨日贪心的7日块区间|
|storage-capacity.png|revision/storage-study/build_storage_evidence.py|三档可用窗口的334日费用响应|
|annual-inventory-heatmap.png|revision/storage-study/inventory_figures.py|365日十分钟段末库存结构|
|annual-inventory-envelope.png|revision/storage-study/inventory_figures.py|每日范围及366个午夜库存边界|

原物理可达域图针对主配置[1200,10800]kWh。容量实验另以正文定义的较窄窗口限制可行域；其结果由独立完整回放产生。全年两图包含标注的一月公共初始化，费用图与统计表均为2—12月334日。
