# 权威结果文件

冻结口径：2026-07-31 hardened scorer、完整行动集重放、固定 100 题分母。恢复只允许预注册的
纯基础设施门；3 个恢复成功，原 failure 和 provenance 均保留。

## 最终主结果

| 方法 | 提交 | Active failure | 决策模型等价 | Decision E2E | Semantic E2E |
|---|---:|---:|---:|---:|---:|
| GPT-5.6-sol one-shot frozen corpus | 99 | 1 | 95 | 89 | 47 |
| OPTIMUS-inspired | 100 | 0 | 93 | 84 | 44 |
| CoE-inspired | 13 | 87 | 12 | 8 | 4 |
| OptiMiner training-free compatibility | 92 | 8 | 89 | 72 | 39 |

对应文件：

- `gpt56_sol_high_one_shot_corpus_search_full_summary.json/.md`
- `optimus_inspired_corpus_full_summary.json/.md`
- `coe_inspired_corpus_full_summary.json/.md`
- `optiminer_training_free_compat_corpus_full_summary.json/.md`
- `one_shot_optimus_coe_optiminer_paired.json/.md`

## 其他权威结果

- 无搜索：`gpt56_sol_high_one_shot_no_search_full_summary.json/.md`
- 真实联网：`gpt56_sol_high_one_shot_live_web_full_summary.json/.md`
- 网页来源人工裁决：`live_web_source_adjudication.md`
- 三条件网页题比较：`one_shot_web20_three_condition_paired.json/.md`
- no-search vs frozen：`one_shot_no_vs_corpus_paired.json/.md`
- 数据审计：`dataset_audit.json/.md`
- 检索捷径：`retrieval_baselines.json`
- oracle-base 模板攻击：`template_patch_control.json`
- 错误分析：`ONE_SHOT_ERROR_ANALYSIS.md`、`COE_FAILURE_ANALYSIS.md`、
  `OPTIMINER_FAILURE_ANALYSIS.md`
- 成本：`COST_AND_RUNTIME.md` 与四个 `*_attempted_usage.json`
- 总结：`EXPERIMENT_FINDINGS.md`

## 恢复与失败口径

- CoE 的最终分母保留 87 个 active failure；两次 CLI recovery 均未成功；
- OptiMiner 原始为 89 submission + 11 failure；
- SWOR039、SWOR026、SWOR040 同时满足 response 缺失、events=0、stderr=0，各恢复一次成功；
- SWOR095 stderr 非空，不满足门，不恢复；
- 7 个 controller max-turn 是方法失败，不恢复；
- OptiMiner 最终为 92 submission + 8 active failure + 3 recovered failure。

分片根聚合保留原始全量运行状态；恢复后的最终评分以 task-level `submission.json`、
`failure.json` 与 `resume_resolution.json` 为权威。合并审计为 expected=100、merged=92、
active=8、recovered=3、duplicates/uncovered/unknown 均为 0。

## 口径边界

- one-shot no-search 按合同要求空补丁；0/100 不是自主搜索失败率；
- one-shot frozen corpus 是 runner 提供 metadata-BM25 top-5，不是自主检索；
- `decision_model_equivalent` 比较完整投影可行集和完整最优行动集合；
- `decision_e2e` 还要求 exact Gold document identity；
- live-web exact URL 不等于权威来源语义正确率；
- `reasoning=high` 是请求参数，未独立验证；
- 三个 Agent 方法都是 inspired/compatibility adapter，不是上游未修改复现；
- 当前 Gold 公开且 100/100 仍为 unresolved reject，结果是开发集分析，不是无污染 leaderboard。

最终本地文件 SHA-256 由 `authoritative_manifest.json` 给出；公开包经过路径清洗后使用独立的
`PUBLIC_BUNDLE_MANIFEST.json`，两种 manifest 的字节哈希不可混用。
