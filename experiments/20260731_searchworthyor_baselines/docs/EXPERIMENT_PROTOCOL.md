# SearchWorthyOR baseline 实验协议

状态：2026-07-31 执行版。

本文记录实际执行合同，不把未运行的 4×3 API 设想伪装成实验结果。

## 1. 实验问题

实验回答三个相互独立的问题：

1. 同一 GPT-5.6-sol high 与 Gurobi 条件下，一次性建模、OPTIMUS-inspired、
   Chain-of-Experts-inspired 和 training-free OptiMiner compatibility 的端到端效果与成本如何？
2. 搜索是否提供了改变数学模型所必需的信息，而不是数字填空、文本替换或候选格式捷径？
3. 失败发生在检索、适用性、claim binding、数学补丁、Gurobi 代码还是完整行动集判定的哪一条边？

按用户要求，主实验暂时假定 Gold base 与 patch 可用于评分；数据盲审 reject、适用性歧义、
模板重复与泄漏攻击仍作为独立有效性审计保留，不能因该假设而隐藏。

## 2. 实际执行矩阵

| 方法 | 无搜索 | 冻结语料 | 真实联网 |
|---|---:|---:|---:|
| GPT-5.6-sol high one-shot | 100 | 100 预注册分母 | 20 real-web |
| OPTIMUS-inspired CLI adapter | — | 100 | — |
| CoE-inspired CLI adapter | — | 100 | — |
| OptiMiner training-free compatibility CLI | — | 100 | — |

此外执行不需要 LLM 的负对照：

- 全文 BM25；
- entity + jurisdiction + decision-time metadata BM25；
- task-blind majority/latest 与全文 medoid；
- oracle-base patch-only 固定模板攻击。

没有执行 `oracle-evidence × 四方法`、`distractor-only × 四方法` 或
`counterfactual-swap × 四方法` 的生成矩阵；这些仍是下一版数据集的因果验收设计，不能填入
主结果表。

## 3. 固定运行条件

- 实际 CLI model：`gpt-5.6-sol`；
- 请求参数：`model_reasoning_effort="high"`；
- reasoning 验证：没有独立验证器，因此只记 `requested/reported high`；
- 最终求解器：`gurobipy` / Gurobi 12.0.2；
- 所有最终代码必须通过静态安全检查、实际执行并打印结构化结果；
- public task、冻结语料、输出 schema 和 trusted scorer 对方法一致；
- Gold、Gold evidence ID、patch class、参考行动、参考目标和参考代码不进入生成 prompt；
- 生成器位于 sterile working directory，shell、web、agent spawning 与远程插件禁用；
- scorer 在生成后读取 private Gold，并用可信 IR 后端独立重放；
- 未显式设置或验证 temperature，因此不声称 `temperature=0`；
- 本地 baseline 是非 Git snapshot，run manifest 保存实际源文件路径和 SHA-256。

### 3.1 失败和重试

- 预注册分母不因失败缩小；
- 非空 model event、已落盘 response、代码语法错误、模型语义错误均不重试；
- 只有 `events=0`、`response` 不存在、stderr 为空等纯基础设施失败允许一次恢复；
- 恢复必须复用所有已成功 stage，保留旧 `failure.json` 并写 `resume_resolution.json`；
- prompt adapter stage 允许多个 agent message；
- 仅允许 `todo_list` 生命周期作为无外部副作用的内部 bookkeeping，且最后一个 agent message
  之后只能再出现 `todo_list`；任何 shell、web search、command execution、文件工具或
  subagent item 仍由 event audit 拒绝；
- one-shot event audit 不采用上述多消息/todo compatibility 放宽。

### 3.2 超时与预算

- one-shot 与 OPTIMUS stage/final 的单次 CLI timeout 为 180 秒；
- CoE 专家 stage 因长角色上下文使用 600 秒，最终建模仍为 180 秒；
- OptiMiner controller/final 使用 runner manifest 记录的实际 timeout；
- 方法调用数不强制相同，调用、token、wall time 与搜索次数必须作为结果报告。

