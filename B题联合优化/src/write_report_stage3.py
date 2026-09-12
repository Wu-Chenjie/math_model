import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s1=json.loads((R/'results/summary.json').read_text(encoding='utf-8'))
s2=json.loads((R/'results/summary_stage2.json').read_text(encoding='utf-8'))
s3=json.loads((R/'results/summary_stage3.json').read_text(encoding='utf-8'))
def ci(v):return f'[{v[0]:.2f}, {v[1]:.2f}]'
table=[]
for p in ['3','4']:
    x=s3['iid'][p];single=100*(1-x['new_single_s']/x['baseline_single_s'])
    table.append(f"|问题{p}|{x['baseline_single_s']:.2f}|{x['new_single_s']:.2f}|{single:.2f}%|{x['saving_percent']:.2f}%|200/200|")
stress=[]
for k,label in enumerate(['边界向外','近共线端点','重合近距离','平滑相关','分区端点'],1):
    a,b=s3['stress'][str(k)]['3'],s3['stress'][str(k)]['4'];stress.append(f"|{label}|{a['saving_percent']:.2f}%|{b['saving_percent']:.2f}%|40/40，40/40|")
p3,p4=s3['iid']['3'],s3['iid']['4']
doc=f'''# 联合优化最终结果（第三阶段）

主基线为刚交付的B题动态规划默认两步DP。所有百分比基于同案例比较，没有切换到较弱历史基线。

## 新独立测试

seed1910001—1910200，每问200个基础环境，两方法各运行一次。方法56已在打开此组之前冻结。

|小问|基线单源秒|新单源秒|单源均时下降|总均时下降|全清除|
|---|---:|---:|---:|---:|---:|
{chr(10).join(table)}

单源均时=mean(T/N)，总均时下降=mean(T旧−T新)/mean(T旧)。各局N不同，这两个百分比不相同。

- Q3总均时：{p3['baseline_total_s']:.2f}→{p3['new_total_s']:.2f}秒；节省95%配对t区间{ci(p3['paired_ci95_s'])}秒；更快/更慢={p3['wins']}/{p3['losses']}。
- Q4总均时：{p4['baseline_total_s']:.2f}→{p4['new_total_s']:.2f}秒；节省95%配对t区间{ci(p4['paired_ci95_s'])}秒；更快/更慢={p4['wins']}/{p4['losses']}。
- Q4超过10%门槛的量为0.9T旧−T新，均值{p4['excess_over_10pct_s']:.2f}秒，95%区间{ci(p4['excess_over_10pct_ci95_s'])}秒。若此区间跨零，样本均值达标与总体改善已证超过10%必须区分。

## 三阶段记录

|冻结阶段|新测试种子|Q3总均时下降|Q4总均时下降|
|---|---|---:|---:|
|38：联合调度/直接光学|1510001—1510200|{s1['iid']['3']['saving_percent']:.2f}%|{s1['iid']['4']['saving_percent']:.2f}%|
|39：增加条件权重顺序|1710001—1710200|{s2['iid']['3']['saving_percent']:.2f}%|{s2['iid']['4']['saving_percent']:.2f}%|
|56：增加自适应几何覆盖|1910001—1910200|{p3['saving_percent']:.2f}%|{p4['saving_percent']:.2f}%|

前两阶段没有达到10%，记录及失败/变慢案例全部保留。每次新机制都先在1—40、1001—1040开发组比较，冻结后才打开新测试组。三阶段不是同一固定策略的重复样本，不能合并为一个性能区间。开发探索及多轮验证本身也意味着不能把最后一次结果当作未经任何模型探索的普适保证。

## 最终实际采用的机制

**Q4：** 两步DP、最多63个位置/接收半径/朝向假设，每个实际动作之后重新参与全局路线排序；每源最多6次动态动作；之后直接进入连续光学覆盖。固定发现布局仍为21点，未声称减少到20点。

光学覆盖不再直接填满外接矩形。沿首次示向轴将保守多边形按不超过28米宽的条带切分：某条带的最小包围圆若小于20−1e−5米，用一个清除点覆盖；否则继续纵向分割并逐块检查包围圆。条带覆盖整个多边形，子块均被清除圆覆盖。典型1500米长扇形由108个清除点降为78个。这是局部清除点数的降低，不是21个全局发现点的降低。

随后按已收到观测的有限条件权重比较完整扫掠顺序。排序不删除任何新覆盖子块。权重近似出错会影响效率，但不会使已构造的覆盖子块消失。实际几何使用浮点计算和余量，未冒充形式化实数证书。

**Q3：** 入口候选菜单、动作级联动、每频道最多4次机会补测、1124米六点环加原点、安全清除邻域。问题3在这一轮没有同样达到Q4的改善幅度，须单独报告。

## 覆盖与预算

Q3新环的连续覆盖通过径向凸性和√3的有理数界核验，理想覆盖半径999.6米，实际C++坐标逐点误差小于1e−9米。见q3_coverage_bound.json和q3_production_points.json。

Q4适配光学最多54条带、每条至多两个清除圆，仍以108点作保守上界。相邻保留中心的距离可取77米上界；若循环移位，另取1520米连接上界。以最多133个长移动段、每段5344米，再加局部扫描，可得到保守虚拟费用界182027.2秒，低于100小时。Q3沿用更宽松的354574.4秒界。都以合法响应和正确维护保守区域为条件；网络现实截止仍由通信桥控制。

## 压力和不利情况

第三阶段压力组使用1920001—1960001各起40种子，每问每类40环境。相对同案例旧两步DP：

|压力组|Q3总均时下降|Q4总均时下降|全清除|
|---|---:|---:|---|
{chr(10).join(stress)}

负数表示变慢。压力组不参与IID达标计算。Q3 IID最差种子{p3['worst_seed']}慢{p3['max_slowdown_s']:.2f}秒；Q4最差种子{p4['worst_seed']}慢{p4['max_slowdown_s']:.2f}秒。不会仅保留获胜案例。

## 开销、测试与使用

新版Q3整局C++平均{p3['new_cpu_mean_s']:.3f}秒，最大{p3['new_cpu_max_s']:.3f}秒；Q4平均{p4['new_cpu_mean_s']:.3f}秒，最大{p4['new_cpu_max_s']:.3f}秒。状态预算命中数Q3/Q4={p3['budget_hits']}/{p4['budget_hits']}。

测试包括Bellman穷举对照、观测一致性、每源预算、全局有限进度、光学完整序列、100个不同定位区域的覆盖交叉检查、实际坐标、CLI和通信回归。默认控制器通过原模拟器核与本地HTTP演练，原始记录在original_mock_joint_depth2.json。未执行官方正式测试，未安排外部独立审稿。

默认`--strategy joint --planner-depth 2`。`--strategy baseline`回到原两步DP；stage1、stage2保留此前版本。源代码、开发记录、三阶段独立数据、压力数据和复现脚本均保存在本目录。
'''
(R/'最终结果.md').write_text(doc,encoding='utf-8')
print('final stage3 report generated')
