# GitHub发布说明

本目录为方法78的冻结交付。代码、报告、全部独立/压力测试数据、HTTP日志及负结果按本地`manifest.json`原字节上传；同级`B题联合优化`是验证脚本依赖的方法56基线。

`manifest.json`列出的Windows程序保留；未列入冻结清单的临时试验程序和Python缓存不上传。仓库的`.gitattributes`关闭这两个成果目录的换行转换，避免克隆后哈希失配。

## 首次克隆后复现

在仓库根目录，将已经随仓库提供的模拟器压缩包解压到指定的同级目录。若该目录已存在，请先检查，不要强制覆盖已有配置。

```powershell
Expand-Archive -LiteralPath .\26B-team-v1.0.0.zip -DestinationPath .\26B-team-v1.0.0
Set-Location .\B题连续规划优化
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1
```

需要g++和Python；`-Full`会重新运行冻结的1600次策略测试。不加`-Full`仍会编译测试、核查既有配对数据并运行原模拟器回归。

## 结果口径

本轮相对上一轮最佳方法56的独立新样本总均时下降：Q3约0.058%，Q4约0.016%。不是新增10%的提升，也不是官方正式成绩。完整假设、微秒级舍入容差及未采用方案见`最终结果.md`。
