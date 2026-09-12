# B题联合优化：第三阶段交付

先读[最终结果](最终结果.md)。默认程序使用方法56，与上一轮默认两步DP做同案例比较。

|第三阶段新IID，每问200例|原单源时间|新单源时间|单源均时下降|总均时下降|全清除|
|---|---:|---:|---:|---:|---:|
|问题3|255.83秒|238.24秒|6.88%|7.00%|200/200|
|问题4|511.18秒|453.78秒|11.23%|11.54%|200/200|

问题4达到本轮10%目标；问题3尚未达到。更快不是逐案例保证，Q4有27/200局变慢。前两阶段Q4独立结果8.94%、9.78%保留在各自数据文件，没有替换或合并。

## 本轮主要变化

- 动作级联合调度：每次真实动作后更新全局目标及下一测点。
- Q4直接连续光学兜底，使用最多63个有限规划假设。
- 根据保守多边形宽度构造光学覆盖圆，典型长扇形由108个清除点降至78个；每块均检查20米覆盖。
- 只调整完整光学序列的顺序，保留全部覆盖子区域。
- Q3采用1124米七点环、入口菜单、机会补测及安全清除邻域。Q4全局布局仍为21点。

## 在线使用

官方模拟器已登录并提示接口就绪后，在本目录运行：

```powershell
python src/bridge.py --problem 4 --team-id 实际队号 --strategy joint --planner-depth 2 --log results/新日志.jsonl
```

默认`joint`为第三阶段方法56；`stage2`对应39；`stage1`对应38；`baseline`为上一轮两步DP（方法0）。`--planner-depth 0`关闭DP并使用更早的常规控制器，**不等于本轮两步DP比较基线**；作公平对照请用`--strategy baseline --planner-depth 2`。

非零`--position-error`使用原工程位置误差模式，不启用本轮名义几何改动。桥不会启动官方正式测试。

## 复现

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./run_all.ps1
```

默认重建第三阶段、单元/回归测试、原模拟器演练及报告。加`-AllStages`重建三个阶段的独立数据。开发选择已经冻结，复现不重新选参。依赖g++、Python、NumPy、SciPy及同级`26B-team-v1.0.0`。

主要入口：

- `src/policy.hpp`、`joint_config.hpp`：调度与冻结配置。
- `src/adaptive_optical.hpp`、`optical_order.hpp`：连续区域分块与完整扫掠排序。
- `results/iid3_*.csv`、`summary_stage3.json`：最终新IID及五类压力结果。
- `results/summary.json`、`summary_stage2.json`：前两阶段结果。
- `results/development*.csv`：包括不利方案的全部开发记录；重复运行不是独立样本。
- `baseline/`：上一轮源码快照。
- `manifest.json`：交付文件哈希与核验结果。

这些为本地模拟结果，不是官方正式成绩；有限规划模型和浮点几何验证不构成整任务全局最优证明。
