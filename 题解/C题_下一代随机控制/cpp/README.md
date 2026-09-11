# C++ 兼容计算后端

这是原框架的数值实现迁移，不是重新选模型或参数。原 `src/`、冻结配置、数据、15 份已完成全年结果保持不变。当前全年计算和自动导出均已按用户要求暂停；本轮只执行一月兼容性校验。

## 实现范围

- `kernels.cpp`：凸分段线性 infimal convolution、合同 Q/R/E 的 CSR 表达式构造，以及供研究对照的完整 C++ M0 递推。
- `native_feedback.py`：默认 M0。保留原 NumPy/BLAS 归约顺序、分组、伪计数和动作选取，调用 C++ 卷积。
- `native_enhanced.py`：保留原 M1 状态估计和 Markov 算子，调用相同 C++ 卷积。
- `native_planner.py`：原 LP 建模代码的可读生成副本，只替换稀疏表达式循环；HiGHS 仍采用原 IPM、单线程和原约束。
- `native.py`：有边界检查的 NumPy/CSR 接口、编译产物和参考源码的新鲜度检查。
- `generate_adapters.py`：从未修改的参考代码生成适配器，并登记来源哈希。
- `run_case.py`：默认仅允许一月验证，结果另存 `artifacts/cpp-development/`，记录实际 C++ 源码和二进制哈希。

完整 C++ M0 不进入默认入口。它改变浮点归约顺序，已发现费用几乎相同但动作不同的退化案例。不能把目标误差小当作闭环策略一致，也不通过新增并列阈值或更改动作偏好掩盖差异。

插值使用显式 `std::fma` 对齐本机 NumPy arm64 实现；编译禁用 fast-math 和隐式浮点收缩。更换 NumPy、编译器、机器架构或二进制后必须重新验证，不能直接沿用本机兼容性结论。

## 编译与验证

在项目根目录执行：

```sh
python3 cpp/build.py
python3 cpp/generate_adapters.py
python3 cpp/test_equivalence.py
python3 tools/verify_cpp_closed_loop.py
python3 tools/benchmark_cpp_feedback.py
```

最终后端验收由 `tools/certify_cpp_backend.py` 读取独立数学、代码和完整一月闭环证据。缺项、哈希改变或动作不一致均不得放行。

查看剩余登记任务，只作清单检查：

```sh
python3 tools/run_cpp_registered.py
```

得到恢复指令后，才使用带 `--execute` 的入口。它复核并保留已完成 Python 结果的原始来源，新结果另存 `artifacts/cpp-formal/`，不能覆盖原全年账本。它不使用被禁用的完整 C++ M0，也不改变一月冻结参数。

未完成的 8 个原任务仍在暂停进程的内存中。它们的进度 JSON 不是完整检查点，不能据此从某一天无损恢复到新后端；新后端的未完成任务需重新进行完整顺序回放。不要同时恢复旧工作进程和启动新队列。

新队列的独立结果登记不自动等同于最终论文验收；全年比较、结果来源接入和最终 PDF/三方审查仍须在正式计算完成后进行。

## 速度结论的边界

原 HiGHS 已经是 C++。独立一月原点剖析表明，其实际求解约占合同规划时间的 98%—99%，组装迁移没有数量级加速空间。反馈加速必须以同一数据、交替顺序的实测结果为准，不能把反馈局部倍数当作全年总耗时倍数。详见 `artifacts/cpp-migration/` 下的性能报告和验证证据。
