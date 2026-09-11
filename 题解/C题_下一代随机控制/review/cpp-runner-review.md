# C++ 后续年度入口：独立门禁与锁审查

审查器：`/root/upgrade_code_review`。本轮经主任务授权仅修改 tools 入口/验收器及 review 测试，不改 cpp、src、冻结参数和正式输出。

## 已修复

1. 默认运行只输出 dry-run 清单；只有显式 `--execute` 才进入锁与证据检查。没有恢复旧进程的操作。
2. 取得 `cpp-pipeline.lock` 后再读取复用候选，避免等待期间形成的结果被重复派发。原 SIGSTOP 流水线继续持有原锁，新输出始终隔离在 cpp-formal。
3. 每次 `pool.submit` 创建单独 `multiprocessing.reduction.DupFd`；worker 最外层 detach 后持有原打开文件描述符直到 run 和独立 audit 全部完成。父进程死亡后，正在运行的 worker 继续保持全局写锁；还没收到描述符的排队任务会失败，不能无锁写入。
4. 冻结门禁精确检查 src、原协调器、数据、预测选择及协议哈希，拒绝空或重复年度配置。每个 worker 前后及全队列结束核验同一来源快照。
5. 验收器严格要求五类当前证据：五个一月闭环、独立数学审查、独立 LP 组装审查、反馈 AST 对照、runner 独立测试。所有证据必须存在、非空且绑定当前源码和结果；闭环重新读取双方 NPZ，要求固定 12 个数组键逐元素相同、日期为 1 月 25—31 日、初末库存一致、费用差零与独立物理检查通过。
6. build.json 和 adapter-sources.json 单独绑定；不以实验完整 native Markov 的混合报告顶层 PASS 作为采用依据。
7. 原 Python 结果只在独立物理/费用验证后复用；cpp-formal 结果缺少 compatible implementation 证明时拒绝。每个新结果完成后审计再登记；完整队列必须精确覆盖冻结的配置 × 四问题。

## 实际验证

`python3 review/check_cpp_runner.py`：**17 个隔离用例 PASS_WITHIN_SCOPE**，涵盖合法正例、默认只读、重复写入拒绝、空壳/缺项/过期验收、冻结源/数据/协议变化，以及真实 spawn 进程池父进程终止后的锁保留。进程试验仅启动和终止临时控制器/无业务 worker，数值函数和审计被明确替代；没有调用年度优化。

已获授权执行 `python3 tools/certify_cpp_backend.py`，使用真实五案例等证据，结果 **PASS_COMPATIBLE_BACKEND**。随后仅运行 dry-run，登记为 128 项，其中 15 项已有输出待逐案核验、113 项待算。这不是 15 项复用已经通过的声明。

没有运行 `--execute`，没有恢复旧 PID。兼容后端验收不替代全年度物理计费审计、最终论文审稿或显式恢复计算的指令。

当前哈希以 `cpp-runner-checks.json` 与 `artifacts/cpp-migration/acceptance.json` 为准。任何绑定源码、后端、元数据或证据变化都会使验收过期，须重新检查后生成。

## 运行环境指纹补充

验收现同时绑定 Python 版本、可执行文件二进制、平台/机器，NumPy 2.4.1 的核心与扩展模块二进制、构建配置及运行时 CPU 特征，以及实际由原 control 模块导入的 vendored HiGHS 1.15.1 核心库与版本。自动检查 HiGHS 确实来自保留的 vendor 路径。本机共绑定 23 个二进制文件；找到的 NumPy 打包 BLAS/LAPACK 共享库也在集合内。

`require_acceptance` 对比此指纹；每个 worker 的执行前、执行后和整队完成时的来源快照也包含同一指纹。版本、核心库、NumPy CPU 分派能力或 Python 平台变化均会拒绝继续。

隔离用例已增至 **22 项，全部 PASS_WITHIN_SCOPE**，新增 NumPy 版本、CPU 特征、NumPy 二进制、HiGHS 二进制、平台变化反例。重新生成并再次核验真实 compatible acceptance，状态仍为当前有效。没有重跑数值算法或恢复暂停实验。
