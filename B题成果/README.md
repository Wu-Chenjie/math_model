# B题成果入口

建议先读 **B题_论文撰写交接.pdf**；写作修改使用 **B题_论文撰写交接.docx** 或 **B题_论文撰写交接.md**。完整交接含四问模型、证明、参数、统计、图、接口、复现及官方测试待办。

当前本地独立测试：问题3、4各200局全部清除，案例等权平均单源虚拟时间349.87秒、868.17秒；五类压力测试共1000局全部清除。原模拟器60局物理核与6局真实本地HTTP演练全部清除。四组配对主/消融共1600行。多层实验不要混为官方测试。

独立模拟审稿质量分91/100；另有独立挑错报告。六次官方正式成绩与原名加密日志尚未取得，因此不能声称官方题目提交材料已齐全。

## 文件

- `src/`：C++几何、策略、模拟与实验；Python只作接口桥、统计、作图和文档生成。
- `results/`：逐局CSV、统计JSON、6份本地HTTP明文日志、构建记录。
- `figures/`：5组PNG、SVG、矢量PDF图。
- `review/`：数学预审、代码独立审查、论文评分、论文独立复核及独立测试。
- `run_all.ps1`：编译并复现全部数据与主文Markdown，已实际整套运行通过。
- `src/build_documents.py`：将主文编译为DOCX/PDF，需本机已有pandoc和XeLaTeX。
- `manifest.json`：最终文件SHA256和环境信息，由`src/freeze.py`生成。

## 复现

当前机器已具备g++、Python、numpy、scipy、matplotlib。保留同级原目录`26B-team-v1.0.0`，程序只调用其公开规则物理与HTTP客户端，不修改模拟器。

```powershell
cd G:\math__model\B题成果
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_all.ps1
python src/build_documents.py
```

墙钟运行时间会变化，复跑后主文自动同步HTTP表；策略虚拟数值及种子集合应固定复现。审稿中记录的是对应版本快照，最终依据主文、CSV和manifest。

## 官方环境连接

官方模拟器登录并提示接口就绪后：

```powershell
python src/bridge.py --problem 3 --team-id 实际参赛队号 --log results/official_practice_p3_01.jsonl
```

问题4将`--problem`改4；每次换新日志文件名。桥本身不启动测试、更不会消耗正式机会；演练或正式模式由官方界面决定。正式测试结束后须在官方界面导出加密日志，保持原文件名，并从官方记录填写六行正式表。

本地策略没有源数、源坐标、接收半径、朝向或debug/truth读取权限。模拟器评估层读取真值只用于检查结果，不参与决策。
