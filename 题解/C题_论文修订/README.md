# C题论文修订稿

本目录以用户明确指定的“基于跨日随机控制与价值反馈的微网购电和储能协同调度.pdf”为底稿，增量修改正文、证明、题定结果表、源代码附录及审稿对照。底稿绑定与哈希见 `revision/origin.json`。旧底稿和原模型目录未改动。

## 阅读入口

- `output/pdf/基于跨日随机控制与价值反馈的微网购电和储能协同调度_修订稿.pdf`：交付PDF。
- `main.tex`、`technical-appendix.tex`：正文与附录；`source-code.tex`逐文件排印完整源程序。
- `revision/逐项修订说明.md`：17项意见的处理位置、数值证据及剩余范围限制。
- `计算结果/`：固定真实年末库存的工作簿和CSV；主费用口径仅2025-02-01至12-31共334日，初末库存均6000 kWh。
- `revision/final-math-review.md`、`revision/final-judge-review.md`：独立数学、代码和数值文本审查，视觉检查另见 `revision/pdf-qa.json`。

## 目录与运行环境

保留并列目录 `题解/C题_跨日随机控制/` 与 `题解/C题_论文修订/`。本修订读取相邻原模型的冻结源码、原始数据和全年轨迹，不覆盖这些证据。不要只迁移本修订目录后声称可以从零运行；迁移时必须同时带上原模型目录。原始Excel放入模型的 `inputs/附件/附件1.xlsx` 至 `附件4.xlsx`；`prepare_data.py`也支持项目根目录的 `C题/` 原始附件。

数值环境使用Python 3.13、NumPy、SciPy、HiGHS（highspy）、openpyxl和Matplotlib。绘图原脚本使用macOS黑体，其他系统须设置同等中文字体；LaTeX采用XeLaTeX/ctex及相关数学、表格、绘图与fvextra宏包。原模型 `vendor/` 为平台相关依赖，迁移Windows时重新安装Python依赖，不能沿用macOS二进制。

## 一键核验与编译

在本目录运行：

```sh
sh reproduce.sh check
```

该入口重算原账单/块bootstrap，独立验证新计费和预测控制轨迹，重建题定表格，编译两遍PDF并复核数学证据。使用已存轨迹核验，不会启动远程任务或全年重训练。可通过 `MICROGRID_PYTHON` 指定Python解释器。`xelatex`需在PATH内。

重跑本轮新增数值实验（耗时明显更长）：

```sh
sh reproduce.sh supplement
```

此模式重算Q1自由周期库存、新计费开发期重规划、同终点跨日贪心、预测诊断、一月初始化和增益敏感性。强基线只重算末两日，前332日复用的合法性通过复现自由末端后缀以及终端可达性分析验证；没有把两日结果当作完整全年费用。

原全年基线及主模型的从零入口仍为 `src/run.py` 等原程序，完整原始运行说明保留于相邻模型目录。新增脚本与原始生产脚本均全文列入论文附录。`reference/scripts/` 保存底稿统计、全年增益复演和同终点消融生产程序，输出隔离到 `reference/artifacts/`；需要重新求解这类历史审查时分别运行 `run_supplement.py`、`gain_replay.py`，再运行 `register_results.py`。这些长时计算未在本轮重复执行，但其既有数值由同一登记程序逐字段核对。

`revision/edit_manuscript.py`和`integrate_evidence.py`是已经应用的编辑迁移记录，**不得再次直接运行**。最新TeX是权威稿源。`revision/superseded-start/`是已排除的早期起稿归档，不是可交付版本。

## 解释边界

四种机制对同终点跨日贪心的节省约为1.44%、1.69%、1.03%、1.58%；不得将全部收益归因于上层仿射规划或与其他消融百分比相加。全年新计费数字为原策略重计费，一月重规划是独立补充，不声称已获得新口径全年最优策略。有效增益触边诊断仅覆盖一月25—31日，不替代全年有效列统计。论文仍保留末值改善很小和复杂模块不稳定的负结果。
