# 输出、信息消融与一键复现有界审查

审查人：`/root/upgrade_code_review`。只读检查生产工具，只修改review文件。未派发年度优化、未启动活跃流水线副本。

## 当前结论

已修复冷启动缺清单文件及父进程过早释放锁两个实际问题。临时首派发夹具通过：全新REPLAY会有modeling-manifest.json，进入首个命令时pipeline.lock仍由父进程持有。独立无害子进程实验确认pass_fds可沿用同一锁，另一独立打开文件的进程不能同时获取锁。该检查在任何模型计算之前停止，不等于已经运行完整一键复现。

新版v5协议反例通过：人为设置S=5/14的开发账单远低于7/10，最终主候选仍只能取7或10，敏感性5/14继续进入年度登记。阶段分别为representative_count_sensitivity（selecting=false）和representative_count_main_selection（selecting=true）。这不会使用正式费用改变选择。

## 工具逐项审查

- `match_information_ablation_endpoints.py`先要求完整基线复现PASS，从复现后的334日发布受限策略取第333日初库存，重算自由末端最后两日并与原全部NPZ数组比较，包含NaN/有限位置、日期、价格、发布记录与投影。匹配后才切换为6000硬终点，拼接费用和库存再独立核验。该前缀依据仅适用原两午夜控制器，不用于新固定长H。不同发布消融保留原合同权限，只改变合法预报可见集合。
- `build_paper_results.py`主费用读取采用配置对应的实际账单对照；Q1读冻结已验证LP并用原数据计算无电池参照；M1直接比较读取最终同末值M0/M1；信息价值采用“受限信息费用减完整预报费用”，符号方向正确，双方固定6000。完美信息只作参照，未取得因果期望下界时字段为null，不伪造gap。
- `export_selected.py`只按已采用配置将formal输出复制为工作簿别名，没有从正式候选重新选最便宜者。Q1来自独立完整复现目录。后续旧表格布局适配器读原始q与最终r，保持账单、实时电池动作及指定日期细表。
- `reproduce_project.py`当前持锁覆盖基线、开发、年度续跑、导出和论文阶段，锁FD传给continuation。冷启动会复制冻结根文件、paper与所需目录；重跑年度通过归档保存旧结果，保留冻结选择，不再重新调参。
- `continue_registered_pipeline.py`按完整基线比较、冻结开发、独立模型检查、开发验证、冻结年度登记、全部正式验证、配对费用、再次模型证书、唯一challenger采用、作图顺序执行。任何非零返回码停止。真实运行仍需等其各阶段完整结束，不能把本次静态审查当作执行成功证据。

## 最终输出前的追溯建议

1. 论文数值生成器应核对adoption、comparisons与当前freeze摘要一致；对信息消融核对执行清单中的validation_sha256及proof绑定的NPZ/JSON摘要，而不是只检查status。所有字段已有，检查成本很低。
2. 采用输出清单应把复制的Q1两份文件也加入source_hashes，方便从工作簿精确追溯到本次复现文件。
3. 从原src复制到tools的工作簿验证器仍应更新记录中的实际命令路径，避免输出声称执行不存在的src/verify_workbooks.py。
4. 这些工具没有自动完成人工视觉审查或评委终审；编译器记录仍应保留visual_review_pending，直至检查渲染页并完成独立最终审查。

机器证据：`output-pipeline-checks.json`、`protocol-comparison-checks.json`。前者只验证冷启动准备和互斥机制；后者使用临时假账本测试协议，任何夹具数字都不属于竞赛年度成果。
