# C题跨日随机控制

数值计算和结果导出已完成。验收状态及独立审查记录分别见 artifacts/acceptance.json 与 review/findings.json。

本题解独立于旧目录，把连续储电状态、因果合同决策、随机滚动控制和通用SDDP落实到原附件。论文由用户手工撰写。建模计算交接、工作簿和独立审查对应同一组计算结果。

## 阅读入口

- 模型与推导.md：题意、假设、符号、四问公式和实现限制。
- 建模计算交接.md：主结果、候选比较及验证。
- 指定日期结果表.md、计算结果：指定日与完整结果。
- review：独立SDDP小树、信息时序、凸DP与轨迹检查。

## 计算结构

第一问是确定性LP。后续问题的主候选为跨日因果仿射策略SAA计划加Markov随机DP反馈；SDDP按月训练辅助未来价值，再作为同一MPC的备选末值。根库存只初始化一次，中间午夜不固定6000，年末自由为主设置。

通用SDDP是有限时域、阶段独立有限噪声、连续状态凸线性接口。它需要有效的初始继续费用下界。当前SDDP原数据结果是粗辅助模型及末值增强MPC，不是原题全时段精确SDDP最优策略。

## 复现环境

本地计算使用Python 3.13、numpy、scipy、matplotlib和HiGHS。vendor保存本机macOS ARM64所用highspy；其他平台需移走不适配的vendor/highspy后，安装该平台的highspy；依赖版本见requirements-model.txt。Excel读取使用带openpyxl的bundled Python，工作簿生成使用bundled Node与artifact-tool。最终复现命令和各次实际执行记录在复现.sh与artifacts/execution-*.json中。

重新执行数值或导出后，先前独立审查的哈希不自动适用于新文件，需要重新审查并运行验收器。
