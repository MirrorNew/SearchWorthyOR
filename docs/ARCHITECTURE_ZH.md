# SearchWorthyOR 代码架构与人工审查指南

## 1. 最小运行结构

```text
EXPERIMENT_CONFIG.json
        |
inputs/public_cases.jsonl  --只含 eval_id + prompt_zh
        |
scripts/common.py  --配置、digest、严格 API、输出与 token/time 统计
        |
        +--> Direct / Search-First
        |      scripts/gated_search_pipeline.py
        |
        +--> SearchWorthy
               searchworthy/run_searchworthy.py
                         |
               searchworthy/pipeline.py
                 |       |        |
              state   evidence   patch + or_model
        |
scripts/validate_outputs.py  --身份、digest、终态、token、速度
```

`scripts/run_all.py` 只并发启动三个 Runner 和调用校验器，不改变任何方法语义。网络访问统一进入 `StrictAPIClient` 和 `PublicWebRetriever`。

## 2. 三种方法的差异

| 方法 | 搜索触发时看到什么 | 搜索后怎样使用信息 |
|---|---|---|
| Direct | prompt、Base 模型和 Base solve | 对最终模型做一次证据约束的必要修改并重求解 |
| Search-First | 只有 prompt | 把核验后的 Raw-NL 证据交给一次最终建模/求解 |
| SearchWorthy | Base IR、Base solve、信息审查和 impact probe | 证据先过硬门，形成绑定 canonical IR target 的 Patch，事务提交并重求解 |

Direct 与 Search-First 的 provider、模型、检索预算、页面打开和输出外壳完全共享；差别只在 Gate 的时点与证据进入模型的方式。

## 3. SearchWorthy workflow

`searchworthy.pipeline.run_case()` 是主流程，顺序固定为：

1. `initial_modeling`：从 `prompt_zh` 生成 canonical OR IR、候选信息缺口和初始审查。
2. `solve_initial`：校验 IR 并求解 Base。
3. `initialize_state`：建立持续更新的“信息作用状态空间”。
4. `probe_all_gaps`：实际扰动/封闭一个缺口对应的模型 target，只有 solver 观察到决策相关影响时才允许进入搜索候选。
5. `select_next_gap + authorize_search`：一次只激活一个 gap，全 case 最多 3 次 hosted search。
6. `assess_evidence`：重新计算 `SUPPORTED ∧ APPLIES ∧ BINDABLE ∧ CONSISTENT`。
7. `route_evidence`：只能 Search Again、Retain、Patch 或 Abstain。
8. `apply_patch_and_solve`：Patch 必须绑定当前 canonical IR，事务化应用；任一操作失败则整包回滚。
9. `record_solve_delta + probe_all_gaps`：记录决策是否改变，并对剩余 gap 基于新 IR 重新 probe。
10. 所有信息作用闭合后输出 NO_SEARCH / RETAIN / PATCH_CHANGES；无法闭合则 ABSTAIN。

## 4. OR-specific 信息作用状态空间

它不是聊天历史的短期记忆，而是围绕“外部信息能否改变优化决策”维护的结构化状态：

- 双向覆盖：`Prompt Fact → Model Use` 与 `Model Interface → Grounding`。
- 九类 negative space：主体资格、地域/法域、时间版本、对象范围、单位阈值、容量可行性、例外豁免、行动后果、成本收益。
- 每个 gap 绑定明确的 IR target、潜在作用、probe 结果、搜索预算、证据卡、Patch 状态和 solve delta。
- `select_next_gap` 保证一次只处理一个 active gap；`apply_state_update` 校验所有状态转移。

这里的闭合条件是“影响路径已被证明无关、已由题内信息覆盖、已被证据保留/修补，或明确 ABSTAIN”，不是“模型已经读过一段资料”。

## 5. 证据准入与 Patch

程序会重新核验以下门：

- `SUPPORTED`：quote 必须逐字出现在实际打开的 http(s) 页面正文中。
- `APPLIES`：source scope quote 与题内 case quote 都必须可定位。
- `BINDABLE`：证据必须绑定当前 gap 的合法 canonical IR target，且结构化值能从 quote 支撑。
- `CONSISTENT`：同一 target 的结构化 binding 冲突会被程序拒绝；一般语义一致性仍是当前方法的限制。

只有四门同时通过且 Evidence→Patch target/value 完全匹配，才允许 `ADMIT_PATCH`。`NOT_APPLIES` 在缺少结构化 scope-atom 比较器时不会被用来关闭 gap。

## 6. 建议人工检查顺序

1. `EXPERIMENT_CONFIG.json`：确认模型/provider、三方法、8 Smoke、1080 Formal 和搜索预算。
2. `scripts/common.py`：确认只读取二字段输入、private path 为零、digest/gate 和 token/time 统计。
3. `scripts/gated_search_pipeline.py`：比较 Direct 与 Search-First 的唯一允许差异。
4. `searchworthy/contracts.py`、`state.py`：检查状态字段、九维审查和合法转移。
5. `searchworthy/evidence.py`、`patch.py`、`or_model.py`：检查准入硬门、IR target 绑定、事务回滚与求解。
6. `searchworthy/pipeline.py`：沿 `run_case()` 从上到下看一条完整轨迹。
7. `scripts/web_retrieval.py`：检查 SSRF/redirect、authority/relevance、page byte limit 和 quote verification。
8. `scripts/run_all.py`、`validate_outputs.py`：确认 Harness 只负责启动、收集和校验。
9. `tests/`：先看 `test_impact_probe.py`、`test_evidence_gate.py`、`test_patch.py`、`test_searchworthy_smoke.py`，它们分别对应两个核心科学问题和完整闭环。

发布前可用以下零引用检查确认排除项没有回到公开 runtime：

```powershell
rg -n -i "CoE|OptiMUS|optiminer|private_gold|ReplayStrictAPIClient|FORMAL_RECOVERY_ROOT|recovery_plan" scripts searchworthy tests EXPERIMENT_CONFIG.json
```

预期只有文档中的排除说明；运行代码与测试应为 0。
