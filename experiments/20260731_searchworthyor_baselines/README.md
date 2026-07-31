# SearchWorthyOR baseline 实验

本目录评测一个具体问题：外部规则搜索是否真的改变 OR 模型与决策，以及这种改变是否需要复杂
Agent，而不是候选格式、固定补丁模板或简单文本替换。

## 当前执行状态

截至 2026-07-31：

- GPT-5.6-sol high one-shot、无搜索：100/100；
- GPT-5.6-sol high one-shot、冻结语料检索：99 个完整提交，1 个非重试代码语法失败，分母仍为 100；
- GPT-5.6-sol high one-shot、真实联网搜索：20/20 real-web 任务；
- OPTIMUS-inspired prompt adapter、冻结语料：100/100；
- Chain-of-Experts-inspired role adapter、冻结语料：13 个提交、87 个 active failure；
- training-free OptiMiner compatibility adapter、冻结语料：92 个提交、8 个 active failure，
  其中 3 个严格基础设施失败各恢复一次。

实际模型标识是独立 Codex CLI 接受的 `gpt-5.6-sol`，调用参数为
`model_reasoning_effort="high"`。`high` 是已记录的请求参数，当前没有独立的内部 reasoning
验证器，不能写成“reasoning 已验证”。实验不依赖聊天中提供的 token，也没有用其他模型静默
替代。

## 已得到的核心结果

### 全量 one-shot

| 条件 | 分母 | Base model | 结构改模 | 完整决策模型等价 | Decision E2E | Semantic E2E | Strict exact E2E |
|---|---:|---:|---:|---:|---:|---:|---:|
| 无搜索 | 100 | 100 | 0 | 0 | 0 | 0 | 0 |
| 冻结语料 | 100 | 99 | 98 | 95 | 89 | 47 | 0 |

冻结语料相对无搜索使完整决策模型等价从 0/100 提升到 95/100；任务级成对 bootstrap 95% CI
为差值 90–99 个百分点，McNemar 精确双侧 `p=5.049e-29`。这证明证据条件确实改变了模型和
决策，但不证明高级检索 Agent 必要：当前候选组织可被 task-blind medoid 100% 命中，Gold
patch 只有 7 种匿名结构签名，96/100 是很小的 append-only patch。

这里的 one-shot `no_search` 是受控 evidence ablation：提示合同明确要求在没有证据时保持
base/patched IR 相同，所以 0/100 不是“模型尝试凭记忆搜索并全部失败”。`corpus_search` 也不是
模型自主查询：runner 用实体、辖区和决策时间执行固定 BM25，并把 top-5 候选放入唯一一次模型
调用。该差值识别的是“提供冻结证据候选的价值”，不是“自主搜索策略的价值”。

### 四种冻结语料方法

| 方法 | 提交 | 完整决策模型等价 | Decision E2E | Semantic E2E | 完成调用 input |
|---|---:|---:|---:|---:|---:|
| one-shot | 99 | 95 | 89 | 47 | 1,777,010 |
| OPTIMUS-inspired | 100 | 93 | 84 | 44 | 8,651,106 |
| CoE-inspired | 13 | 12 | 8 | 4 | 62,726,738 |
| OptiMiner compatibility | 92 | 89 | 72 | 39 | 7,241,908 |

one-shot 相对 OPTIMUS 的决策模型等价差值为 `+2pp`，95% CI `[-2,+6]`；相对 OptiMiner
为 `+6pp`，95% CI `[+1,+12]`，但 McNemar exact `p=0.0703`。因此没有证据说明更复杂的
OPTIMUS 或自主搜索控制器优于固定 top-5 one-shot。OptiMiner 在形成提交的 92 题中有
`89/92=96.7%` 决策等价，主要损失来自 8 个 pipeline failure；CoE 在成功的 13 题中有
12 题决策等价，但 87 个执行失败使该条件准确率不能代表全量能力。

成本上，OPTIMUS、OptiMiner、CoE 的 input 分别约为 one-shot 的 `4.87×`、`4.08×` 和
`35.30×`。CoE 与 OptiMiner 的完成调用数几乎相同（398 vs 397），但 CoE input 是后者的
`8.66×`，反映的是专家链上下文膨胀和运行时能力失控。

