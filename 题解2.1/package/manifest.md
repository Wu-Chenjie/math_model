# 评审工件清单（manifest）

- 竞赛：2026 年全国大学生数学建模竞赛（CUMCM）C 题
- 题目：微网与外部电网电力调控策略
- 参赛论文（渲染 PDF）：`D:\shumo\shumoC\paper\main.pdf`（46 页 = 摘要 1 + 正文 17 + 附录 A 支撑材料清单 + 附录 B 完整源代码 + 附录 C AI 工具使用说明；页码页脚中部，自摘要页起编）

## 支撑材料（与论文附录 A 一致）

- 代码（Python 3.11，全部可运行）：`D:\shumo\shumoC\code\`（总控 `run_all.py`；模块见论文附录 B.1–B.12）
- 预处理后数据：`D:\shumo\shumoC\data\data.npz`（负载/光伏/电价/预报，365×144）
- 原始附件：`C:\Users\y'h\Downloads\CUMCM2026Problems\`（附件 1–5 与题面；公开数据未重复打包）
- 结果工作簿：`D:\shumo\shumoC\results\result1.xlsx`、`result2.xlsx`、`result3.xlsx`、`result4-2.xlsx`、`result4-3.xlsx`
- 表格数值机器可读汇总：`D:\shumo\shumoC\results\paper_tables.json`（论文全部表格数值来源，零手抄）
- 论文图 1–5：`D:\shumo\shumoC\figures\fig1_*.png` … `fig5_*.png`（300 dpi）
- 论文表格 LaTeX 片段：`D:\shumo\shumoC\paper\tables\*.tex`
- 运行日志：`D:\shumo\shumoC\results\log_*.txt`

## 复现方式

在 `D:\shumo\shumoC\code\` 执行 `python run_all.py`（约 6–8 分钟）完成数据预处理、四问求解、结果工作簿、表格与图形生成及独立校验。
