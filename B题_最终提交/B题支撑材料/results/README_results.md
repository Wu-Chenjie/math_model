# results/ 数据文件说明

本目录存放逐局实验CSV。为避免按文件名复核时产生歧义，特此说明两处**同编号多版本**的情形。

## dev81.csv 与 dev81b.csv（关键）

两个文件的 `method` 列都写 81，但内容不同：

| 文件 | Q3 配对节省 | Q4 配对节省 | 说明 |
|---|---:|---:|---|
| `dev81.csv` | 0.00 | **0.00** | 早期版本：Q4 的发现点替换尚未启用 |
| `dev81b.csv` | 0.00 | **+31.83** | 定稿版本：即论文表5中"方法81，Q4 节省 31.83 秒"的来源 |

**论文、`artifacts/summary.json`、`artifacts/result-registry.json` 与 `paper/result-claims.json` 中的方法81数值一律取自 `dev81b.csv`。** `dev81.csv` 作为中间版本保留，仅用于追溯；按 `dev81.csv` 复核会得到 0.00，与论文不符，这是版本差异而非数据错误。

## 其他文件

- `dev56.csv` … `dev86.csv`：开发集（种子 2110001–2110040，每问 40 局）。方法84 的 Q4 等模块组合见论文表5。
- `baseline_native56.csv`：重新编译的原始未修改方法56在同一编译器下的 80 行基线，与 `dev56.csv` 逐行 `time_s` 相同。
- `iid56.csv` / `iid78.csv` / `iid84.csv`：独立集（种子 2610001–2610200，每问 200 局），各 400 行。
- `stress1_56.csv` … `stress5_84.csv`：五组压力测试（起始种子 2620001–2660001，步长 10000，每组每问 40 局）。
- `original_mock_geometric_depth2.json` / `original_mock_joint_depth2.json`：公开协议内核的 10 个物理核案例与 6 个本地 HTTP 案例记录。
- `q3_coverage_bound.json` / `q3_production_points.json`：问题三七点环覆盖证书与七点坐标。
- 所有含 `cleared` 与 `n` 两列的 CSV 均满足 `cleared == n`（全部清除）。

## 统计口径

论文表6（独立集）中的配对差定义为 `d_i = T_56,i − T_84,i`，区间按 `d̄ ± t_{0.975,199}·s_d/√n` 计算，`t_{0.975,199}=1.971957`。退步局以 `1e-4` 秒容差判定。
