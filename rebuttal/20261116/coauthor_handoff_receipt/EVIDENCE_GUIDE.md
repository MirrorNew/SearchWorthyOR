# 证据导航与口径

所有下述路径均相对于 `SWAgent-for-ICLR/`。

| 写作时使用的事实 | 数字／范围 | 直接证据 |
|---|---|---|
| C2同骨干比较 | Standard答案133/300、模型100/300；SWAgent答案199/300、模型166/300 | `rebuttal/20261116/full_model_audit/independent_model_equivalence_summary.json`、同名records.csv |
| 三次运行的模型提升 | +24、+21、+21个百分点 | `rebuttal/20261116/full_model_audit/focused_evidence_summary.json` |
| 完整模型修正 | 156次FAIL→PASS；初始PASS14、最终PASS166，净增152 | `rebuttal/20261116/full_model_audit/independent_model_equivalence_report_zh.md` |
| 外部正文与实际补丁可追踪 | 上述156次均核实实际请求含正文、匹配响应被消费、非空补丁接受 | `rebuttal/20261116/full_model_audit/model_payload_validation.json` |
| 另28次优化改进 | 与156次不重叠；修正最优值及完整最优行动集 | `rebuttal/20261116/full_model_audit/semantic_33_run_index.csv`、`semantic_optima_recompute.json` |
| SWAgent答案正确但严格不等价 | 全部33次、18个源任务；33/33完整最优行动集相同 | `rebuttal/20261116/full_model_audit/semantic_fullmodel_case_audit_20261116.md` |
| 安全优化约简 | R025三次、R103一次、R105一次；10个被删组合均有同一业务选择、更优的保留替代 | `rebuttal/20261116/full_model_audit/dominance_audit.json`、`dominance_audit_zh.md` |
| SWAgent语义子集 | 7参考边界、5安全约简、9明确错误、3混合、9未定；确认含错12/33 | `rebuttal/20261116/full_model_audit/semantic_33_run_index.csv`及语义报告 |
| Standard语义子集（新增材料） | 33次、14源任务；6确认含错、12安全约简、6参考边界、9未定 | `rebuttal/20261116/full_model_audit/standard_33_semantic_audit_20261116.md`及同名JSON |
| C3正式试验 | Standard17/20=85%，SWAgent18/20=90%；全部失败保留分母 | `rebuttal/20261116/orlm_c3/RESULTS_20261116.md`、`batches/main20_v1/objective_scores.csv` |
| C3参考与输入 | 20题、110张CSV；20个参考COPT最优，19个跨求解器一致，1个Gurobi许可证规模限制 | `rebuttal/20261116/orlm_c3/source_manifest.json`、`orlm_reference/reference_results.json`与`reference_crosscheck.json` |
| 描述性输入示例 | REAL_RB-CO-00，8天、12产品；仅改写展示，未跑新实验 | `rebuttal/20261116/dqz1_第一点_业务描述还原示例.md`、`real6_example_provenance.json` |

## 表述时需要保持的区分

1. 300是每方法100源任务×3次运行，不是300个独立源任务；33也是运行数。156与28是两类轨迹，不能写成184个完整正确模型。
2. 33条完整最优行动集相同不等于33条全部约束语义正确。5条约简证书限于给定任务的约束与成本；原55.33%不重算。
3. 最新中文表4把各自33条条件子集的确认错误比例与300条全量成绩放在一起。不同方法的33条任务组成不同，不能把6/33与12/33解释成全量可靠性排名。为保持论证重点，可把该列移到单独诊断或核查材料；数据仍完整保留。
4. 156/156的请求到补丁核验是过程证据，不单独证明每份外部正文都相关／适用，也不替代检索因果作用的消融。
5. C3的85%/90%是最优目标值匹配，使用自由变量IR与COPT适配。原始运行协议在 `orlm_c3/SCORING_PROTOCOL.md`；不把它写成全模型正确率。
6. 最新（a）的来源陈述按作者稿保留。本包不额外认证其客户来源；20题C3与REAL6是两套材料。REAL6原文件明确写数值独立合成，不能用它冒充20题成绩对应的客户原始实例。是否使用真实业务／脱敏等来源措辞，应由作者持有的来源证明支持。

## 复核入口

- 新的完整C2复算：`rebuttal/20261116/full_model_audit/independent_model_equivalence_audit.py`。
- 原先（20261114）的统计与载荷源记录：`analysis/rebuttal_dqz1_evidence_20261114/`。
- 全部冻结题面、规则、gold、参考IR：`datasets/SearchWorthyOR-v1.6.3/`。
- C2原始案例目录由records.csv中的`model_file`、`initial_model_file`和`result_file`定位。
- C3离线评分：在项目根运行 `python rebuttal/20261116/score_orlm_runs.py main20_v1`。
- 历史`publication_manifest.json`可能早于作者后来改稿；本次快照的权威清单为本包根目录`MANIFEST.json`及`AUTHOR_DRAFT_STATUS.json`。
