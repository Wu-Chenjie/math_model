# B题第二轮优化

先读`B题优化_论文交接.pdf`；可编辑版本为同名DOCX和Markdown。它替换首版Q2和问题3/4策略及实验部分，问题1沿用首版完整交接。

- Q2：精确有理数证书，完整首扇区连续模型全局差≤0.00071米；真实量化模型差≤0.08831米。一般地图截断后仅保留上界保证。
- Q4：25个固定测点连续覆盖，数量下界14；不宣称25最少。
- 新独立测试：两问各200局全清除，相对同案例旧策略总时间下降17.08%/23.63%；平均单源285.28/646.76秒。
- 原模拟器66局和1000局新压力测试全清除；六次官方正式测试仍未取得。

## 运行

```powershell
cd G:\math__model\B题优化
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1
python src/build_documents.py
```

依赖同级`26B-team-v1.0.0`、g++、Python和numpy/scipy/matplotlib。文档生成用已有pandoc和XeLaTeX。Q2精确证书验证仅需Python标准库。

官方模拟器已登录且接口就绪后，使用`python src/bridge.py --problem 3 --team-id 实际队号 --log results/新日志.jsonl`，问题4改4。默认机器人已经启用最终冻结方案；程序不启动官方正式测试。

`src/`保留旧方案开关便于同案例比较，`robot.exe`默认最终方案。`冻结配置.md`说明所有参数及种子；`results/`保留全部逐局数据；`review/`含独立数学、布局路线、Q2专项复核和最终论文审稿。

所有“最优”声明必须区分：Q2完整扇区纯精度近最优；固定布局仅14—25界；2-opt只是代理路径局部改进。真正任务时间依赖实验验证。勿把不同测试集的原始均值相除计算增益。