### 同一 20 条网页题

| 条件 | 完整决策模型等价 | 结构改模 | Gold ID/URL exact |
|---|---:|---:|---:|
| 无搜索 | 0/20 | 0/20 | 0/20 |
| 冻结网页快照 | 16/20 | 19/20 | 18/20 |
| 真实联网 | 16/20 | 19/20 | 3/20 |

人工 source adjudication 显示真实联网 20/20 都找到语义等价的权威来源；3/20 只是 Gold URL
字符串完全相同。因此 exact URL 不能当作检索正确率。SWOR085 还暴露了公开题面的适用主体
歧义：没有说明食品受 FDA 而非 USDA/TTB 管辖，Agent 的 abstention 有合理依据。

## 先读什么

- [实验结论](results/EXPERIMENT_FINDINGS.md)
- [one-shot 错误分析](results/ONE_SHOT_ERROR_ANALYSIS.md)
- [CoE 全量失败分析](results/COE_FAILURE_ANALYSIS.md)
- [OptiMiner 全量失败分析](results/OPTIMINER_FAILURE_ANALYSIS.md)
- [成本与运行时](results/COST_AND_RUNTIME.md)
- [四方法成对统计](results/one_shot_optimus_coe_optiminer_paired.md)
- [Graph Engineering 框架](docs/GRAPH_OR_SEARCH_AGENT.md)
- [实验协议与身份边界](docs/EXPERIMENT_PROTOCOL.md)
- [污染与公开发布边界](docs/CONTAMINATION_AND_RELEASE_BOUNDARY.md)
- [Runner 与恢复 provenance](docs/RUNNER_PROVENANCE.md)
- [数据审计摘要](results/dataset_audit.md)
- [无搜索 vs 冻结语料成对统计](results/one_shot_no_vs_corpus_paired.md)
- [20 条网页题三条件成对统计](results/one_shot_web20_three_condition_paired.md)

## 方法身份边界

- `gpt56_sol_codex_cli_one_shot`：每题一次独立最终建模调用；无 Agent loop。
- `optimus_inspired_cli_adapter`：读取本地 OptiMUS 提示文件的参数、目标、约束阶段形状，再做
  独立最终建模；不是上游仓库未修改复现。
- `coe_inspired_cli_adapter`：读取本地 Chain-of-Experts 的专家提示与交接顺序；不是上游仓库
  未修改复现。
- `optiminer_training_free_compat_cli`：保留搜索控制—结果回填—最终建模的 training-free
  形状，但允许外部业务规则改变约束。原本地复现只允许外部文档提供建模/求解提示，和本数据集
  的任务合同冲突，因此只能称 compatibility adapter。

本地 baseline 目录是非 Git snapshot。run manifest 保存了实际读取文件的绝对路径与 SHA-256，
不能声称对应某个未经验证的 upstream commit。

## 评分口径

`score_submissions.py` 区分：

- `base_model_success`：可信后端重放出的 base 模型正确；
- `generated_code_ir_consistent`：生成的 Gurobi 代码行动属于该 IR 的完整最优行动集合；
- `model_structurally_changed`：证据模型相对 base 发生非空结构变化；
- `projected_feasible_set_match`：完整投影可行集与 Gold 一致；
- `optimal_action_set_match`：完整最优行动集合与 Gold 一致；
- `decision_model_equivalent`：可行集和最优行动集同时等价；
- `decision_e2e`：再要求采用 exact Gold 文档身份；
- `semantic_e2e`：语义 IR、typed patch、claim binding 与决策均通过；
- `strict_e2e`：所有过程对象 canonical exact match。

只比较一个 Gurobi incumbent 会把 multiple-optima 错模型计为成功；本 scorer 枚举小模型的完整
投影可行集和最优行动集。

