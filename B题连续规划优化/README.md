# B题连续规划与执行优化：微小收益，未达到新增10%

先读[最终结果](最终结果.md)。本轮实现并测试了终端校准、连续候选点、可变光学覆盖、期望搜索排序等方案；没有发现显著优于上一轮最佳方法56的规划方案。

默认方法78只增加经过验证的“保证清除时沿原路提前停车”，保留原控制器的未来测向位置和全部覆盖保证。

执行适配器假设新会话从原点开始，不能中途接管已移动的机器人。

|独立新样本，每问200例|方法56总均时|方法78总均时|下降|
|---|---:|---:|---:|
|Q3|3047.584665秒|3045.827892秒|0.057645%|
|Q4|5726.996123秒|5726.070023秒|0.016171%|

全部清除；另有五组各40例/问压力测试也全部清除。无超过0.0001秒容差的变慢；累计时间舍入可出现微秒级差异。以上是本地模拟结果，不是官方正式成绩，也不证明全局最优。

## 使用

官方模拟器已登录且接口就绪后，在本目录运行：

```powershell
python src/bridge.py --problem 4 --team-id 实际队号 --strategy joint --planner-depth 2 --log results/新日志.jsonl
```

`joint`为方法78；`previous`为上一轮最佳方法56。`baseline`仍是更早的方法0，不是本轮比较基线。`--planner-depth 0`和非零`--position-error`使用旧控制器，不启用提前停车。

## 复现

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./run_all.ps1
# 重新生成冻结样本的1600次策略运行：
powershell -NoProfile -ExecutionPolicy Bypass -File ./run_all.ps1 -Full
```

需要g++、Python，以及同级`26B-team-v1.0.0`原模拟器。脚本只写当前新目录中的派生文件，不改旧的`B题联合优化`成果。

直接运行单一冻结方法时，最后两个参数都要给出：

```powershell
./benchmark.exe results/自选样本.csv 2500001 40 0 78 78
```

开发试验方法58—77保留供检查负结果，不是推荐在线配置；59未做完整开发对照。不要将典型覆盖点78→62的20.5%数量减少误写成总耗时下降。

主要文件：`src/shortcut_sensor.hpp`、`validation_frozen.json`、`results/independent_summary.json`、`results/stress_summary.json`、`results/development_summary.json`。路径不变量及适用假设见最终结果报告。