因此方法准确率可比较，但不是固定计算预算下的纯算法比较；尤其不能忽略 CoE 的额外 stage
预算后声称其无成本优越。

## 4. 三种证据条件

### 4.1 No-search

只给 public task；禁用网络、浏览器和本地证据语料。测量 base 建模能力与模型先验。此条件没有
搜索 trace，检索指标应记 N/A，而不是过程失败。

### 4.2 Frozen-corpus

通过统一 BM25 接口检索冻结的 400 文档语料。一次性与 prompt adapters 获得同一 precomputed
top-5；OptiMiner compatibility controller 可以提出自然查询并进行至多三轮检索。不得使用任务
ID、DOC ID 或 task→Gold 映射。该条件不访问互联网。

20 条 real-web 任务在此条件使用冻结网页快照，以保证方法间可重复。

### 4.3 Live-web

仅对 20 条 real-web 任务执行。模型使用真实 web search 自主查询权威来源，保存搜索事件、URL、
主张和适用性。Gold URL exact 只测字符串身份；source quality 由权威方、时点、辖区、主体、
例外和支持主张人工裁决。

## 5. Baseline 身份

### 5.1 GPT-5.6-sol high one-shot

每题一个最终模型调用，完成证据选择、适用性、base/patched IR、typed patch、Gurobi 代码和
claim mapping。没有自我修复 loop 或 subagent。纯基础设施零事件失败可恢复一次。

### 5.2 OPTIMUS-inspired prompt adapter

读取本地 `<LOCAL_BASELINES_ROOT>\OptiMUS-main` 的参数、目标与约束提示文件，按三个阶段构造 scratchpad，
再由独立 final call 交付统一 schema。所有 stage 均为 GPT-5.6-sol high。

身份固定为 `optimus_inspired_cli_adapter`；不是原仓库的未修改运行。

### 5.3 Chain-of-Experts-inspired role adapter

读取本地 `<LOCAL_BASELINES_ROOT>\Chain-of-Experts-main` 的 ParameterExtractor、
TerminologyInterpreter、ModelingExpert、ProgrammingExpert 与 CodeReviewer 角色提示，按原
交接形状生成 scratchpad，再由 final call 交付统一 schema。

身份固定为 `coe_inspired_cli_adapter`；不是原仓库的未修改运行。

### 5.4 OptiMiner training-free compatibility

保留 controller 逐轮提出搜索查询、接收 `<result>`、决定继续或停止、再最终建模的 training-free
形状。所有 controller 与 final call 均为同一 GPT-5.6-sol high。

本地原复现 `run_optminer_training_free.py` 明确规定外部文档只能提供建模模式、变量/约束想法和
solver API 提示，不能提供实例业务约束；SearchWorthyOR 则要求外部规则合法改变业务模型。
因此执行版有意修改这一合同，身份固定为 `optiminer_training_free_compat_cli`，并在 manifest
写入 `compatibility_adapter_not_unmodified_reproduction=true`。

## 6. 主指标

### 6.1 可执行性与 base

- `base_model_success`：trusted base IR replay 正确；
- `generated_code_ir_consistent`：生成 Gurobi 代码的行动属于提交 IR 的完整最优行动集合；
- Gurobi status、objective recomputation、constraint residual、integrality 与 bound violation。

### 6.2 检索与适用性

- `EvidenceHit@1/@5`；
- `evidence_selected`：冻结语料为 exact document ID，live-web 为 exact Gold URL；
- 人工 authoritative semantic source equivalence；
- authority、decision time、jurisdiction、subject 与 exception applicability；
- claim 与所选 evidence 的一致性。

### 6.3 模型与决策

- `model_structurally_changed`；
- semantic base/patched IR；
- typed patch 与 claim→model-slot mapping；
- `projected_feasible_set_match`；
- `optimal_action_set_match`；
- `decision_model_equivalent`：完整可行集与完整最优行动集同时等价；
- `decision_e2e`：再要求 exact Gold document identity；
- `semantic_e2e`：语义模型、patch、binding、适用性与决策通过；
- `strict_e2e`：所有 canonical 表示 exact match。