## 复现环境

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$python = '<PYTHON>'
```

从实验目录运行时，先解析数据集根目录；第一项适用于公开仓库，第二项适用于原工作区：

```powershell
$datasetRoot = if (Test-Path '..\..\public\tasks_zh.jsonl') {
  '..\..'
} else {
  '..\..\datasets\SearchWorthyOR-100'
}
```

## 复现确定性审计

```powershell
& $python scripts\audit_dataset.py `
  --dataset-root $datasetRoot `
  --json-out results\dataset_audit.json `
  --markdown-out results\dataset_audit.md

& $python scripts\evaluate_retrieval_baselines.py `
  --dataset-root $datasetRoot `
  --output results\retrieval_baselines.json

& $python scripts\run_template_patch_control.py `
  --dataset-root $datasetRoot `
  --output results\template_patch_control.json
```

`run_template_patch_control.py` 读取 Gold base IR，只能解释为
`oracle-base patch-only attack`，不是端到端 baseline。

## 复现评分与统计

单个 run 可直接从逐题 `submission.json` 重新评分：

```powershell
& $python scripts\summarize_full_run.py `
  --dataset-root $datasetRoot `
  --run-root runs\codex_cli_one_shot\corpus_search_full `
  --label 'GPT-5.6-sol high one-shot frozen corpus' `
  --output results\gpt56_sol_high_one_shot_corpus_search_full_summary.json `
  --markdown results\gpt56_sol_high_one_shot_corpus_search_full_summary.md
```

任务级成对比较：

```powershell
& $python scripts\compare_full_runs.py `
  --tasks (Join-Path $datasetRoot 'public\tasks_zh.jsonl') `
  --run 'no-search=results\gpt56_sol_high_one_shot_no_search_full_summary.json' `
  --run 'frozen-corpus=results\gpt56_sol_high_one_shot_corpus_search_full_summary.json' `
  --json-out results\one_shot_no_vs_corpus_paired.json `
  --markdown-out results\one_shot_no_vs_corpus_paired.md
```

该统计固定种子、使用 20,000 次 task bootstrap，并对成对布尔结果执行 McNemar 精确双侧检验。
失败和缺失始终保留在预注册分母内。

## 公开可复核快照

公开仓库使用 `public_run_snapshot_v3/` 作为唯一权威运行快照。它按方法和任务保存
`submission.json`、生成的 `model.py`、失败记录和严格恢复 provenance，共覆盖 6 个条件、
520 个 task-condition。原始 prompt、逐事件流、机器路径和临时运行目录不进入公开包。

先校验公开实验包和逐题快照哈希：

```powershell
python scripts\verify_public_bundle.py --root .
python scripts\verify_public_run_snapshot.py --root public_run_snapshot_v3
```

再从公开逐题提交重新评分，例如：

```powershell
python scripts\summarize_full_run.py `
  --dataset-root $datasetRoot `
  --run-root public_run_snapshot_v3\optiminer `
  --label "OptiMiner training-free compatibility" `
  --output optiminer_rescore.json `
  --markdown optiminer_rescore.md
```

该快照用于复核已经完成的运行，不等于原始 telemetry 全量公开。成本与调用统计以
`results/*_attempted_usage.json` 为准；运行身份、预算差异和恢复规则见
`docs/EXPERIMENT_PROTOCOL.md` 与 `docs/RUNNER_PROVENANCE.md`。

## 目录

```text
configs/             输出 schema 与运行配置
docs/                实验协议与 SearchGraph-OR 设计
runs/                原始 prompt、事件、响应、代码、失败与提交
replay_artifacts/    独立 Gurobi 重放产物
results/             审计、评分、成对统计与人工裁决
scripts/             运行、合并、评分、审计和回归工具
```

公开仓库中的实验子目录只包含上述可复核快照和选定的权威结果，不包含本地 `runs/`、
`replay_artifacts/`、早期 smoke/partial 结果或两个已废弃的快照目录。

## 当前解释边界

当前数据能证明“Gold evidence 对决策有因果影响”，也能证明强模型在拿到相关证据时大多能正确
改模；它不能证明“复杂搜索是必要的”。在修复 100/100 Gold 盲审 reject、候选 medoid 泄漏、
固定 patch 模板、公开 Gold 污染风险和 SWOR085 适用性歧义之前，不应把分数写成方法排行榜或
开放世界搜索能力结论。
