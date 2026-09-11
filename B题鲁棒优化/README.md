# 第四轮交接

主文为`B题鲁棒优化_论文交接.pdf`，另有经过本机Word原生渲染核对的同名DOCX及Markdown。前三轮文档和源代码仍完整保留。

- 固定通用布局下界15，上界21；18—20点探索未获证书，不声称不存在。
- 冻结21点具备每点独立任意0.4米扰动保证。可选未知站址误差模式还扩张局部角锥并缩小清除网格。
- Q2全域点在线消融使任务时间更长，默认继续使用750±300。
- 默认控制器为M5，加入发现16频道停扫、入口—出口路程代理、小规模DP及大规模上下界与局部终止检查。真实全任务最优性仍未证明。

## 运行

在此目录执行`powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1`重建数值结果。证书仅需Python标准库；统计绘图需numpy/scipy/matplotlib；主仿真和规划器使用C++17。

官方模拟器已就绪后执行`python src/bridge.py --problem 4 --team-id 实际队号 --log results/新日志.jsonl`。默认`--position-error 0`，符合题面接口；另有`--position-error 0.4`工程误差扩展，不能把它解释为官方模拟器真的加入了硬件误差。

文档构建使用已发现的bundled文档Python运行`src/build_documents.py`及`src/style_word.py`。通用Word渲染器在此机因缺LibreOffice失败后，使用`tools/render_with_word.ps1`通过已安装Word的隐藏独立实例生成只读QA输出，再检查PNG；不替代或修改用户已打开的Word文档。

`results/iid.csv`为6方法2400行；`results/stratified.csv`为2方法6480行；`results/hardware.csv`为160个扩展环境×2模式。名义模式的审计中止与真实完成失败分开解释。官方六次正式成绩及加密日志仍待补齐。
