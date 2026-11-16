# dqz1 第二点：可直接用于回复的核查结论

最有力的回应是澄清 **55.33% 衡量严格参考等价，而不是外部规则纳入的成功率**。我们已有具体实例和完整枚举支持这一点，无需诉诸“不同建模总能得到相同答案”的泛泛论述，也无需撤回原指标。

| 可用于正文的结论 | 原始数据证据 | 准确解释 |
|---|---|---|
| 同一骨干下，SWAgent 的答案正确率和严格全模型等价率均提高 22.00 个百分点 | 199/300 对 133/300；166/300 对 100/300 | 改进并不限于返回一个正确数值，严格模型诊断也同步改善。 |
| 33 条答案正确但全模型不等价的记录，均保留完整最优行动集合和最优值 | 对该完整子集逐点枚举，33/33 一致 | 非最优行动上的差异不能自动否定已经得到的优化结果；这比仅核对返回数值更强。 |
| 其中 28 条通过更新修正了初始错误的最优值和最优行动集合 | 首次 UPDATE 前模型与最终模型对比 | 这些轨迹显示了更新带来的实际优化改进，不能统一解释为初始模型碰巧答对。 |
| 7 条参考差异得到明确题面事实支持 | R023 一次、R055 三次、R090 三次；把相应事实加入参考副本后可行集合完全相同 | 严格参考检查可以把遵循 case 条件的模型记为不一致。原参考与原成绩均未修改。 |
| 5 条差异具有保持优化结果的支配关系证书 | R025 三次、R103 一次、R105 一次；10 个被删除动作均有同一业务选择、目标严格更优的保留替代 | 在给定任务约束和成本下，这些限制是安全优化裁剪；不需要保持全部非最优可行动作。 |
| 156 次更新将初始不等价模型修正为完全等价模型 | 全部 300 条 SWAgent 轨迹的初态／终态比较 | 严格参考指标本身也提供了大量成功修正的证据。不能把所有未通过终态检查的原因都归于 UPDATE。 |

最适合作为回复核心的表述：

> The 55.33% figure is a strict reference-equivalence rate, rather than a measured success rate of external-rule incorporation. Our case-level audit identifies concrete reference-boundary differences and certified optimality-preserving reductions. Therefore, failure of this diagnostic cannot uniformly be interpreted as incorrect or missing constraints.

建议先重申贡献定位：本文首先提出并刻画未明示外部规则的主动发现问题，建立控制适用性与可见性的可评测基准，再提出 SWAgent 展示可行路径与实证改进。方法尚有提升空间，不影响问题及基准贡献；方法的价值则由同骨干比较和更新轨迹支持。

正文聚焦以上证据。完整审计仍保留所有分类、未决边界和反例，便于复核；12 条有解释／证书的记录是明确限定的子集，不能外推为所有不等价模型都正确。33 次运行对应 18 个源任务，也不能写成 33 个独立任务。

证据入口：

- `full_model_audit/independent_model_equivalence_report_zh.md`：600 条记录的独立精确复算。
- `full_model_audit/semantic_33_run_index.csv`：33 条逐运行索引和最终分类。
- `full_model_audit/semantic_fullmodel_case_audit_20261116.md`：18 个源任务的逐例依据。
- `full_model_audit/dominance_audit_zh.md`、`dominance_audit.json`：安全裁剪证明与全部动作证书。
- `dqz1_followup_model_reply_EN.md`、`dqz1_followup_model_reply_ZH.md`：聚焦有利证据的中英文回复。
