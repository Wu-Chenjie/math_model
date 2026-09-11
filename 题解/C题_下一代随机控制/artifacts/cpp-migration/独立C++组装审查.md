# 独立 C++ 组装及绑定审查

审查器：`/root/upgrade_code_review`。未修改原 src、冻结参数或正式结果，未恢复暂停实验。本次不调用 HiGHS。

## 数值结论

- 4 套 2025-01-25 合法原点的真实捕获 LP（legacy/state × H72/H96）：原 Python 与 native_planner 的目标、右端、变量边界及 CSR 行指针、列号、非零值、形状全部逐元素精确相等；与捕获时保存的 LP 也完全相等。
- 复用原 HiGHS solution，不重新求解。合同 q/r、场景合同及场景库存与原函数和原捕获输出全部精确相等。
- 32 个附加模型边界：legacy 均匀/加权、state 两维/四维，各自有无合同调整，再覆盖单槽、非午夜既有 base + 真实 terminal、跨午夜部分合同以及午夜末值切平面。所有 LP 与用同一向量重算的输出精确相等。附加用例的向量只用于证明代数相同，不声称其是可行策略或最优解。

## 防护结果及待修复

内核源码/动态库及普通参考源码/适配器内容变化已被导入门禁拒绝；零维度、负索引、普通列越界和 int32 容量越界也正确拒绝。

追加反例仍有三项：

1. `asof=np.int64(2**63-1)` 且 T=2 时，NumPy 标量加法先溢出，再进行界限比较，导致 C 调用仍会被派发。测试将 C 函数替换为硬停止器，没有实际执行危险调用。应验证整数类型后将全部整数参数转为 Python int，再计算范围与容量。
2. `adapter-sources.json={}` 时，当前 for 循环不检查任何参考源码，导入仍成功。
3. 从该清单删除 `src/control.py` 后再改变对应参考文件，导入仍成功。应要求完整、精确的必需键集合，而不是只验证清单中现有条目。

这些是接口与证据完整性问题，正常赛题原点没有触发整数溢出，不否定上述模型数值等价。已要求在当前七日验证结束后修复，不应在回放中途改变后端。`run_case.py` 目前的 backend_hashes 仅纳入 .py/.cpp/.dylib；建议同时纳入 build.json、adapter-sources.json，保留编译与适配器清单的来源证据。

完整 C++ Markov 递推的并列动作不一致已由主任务发现，未作为默认；本次 LP 精确等价不能替代默认 native_feedback 的动作及闭环验证。

执行入口：`python3 review/check_cpp_planner.py`。当前审查状态 **CHANGES_REQUESTED**，仅由上述三项防护反例导致；逐项模型数值结果保存在 `independent-planner-checks.json`。最终迁移采用仍需通过真实闭环、信息与计费验证。

## 修复后复核

当前 `native.py` 已先转 Python int 再检查容量，并要求六项适配器清单精确覆盖；动态库加载后变化也会强制要求新进程。独立脚本重新运行，**54 个用例 PASS_WITHIN_SCOPE**：4 个真实 LP、32 个模型代数边界、10 个输入域检查、8 个绑定导入检查。新增加载后原子替换 dylib 并同步更新 build.json 的反例也被拒绝；测试只改临时副本。三个旧防护反例全部修复，当前没有未解决的组装/导入阻断。

默认反馈的三份类体另外完成 AST 对照：MarkovDP、WeightedMarkovDP、EnhancedMarkovDP 与原参考逐节点完全一致，只有导入的卷积函数换成 native；因此 NumPy/BLAS 求和和动作并列选择的代码路径保持原顺序。证据见 `feedback-reference-ast-checks.json`。这项静态证据与 LP 精确等价均不替代当前源码状态下的一月真实闭环及迁移采用门禁。
