# 微网下一代随机控制

当前阶段：旧基线 365 项严格复现检查全部通过；新版一月开发已冻结，128 组开发轨迹通过独立物理与计费检查。32 个冻结配置 × 四种任务的正式 334 日回放已启动，尚未形成完整年度采用结论。用户后续明确要求“立即启动新版模型落地”，据此调整实施顺序；最终模型采用仍要求完整复现、同口径年度结果及独立验证全部完成。

本目录保存冻结基线、升级代码、开发记录、闭环实验、独立审查及最终论文。旧题解保持原样。基线计算在同级 `C题_下一代基线复现` 中执行，以保留原脚本的相对输入路径。

- `artifacts/baseline-freeze.json`：启动前封存的源码、输入及结果哈希。
- `artifacts/baseline-parameters.json`：从未修改源码读取的参数、预测器和版本记录。
- `artifacts/source-verification/official-input-comparison.json`：官方压缩包与本地C题10个输入文件的逐字节哈希核验，全部一致。
- `baseline_frozen`：上一版完整只读参考副本；其中旧验收不代表本轮验收。
- `tools/reproduce_baseline.py`：调用未修改旧源码，重做训练、回放、消融与验证。
- `artifacts/baseline-reproduction-execution.json`：实际命令、退出码和运行日志。
- `tools/check_baseline_reproduction.py`：独立比较器，缺结果时保持未通过。
- `review/升级前数学边界.md`：固定时域、价格可测性、有限历史和因果下界的前置审查。
- `src/nextgen_scenarios.py`：官方/历史预测融合、在线误差修正、完整成熟条件场景与加权轨迹缩减。
- `src/nextgen_control.py`：保留旧兼容路径的加权因果合同规划、M0和增强M1凸库存反馈。
- `src/nextgen_run.py`：同初末库存的连续回放，逐日进度和完整账本输出。
- `artifacts/experiment-protocol.json`：正式评价前登记的候选、选择制度和7日块bootstrap口径。
- `tools/run_incremental_experiments.py`：仅从一月选择参数，再冻结全部经济候选的334日回放登记。
- `review/check_nextgen_scenarios.py`、`review/check_nextgen_control.py`、`review/check_nextgen_physics.py`：独立信息、控制与账单核验。

本轮主比较限定为2025年2月1日至12月31日，初末库存均6000 kWh。旧自由末端结果先原样复现，再单独保留为敏感性参照。尚未生成或宣称任何升级收益。

一月开发已经完成，候选参数及选择结果已冻结在 `artifacts/frozen-development-selection.json`。正式年度只按事先冻结的门槛接受或拒绝开发期指定模型，不用年度费用反选参数，也不把已经被观察的年度称为全新盲测。

非午夜的固定时域版本采用库存末值截断，显式保存域外原合同后缀的因果延拓规则与数值。已有SDDP根割只在共同午夜接口对照中使用；尚未实现的合同续期桥不作为成果。旧M0兼容测试与新版单日烟雾测试已经通过，不能据此声称全年改进。

## 一键复现

在本目录运行：

```sh
./复现.sh --workers 8
```

程序依次检查旧基线、冻结一月配置、执行全部登记的正式回放、独立验证、配对统计、采用门槛、图表、同终点信息消融、工作簿和 PDF。已有同源码结果可以核验后续跑；锁文件防止重复派发。当前已有流水线运行时，不要再启动第二份。

需要重做全部正式回放、保留旧输出时使用：

```sh
./复现.sh --workers 8 --rerun-year
```

该选项把旧正式输出归档到 `artifacts/replay-history/`，继续使用原冻结参数，不重新开发或根据全年费用选择参数。数学计算使用本机 Python、NumPy、SciPy 与项目中的 HiGHS；工作簿和 PDF 读取使用本机已配置的辅助运行环境，LaTeX 使用本机 XeLaTeX。具体执行路径和版本随运行证据交付。

数值结果文件夹为 `artifacts/formal/`，逐日配对及消融表为 `计算结果/`，建模交接为 `建模与计算交接.md`，开发选择为 `一月开发冻结记录.md`。当前摘要排版稿位于 `tmp/pdfs/`，不是最终论文；最终 PDF 仅在数值来源通过检查后写入 `output/pdf/微网跨日随机控制.pdf`。

自动编译不代表完成最终审核。每页渲染图均需检查，并由独立数学/控制审查、代码审查和模拟评委终审；仅当对应哈希绑定的报告均通过时，`tools/finalize_project.py` 才能关闭交付清单。

当前独立启动的数值流水线由 `tools/finish_registered_outputs.py` 衔接后续输出。该一次性本地进程等待数值验证和采用门槛通过，再导出工作簿、生成论文数值和编译渲染；它不重新派发全年实验、不更改参数，也不自动替代终审。执行状态见 `artifacts/output-continuation-execution.json`，数值进度见 `artifacts/formal/*.progress.json`。`rendered_outputs_ready` 仅表示自动输出完成，项目最终通过以独立终审和交付清单为准。
