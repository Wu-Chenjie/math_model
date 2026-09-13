# B题几何策略优化

本轮已实现并验证五组几何优化，候选84在独立Q4中平均节省29.62秒，但95%区间跨零，未推广。推荐默认仍为方法78。完整推导和全部负结果见《B题几何策略优化_题解.md》与论文PDF。

交付文件：

- [论文 PDF](B题几何策略优化_论文.pdf)与[题解 PDF](B题几何策略优化_题解.pdf)。
- [论文与支持材料整包](B题_论文与支持材料.zip)，或单独下载[代码与数据包](B题几何策略优化_代码与数据.zip)。
- 最新补充：[信号源数量与平均时长](补充分析/信号源数量与平均时长/信号源数量与平均时长_论文补充.md)、[可插入论文的 LaTeX 段落](补充分析/信号源数量与平均时长/论文插入段落.tex)及同目录中的原始 CSV、验证记录和绘图源码。该补充分析晚于上述 PDF 和 ZIP，当前单独交付，尚未合入论文 PDF 或压缩包。
- 不限于现有策略的[数量—时长一般理论](补充分析/源数量与时长_一般理论/一般理论与论文表述.md)及[论文一般理论段落](补充分析/源数量与时长_一般理论/论文一般理论段落.tex)：包含任意策略的均时下降判据、BHH条件模型和20米邻域巡游下界。此前方法78的系数仅是案例；一般理论未宣称完成跨策略实证。此补充同样尚未合入原PDF和ZIP。

策略入口：

- `joint`：推荐方法78。
- `geometric`：本轮实验候选84，Q4动态认证发现点，Q3与78相同。
- `previous`：比较基线56。

在本目录运行 `python3 run_all.py` 可编译和核验；`--full` 重跑固定独立及压力集；`--paper` 重建LaTeX论文。Linux字体需将paper/main.tex的fontset=mac改为相应本机CJK字体；C++计算不依赖字体。

在线使用：`python3 src/bridge.py --problem 4 --team-id 实际队号 --strategy joint --planner-depth 2`。

需要C++17编译器和Python；科研图需要NumPy、SciPy与Matplotlib，论文需要XeLaTeX、ctex和listings。禁止fast-math。桥接依赖已随附的vendor/mocksim公开协议实现，它不是官方模拟器。

本地全部清除不能替代Q3/Q4各三次官方正式测试。当前未含可核验的正式加密日志；论文正式表格明确待填。原B题连续规划优化目录保持原状。

复现边界：`run_all.py` 必须在项目根目录使用，解压目录可改名；`work/` 仅为评审快照。Python统计依赖SciPy，不会缺包时改用不同置信区间。PDF元数据清理需pypdf，可用 `PDF_PYTHON` 指向具备它的Python；图表和论文默认使用macOS宋体，在其它系统需明确替换字体。C++编译器可用 `CXX` 指定。

本地普通场景有40米源间距排斥条件。相同种子标签跨编译器或标准库不保证同一场景；历史CSV未混入本轮对比。原始源码的80行本机基线复核相同，详见 `artifacts/baseline-compatibility.json`。

验证状态为LIMITED：本地计算、独立评审修复和PDF质量检查已完成，正式六次测试及加密日志尚未完成。完整主张登记、运行命令与哈希见 `modeling-manifest.json`、`artifacts/result-registry.json` 和 `artifacts/reproducibility.json`。