只比较一个 Gurobi incumbent 不构成模型正确。小模型必须枚举完整投影可行集和最优行动集。

### 6.4 成本

- stage/controller/final 模型调用数；
- input、cached input、output 与 reasoning output token；
- 搜索调用数与返回文档数；
- Gurobi 执行数；
- wall time；
- active 与 recovered failure。

## 7. “搜索有用”与“高级 Agent 必要”的分离

以下命题不能混为一个：

1. **证据改变决策**：base 与 patched 完整最优行动集合不相交；
2. **给模型证据有帮助**：no-search 与 evidence condition 的成对决策等价率有差；
3. **模型真正依赖正确证据**：错误文档替换、evidence removal 或 binding permutation 会破坏
   结果；
4. **高级搜索必要**：task-blind、metadata-only、medoid、固定模板等低能力方法不能接近 Agent。

当前 full run 可以直接检验 1、2，并部分检验 3；确定性攻击直接检验 4。没有运行的
distractor/counterfactual LLM 矩阵不能作为已完成证据。

## 8. 非平凡性与泄漏审计

Gold 层报告：

- 变量增删、变量域、约束增删改、辅助变量、条件逻辑、作用域和目标结构；
- patch op 数量与匿名结构签名；
- base/patched 最小行动 Hamming 距离与目标变化；
- 是否只是 append-only 小补丁。

低能力攻击：

- 不看题面的候选文档 majority/latest 与 medoid；
- metadata-only BM25；
- 关键词到固定 patch 模板；
- oracle-base patch-only。

若这些方法接近 Agent，只能说明外部规则文本能改变模型，不能说明 benchmark 测到了开放世界
问题发现、多来源裁决或复杂模型 Graph Rewrite。

## 9. 统计

- 所有比例以预注册任务数为分母，失败/缺失计 false；
- 使用固定 seed `20260731`、20,000 次 task-level bootstrap 报告 95% CI；
- 同题方法差异使用 paired bootstrap；
- 成对布尔结果同时报告 McNemar 精确双侧检验；
- 按 family、patch class、private/web 分层；
- 共享任务模板和证据模板意味着 100 题不是 100 个完全独立生成过程，显著性不替代数据有效性
  审计。

## 10. 完成门

最终交付必须包含：

- one-shot 的 100 no-search、100 frozen-corpus、20 live-web；
- 三个 Agent baseline 的 frozen-corpus 100 题预注册分母；
- 每条成功提交的 Gurobi 代码、CLI events、prompt、response、IR 与 trusted replay；
- active/recovered failure，不静默补样；
- 检索、适用性、模型、代码、完整行动集、成本与成对统计；
- 数据集非平凡性、泄漏、歧义和 Gold adjudication 审计；
- SearchGraph-OR 的 graph state、graph rewrite、验证与停止条件；
- 所有发布文件的 SHA-256 与公开仓库 commit。

任何 baseline 失败题保留为失败；完成实验不等于 100% 正确，而是 100% 任务都有可审计的成功或
失败状态。

## 11. 实际完成记录

- one-shot：no-search 100/100；frozen corpus 99 submission + 1 active failure；live-web 20/20；
- OPTIMUS：100 submission；
- CoE：13 submission + 87 active failure；
- OptiMiner 原始：89 submission + 11 failure；
- OptiMiner 恢复门：SWOR039、SWOR026、SWOR040 各一次成功；SWOR095 因 stderr 非空被拒绝
  恢复；7 个 max-turn 不恢复；
- OptiMiner 最终：92 submission + 8 active failure + 3 recovered failure；
- 四方法固定分母 trusted replay、20,000 次 paired bootstrap 与 McNemar 已完成。

恢复前的任务目录、根 manifest/聚合、空事件和 stderr 均在
`runs/codex_cli_optiminer/corpus_full_recovery_provenance/` 保存；分片根聚合被恢复为原始全量
状态，最终合并明确以 task-level 文件为权威。
