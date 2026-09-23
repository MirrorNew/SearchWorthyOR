# SearchWorthyOR-v1.6.2 候选数据集

本版保留120个source与360个case，C1搜后保留、C2搜后修改、C3无需搜索；尚未冻结，当前状态以validation_report.json为准。

2026-09-08经用户授权仅修复R047/R050/R083/R116：补明被冻结主体、Medicare付款与有限服务日期、已获批准的第二事件安排，以及本地平台技术依赖。R116 Base由285改为267，Full仍为265；其余三题数值不变。四题公开骨架、事实、规则、模型和评分字段同步更新，未把Gold加入模型输入。

可复现脚本：../../scripts/repair_searchworthyor_v162.py。逐字段修订与算术检查：../../experiments/20260829_searchworthyor_v161_searchworthy/reports/v162_preparation_20260908/fixed_repairs.json。

以下继承V1.6.1格式说明；四题展示已同步本版。旧审查表、修订记录、快照和完整性清单均保留历史身份，不代表V1.6.2通过或冻结；“Base必须等于V1.5.1”等旧版本限制不适用于本次明确修复。

---

# SearchWorthyOR-v1.6.1 数据集说明

## 1. 版本定位

SearchWorthyOR-v1.6.1 以已经通过全量验证的 V1.5.1 为只读来源，把每个 source task 扩展为 C1/C2/C3 三元组，用于分离“是否需要搜索”“规则是否适用”“模型是否从初始状态发生修改”和“最终优化答案是否正确”。本版本只重建数据集与验证资产，不包含正式 Agent 实验。

三个 scorer-only 状态为：

- `RETAIN`：题面未提供完整规则，需要搜索；规则对当前事实不适用；初始与最终均为 Base；Patch 为空；决策不变。
- `PATCH_CHANGES`：题面未提供完整规则，需要搜索；规则适用；Base 经非空 typed Patch 变为 Full；决策改变。
- `NO_SEARCH`：题面已提供足以直接建模的浓缩规则；初始与最终均为 Full；Patch 为空；决策不变。

`patch=[]` 不能单独区分 `RETAIN` 与 `NO_SEARCH`。scorer 必须联合状态、搜索、适用性、初始/最终模型、行动与目标判断。

## 2. 数据规模

| 项目 | 数量 |
|---|---:|
| source task | 120 |
| C1 / RETAIN | 120 |
| C2 / PATCH_CHANGES | 120 |
| C3 / NO_SEARCH | 120 |
| 公开 case | 360 |
| Base IR | 120 |
| Full IR | 120 |

每个 C3 的 `case_facts_zh` 由构建器直接复制同题 C2 文本，优化骨架与 `output_schema` 也相同；C3 唯一新增的业务输入是 `rule_information_zh`。构建器从只读 V1.5.1 `private/v151_case_repair_records.jsonl` 读取同题 C2 的 ISO `decision_date`，并统一把规则材料规范化为“在YYYY年M月D日的决策时点，下述规则处于有效期：”加核心规则文本；月份和日期以十进制数字输出，不补前导零。

## 3. 公开输入合同

正式模型调用只接收 `eval_id` 与 `prompt_zh`。数据集根目录的 README、规范、修订记录以及整个 `private/` 都不是 evaluation-public 模型输入；评测器不得把这些文件追加到上下文。盲化 `eval_id` 不包含 source task、C1/C2/C3 或状态；真实映射只在 private 中。`public/tasks_zh.jsonl` 必须按 `id` 严格排序，`public/cases_zh.jsonl` 必须按随机 `eval_id` 严格排序，验证器会拒绝乱序文件。

360 个 `eval_id` 不是由 `case_id` 哈希推导。构建器首次运行时用密码学随机源生成互不重复的 20 位十六进制 opaque token，并把唯一稳定映射持久化在构建侧 `scripts/.private/v161_opaque_eval_ids.json`；后续构建只能复用并严格验证该文件。旧版无盐 BLAKE2 可枚举 ID 被显式拒绝。这个持久映射不是数据集公开资产，也不得进入模型上下文、prompt、日志或公开目录；数据集 scorer 通过 `private/eval_identity_map.jsonl` 使用对应关系。

公开 prompt 的顺序固定为：

1. `【本 case 权威事实】`：一个完整自然语言事实段落；
2. 仅 C3 出现的 `【随题规则材料】`：一个浓缩自然语言规则段落；
3. `【优化骨架】`；
4. 公开 `output_schema`。

单题中不再重复“基础优化语义合同”“解释优先级”或“信息边界”。题内优化骨架定义候选行动、成本、收益、预算、互斥和本地能力；题外规则材料只定义适用边界与义务，不能发明题内行动或成本。

## 4. 规则材料与证据准入

每条 C3 规则材料按逐题修订记录绑定 private 官方证据节点，并显式检查生效时点、地理范围、主体、对象范围、阈值及等号边界、义务与正式例外；不适用的覆盖轴明确记录为 `NOT_APPLICABLE`。Multi 题必须覆盖所有独立 Patch 分支。

统一决策时点前缀只声明下述规则在该评估时点处于有效期，不声明本 case 已满足规则的主体、对象、地域、阈值或例外条件，也不把法规履约截止日、报告期边界或历史特许日期误写成生效日。逐题生成分片保存核心规则文本，构建器在内存中统一添加前缀，并将同一规范化字节串写入公开 C3、private provenance、`v161_revision_records.jsonl`、README 与 `V161_REVISION_RECORDS_zh.md`。验证器独立读取随数据集保留的 V1.5.1 修复记录，按 source task 的 C2 日期重算并核对精确前缀。

公开规则材料不含 URL、官方原文、证据节点、状态标签、搜索结论、typed Patch、私有变量、正确行动或目标值。C1 专属排除证据不会混入 C3 provenance。

所有 `official_evidence_additions` 与构建侧 `v161_new_evidence_verification.json` 动态一一对应，不硬编码题号或数量；本源码快照共有6个新增节点。每条必须为 `PASS`，task/node/URL/quote 精确一致，且verification文件按字节复制到target private。公开facts/rule还要递归扫描全部嵌套键值：拒绝private/Gold/state/search/model/evidence/provenance键族、case/triplet/role/state标识、URL、模型路径和节点ID；私有变量、constraint及Patch token只有在V1.5.1原公开优化骨架或schema中已经出现时才允许，不能通过新事实“洗白”。长度不少于40字符的官方原文不得整段进入公开facts/rule。

## 5. 模型与 Gold 时点

“初始模型”是模型读完该 case 的全部可见输入后的模型：

- C1：`base_ir → base_ir`；
- C2：`base_ir → full_ir`；
- C3：`full_ir → full_ir`。

每个 task 只有 `base_ir.json`、`full_ir.json` 和 `solve_result.json` 三个模型资产；V1.6.1 不保留 `patched_ir.json`。120题的Base必须精确等于V1.5.1 `base_ir.json`，Full必须精确等于V1.5.1 `patched_ir.json`仅把`variant`改为`full`，不授权语义等价重写。验证器还独立重放 `apply(base_ir, base_to_full_patch)`，完整枚举 Base/Full 的全部最优行动集合，并核对solve_result的精确字段、状态、可行计数、incumbent、完整最优集、公共最优集、布尔值与目标合同。

private case Gold中的布尔字段必须是真正JSON boolean，`gold_patch_elements`必须是list且C1/C3严格为`[]`、C2严格等于task Patch。`official_support`按source node有序精确投影；`search_necessity`按角色精确核对字段、identity、search object、页面和引文顺序。target task asset必须等于V1.5.1 asset加逐题授权的新证据，且仅R112允许声明的reason替换。

## 6. 目录结构

```text
SearchWorthyOR-v1.6.1/
├─ README.md
├─ MODEL_IO_CONTRACT_zh.md
├─ V161_CASE_REVISION_SPEC_zh.md
├─ V161_REVISION_RECORDS_zh.md
├─ validation_report.json
├─ inherited/
│  ├─ V151_CASE_REPAIR_SPEC_zh.md
│  ├─ V151_REPAIR_RECORDS_zh.md
│  └─ v151_validation_report.json
├─ public/
│  ├─ tasks_zh.jsonl
│  └─ cases_zh.jsonl
├─ private/
│  ├─ build_integrity_manifest.json
│  ├─ case_gold.jsonl
│  ├─ decision_state_spec.json
│  ├─ eval_identity_map.jsonl
│  ├─ evidence_node_omissions.jsonl
│  ├─ gold.jsonl
│  ├─ multi_hardening_manifest.jsonl
│  ├─ public_first_review_records.jsonl
│  ├─ public_review_snapshot_manifest.jsonl
│  ├─ rule_information_provenance.jsonl
│  ├─ search_necessity.jsonl
│  ├─ task_assets.jsonl
│  ├─ v151_case_repair_records.jsonl
│  ├─ v161_new_evidence_verification.json
│  ├─ v161_private_metadata_overrides.json
│  └─ v161_revision_records.jsonl
└─ models/SWOR-Rxxx/
   ├─ base_ir.json
   ├─ full_ir.json
   └─ solve_result.json
```

正式闭包恰为386个文件和124个子目录（不计数据集根目录）：root 5、public 2、private 16、models 360、inherited 3。只读V1.5.1源固定为375个文件、7,062,812字节、123个子目录，按“UTF-8路径长度+路径+文件大小+文件内容BLAKE2b-256”的排序树算法得到 `34c96a3e70665fbe297e5270c037f6ce3dad922591169cc0f7bf2ed5bc27b25f`；文件路径摘要与123目录计数共同排除额外空目录。构建前后都必须精确命中，并写入 `private/build_integrity_manifest.json`。

Windows inventory固定使用 `os.scandir` 枚举、`os.lstat` 获取真实identity且不跟随链接；source/target/datasets root必须保持固定名称、解析后不相交，并拒绝symlink、junction、reparse、special file、source↔target hardlink及target内部hardlink。脚本侧revision/review/template/override/evidence和持久opaque map同样必须是plain、非reparse、单链接regular file。

构建器对既有target的第一个实质写入是创建 `BUILD_IN_PROGRESS` 并把validation report置为同名状态；首次创建target根到marker之间不存在旧PASS。所有文件写完、源后指纹和带marker闭包通过后，才写 `NOT_RUN_AFTER_BUILD` 并删除这一个明确marker。失败会保留或恢复marker，禁止把旧PASS当成本轮结果。验证器对unsafe/incomplete/marker target零写；安全闭包通过后，在解析任何target JSON前原子写 `VALIDATION_IN_PROGRESS`，任何异常统一落为结构化FAIL。

## 7. 继承修复与审查边界

V1.5.1 的全部逐题修复记录和私有机器记录原样保留，V1.6.1 的新自然语言事实、规则材料、证据准入、Patch 覆盖和枚举结果也逐题写入 README、生成分片以及 `V161_REVISION_RECORDS_zh.md`。

证据 omission 文件只声明结构绑定；`empirical_omission_test_status=NOT_RUN` 的记录不应被解释为已完成删节点实验。

每题使用两个 BLAKE2b-256 快照。`public_snapshot_id` 的 canonical JSON 由完整公开 task 骨架和三条完整公开 case 组成；case 中的 opaque `eval_id`、事实、规则、problem、schema 与 prompt 全部进入摘要。`private_crosscheck_snapshot_id` 绑定同题最终 revision/provenance（含纳入/排除节点、coverage、Patch 名和官方证据）、修改后 task asset、task Gold、Base/Full/solve、三条 case Gold/search contract、相关新证据 verification 以及该题 metadata override（无则为 null）。二者共同写入 `private/public_review_snapshot_manifest.jsonl`。正式审查文件使用 `searchworthyor.v161.public_first_review.v3`，每条记录必须带两个 digest；验证器分别从 target public+identity 和 target private+models 独立重算。任何公开输入、模型、Gold、provenance、官方证据或 verification 改变都会使旧审查失效。构建侧三个revision shard是允许修改case层的外部授权源，三个v3 review shard是target之外的审查信任锚；验证器以plain-file方式独立读取六个分片，要求target revision（规则添加统一时点前缀后）和target review逐题精确投影，不能靠同时重算target内无密钥摘要自签PASS。

最终固定审查分工为：A 分片 `Codex final blind reviewer A`、B 分片 `Codex final blind reviewer B`、C 分片 `Codex final blind reviewer C`；三者均必须声明 `reviewer_generated_shard="NONE"`，且不得参与 revision 分片生成或 builder/validator 修改。正式构建不带 `--allow-pending-blind-review`，要求120题均为 v3、`review_outcome=PASS`、五项 status 全为 `PASS`、`issues=[]`、reviewer 与 review_notes 非空、reviewer声明符合固定分工，并精确绑定当前public/private两个快照。机器只能验证这些固定身份声明和快照绑定，不能对实际操作者做密码学身份认证；Codex审查也不等同于人类法律复核，本版本的`human_legal_review`明确为`NOT_RUN`。

本源码快照的三个审查分片仍为v1，因此只能做草案迁移，正式验证预期在review authority/snapshot/PASS门失败。从现有v1审查迁移时，先在仓库根目录运行草案构建：

```powershell
python "20260710_Align Opt-Miner Agent Workflow/scripts/build_searchworthyor_v161.py" --allow-pending-blind-review --update-existing
```

该步骤会在需要时首次创建构建侧 opaque-ID 私有映射，并生成含当前双快照 manifest 的 target 草案；现有 v1 或缺失记录的两个 digest 都标为 `UNBOUND`，v2 保留原 public digest 并把 private digest 标为 `UNBOUND`，已有 v3 的两个旧 digest 原样保留。构建器绝不把任何当前 digest 冒充为已经审过。随后三位未参与生成/代码修改的全新 reviewer 严格执行 public-first、再做 private cross-check，并把各自源审查分片更新为 v3 和实际核过的当前两个 digest。最后去掉 `--allow-pending-blind-review` 重跑正式构建；正式门通过前不得发布数据集。

## 8. 私有元数据定点修复

`private/v161_private_metadata_overrides.json` 是构建输入的原样副本。构建器只允许其中声明的 R112 `applicability_decision.reason` 路径发生变化；old value 必须与只读 V1.5.1 精确匹配，E1/E2 必须存在。该 override 不得改动公开事实、规则、Gold 或模型。

### SWOR-R112

- 限定路径：`private/task_assets.jsonl -> applicability_decision.reason`。
- old_value：The 45-degree auxiliary temperature ceiling activates beginning 36 hours after lay.
- new_value：Because the retail establishment receives shell eggs that were not specifically processed to destroy all viable Salmonella, the exception in 21 CFR 115.50(c) does not apply. Each candidate package places the eggs under refrigeration immediately upon retail receipt, and 21 CFR 115.50(b) requires prompt refrigeration upon receipt and retail holding at an ambient temperature no greater than 45°F. Accordingly, the 24-hour/50°F and 40-hour/50°F packages are excluded, while the 40-hour/45°F and 60-hour/42°F packages remain feasible.
- 证据 source ID：`E1, E2`。
- 修复原因：V1.5.1的applicability_decision.reason仍残留已从修复记录和Gold Patch中删除的产蛋后36小时门槛，与21 CFR 115.50的零售收货分支、公开C3规则及纳入证据不一致。
- 复核说明：E1要求除正式例外外的零售分销带壳蛋在零售场所收货时及时冷藏，并在持有期间保持环境温度不高于45°F；E2仅豁免已经专门处理以灭活全部viable Salmonella的鸡蛋。本题C2没有灭活记录，故两个50°F包分别由exclude_24h_50f和exclude_40h_50f排除，45°F与42°F包保留；本override只修正私有元数据理由，不改事实、证据、Gold Patch或模型。

## 9. 全量修订索引

| 任务 | 结论 | C2完整性 | 证据纳入/排除 | Patch槽 | 风险标记 |
|---|---|---|---:|---:|---|
| SWOR-R001 | READY | PASS | 11/2 | 1 | PRIMARY_EVIDENCE_ADDED_FOR_C3_CLOSURE |
| SWOR-R002 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R003 | READY | PASS | 1/0 | 2 | LONG_COMPOSITE_SOURCE_QUOTE |
| SWOR-R004 | READY | PASS | 1/0 | 2 | 无 |
| SWOR-R005 | READY | PASS | 2/1 | 2 | 无 |
| SWOR-R006 | READY | PASS | 1/0 | 4 | 无 |
| SWOR-R007 | READY | PASS | 1/0 | 3 | 无 |
| SWOR-R008 | READY | PASS | 1/0 | 1 | V151_GOLD_BOUNDARY_REPAIRED |
| SWOR-R009 | READY | PASS | 1/0 | 3 | 无 |
| SWOR-R010 | READY | PASS | 3/0 | 2 | 无 |
| SWOR-R011 | READY | PASS | 1/0 | 5 | 无 |
| SWOR-R012 | READY | PASS | 3/0 | 3 | 无 |
| SWOR-R013 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R014 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R015 | READY | PASS | 1/0 | 2 | 无 |
| SWOR-R016 | READY | PASS | 2/0 | 1 | POST_JUDICIAL_REVIEW_STATUS |
| SWOR-R017 | READY | PASS | 4/0 | 64 | LARGE_ENUMERATED_PATCH_SET, CROSS_MIDNIGHT_WINDOW_ENCODING |
| SWOR-R018 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R019 | READY | PASS | 8/0 | 4 | MULTI_NODE_VALID_REQUEST_CLOSURE |
| SWOR-R020 | READY | PASS | 5/0 | 2 | V151_GOLD_REPAIR_RECHECKED, V161_64_2005_NO_APPROVAL_EXCEPTIONS |
| SWOR-R021 | READY | PASS | 3/0 | 1 | 无 |
| SWOR-R022 | READY | PASS | 4/0 | 2 | 无 |
| SWOR-R023 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R024 | READY | PASS | 2/0 | 3 | V151_GOLD_REPAIR_RECHECKED |
| SWOR-R025 | READY | PASS | 2/0 | 3 | V151_GOLD_REPAIR_RECHECKED |
| SWOR-R026 | READY | PASS | 3/0 | 6 | 无 |
| SWOR-R027 | READY | PASS | 4/0 | 3 | 无 |
| SWOR-R028 | READY | PASS | 3/0 | 2 | 无 |
| SWOR-R029 | READY | PASS | 3/0 | 6 | 无 |
| SWOR-R030 | READY | PASS | 10/0 | 3 | TEN_NODE_ELIGIBILITY_CHAIN, QUALIFICATION_DATES_EXPLICIT |
| SWOR-R031 | READY | PASS | 7/0 | 1 | E8_TECHNICAL_CROSS_REFERENCE_NOT_NEEDED_FOR_PATCH |
| SWOR-R032 | READY | PASS | 5/0 | 13 | V151_GOLD_REPAIR_RECHECKED, THIRTEEN_INTERACTION_PATCHES |
| SWOR-R033 | READY | PASS | 5/0 | 4 | 无 |
| SWOR-R034 | READY | PASS | 2/0 | 6 | 无 |
| SWOR-R035 | READY | PASS | 3/0 | 3 | 无 |
| SWOR-R036 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R037 | READY | PASS | 4/0 | 3 | 无 |
| SWOR-R038 | READY | PASS | 4/0 | 2 | 无 |
| SWOR-R039 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R040 | READY | PASS | 5/0 | 4 | 无 |
| SWOR-R041 | READY | PASS | 5/0 | 3 | DUPLICATE_QUOTE_DISTINCT_NODES, MULTI_BRANCH_EXCEPTION |
| SWOR-R042 | READY | PASS | 4/0 | 4 | TEMPORARY_APPROVAL_DATE_BRANCHES |
| SWOR-R043 | READY | PASS | 6/0 | 5 | MULTI_BRANCH_CHEMICAL_USE |
| SWOR-R044 | READY | PASS | 1/0 | 4 | 无 |
| SWOR-R045 | READY | PASS | 3/0 | 2 | MULTI_HOP, TEMPORAL_INSTALLATION_BRANCHES, FACT_LABEL_REMOVED |
| SWOR-R046 | READY | PASS | 10/0 | 3 | MULTI_HOP, TEN_EVIDENCE_NODES, PROCESSING_EXCEPTION_CHAIN, FACT_LABEL_REMOVED |
| SWOR-R047 | READY | PASS | 2/0 | 5 | MULTI_HOP, INDIRECT_OWNERSHIP_AGGREGATION |
| SWOR-R048 | READY | PASS | 3/0 | 3 | MULTI_HOP, MULTIPLE_PERCENTAGE_CAPS |
| SWOR-R049 | READY | PASS | 5/0 | 3 | SOFTWARE_AS_MAJOR_REPAIR |
| SWOR-R050 | READY | PASS | 1/0 | 1 | FACT_LABEL_REMOVED, DATE_BOUNDARY |
| SWOR-R051 | READY | PASS | 6/0 | 2 | DUPLICATE_QUOTE_DISTINCT_NODES, EXACT_CHEMICAL_IDENTITY |
| SWOR-R052 | READY | PASS | 1/0 | 2 | EXACT_LOT_MATCH |
| SWOR-R053 | READY | PASS | 3/0 | 3 | DATE_BOUNDARY, TRANSACTION_TYPE_BRANCHES |
| SWOR-R054 | READY | PASS | 4/0 | 3 | DATE_AND_SCHEME_CROSS_PRODUCT |
| SWOR-R055 | READY | PASS | 3/0 | 3 | MULTI_HOP, RECURRING_DISTANCE_OR_TIME |
| SWOR-R056 | READY | PASS | 2/0 | 2 | IMPLICIT_YEAR_RESOLVED_BY_PUBLICATION_DATE, TWO_CLOSURE_WINDOWS |
| SWOR-R057 | READY | PASS | 4/0 | 11 | LARGE_PATCH, SLEEP_TIME_BRANCHES, EMPLOYMENT_STATUS_CHANGE |
| SWOR-R058 | READY | PASS | 6/0 | 9 | MULTI_HOP, LARGE_PATCH, EXISTING_VS_NEW_OPERATION, TOURIST_EXCEPTION |
| SWOR-R059 | READY | PASS | 2/0 | 3 | CLOSED_EQUIPMENT_CATEGORY_LIST |
| SWOR-R060 | READY | PASS | 2/0 | 2 | MULTI_HOP, MULTIPLE_OPTIMA_BOUNDARY, DISTINCT_SERVICE_QUOTAS |
| SWOR-R061 | READY | PASS | 1/0 | 2 | MODEL_AND_VISIBLE_SCREW_CONJUNCTION |
| SWOR-R062 | READY | PASS | 1/0 | 4 | ROOM_ASSIGNMENT_EXPANSION, EXPRESS_MODEL_EXCLUSION |
| SWOR-R063 | READY | PASS | 7/0 | 6 | MULTI_HOP, SEVEN_EVIDENCE_NODES, THREE_REPORTING_BRANCHES |
| SWOR-R064 | READY | PASS | 4/0 | 1 | SPECIES_COMPLEX_AND_DATE |
| SWOR-R065 | READY | PASS | 2/0 | 3 | MULTI_HOP, STATE_BY_STATE_PRIMACY |
| SWOR-R066 | READY | PASS | 1/0 | 2 | STRICT_BEFORE_DATE_BOUNDARY |
| SWOR-R067 | READY | PASS | 3/0 | 101 | MULTI_HOP, MASSIVE_101_PATCH_ENUMERATION, QUARTER_END_30_DAY_WINDOW, PENSION_EXCEPTION |
| SWOR-R068 | READY | PASS | 3/0 | 2 | TAX_EXEMPT_DAILY_ONLY_EXCEPTION |
| SWOR-R069 | READY | PASS | 4/0 | 2 | MULTI_HOP, WORKING_DAY_BOUNDARIES, FURTHER_DECISION_CHAIN |
| SWOR-R070 | READY | PASS | 2/0 | 3 | FACT_LABEL_REMOVED, TWO_DISTINCT_STAFFING_TRIGGERS |
| SWOR-R071 | READY | PASS | 1/0 | 2 | MODEL_DATE_CONJUNCTION, REMEDY_TYPE_DIFFERS_BY_MODEL |
| SWOR-R072 | READY | PASS | 2/0 | 6 | CONTRACT_AND_IMPORT_DATE_CONJUNCTION, STRICT_BEFORE_BOUNDARY, SIX_ASSIGNMENT_EDGES |
| SWOR-R073 | READY | PASS | 3/2 | 4 | MULTI_HOP, STANDARDIZED_FOOD_EXCEPTION, MULTIPLE_IMPURITY_CEILINGS, C1_ONLY_EVIDENCE_EXCLUDED |
| SWOR-R074 | READY | PASS | 1/0 | 2 | EXISTING_LOG_CONDITION |
| SWOR-R075 | READY | PASS | 1/0 | 2 | CURRENT_OPERATIONAL_STATUS, WIDTH_EQUALITY_BOUNDARY |
| SWOR-R076 | READY | PASS | 7/0 | 2 | MULTI_HOP, SEVEN_EVIDENCE_NODES, LOW_PRODUCTION_EXCEPTION_CHAIN, AIR_MODE_SPLIT |
| SWOR-R077 | READY | PASS | 7/0 | 4 | MULTI_HOP, SEVEN_EVIDENCE_NODES, MULTIPLE_OPTIMA_BOUNDARY, DAILY_AND_PERIOD_OVERTIME, EXECUTIVE_EXCEPTION |
| SWOR-R078 | READY | PASS | 2/0 | 1 | DUTY_AND_REST_EQUALITY_BOUNDARIES |
| SWOR-R079 | READY | PASS | 1/0 | 3 | PROVIDER_PARTICIPATION_VS_ID_REGISTRATION |
| SWOR-R080 | READY | PASS | 1/0 | 3 | FY2026_CATEGORY_RECLASSIFICATION, IC_VS_BMIC_BOUNDARY |
| SWOR-R081 | READY | PASS | 1/0 | 2 | 无 |
| SWOR-R082 | READY | PASS | 1/0 | 1 | 无 |
| SWOR-R083 | READY | PASS | 7/0 | 21 | 无 |
| SWOR-R084 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R085 | READY | PASS | 4/0 | 8 | 无 |
| SWOR-R086 | READY | PASS | 5/0 | 3 | 无 |
| SWOR-R087 | READY | PASS | 6/0 | 4 | 无 |
| SWOR-R088 | READY | PASS | 1/0 | 6 | 无 |
| SWOR-R089 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R090 | READY | PASS | 2/0 | 3 | E2_QUOTE_IS_TRUNCATED_AFTER_PRESTART_AND_EARLY_FOLLOWUP_TEXT |
| SWOR-R091 | READY | PASS | 3/0 | 12 | 无 |
| SWOR-R092 | READY | PASS | 7/0 | 1 | 无 |
| SWOR-R093 | READY | PASS | 3/0 | 2 | 无 |
| SWOR-R094 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R095 | READY | PASS | 3/0 | 3 | 无 |
| SWOR-R096 | READY | PASS | 3/0 | 4 | 无 |
| SWOR-R097 | READY | PASS | 1/0 | 2 | 无 |
| SWOR-R098 | READY | PASS | 4/0 | 5 | 无 |
| SWOR-R099 | READY | PASS | 5/0 | 7 | 无 |
| SWOR-R100 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R101 | READY | PASS | 3/0 | 3 | 无 |
| SWOR-R102 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R103 | READY | PASS | 2/0 | 1 | 无 |
| SWOR-R104 | READY | PASS | 2/0 | 1 | 无 |
| SWOR-R105 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R106 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R107 | READY | PASS | 1/0 | 2 | 无 |
| SWOR-R108 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R109 | READY | PASS | 4/0 | 1 | 无 |
| SWOR-R110 | READY | PASS | 2/0 | 6 | 无 |
| SWOR-R111 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R112 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R113 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R114 | READY | PASS | 3/0 | 1 | 无 |
| SWOR-R115 | READY | PASS | 2/0 | 2 | 无 |
| SWOR-R116 | READY | PASS | 3/0 | 4 | 无 |
| SWOR-R117 | READY | PASS | 2/0 | 3 | 无 |
| SWOR-R118 | READY | PASS | 2/0 | 1 | 无 |
| SWOR-R119 | READY | PASS | 4/0 | 3 | 无 |
| SWOR-R120 | READY | PASS | 2/0 | 3 | 无 |

## 10. 全量逐题修订明细

### SWOR-R001

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年1月2日，鹿特丹岚桥贸易公司在荷兰登记。该公司计划于2026年以自己的名义申报六批候选货物，货物均经鹿特丹港向荷兰海关办理进口申报并进入欧盟关境。批次A为CN 3105 60 00磷钾肥料，B为CN 7202 30 00硅锰铁，C为CN 7202 50 00硅铬铁，D为CN 7202 70 00钼铁，E为CN 7202 80 00钨铁及硅钨铁，F为CN 7204 10 00铸铁废碎料；本次候选范围仅限上述六批。
- C2/C3事实：2026年1月2日，鹿特丹岚桥贸易公司在荷兰登记。该公司计划于2026年以自己的名义申报六批候选货物，货物均经鹿特丹港向荷兰海关办理进口申报并进入欧盟关境。批次A为CN 2523 10 00水泥熟料，B为CN 2523 21 00白色硅酸盐水泥，C为CN 2523 29 00其他硅酸盐水泥，D为CN 2523 30 00矾土水泥，E为CN 2523 90 00其他水硬性水泥，F为CN 2814 20 00氨水；本次候选范围仅限上述六批。
- C3规则材料：在2026年1月2日的决策时点，下述规则处于有效期：自2026年1月1日起，进入欧盟关境的有关进口货物按同一进口人、同一日历年累计净重。商品清单列有CN 2523 10 00、2523 21 00、2523 29 00、2523 30 00和2523 90 00，并包含CN品目2814的氨及氨水。年度累计净重不超过50吨时免于有关义务；一旦严格超过50吨，当年全部相关进口均须由获授权申报人办理，并完成年度排放申报及相应凭证的购买和交回。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7, V161-R001-E10, V161-R001-E11, V161-R001-E12, V161-R001-E13`。
- 排除的C1专属证据：`E8, E9`。
- 规则覆盖：`{"effective_date":["V161-R001-E10"],"formal_exceptions":["V161-R001-E11"],"geographic_scope":["E1","V161-R001-E10"],"object_scope":["E2","E3","E4","E5","E6","E7"],"obligations":["V161-R001-E11","V161-R001-E13"],"regulated_subject":["E1","V161-R001-E11","V161-R001-E13"],"threshold_and_equality":["E1","V161-R001-E11","V161-R001-E12"]}`。
- Patch：`annual_mass_branch`。
- 风险：`PRIMARY_EVIDENCE_ADDED_FOR_C3_CLOSURE`。
- 复核说明：按附件R001三元组校准；C2模型为Base 69到Full 65，C3直接使用C2事实和Full模型；E8/E9仅服务C1排除判断，不进入C3规则材料。E11以Official Journal PDF中Article 2a(1)-(2)连续规范正文闭合年度累计、豁免和超阈值义务，E12以同一OJ PDF的Annex VII point 1闭合50吨净重数值。E13以2025年10月20日EUR-Lex合并文本的Article 25(1)、6(1)和22(1)三个明确分隔摘录，逐条闭合获授权申报人进口、年度申报和凭证交回义务；公开rule文本未改。

### SWOR-R002

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，五大湖一级铁路公司安排一趟依次经过海湾县、松林县和河口市的列车。电子货物清单仅列普通机械零件、纸制品和食品，均使用普通商业运单；运行事件日志为零，三地消防、急救和警务调度均没有该列车的事故派遣记录。
- C2/C3事实：2026年8月2日，五大湖一级铁路公司安排一趟依次经过海湾县、松林县和河口市的列车。电子编组清单载有多票标注UN编号、危险类别和包装等级的材料；三地消防、急救和警务调度均由当地政府授权，并保持该线路事故响应和调查值班。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：铁路运输危险材料时，须以电子形式生成并实时更新列车编组信息，在列车外保存该信息，并在事故或公共安全事件发生前向沿线可能参与响应或调查的获授权联邦、州和地方急救、应急及执法人员提供。事故或疑似泄漏发生后，还须立即通过电话通知事发地主要公共安全应答点，并以电子方式提供列车编组信息。针对一级铁路的临时执法宽限已于2026年6月24日届满。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2"],"formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`fire_authorized, medical_authorized, police_authorized`。
- 风险：`无`。
- 复核说明：C2三个地方调度单位均属于题内给定的获授权沿线响应或调查单位；三项Patch与E1义务一一闭合。

### SWOR-R003

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年2月2日，波士顿澄泉设计公司为五名未满65岁且不作为他人税务被抚养人的员工安排年度福利。A持有与交易所内版本相同的交易所外个人铜级计划；B的SHOP合同写明个人年度免赔额2000美元、最高自付额8000美元；C和D的个人医保报销安排均只报销保费；E参加美洲印第安人铜级费用分担减免变体，并在此前三个月接受过IHS服务。
- C2/C3事实：2026年2月2日，波士顿澄泉设计公司为五名未满65岁且不作为他人税务被抚养人的员工安排年度福利。A持有与交易所内版本相同的交易所外个人铜级计划；B的SHOP合同写明个人年度免赔额1500美元、最高自付额9000美元；C的个人医保报销安排只报销保费，D的安排同时报销保费和就医共付额；E参加美洲印第安人铜级费用分担减免变体，并在此前三个月接受过IHS服务。
- C3规则材料：在2026年2月2日的决策时点，下述规则处于有效期：可作为个人保险获得的铜级或灾难性计划，可按规定视作高免赔额健康计划；交易所外购买但与交易所内版本相同的个人铜级计划也可如此处理。SHOP小企业计划不是个人保险，只有自身另行满足最低免赔额和最高自付额等条件时才可进入该类别。雇主医疗报销安排通常必须仅报销保费，若还报销共付额等医疗费用，会妨碍个人取得相应缴款资格。参加面向美洲印第安人或阿拉斯加原住民的铜级费用分担减免变体者，不因前三个月曾在IHS机构接受服务而当然失去资格。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`shop_bronze_not_individual_coverage, ichra_reimbursing_copayments_disqualifies`。
- 风险：`LONG_COMPOSITE_SOURCE_QUOTE`。
- 复核说明：规则材料只保留影响B与D建模的判据，同时保留A与E所需正式例外，未写入员工选择结果。

### SWOR-R004

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，山谷输电运营商为一个风场并网项目安排邻区协调消息。已完成的集群研究和复研均记录邻区系统影响为零，后续研究也没有新增影响记录；邻区运营商没有提交受影响系统请求，本次消息仅作为自愿预案协调。
- C2/C3事实：2026年8月2日，山谷输电运营商为一个风场并网项目安排邻区协调消息。第0个工作日形成的研究记录标明一项潜在邻区系统影响，所列邻区运营商是当前并网资费流程中的受影响系统参与方。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：输电运营商在首次识别潜在受影响系统影响后，应在10个工作日内通知受影响系统运营商；该首次识别可能发生在集群研究或集群复研完成时。受影响系统输电运营商收到通知后，应在20个工作日内书面回复是否拟开展受影响系统研究。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`initial_notice_deadline, response_deadline`。
- 风险：`无`。
- 复核说明：两个工作日窗口均由同一官方命令段落直接支持，题内25日内部窗口保持独立。

### SWOR-R005

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，晨港商务中心管理一座240位地面设施。全部位置均按车队调度台账分配给配送卡车和其他商用车辆，入口尺寸、地面标线和调度记录均显示商用车专用；设施不向公众开放，员工和访客使用另一座固定乘用车停车设施。
- C2/C3事实：2026年8月4日，晨港商务中心为一栋新建办公楼配置一座240位地面停车设施。全部位置供办公楼员工和访客的普通乘用车使用；该设施独立建设，园区台账中没有需要与其合并计数的其他停车设施。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：一座提供201至300个停车位的设施，至少应设置7个无障碍停车位。每6个或不足6个所需无障碍车位中至少有1个应为厢式车无障碍车位，因此7个所需无障碍车位至少包含2个厢式车位。计算时以同一停车设施实际提供的总车位数为基础。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`E3`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1","E2"],"regulated_subject":["E1"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`exclude_no_accessible_package, exclude_one_van_package`。
- 风险：`无`。
- 复核说明：C3仅需一般停车设施数量和厢式车比例；E3是解释C1商用车专用情形的排除节点，不进入C3规则正文。

### SWOR-R006

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，北原管道公司运营一条复杂原油管线。公司已有一套固定控制系统持续运行，能够实时监控、保存历史运行数据、回溯消息和报警，并按管线复杂度、运行方式和原油特性探测泄漏；题列五项均为额外分析模块。
- C2/C3事实：2026年8月2日，北原管道公司为一条复杂原油管线配置本期唯一控制系统。实时监控、历史数据保存、消息和报警回溯，以及按管线复杂度、运行方式和原油特性设计的泄漏探测，分别只能由题列对应候选模块提供。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：管道公司应建立并实施一套用于控制和监测管道运行的控制系统。该系统须记录可供回溯的历史运行数据、消息和报警；对于输油管道，还须具有符合相应技术要求并反映管道复杂程度、运行方式和所输产品特性的泄漏探测系统。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`alarm_required, history_required, monitor_required, z662_leak_required`。
- 风险：`无`。
- 复核说明：四个能力均由同一完整官方条款支持；自然语言规则不暴露候选模块的最优组合。

### SWOR-R007

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，泰晤士流动性公司按私人回购合同从六只已经完成结算准备的债券中选择三只。融资由私人交易对手提供，公司不参加英格兰银行操作；合同附件逐一列明六个ISIN，发行人地区、发行人类型和外部评级与题面一致。
- C2/C3事实：2026年8月4日，泰晤士流动性公司以在册英镑货币框架参与者身份，从六只已经完成结算准备的债券中选择三只参加英格兰银行操作。公司的英格兰银行结算账户开放，六个ISIN及发行人资料均已上传至本次操作文件。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年6月19日起，G10经济体和澳大利亚的区域或地方政府以及开发银行或政策性银行发行的债券，在满足其他抵押品和结算条件且信用质量大体相当于AA-或以上时，可作为Level B抵押品。发行地区不在该范围、评级低于该水平或由普通私营公司发行的债券不属于这一类别。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_noncovered_seoul_issuer, exclude_below_quality_quebec_bond, exclude_private_infrastructure_issuer`。
- 风险：`无`。
- 复核说明：发行地区、发行人类型与信用质量三条边界均由E1同时给出。

### SWOR-R008

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，纽约州海岳机构以自身账户进行证券交易，未注册为broker或dealer。普通上市股票、市政证券、成交时书面约定延后交收的上市股票大宗交易以及四个付款交付时点，均按题列合同执行。
- C2/C3事实：2026年8月5日，纽约州海岳机构作为注册broker-dealer，代表客户订立一项证券买卖合同。普通上市股票没有替代交收协议；一项候选为市政证券；上市股票大宗交易的延后交收日已由双方在成交时书面约定。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：broker或dealer订立证券买卖合同时，除豁免证券、政府证券、市政证券、商业票据、银行承兑汇票和商业汇票外，不得约定在成交日后的第一个营业日之后才付款并交付证券；但双方在交易发生时另有明示约定的除外。该期限允许在成交当日或第一个营业日完成，并非必须恰好在第一个营业日交收。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`listed_stock_requires_t1`。
- 风险：`V151_GOLD_BOUNDARY_REPAIRED`。
- 复核说明：复核了V1.5.1对T+1边界的修正：规则是不得晚于第一个营业日，而非必须恰好T+1。

### SWOR-R009

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，波托马克儿童细胞治疗中心从六名已完成其他临床准备的候选患者中分配三个Casgevy治疗名额。A为3岁且有反复血管闭塞危象的镰状细胞病患者；B为4岁输血依赖型β地中海贫血患者；C为11岁且有反复血管闭塞危象的镰状细胞病患者；D为13岁且有反复血管闭塞危象的镰状细胞病患者；E为2岁输血依赖型β地中海贫血患者；F为8岁输血依赖型β地中海贫血患者。
- C2/C3事实：2026年8月4日，波托马克儿童细胞治疗中心从六名已完成其他临床准备的候选患者中分配三个Casgevy治疗名额。A为3岁且有反复血管闭塞危象的镰状细胞病患者；B为4岁输血依赖型β地中海贫血患者；C为11岁但没有反复血管闭塞危象的镰状细胞病患者；D为13岁且有反复血管闭塞危象的镰状细胞病患者；E为1岁输血依赖型β地中海贫血患者；F为8岁非输血依赖型β地中海贫血患者。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：Casgevy获准用于年满2岁的两类患者：一类是伴有反复血管闭塞危象的镰状细胞病患者，另一类是输血依赖型β地中海贫血患者。年龄不足2岁、镰状细胞病但没有反复血管闭塞危象，或β地中海贫血但不依赖输血，均不在所述获准人群内。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_SCD_without_recurrent_VOCs, exclude_patient_below_approved_age, exclude_non_transfusion_dependent_thalassemia`。
- 风险：`无`。
- 复核说明：患者的年龄、诊断和危象或输血记录保持为可观察临床事实，规则段不写入名额分配结论。

### SWOR-R010

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，波托马克门诊医院结算组准备重提2026年7月18日和7月22日两次接种记录中的三条申报行。两次就诊各有一条固定且不在本次三条决策内的90480主程序行，该行与对应90481属于同一患者、同一服务日期和同一机构。
- C2/C3事实：2026年8月4日，波托马克门诊医院结算组准备重提2026年7月18日和7月22日两次接种记录中的三条申报行。每次就诊可提交的代码行仅为题列三项，没有决策外的非附加主程序行；同次就诊代码均属于同一患者、同一服务日期和同一机构。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：2026年7月的医院门诊代码编辑规则要求附加代码90481与另行报告且本身不是附加代码的主程序代码共同出现。该月完整映射把90480、G0008、G0009和G0010列为90481可接受的主程序代码；仅有其他代码或仅提交90481不能满足这一编辑条件。规则按服务日期生效，因此覆盖两次2026年7月就诊。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E3"],"obligations":["E2","E3"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`encounter_a_90481_requires_g0008, encounter_b_90481_requires_g0009`。
- 风险：`无`。
- 复核说明：E3用于闭合90481的可接受主程序集合，C1已有决策外90480，C2只能依靠题列G0008/G0009。

### SWOR-R011

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2027年8月2日，2023年设立的葡萄牙林海合作社以微型初级经营者身份，从自有生产的可可豆、咖啡豆、大豆、天然橡胶和原木批次中选择两批，直接运往摩洛哥境内买方。合作社已备齐产地、地理定位和风险材料，并可使用题列两条内部数据提交路线。
- C2/C3事实：2027年8月2日，2023年设立的葡萄牙林海合作社以微型初级经营者身份，从自有生产的可可豆、咖啡豆、大豆、天然橡胶和原木批次中选择两批投放欧盟市场。合作社已备齐各批次的产地、地理定位和风险材料。
- C3规则材料：在2027年8月2日的决策时点，下述规则处于有效期：截至2024年12月31日已经设立的微型或小型初级经营者，在把有关产品投放欧盟市场或出口前，应通过指定信息系统提交一次性简化声明。针对这类经营者，该要求自2027年6月30日起执行；属于另一项既有木材制度覆盖范围的经营者除外。可可、咖啡、大豆、天然橡胶和木材均属于有关产品类别。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`lot_cocoa_activates_simplified_declaration, lot_coffee_activates_simplified_declaration, lot_soy_activates_simplified_declaration, lot_rubber_activates_simplified_declaration, lot_wood_activates_simplified_declaration`。
- 风险：`无`。
- 复核说明：市场地理边界、企业设立时点、主体规模和五类产品均在C2事实或骨架中闭合。

### SWOR-R012

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，松原禽品厂在美国联邦检查场所安排一个已包装待烹禽肉批次。A、B、C包装只写普通frozen；A、B在初冷后50小时入冻，C在初冷后44小时入冻。D在入冻前已冷却并完成包装，屠宰后3小时入冻。四批均在入冻后70小时内使包装中心禽体内部温度降至不高于0华氏度。
- C2/C3事实：2026年8月4日，松原禽品厂在美国联邦检查场所安排一个已包装待烹禽肉批次。A和C包装写有quick frozen；A在初冷后50小时入冻，C在初冷后44小时入冻且包装后等待温度高于36华氏度。B只写普通frozen并在初冷后50小时入冻。D为温包装禽肉，采用厂内冷冻机立即冷却流程，屠宰后3小时入冻。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：标签使用fresh frozen、quick frozen、frozen fresh或其他暗示由鲜品快速转为冻品的待烹禽肉，应在初冷后48小时内放入冷冻机；若初冷和包装后没有立即入冻，等待期间须保持36华氏度或以下。采用厂内冷冻机立即冷却的温包装待烹禽肉，应在屠宰后2小时内进入板式冷冻机，或进入温度不高于零下10华氏度且空气循环正常的冷冻机。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E3"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`quick_frozen_a_requires_48h_entry_and_cold_hold_package, quick_frozen_c_requires_36f_pre_freezer_hold, warm_packaged_d_requires_entry_within_two_hours`。
- 风险：`无`。
- 复核说明：三个Patch分别对应48小时入冻与冷藏等待、C的等待温度、D的屠宰后2小时边界。

### SWOR-R013

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月25日，佛罗里达州朝湾果汁厂使用十个不可拆分的未发酵原汁批次调配100升橙味果汁饮料。成品标签和广告只使用orange-flavored juice beverage名称，不使用pasteurized orange juice名称；不添加水、甜味剂或浓缩调节成分。
- C2/C3事实：2026年8月25日，佛罗里达州朝湾果汁厂使用十个不可拆分的未发酵原汁批次调配100升产品，并以pasteurized orange juice名称销售。生产批记录没有水、甜味剂、浓缩调节成分或题列十批以外的其他原料。
- C3规则材料：在2026年8月25日的决策时点，下述规则处于有效期：自2026年8月19日起，以pasteurized orange juice名称销售的产品，最低可溶性固形物含量由10.5° Brix降为10.0° Brix；Citrus reticulata或其杂交种果汁的体积占比上限由10%提高至15%。配方应按最终100升产品的体积加权固形物含量和所含该类果汁体积判断。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`current_weighted_brix, current_reticulata_volume`。
- 风险：`无`。
- 复核说明：两个模型边界分别对应10.0° Brix下限和15%体积上限，决策日在生效日之后。

### SWOR-R014

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，俄亥俄州青砾零件厂为一个单性别生产班组选择规模和新增厕所便利单元。厂内另有一组不在决策变量中的永久水冲式坐便设施，在14人、28人、48人和70人四种班组规模下均有4个可用，员工在工作时段可随时使用。
- C2/C3事实：2026年8月5日，俄亥俄州青砾零件厂为一个单性别生产班组选择规模和厕所设施包。该厂为固定制造场所，题列设施包是本次生产时段员工能够使用的唯一水冲式坐便设施，员工人数由所选班组决定。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：固定工作场所应按员工人数提供水冲式坐便设施，并为不同性别设置独立厕所间。单一性别班组中，1至15人至少1个，16至35人至少2个，36至55人至少3个，56至80人至少4个。可用数量应包括员工在工作期间实际能够使用的既有设施和本次新增设施。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E2"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1"]}`。
- Patch：`crew28_needs_two, crew48_needs_three, crew70_needs_four`。
- 风险：`无`。
- 复核说明：人数区间与厕所数量由Table J-1直接给出；C2不存在题列包之外的可用设施。

### SWOR-R015

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，岬岭运营方在围栏封闭的美国工业场地内，从三辆轻型工具车中选择一辆执行场内路线。车辆不进入公共道路或跨州运输；制动器和喇叭故障报告、匹配维修效果及其他部件状态均按题列记录。
- C2/C3事实：2026年8月5日，岬岭运营方以motor carrier身份，从三辆商业机动车中选择一辆执行美国公共道路跨州路线，并安排出车前维修。已报告的制动器或喇叭故障在匹配维修前持续存在，匹配维修恢复对应部件，完整维修包同时恢复两者。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：商业机动车不得出车，除非驾驶员确认规定的部件和附件处于良好工作状态，并在需要时正常使用。其中明确包括服务制动器及拖车制动连接，以及喇叭。因此，带有仍未修复制动器故障的车辆须先恢复制动器，带有仍未修复喇叭故障的车辆须先恢复喇叭。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`brake_defect_requires_brake_repair, horn_defect_requires_horn_repair`。
- 风险：`无`。
- 复核说明：服务制动器和喇叭均在同一出车前条款中明列，题内维修包提供对应物理修复能力。

### SWOR-R016

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，美国地面运输委员会审理河谷化工厂的铁路服务申请。申请人与两家承运人已经签署可自行执行的和解，案卷内2026年6月15日委员会命令逐项记载条款，并指示书记员按和解条款签发命令。
- C2/C3事实：2026年8月2日，美国地面运输委员会审理河谷化工厂通过互惠换装获得铁路服务的申请。工厂位于换装终端区且只接入北陆一家一级铁路；申请书请求委员会因所称服务不足签发实体互惠换装命令，案卷没有承运人和解，也没有基于其他独立授权形成的竞争行为或服务不足认定。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：第七巡回法院已经撤销并发回委员会进一步处理2024年发布、编入49 CFR part 1145的Reciprocal Switching for Inadequate Service最终规则。到本案决策时，委员会对该事项仍标记为司法审查后阶段，下一行动日期待定。因此，在没有和解或其他独立授权与实体认定的案卷中，不能依据该已撤销规则签发实体互惠换装命令。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`vacated_rule_unavailable`。
- 风险：`POST_JUDICIAL_REVIEW_STATUS`。
- 复核说明：C3材料区分法院撤销与委员会尚未完成替代处理，不把C1和解行政签发路径误写为一般例外。

### SWOR-R017

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，一艘越过美国boundary line运行的货船，由船长为同一名承担轮机值班和指定安全职责的船员安排八个连续3小时块中的四个。一项有记录的突发船舶和人员生命安全事件要求执行本日所选值班块；船长已记录事件与值班，后续补偿休息固定在决策时域之外。
- C2/C3事实：2026年8月4日，一艘越过美国boundary line运行的货船，由船长为同一名承担轮机值班和指定安全职责的船员安排八个连续3小时块中的四个。本日没有突发安全事件、召回或演练；入选块全程值班，未选块全程连续休息。此前和此后各七个完整日均全程下班，完整记录覆盖所有受本日选择影响的24小时和7日窗口。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：承担船舶值班和指定安全职责的船员，在任意连续24小时内至少应有10小时休息，在任意连续7日内至少应有77小时休息。24小时内休息最多分为两段，其中一段至少连续6小时；相邻休息期之间的间隔不得超过14小时。判断时应覆盖跨午夜的全部连续窗口，而不只检查日历日内的总量。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E2","E3","E4"],"obligations":["E1","E2","E3","E4"],"regulated_subject":["E1"],"threshold_and_equality":["E1","E2","E3","E4"]}`。
- Patch：`ten_hours_rest_in_every_sliding_day, seventy_seven_hours_rest_in_every_sliding_week, exclude_cross_boundary_rest_pattern_01, exclude_cross_boundary_rest_pattern_02, exclude_cross_boundary_rest_pattern_03, exclude_cross_boundary_rest_pattern_04, exclude_cross_boundary_rest_pattern_05, exclude_cross_boundary_rest_pattern_06, exclude_cross_boundary_rest_pattern_07, exclude_cross_boundary_rest_pattern_08, exclude_cross_boundary_rest_pattern_09, exclude_cross_boundary_rest_pattern_10, exclude_cross_boundary_rest_pattern_11, exclude_cross_boundary_rest_pattern_12, exclude_cross_boundary_rest_pattern_13, exclude_cross_boundary_rest_pattern_14, exclude_cross_boundary_rest_pattern_15, exclude_cross_boundary_rest_pattern_16, exclude_cross_boundary_rest_pattern_17, exclude_cross_boundary_rest_pattern_18, exclude_cross_boundary_rest_pattern_19, exclude_cross_boundary_rest_pattern_20, exclude_cross_boundary_rest_pattern_21, exclude_cross_boundary_rest_pattern_22, exclude_cross_boundary_rest_pattern_23, exclude_cross_boundary_rest_pattern_24, exclude_cross_boundary_rest_pattern_25, exclude_cross_boundary_rest_pattern_26, exclude_cross_boundary_rest_pattern_27, exclude_cross_boundary_rest_pattern_28, exclude_cross_boundary_rest_pattern_29, exclude_cross_boundary_rest_pattern_30, exclude_cross_boundary_rest_pattern_31, exclude_cross_boundary_rest_pattern_32, exclude_cross_boundary_rest_pattern_33, exclude_cross_boundary_rest_pattern_34, exclude_cross_boundary_rest_pattern_35, exclude_cross_boundary_rest_pattern_36, exclude_cross_boundary_rest_pattern_37, exclude_cross_boundary_rest_pattern_38, exclude_cross_boundary_rest_pattern_39, exclude_cross_boundary_rest_pattern_40, exclude_cross_boundary_rest_pattern_41, exclude_cross_boundary_rest_pattern_42, exclude_cross_boundary_rest_pattern_43, exclude_cross_boundary_rest_pattern_44, exclude_cross_boundary_rest_pattern_45, exclude_cross_boundary_rest_pattern_46, exclude_cross_boundary_rest_pattern_47, exclude_cross_boundary_rest_pattern_48, exclude_cross_boundary_rest_pattern_49, exclude_cross_boundary_rest_pattern_50, exclude_cross_boundary_rest_pattern_51, exclude_cross_boundary_rest_pattern_52, exclude_cross_boundary_rest_pattern_53, exclude_cross_boundary_rest_pattern_54, exclude_cross_boundary_rest_pattern_55, exclude_cross_boundary_rest_pattern_56, exclude_cross_boundary_rest_pattern_57, exclude_cross_boundary_rest_pattern_58, exclude_cross_boundary_rest_pattern_59, exclude_cross_boundary_rest_pattern_60, exclude_cross_boundary_rest_pattern_61, exclude_cross_boundary_rest_pattern_62`。
- 风险：`LARGE_ENUMERATED_PATCH_SET, CROSS_MIDNIGHT_WINDOW_ENCODING`。
- 复核说明：64个Patch name与V1.5.1 Gold逐项一致；大量cross-boundary约束是四条连续休息规则的有限枚举实现，需由validator重放而非按名称推断。

### SWOR-R018

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，星湾饮料公司为内部采购和减量分析准备包装数据表。公司本年度经审计营业额为800万新元，在新加坡进口或使用塑料瓶20吨、纸盒12吨、金属罐8吨、玻璃罐0吨；董事会任务单写明表格只进入内部采购系统，截至决策日没有向NEA传送。
- C2/C3事实：2026年8月2日，星湾饮料公司本年度经审计营业额为1200万新元，在新加坡进口或使用塑料瓶120吨、纸盒80吨、金属罐40吨、玻璃罐0吨。每种实际材料和包装形式均有独立称重记录，年度工作日历列有向NEA提交包装数据和3R计划的任务。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：在新加坡供应受列明商品、年度营业额严格超过1000万新元并进口或使用指定包装的企业，应按年度提供在新加坡进口或使用的包装重量数据。数据须按包装材料类别和包装形式拆分，例如塑料、纸、金属、玻璃以及瓶、袋等形式；企业还应提交包装3R计划。没有实际使用的材料形式无需虚构重量记录。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E2"],"threshold_and_equality":["E2"]}`。
- Patch：`metal_material_form, paper_material_form, plastic_material_form`。
- 风险：`无`。
- 复核说明：营业额是严格大于1000万新元；C2实际材料形式只有塑料瓶、纸盒和金属罐，玻璃为零。

### SWOR-R019

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，海岬通信工程公司为四家美国业务方安排IP交付。四份请求文件均没有技术准备认证，业务方没有补交认证，提供商也没有书面同意把这些文件作为完整请求接收；案卷没有替代交付协议或争议裁定。
- C2/C3事实：2026年8月4日，海岬通信工程公司为全国性CMRS、非全国性CMRS、互联VoIP和农村本地交换运营商各安排一次NG911交付。两份一期请求所列基础SIP接收与PSAP转送设施均已运行；两份二期请求所列标准SIP设施、ESInet、NGCS、LVF及LIS接口均已运行。四份请求均由有权911 Authority书面发出、载明指定交付点并附认证；各请求日期和一期完成日期按题列记录，双方没有替代协议。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：一期有效请求须同时满足技术准备、授权和通知三项前提，并载明911 Authority指定的交付点。全国性CMRS应在有效一期请求后6个月内完成，非全国性CMRS应在12个月内完成。二期中，互联VoIP应在有效二期请求日与一期到期日或更早实际完成日两者中较晚者之后6个月内完成；农村本地交换运营商采用同一较晚锚点后的12个月。二期技术准备还须覆盖标准SIP接收和PSAP转送，以及已连接运行中NGCS、可提供LVF并与LIS或等效系统接口的ESInet。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7, E8`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E5","E8"],"object_scope":["E5","E6","E7","E8"],"obligations":["E1","E2","E3","E4"],"regulated_subject":["E1","E2","E3","E4"],"threshold_and_equality":["E1","E2","E3","E4"]}`。
- Patch：`nationwide_phase1_six_month_class, nonwide_phase1_twelve_month_class, voip_phase2_six_month_latest_anchor, rlec_phase2_twelve_month_latest_anchor`。
- 风险：`MULTI_NODE_VALID_REQUEST_CLOSURE`。
- 复核说明：保留全部八个C2节点：四个期限节点与四个请求有效性节点共同闭合，不能只给期限摘要。

### SWOR-R020

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，伊利诺伊州星湾电信公司从四个客户分析工作流中选择一个。四个工作流均只读取不可逆聚合数据，无法识别或合理链接回个别客户；向独立合作保险商交付的也只有同一聚合结果，不传送行级记录。
- C2/C3事实：2026年8月5日，伊利诺伊州星湾电信公司从四个客户账户工作流中选择一个。在未启用聚合处理时，工作流读取按姓名和账户号关联的行级记录，字段包括订阅服务类别、数量、技术配置、位置和使用量；用途分别为同类别增值包营销、移动无线服务营销、向无控制关系的独立保险商联合营销和室内布线维修。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：同一承运人可以无须客户批准，使用、披露或允许访问个别可识别的客户网络信息，以向该客户提供或营销其已向同一承运人订阅的同一服务类别内产品；在提供室内布线安装、维护和维修服务时也可无须客户批准。营销客户尚未向该承运人订阅的不同类别通信相关服务时，可以在有效退出式或加入式批准下使用个别可识别信息。除上述无需批准的列明用途或其他明文情形外，使用、披露或允许访问个别可识别信息原则上须取得加入式批准，向不属于代理、关联方或通信服务承包商的独立保险商披露也适用这一要求。已移除个别身份和特征的群组或类别数据属于聚合客户信息，可以在相应非歧视条件下使用或披露，不受个别信息批准路径约束。
- 纳入证据：`E1, E2, E3, E4, V161-R020-E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":["E3","E4","V161-R020-E5"],"geographic_scope":["E1","E2"],"object_scope":["E3","V161-R020-E5"],"obligations":["E1","E2"],"regulated_subject":["E1","E2","E4","V161-R020-E5"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`different_category_needs_optout_or_optin, partner_disclosure_requires_optin`。
- 风险：`V151_GOLD_REPAIR_RECHECKED, V161_64_2005_NO_APPROVAL_EXCEPTIONS`。
- 复核说明：复核V1.5.1修复并补入§64.2005(a)、(c)(1)：同类别已订阅服务营销与室内布线安装、维护、维修均可无批准；聚合处理仍是独立可选路径，独立保险商收到个别信息时只能使用加入式批准。

### SWOR-R021

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，爱尔兰环境部门用本部门预算采购两个包装废物市政试点职责包，并由部门签署和控制两份承包合同。生产者不出资，合同名册中没有生产者代表组织；登记联络报告和分类回收处理工作均只服务该市政试点。
- C2/C3事实：2026年8月2日，爱尔兰环境部门为一项包装废物责任计划采购职责包。在爱尔兰市场投放包装产品的生产者为计划出资并指定代表组织；登记、联络和报告，以及包装废物分类、回收和处理两组工作均在本期发生，本期废物管理目标栏尚为空白。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：由产品生产者承担产品生命终结废物阶段财务责任，或同时承担财务和组织责任的一组措施，构成生产者延伸责任安排。建立此类安排时，部长或有关政府部长应按照废物层级设置废物管理目标，至少以实现有关欧盟废物和包装等指令中的定量目标为方向，并可设置其他相关定量目标或定性目标。
- 纳入证据：`E1, E2a, E2b`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2a"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E2a"],"object_scope":["E1","E2b"],"obligations":["E2a","E2b"],"regulated_subject":["E1","E2a"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`waste_target_set`。
- 风险：`无`。
- 复核说明：E1闭合计划类型，E2a闭合行动主体，E2b闭合设置目标的完整谓词。

### SWOR-R022

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，宾夕法尼亚州澄岭专业护理机构为一个班次选择工作人员和支持任务包。入选人员只执行前台接待、送餐和陪伴，不进行护理或护理相关操作；全部临床与护理相关工作由另行排班的持证人员完成。
- C2/C3事实：2026年8月5日，宾夕法尼亚州澄岭专业护理机构为一个班次选择一名非持证工作人员执行护理相关服务。甲全职任职2个月并全职参加州批准训练和能力评估；乙任职2个月但只完成机构内部岗前导向；丙为派遣护理员且能力、批准训练和州登记均已核验；丁曾合格但此后连续25个月没有有偿提供护理或护理相关服务。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：专业护理机构使用人员担任nurse aide时，任职少于4个月者也必须处于州批准训练与能力评估项目、已通过州批准项目证明能力，或已按规定被认定合格；仅完成机构内部岗前导向不足以替代这些条件。某人自最近完成训练和能力评估后，若连续24个月都没有因报酬提供护理或护理相关服务，必须重新完成训练与能力评估项目或新的能力评估。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E3"],"object_scope":["E1","E4"],"obligations":["E1","E2","E4"],"regulated_subject":["E1","E3","E4"],"threshold_and_equality":["E1","E2","E4"]}`。
- Patch：`orientation_only_aide_ineligible, gap25_requires_retraining`。
- 风险：`无`。
- 复核说明：乙由少于4个月且仅内部导向的事实触发，丁由连续25个月无有偿护理服务触发。

### SWOR-R023

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，内华达州白岩维修中心从四批经独立检测的气雾容器中选择一批处理。A至D均完全空、已泄压且没有危险残留，随后进入金属回收流；穿孔时没有残余内容物或排放逸出。
- C2/C3事实：2026年8月5日，内华达州白岩维修中心现场累计存放不足5000千克废气雾罐并选择一批处理。A为须当天处理的泄漏批次，B为普通泄漏批次，C未泄漏但仍有残液，D经确认完全空；中心已备齐专用密闭穿孔装置、书面程序、制造商说明、员工培训、通风场地、密闭残液转移、残液鉴别和泄漏清理能力。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：显示泄漏迹象的废气雾罐，必须装入独立密闭容器、使用带吸附材料的外包装，或立即按规定穿孔排空。小量处理者选择穿孔排空时，应使用专门设计、能安全穿孔并容纳残余内容物和排放的装置，随后回收空罐；还须建立并遵循书面安全程序，现场保留制造商说明，并确保操作员工接受相应培训。普通手工工具穿孔后混放残液不满足这些条件。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`leak_a_not_open, leak_b_not_open, improvised_puncture_forbidden`。
- 风险：`无`。
- 复核说明：泄漏包装路径和合格穿孔路径分别由E1、E2闭合；题内专用装置具备E2列明能力。

### SWOR-R024

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，云浦工业设施为内部温室气体摘要选择下一年度数据计划和档案服务。EPA于2025年12月15日签发停止报告通知接受函，账户页面自该日显示closed；题列计划只生成内部摘要，全部旧档案距相应提交日均已满三年六个月。
- C2/C3事实：2026年8月5日，云浦工业设施为2025日历年的EPA温室气体年度报告选择提交时间和记录服务。设施持续运行，GHGRP账户页面显示active并列有facility ID；案卷没有延期函或停止报告通知，题列记录状态覆盖本报告涉及的全部记录。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：仍承担年度温室气体报告的设施，应在每个日历年3月31日或之前提交上一日历年的报告。设施所有者或运营者还应自对应年度报告提交之日起，将该报告年度产生的全部规定记录至少保存3年。晚于3月31日的计划须提前，任何未建立档案的计划须增加完整的三年记录保存。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`april5_requires_deadline_acceleration, march20_no_archive_requires_retention, april5_no_archive_requires_retention`。
- 风险：`V151_GOLD_REPAIR_RECHECKED`。
- 复核说明：复核V1.5.1新增的4月5日未建档计划记录保留约束；两条官方原文覆盖全部三个Patch。

### SWOR-R025

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，苍桥制造公司在美国工厂选择一条出口通道和改造。A全程远离高危险区；B沿途房间的锁与锁具已经永久拆除；C连续通向出口并有贯通平面图；D为直接无障碍通道。
- C2/C3事实：2026年8月5日，苍桥制造公司在美国工厂选择一条出口通道和改造。A朝高危险反应区方向经过，连续实体隔墙可把该区域与通道屏蔽；B穿过一间工作时开启但硬件仍可上锁的更衣室；C通向死胡同后折返；D为直接无障碍通道。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：出口通道的布置不得迫使员工朝高危险区域行进，除非通行路径由适当隔墙或其他实体屏障与高危险区域有效隔开。出口通道不得穿过可以上锁的房间后才到达出口或出口排放处，也不得进入死胡同走廊。只有确实消除这些物理状态的屏蔽、永久拆锁或重新布置路线，才能使相应通道继续使用。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`hazard_route_requires_shield_or_reroute, lockable_route_requires_remove_or_reroute, dead_end_requires_reroute`。
- 风险：`V151_GOLD_REPAIR_RECHECKED`。
- 复核说明：A、B、C三条通道分别对应高危险方向、可上锁房间和死胡同边界；D保持无附加条件。

### SWOR-R026

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，霁川工业物流从六票美国公路运输中选择三票。A、B外包装展示limited quantity标记，C、D展示excepted quantity标记，E也展示limited quantity标记；F运单的proper shipping name栏填写Dry ice。题列日间和夜间值班台均为可选内部服务。
- C2/C3事实：2026年8月4日，霁川工业物流从六票美国公路运输中选择三票。A至D运单分别列有UN编号、proper shipping name、危险类别和packing group，外包装没有limited quantity或excepted quantity标记，运输时段按题列覆盖其全部在途时间；E展示limited quantity标记，F运单proper shipping name为Dry ice。日夜值班台均由掌握相应材料应急资料的人员即时接听。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：危险材料运输单据所列应急电话号码，在材料处于运输中及运输附带储存的全部时间都应有人监控，并直接接通掌握该材料全面应急响应和事故缓解信息、或能够立即联系到此类人员的人。依limited quantity或excepted quantity条款交运的材料不承担这项要求；proper shipping name为Dry ice的材料也在明列例外中。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E2","E3"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`dispatch_a_requires_day_desk, dispatch_b_requires_day_desk, dispatch_b_requires_night_desk, dispatch_c_requires_day_desk, dispatch_c_requires_night_desk, dispatch_d_requires_night_desk`。
- 风险：`无`。
- 复核说明：A至D的在途时段与日夜台覆盖区间决定六条Patch；E和F由两个正式例外节点排除。

### SWOR-R027

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Meridian Securities把Q1、Q2、Q3三批受限票据和R一批已注册公开票据分配给四个机构自营账户。保险公司、注册交易商和两家美国银行的实体类型、酌情持有金额及审计报表日期按题列记录；B20经审计净值为2500万美元。
- C2/C3事实：2026年8月4日，Meridian Securities把Q1、Q2、Q3三批受限票据和R一批已注册公开票据分配给四个机构自营账户。保险公司酌情持有1.05亿美元非关联发行人证券，section 15注册交易商持有1200万美元；两家美国银行均持有1.20亿美元且审计报表距出售12个月，B30净值3000万美元，B20净值2000万美元。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：依Rule 144A出售的证券只能卖给合格机构买方，或卖方及其代理有合理理由相信属于合格机构买方的购买者。保险公司等列明机构自营时，通常须酌情拥有并投资至少1亿美元非关联发行人证券；section 15注册交易商的对应门槛为1000万美元。银行除至少1亿美元证券门槛外，还须具有至少2500万美元经审计净值。公开注册票据不依赖上述受限证券出售路径。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1","E2","E3","E4"],"threshold_and_equality":["E2","E3","E4"]}`。
- Patch：`bank20_not_qib_for_q1, bank20_not_qib_for_q2, bank20_not_qib_for_q3`。
- 风险：`无`。
- 复核说明：B20的2000万美元净值低于银行2500万美元门槛，三批受限票据分别形成同一资格限制。

### SWOR-R028

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，棱湾财富管理公司为同一个英国stocks and shares ISA选择两项账面行动。A、B、C三只cETN均在2026年4月6日前存入该账户并持续持有；A、B只进行继续持有下的账面分配。D为新购LTAF，E为FCA授权OEIC份额，F为伦敦证券交易所主板上市普通股。
- C2/C3事实：2026年8月4日，棱湾财富管理公司为同一个英国stocks and shares ISA选择两项交易或持有行动。A为当日新购cETN，B为当日从普通应税账户转入另一只cETN，C在2026年4月6日前已存于同一账户并连续持有；D为新购LTAF，E和F满足题列普通投资条件。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年4月6日起，stocks and shares ISA不得接受新的cryptoasset exchange traded note购买或转入；在该日前已经存在于同一账户的此类票据，只要继续留在该账户，即继续视为合资格投资。2026年修订还把long-term asset fund投资加入该账户的合资格投资清单。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":["E2"],"geographic_scope":["E1","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`new_cetn_purchase_not_qualifying_for_ss_isa, new_cetn_transfer_not_qualifying_for_ss_isa`。
- 风险：`无`。
- 复核说明：A/B分别是生效日后的新购和新转入，C由grandfathering节点保留；D由LTAF节点支持。

### SWOR-R029

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，滨湾康护药房由合格药剂师负责四张订单。A、B、D均由诊所通过闭环系统直接传送处方，C为普通处方药；药房已持续运行覆盖全部候选的闭环保障和安全到家配送系统，题列两个服务行动只是额外审计升级。
- C2/C3事实：2026年8月4日，滨湾康护药房由合格药剂师负责四张订单。A、D为处方药，B为药房专售药，C为受控药品；A/B两条路径分别为诊所直传闭环到家和患者PDF到家，C两条路径为电子配方到家和内容完整的纸质处方柜台领取，D两条路径为诊所直传闭环柜台领取和患者PDF柜台领取。HSA授权登记表没有该药房对C进行电子配方或到家配送的条目。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：电子药房服务应采用闭环电子处方传输，即处方由诊所直接发送至药房，使其不能被更改或重复使用、能够追溯开方医生并具备网络安全保障。药房还应建立药品储存、包装、标签和安全交付程序，在合格药剂师专业监督下把药品交给预定患者。受控药品不得通过电子方式配方，也不得到家配送。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E3"],"geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`a_pdf_not_valid_eprescription, b_pdf_not_valid_eprescription, d_pdf_not_valid_eprescription, controlled_not_electronically_filled_or_delivered, closed_orders_activate_assurance, home_orders_activate_secure_delivery`。
- 风险：`无`。
- 复核说明：三个患者PDF路径由闭环要求排除，C受控药品同时受电子配方和到家配送限制，两个共享服务对应闭环和安全配送义务。

### SWOR-R030

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，槐岸成人社会服务机构选择两名参与者提交2026—2027年度ASYE资助申请。A至F在项目开展、完成和申报期间均由该机构直接雇用，岗位记录均为成人社会照护或NHS成人社会工作；六人的认可社会工作资格取得日依次为2024年5月1日、2024年5月1日、2025年5月1日、2023年5月1日、2022年5月1日和2025年5月1日，在Social Work England的首次登记日也依次为上述日期。
- C2/C3事实：2026年8月4日，槐岸成人社会服务机构选择两名参与者提交2026—2027年度ASYE资助申请。A、D、F由机构直接雇用并从事成人社会工作；B在全部项目期由劳务机构派驻，C只从事儿童社会工作。A至F的认可社会工作资格取得日依次为2024年5月1日、2024年5月1日、2025年5月1日、2023年5月1日、2021年5月1日和2025年5月1日，在Social Work England的首次登记日也依次为上述日期；因此截至2026年5月1日，A、D、F分别取得资格并注册2年、3年和1年，E已满5年。六人均于2026年5月1日首次开始ASYE。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：2026年4月1日至2027年3月31日支付的合格ASYE项目可以申领该年度资助。申领机构可以是法定、私营、志愿或独立组织，但参与者必须在英格兰由申领机构直接雇用，从事成人社会照护服务或NHS中的成人社会工作，并在开展、完成项目和提出申请时保持直接雇佣。参与者须持认可资格、在Social Work England注册且注册不超过4年；相关资格也须在最近4年取得。相同员工原则上只能获得一次资助，先前未完成项目的情形除外。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7, E8, E9, E10`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2","E9"],"formal_exceptions":["E7"],"geographic_scope":["E3"],"object_scope":["E1","E4"],"obligations":["E3","E4","E6","E10"],"regulated_subject":["E3","E6","E10"],"threshold_and_equality":["E5","E8","E9"]}`。
- Patch：`agency_contractor_b_not_directly_employed, children_social_work_c_outside_adult_scheme, five_year_registered_e_not_newly_qualified`。
- 风险：`TEN_NODE_ELIGIBILITY_CHAIN, QUALIFICATION_DATES_EXPLICIT`。
- 复核说明：十个节点分别闭合支付年度、项目、主体、直接雇佣、成人服务、认可资格取得时间、注册年限、首次资助和申报材料；C1六人及C2全部候选均显式给出资格取得日和首次登记日，A、D、F在最近4年内，E明确满5年。

### SWOR-R031

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，海岬租赁公司从六辆已登记的新加坡道路摩托车中购入两辆。A于2026年4月30日按普通摩托车登记，B也在2026年5月1日前登记，二者各有一面镜；C按经典车辆登记，E按普通古董车辆登记，二者各有一面镜；D、F左右两侧各有一面镜。所有车辆均无边车。
- C2/C3事实：2026年8月4日，海岬租赁公司从六辆已登记的新加坡道路摩托车中购入两辆。A于2026年6月按普通摩托车登记且仅右侧有一面镜；B于2026年4月按普通摩托车登记且仅左侧有一面镜；C按经典车辆登记，E按普通古董车辆登记，二者各有一面镜；D、F左右两侧各有一面镜。所有车辆均无边车。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：有关修订自2026年5月1日起实施。摩托车通常至少应安装一面构造和安装方式能够帮助骑手观察后方交通的后视镜；但在2026年5月1日或以后登记、且没有登记或重新登记为经典车辆或各类古董车辆的摩托车，应在左右两侧各至少安装一面符合用途的后视镜。2026年5月1日前登记的车辆，以及列明经典或古董类别车辆，保留单面镜路径。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E4","E5"],"geographic_scope":["E1"],"object_scope":["E4","E5","E7"],"obligations":["E2","E3","E6"],"regulated_subject":["E2","E6"],"threshold_and_equality":["E1","E4","E7"]}`。
- Patch：`ordinary_post_may_one_mirror_a_requires_cell`。
- 风险：`E8_TECHNICAL_CROSS_REFERENCE_NOT_NEEDED_FOR_PATCH`。
- 复核说明：A是唯一在生效日后登记的普通单镜车辆；B及经典/古董车辆由日期或类别分支保留。

### SWOR-R032

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，IronRoute Logistics在一辆不经水路运输的美国公路货车上，从八票惰性工业测试样品中装载三票。A至H均不含危险材料，托运说明和包装检验记录没有危险类别、次要危险、危险标签或车辆标牌；G与H隔离舱板只是可选的防破损混合设备。
- C2/C3事实：2026年8月4日，IronRoute Logistics在一辆不经水路运输的美国公路货车上，从八票危险材料中装载三票。A为与酸混合释放氰化氢的氰化物溶液，B为Class 8硫酸，C为Division 4.2，D为Class 8碱液，E为Division 6.1、Packing Group I、Hazard Zone A，F和G为Class 3，H为Division 5.1；各包装展示对应标签或车辆标牌。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：带有规定危险标签或车辆标牌的材料包件进入同车隔离要求。能与酸混合释放氰化氢的氰化物不得与酸同车；Division 4.2不得与Class 8液体同车；Division 6.1、Packing Group I、Hazard Zone A材料不得与Class 3、Class 8液体以及Division 4.1、4.2、4.3、5.1或5.2材料同车。Class 3与Division 5.1以及Class 8液体与Division 5.1的表格关系要求物理分隔，使通常运输泄漏时不会发生混合；Class 8液体还不得装在Division 5.1材料上方或相邻位置。
- 纳入证据：`E1, E2, E3, E4, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1","E2","E4","E5"],"obligations":["E2","E3","E4","E5"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`cyanide_acid_conflict, division42_class8_conflict, zonea_class3_conflict, class3_oxidizer_separation, division42_sulfuric_acid_conflict, zonea_class8_sulfuric_conflict, zonea_division42_conflict, zonea_class8_alkali_conflict, zonea_second_class3_conflict, zonea_division51_conflict, class8_sulfuric_oxidizer_requires_unavailable_separation, class8_alkali_oxidizer_requires_unavailable_separation, class3_f_oxidizer_requires_unavailable_separation`。
- 风险：`V151_GOLD_REPAIR_RECHECKED, THIRTEEN_INTERACTION_PATCHES`。
- 复核说明：13个Patch name与V1.5.1 Gold完全一致；E2负责绝对禁配，E3至E5负责只有足够分隔时可同车的O关系。题内隔离舱板只服务G/H，不能推广到其他组合。

### SWOR-R033

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Red Mesa Components从八个先进制造campaign中执行三个。A在美国生产并于本年度售给无关联客户；B保留俄亥俄生产销售记录；C于本年度售给无关联客户；D在内华达完成矿物精矿破碎、浸出、分离和精炼后出售；E经关联方集成后售给无关联客户；F设施没有48C申领记录；G在波多黎各生产且已提交关联方选择文件；H在加州从晶圆开始完成电池扩散、金属化、电连接、层压、封装和接线盒组装后出售。
- C2/C3事实：2026年8月4日，Red Mesa Components从八个先进制造campaign中执行三个。A在加拿大生产后售给无关联客户；B在俄亥俄生产并出售；C只转入本公司库存且没有下游集成或关联方选择文件；D在内华达完成矿物精矿破碎、浸出、分离和精炼后出售；E经关联方集成后售给无关联客户；F设施有48C申领记录；G在波多黎各生产且已提交关联方选择文件；H只把进口成品组件换入新纸箱并贴新标签后出售。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：相应生产价值要求合格组件由制造商在其经营活动中，于美国或其属地生产，并在申领年度内出售。出售通常应面向无关联方；如果组件被关联方集成进另一合格组件后再售给无关联方，或已经作出关联方选择，也可满足销售链条。制造活动须对合格组件形成实质性转化，仅换包装和标签不足。曾由同一设施申领48C先进能源项目抵免的，不得再对该设施申领此项生产价值。
- 纳入证据：`E1, E2, E3, E4, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E2","E5"],"geographic_scope":["E3"],"object_scope":["E1","E4"],"obligations":["E1","E2","E3","E4"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`claim_a_not_eligible, claim_c_not_eligible, claim_f_not_eligible, claim_h_not_eligible`。
- 风险：`无`。
- 复核说明：A、C、F、H分别触及生产地、销售链、48C设施和实质转化边界；其余campaign保留。

### SWOR-R034

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，美国星港工厂把四个密封成品托盘分配给Red或Blue两条装载线并装入对应封闭货车。A至D外包装和运输文件分别标明limited quantity或excepted quantity，没有危险标签，车辆没有危险标牌；车内没有独立运输车辆或储存设施。
- C2/C3事实：2026年8月4日，美国星港工厂把四个密封危险材料托盘分配给Red或Blue两条装载线并装入对应封闭货车。A仅为Class 3，B仅为Division 6.1、Packing Group I、Hazard Zone A，C仅为Division 5.2，D仅为Division 4.1；四个托盘展示对应危险标签，车内没有独立运输车辆或储存设施。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：按危险类别贴有规定标签的材料包件，在同一运输车辆内装载时进入隔离要求。Division 6.1、Packing Group I、Hazard Zone A材料，不得与Class 3液体、Division 4.1材料或Division 5.2材料装在同一运输车辆内。把托盘分到不同车辆可以满足分离要求，但同一车辆内部没有独立车辆或储存设施时，不能把普通装载区域视为另一个可用分隔空间。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E2"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`red_flammable_liquid_a_poison_liquid_b_x_separation, red_poison_liquid_b_organic_peroxide_c_x_separation, red_poison_liquid_b_flammable_solid_d_x_separation, blue_flammable_liquid_a_poison_liquid_b_x_separation, blue_poison_liquid_b_organic_peroxide_c_x_separation, blue_poison_liquid_b_flammable_solid_d_x_separation`。
- 风险：`无`。
- 复核说明：三个禁配货物对在Red、Blue两辆车上各形成一条约束，共六个Patch。

### SWOR-R035

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，美国澄湾包装回收车队从同一路线七个取件点中选择四个。A、B已清除残留并吹扫蒸气，C重新装入非危险材料，D只留有限数量残留，E、F只留无次要危险的Division 2.2非易燃气体且不是无水氨、20°C表压180 kPa，G从未装料；原危险标记均已移除或覆盖。
- C2/C3事实：2026年8月4日，美国澄湾包装回收车队从同一路线七个取件点中选择四个。A仍有危险残留且原标记可见，B已清除残留并吹扫，C重新装入非危险材料，D只有limited quantity残留且标记已移除，E为非无水氨Division 2.2残留、20°C表压180 kPa且标记已移除，F含无水氨残留，G从未装料但原标记可见。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：仍含危险材料残留的空包装，原则上须按先前装有更大量同一危险材料时的方式交运和运输。低压Division 2.2非易燃气体在20°C时表压低于200 kPa、没有次要危险且不是无水氨时，可进入列明例外。要使用空包装例外，运输中可见的危险运输名称、识别号、危险标签、标牌和其他危险标记还须被移除、抹除或牢固覆盖；由托运人装载且由托运人或收货人卸载、运输中不可见的包装另有例外。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E2","E3"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3"],"obligations":["E1","E3"],"regulated_subject":["E1"],"threshold_and_equality":["E2"]}`。
- Patch：`residue_drum_requires_hazmat_cell, anhydrous_ammonia_exception_unavailable, visible_markings_prevent_empty_exception`。
- 风险：`无`。
- 复核说明：A、F、G分别由残留一般规则、无水氨排除和可见标记条件闭合；D、E保留对应例外。

### SWOR-R036

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，蓝峡物流公司从六名不同司机的欧盟跨海重型货车运输计划中接受两项。A、B为日常正常休息，两次移动各0.4小时并有卧铺；C为缩短周休，两次移动0.5和0.4小时并有卧铺；D、E、F为正常周休，两次各0.4小时、航程9小时并有卧铺客舱或床铺。
- C2/C3事实：2026年8月4日，蓝峡物流公司从六名不同司机的欧盟跨海重型货车运输计划中接受两项。A为日常正常休息且两次移动共1.2小时；B为日常正常休息且共0.8小时；C为缩短周休且共0.9小时；D为正常周休、航程7小时并有卧铺；E为正常周休、航程9小时但没有卧铺客舱、床铺或卧铺；F为正常周休、航程9小时并有卧铺。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：司机的日常正常休息或缩短周休可因上下轮渡或火车最多中断两次，但中断合计不得超过1小时，并且司机须有卧铺客舱、床铺或卧铺。正常周休也可采用轮渡中断路径，但计划航程至少应为8小时，且司机必须有卧铺客舱。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1","E2"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`plan_a_exceeds_total_interruption_hour, plan_d_regular_weekly_ferry_under_eight_hours, plan_e_regular_weekly_ferry_has_no_sleeper_cabin`。
- 风险：`无`。
- 复核说明：A、D、E分别违反1小时合计上限、8小时航程下限和卧铺条件。

### SWOR-R037

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，持有美国航空承运人运行合格证的远海航空从七个计划空乘排班中选择两个。各机型基础空乘人数为4；A为13小时、4人、休10小时，B和C为15小时、5人、休12小时，D和E为17小时、6人、休12小时，F和G为19小时、7人、休12小时，且F、G均含有在48个相邻州及哥伦比亚特区之外起飞或降落的航班。
- C2/C3事实：2026年8月4日，持有美国航空承运人运行合格证的远海航空从七个计划空乘排班中选择两个。各机型基础空乘人数为4；A为13小时、4人、休10小时；B为15小时、5人、休12小时，C为15小时、4人、休12小时；D为17小时、6人、休12小时，E为17小时、5人、休12小时；F、G均为19小时、7人、休12小时，F含域外航班，G全部航班只在48个相邻州及哥伦比亚特区内起降。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：计划空乘值勤超过14小时且不超过16小时时，须比运行规格规定的最低编制至少多1名空乘；超过16小时且不超过18小时时，至少多2名。超过18小时且不超过20小时时，除至少多3名外，值勤期还须包含在48个相邻州及哥伦比亚特区之外起飞或降落的航班。14小时及以下值勤后至少连续休息10小时，14至20小时值勤后通常至少连续休息12小时。
- 纳入证据：`E1, E2, E3, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E3"],"geographic_scope":["E3"],"object_scope":["E1","E2","E3","E5"],"obligations":["E1","E2","E3","E5"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":["E1","E2","E3","E5"]}`。
- Patch：`roster_c_15h_requires_extra_attendant, roster_e_17h_requires_second_extra_attendant, roster_g_19h_requires_external_flight`。
- 风险：`无`。
- 复核说明：三个Patch分别对应15小时少一名、17小时少第二名、19小时缺少域外航班；休息条件用于确认保留排班。

### SWOR-R038

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，云港航空为美国国内航班选择一段空乘值勤、编制包和随后休息。机型基础空乘人数为4，编制包M安排5人、E安排6人；若选择15小时值勤并把休息缩短为t=0至10小时，下一段10小时值勤排在t=10至20小时，随后连续14小时休息排在t=20至34小时。
- C2/C3事实：2026年8月4日，云港航空为美国国内航班选择一段空乘值勤、编制包和随后休息。机型基础空乘人数为4，编制包M安排4人、E安排5人；若选择15小时值勤，题列10小时休息从t=0开始，而从t=10起的后续72小时排班中没有任何连续14小时休息。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：国内、旗运或补充运行中，计划空乘值勤超过14小时且不超过16小时时，须比运行规格规定的最低编制至少多1名。超过14小时且不超过20小时的值勤后通常至少应有连续12小时休息；这一休息可缩短为连续10小时，但必须另有连续14小时休息，并在缩短休息开始后24小时内开始，而且在该24小时内不得再安排超过14小时的值勤。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E4"],"geographic_scope":["E3"],"object_scope":["E1","E2","E4"],"obligations":["E1","E2","E4"],"regulated_subject":["E1","E3"],"threshold_and_equality":["E1","E2","E4"]}`。
- Patch：`duty15_requires_extra, duty15_requires_rest12`。
- 风险：`无`。
- 复核说明：C1具备完整10小时缩短休息、后续短值勤和14小时补偿时序；C2没有补偿休息。

### SWOR-R039

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，北桥通信作为非BT英国小型通信提供商选择两个零售托管包。A至F均只在公司封闭客户专网内传输，没有呼叫在公共交换电话网发起或终止，服务不分配公共号码，也没有与其他英国网络互联的技术接口或请求。
- C2/C3事实：2026年8月4日，北桥通信作为非BT英国小型通信提供商选择两项公共零售服务。A为可跨英国网络互拨的固定语音，B为可跨网互拨的移动语音，C使用070号码并收发英国固定或移动网络来话；D至F只传数据。其他英国网络已分别为A、B、C提交本期生效的书面互联请求，公司没有其他协商人员、流程或技术实施设施。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：来话终止是电话公司把其他网络的来话连接到本公司客户的服务，是英国固定、移动和070个人号码跨网收发呼叫所必需的。公共电子通信网络的提供商提出请求时，相关提供商应在请求范围内与其协商，以在合理期间内缔结或修改互联协议。数据服务或完全封闭、没有跨公共网络呼叫的专网业务不因这一定义本身产生通话互联需求。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E2"],"regulated_subject":["E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`fixed_voice_requires_interconnection_gateway, mobile_voice_requires_interconnection_gateway, personal_070_requires_interconnection_gateway`。
- 风险：`无`。
- 复核说明：A、B、C分别是固定、移动和070跨网通话且均有书面请求，共享互联包是题内唯一协商和实施资源。

### SWOR-R040

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，SignalHarbor Compliance从八个已排期退订响应包中承接三个。A、B为包裹配送通知且均在请求后第6个工作日前停止；C为服刑人员collect call计费安排通知、D为金融机构欺诈通知，二者收到请求时立即停止；E医疗提醒立即停止；F、G传真广告均在请求后第30天停止；H包裹通知第5个工作日停止。
- C2/C3事实：2026年8月4日，SignalHarbor Compliance从八个已排期退订响应包中承接三个。A、B为包裹配送通知，分别在请求后第7和第6个工作日停止；C为服刑人员collect call计费安排通知、D为金融机构欺诈通知，均在请求次日停止；E医疗提醒立即停止；F、G传真收件人均通过通知列明号码提交停止请求，系统记录接收日期和号码，二者分别在第30和31天停止；H包裹通知第5个工作日停止。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：传真广告发送方收到符合条件的停止请求后，应在从请求日起最短合理时间且不超过30天内执行，并在收件人后来重新明示邀请或许可前停止发送。包裹配送公司应提供退订方式，并在请求日起合理时间且不超过6个工作日内执行。服刑人员collect call服务提供商、金融机构和医疗服务提供者收到相应退订请求后，应立即执行。
- 纳入证据：`E1, E2, E3, E4, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2","E3","E4","E5"],"obligations":["E1","E2","E3","E4","E5"],"regulated_subject":["E1","E2","E3","E4","E5"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`required_preparation_a, required_preparation_c, required_preparation_d, required_preparation_g`。
- 风险：`无`。
- 复核说明：A超过包裹6工作日上限，C/D没有立即停止，G超过传真30天上限；其余响应包与规则一致。

### SWOR-R041

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日（星期二），新加坡海峡联航为三项由外国国家航空器执行的非定期飞行选择樟宜机场或实里达机场时段。F1、F2、F3分别持有覆盖候选机场及时段的外交许可，其他飞行许可材料齐全。
- C2/C3事实：2026年8月4日（星期二），新加坡海峡联航为三项非定期飞行选择樟宜机场或实里达机场时段。F1是在导航设备维护后执行的雷达与NAVAID校验飞行，F2用于转送一名生命垂危的病人，F3由商业包机公司按国防供应合同运送军用备件且飞机不由军方所有或运营；实里达机场候选C为09:45，樟宜协调团队本轮不再受理新的SCR或GCR申请。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：樟宜机场的定期和非定期商业或非商业飞行原则上须在运行前取得时刻；紧急、外交、军方实际运营、人道医疗和雷达或导航校验飞行可以免办，但军方以商业方式包租的航班不属于军方例外。实里达机场每周二至周日09:30至10:30为训练飞行时段，非训练飞行不得进入；该时段仅对紧急、外交及涉及生命安全的人道医疗飞行开放例外。
- 纳入证据：`E1, E2, E3, E4, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2","E3","E5"],"geographic_scope":["E1","E4"],"object_scope":["E2","E3","E4","E5"],"obligations":["E1","E4"],"regulated_subject":["E1","E2","E3","E5"],"threshold_and_equality":["E4"]}`。
- Patch：`F1_not_seletar_training_period, F3_not_seletar_training_period, F3_no_closed_changi_slot_window`。
- 风险：`DUPLICATE_QUOTE_DISTINCT_NODES, MULTI_BRANCH_EXCEPTION`。
- 复核说明：E2与E3虽引用相同原文但承担不同飞行分支，均保留；事实段去除了许可规则结论，只陈述飞行性质、运营方式、时点和申请窗口。

### SWOR-R042

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，山河公用事业公司为北区、东区和西区三个应急站规划2027年8月至11月30日连续运行的路由器。A至E均为美国境内生产的RiverLink RL系列，五个型号均未出现在2026年6月采购档案所附的具名型号清单中。
- C2/C3事实：2026年8月4日，山河公用事业公司为北区、东区和西区三个应急站规划2027年8月至11月30日连续运行的路由器。A为Netgear Nighthawk RAX系列，B为Adtran Service Delivery Gateway，C为Arcadyan制造的Verizon CE1000A，D为美国境内生产的RiverLink RL-8，E为外国生产的Pioneer PX-5；E没有国防部或国土安全部的条件批准，A、B、C的批准期限分别以2026年6月采购附件所列日期为准。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年3月23日起，外国生产的路由器进入受限设备范围，已获美国国防部或国土安全部条件批准的型号除外。Netgear Nighthawk RAX系列和Adtran Service Delivery Gateway的列名批准期均为2026年4月14日至2027年10月1日；Arcadyan制造的Verizon CE1000A批准期为2026年6月12日至2027年12月12日。美国境内生产的路由器不落入该外国生产边界。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2","E3","E4"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3","E4"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E2","E3","E4"]}`。
- Patch：`bar_unapproved_north, bar_unapproved_east, bar_unapproved_west, pre_expiry_concentration_cap`。
- 风险：`TEMPORARY_APPROVAL_DATE_BRANCHES`。
- 复核说明：规则材料保留三个具名型号的不同到期日，供题内连续运行风险政策判断；未把采购结果或设备分配写入规则段。

### SWOR-R043

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，蓝岭材料公司的美国非联邦工厂规划2028年7月1日开始的五类化工作业。订单A至E分别使用丙酮、乙醇、异丙醇、正庚烷和乙酸乙酯，均不含四氯乙烯。
- C2/C3事实：2026年8月4日，蓝岭材料公司的美国非联邦工厂规划2028年7月1日开始的五类化工作业。订单A以四氯乙烯生产制冷剂中间体，B使用四氯乙烯蒸气脱脂，C进行有限实验室分析，D使用四氯乙烯清洗带电设备，E调配含四氯乙烯的消费级制动清洁剂。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年9月9日起，四氯乙烯及含该物质产品的加工原则上禁止；可在严格工作场所控制下继续的工业商业用途构成有限例外。用于生产其他化学品或制冷剂以及蒸气脱脂时须采用工作场所化学防护方案；实验室用途须采用规定式工作场所控制；带电设备清洗可采用上述防护方案或规定式控制。消费产品加工不属于这些继续使用分支。
- 纳入证据：`E1, E2, E3, E4, E5, E6`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1","E2","E3","E4","E5","E6"],"geographic_scope":["E1"],"object_scope":["E1","E3","E4","E5","E6"],"obligations":["E1","E2","E3","E4","E5","E6"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1"]}`。
- Patch：`bar_consumer_product, refrigerant_requires_wcpp, degreasing_requires_wcpp, laboratory_requires_prescriptive, electrical_allows_either_control`。
- 风险：`MULTI_BRANCH_CHEMICAL_USE`。
- 复核说明：五种用途分别绑定禁止、两类防护方案与可替代控制分支；未把订单选择或控制单元变量写入规则材料。

### SWOR-R044

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，河城电力企业在俄亥俄州销售零售电力，但不拥有或运营配电系统，也不维护托管容量地图；Q1至Q4是企业可自愿发布的季度透明度更新。
- C2/C3事实：2026年8月2日，河城电力企业在俄亥俄州运营配电系统并维护一张对公众开放的托管容量地图；Q1至Q4分别表示该地图在四个季度的公开更新次数。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：俄亥俄州每一家电力配送公用事业公司最迟须在2026年5月31日前制作并公开配电系统托管容量地图，将地图放在本公司网站上，并保证每个季度至少更新一次。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`quarter_1_update, quarter_2_update, quarter_3_update, quarter_4_update`。
- 风险：`无`。
- 复核说明：主体门、公开方式、截止日期和逐季度下界均由同一完整引文支持。

### SWOR-R045

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，海岬冷链公司规划其2027年美国制冷设施网络。A、B、D、F的满充注量分别为1600、1600、1700、1800磅且制冷剂GWP均为1；C为满充注量1490磅、GWP 675的工业工艺制冷机组，E为满充注量1700磅、GWP 675的办公楼舒适制冷机组，安装日期均以设备台账为准。
- C2/C3事实：2026年8月4日，海岬冷链公司规划其2027年美国制冷设施网络。A是2026年2月安装的密闭商业冷藏机组，满充注量1600磅、GWP 1430；B是2026年3月安装的开放式商业冷藏机组，1600磅、GWP 1；C是2026年5月安装的工业工艺制冷机组，1490磅、GWP 675；D是2015年8月安装的工业工艺制冷机组，1700磅、GWP 675；E是2026年4月安装的舒适制冷机组，1700磅、GWP 675；F是2019年9月安装的工业工艺制冷机组，1800磅、GWP 675。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：商业冷藏或工业工艺制冷机组只有同时满足满充注量不少于1500磅、制冷剂GWP高于53，并且在2026年1月1日或之后安装，或属于2017年1月1日及之后安装的既有设备时，才须安装并使用自动检漏系统。2017年1月1日至2026年1月1日前安装的既有机组最迟须于2027年1月1日启用该系统。直接式和间接式系统均可接受，一套系统可以监测多台机组。
- 纳入证据：`E3, E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`new_appliance_a_needs_shared_ald, legacy_appliance_f_needs_shared_ald`。
- 风险：`MULTI_HOP, TEMPORAL_INSTALLATION_BRANCHES, FACT_LABEL_REMOVED`。
- 复核说明：规则材料保留用途、充注量、GWP、安装时点和既有设备期限五个判断轴，并说明共享监测能力。

### SWOR-R046

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，GreenDelta是一家只采购已收获番茄、葡萄、甜菜、马铃薯和草莓原料并进行下游食品加工的独立企业，不参与这些农产品的种植、采收、包装或持有。D、E、F分别把对应原料制成常温稳定番茄酱、葡萄酒和糖，并提供随货披露及2026年度客户书面保证；H的草莓全部供经营者家庭食用。
- C2/C3事实：2026年8月4日，GreenDelta在美国经营种植、采收、包装并持有农产品的农场网络。A、B、C在未选择对应D、E、F时分别把番茄、葡萄和甜菜作为生鲜农产品销售；D、E、F把全部对应产出制成常温稳定番茄酱、葡萄酒和糖，并提供随货披露及2026年度客户书面保证；G经营马铃薯，H的草莓全部供经营者家庭食用。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：在农场种植、采收、包装或持有受覆盖农产品属于受管活动。极少生食的列明农产品包括马铃薯，个人为自己消费而生产的农产品也在排除范围。番茄制成番茄酱或常温稳定番茄制品，以及葡萄制酒、甜菜制糖等能充分降低公共卫生微生物的商业加工，可进入加工分支，但经营者须在随货文件中作相应披露，并每年取得客户书面保证；未进入这些排除或加工分支的生鲜番茄、葡萄和甜菜仍须执行完整的种植、采收、包装和持有控制。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7, E8, E9, E10`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E2","E3","E4","E5","E6","E7","E8","E9"],"geographic_scope":["E10"],"object_scope":["E1","E2","E3","E4","E5","E6","E7"],"obligations":["E8","E9","E10"],"regulated_subject":["E10"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`a_processing_or_full_rule, b_processing_or_full_rule, c_processing_or_full_rule`。
- 风险：`MULTI_HOP, TEN_EVIDENCE_NODES, PROCESSING_EXCEPTION_CHAIN, FACT_LABEL_REMOVED`。
- 复核说明：十个节点均保留：E1至E4覆盖对象排除，E5至E9闭合商业加工、披露和年度保证，E10给出农场活动主体边界。

### SWOR-R047

- V1.6.2：已按用户授权定点修复，等待本版全量检查；下述旧复核说明为历史记录，不代表新审查通过。
- C1事实：2026年8月4日，Northbank美国国民银行拟为自营账户买入公司债券。本题交易尽调档案确认：Raven Holdings、Sable Ventures和Tern Industries在决策日均为财产权益已被冻结的主体；Raven与Sable各持Alder 24%，Raven持Birch 49%，Raven持Cedar 49%且Cedar分别持Dune和Ember 49%，Raven与Tern分别持Fjord 29%和20%，Alder持Gale 50%，Sable持Harbor 30%，Raven与Sable分别持Iris 25%和24%，Juniper无上述直接或间接持股。
- C2/C3事实：2026年8月4日，Northbank美国国民银行拟为自营账户买入公司债券。本题交易尽调档案确认：Raven Holdings、Sable Ventures和Tern Industries在决策日均为财产权益已被冻结的主体；Raven与Sable各持Alder 25%，Raven持Birch 49%并控制董事会，Raven持Cedar 60%且Cedar分别持Dune 50%和Ember 49%，Raven与Tern分别持Fjord 30%和20%，Alder持Gale 50%，Sable持Harbor 30%并控制董事会，Raven与Sable分别持Iris 25%和24%，Juniper无上述直接或间接持股；所有候选交易均无单独许可证或授权。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：一个或多个财产权益被冻结的人直接或间接、单独或合计持有某实体50%或以上权益时，该实体本身未列名也按冻结实体处理，其财产权益同样受限。合计持股低于50%时，仅有董事会控制等控制关系不会因该50%所有权标准自动使实体被冻结，除非另有独立禁止；计算时须沿直接和间接持股链合并。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`blocked_issuer_buy_alder_bond, blocked_issuer_buy_cedar_bond, blocked_issuer_buy_dune_bond, blocked_issuer_buy_fjord_bond, blocked_issuer_buy_gale_bond`。
- 风险：`MULTI_HOP, INDIRECT_OWNERSHIP_AGGREGATION`。
- 复核说明：规则段保留50%等号边界、跨主体合计和间接持股，并明确低于50%时控制本身不自动触发。

### SWOR-R048

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，资本和盈余为1亿美元的Meridian Bank是一家美国州立非会员银行，拟为自营账户从十二个不可拆分证券包中采用五个。A/B来自同一Alpha义务人，C/D来自同一Theta发行人，E至H来自四个不同义务人且均可销售但不符合投资级要求，银行分别形成了基于可靠估计的履约判断；I为美国政府Type I证券，J/K为不同发行人的Type IV证券，L为另一义务人的Type III证券。
- C2/C3事实：2026年8月4日，资本和盈余为1亿美元的Meridian Bank是一家美国国民银行，拟为自营账户从十二个不可拆分证券包中采用五个。A/B分别是同一Alpha义务人的Type II和Type III证券，C/D是同一Theta发行人的Type V证券，E至H来自四个不同义务人且均可销售但不符合投资级要求，银行分别形成了基于可靠估计的履约判断；I为美国政府Type I证券，J/K为不同发行人的Type IV证券，L为另一义务人的Type III证券，且银行没有相关既有持仓或未履行承诺。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：美国国民银行持有同一义务人的Type II与Type III证券时，合计票面价值不得超过资本和盈余的10%；持有同一发行人的Type V证券不得超过资本和盈余的25%。可销售但未达到通常投资级要求的债务证券，只有银行基于其合理认为可靠的估计认定义务人能够履约时，才可作为投资证券处理，且所有经该路径处理的证券票面价值合计不得超过资本和盈余的5%。
- 纳入证据：`E3, E2, E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E3"],"geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1","E2","E3"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":["E1","E2","E3"]}`。
- Patch：`alpha_combined_type_ii_iii_limit, theta_type_v_issuer_limit, estimated_performance_securities_aggregate_limit`。
- 风险：`MULTI_HOP, MULTIPLE_PERCENTAGE_CAPS`。
- 复核说明：三个独立百分比上限均保留等号边界；可靠履约估计是5%聚合分支的前置条件。

### SWOR-R049

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，银湾影像中心的非临床实验室只对设备做台架研究，不为人体患者提供乳腺摄影检查。A为新安装设备，C在原址拆卸后重装，D安装了软件升级；B、E、F未经历安装、拆装、主要部件维修或软件变更，题列评估时段均由医学物理师执行并可在设备投入计划用途前纠正问题。
- C2/C3事实：2026年8月4日，银湾影像中心准备把乳腺摄影设备和影像处理器恢复用于患者检查。A为新安装设备，C在原址拆卸后重装，D安装了软件升级；B、E、F未经历安装、拆装、主要部件维修或软件变更，题列评估时段均由医学物理师执行并可在患者使用前纠正问题。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：用于患者乳腺摄影检查的设备或影像处理器在安装、拆卸后重新组装，或者主要部件发生更换或维修后，须追加设备评估；软件变更或升级按主要维修处理。评估应由医学物理师或其直接监督下的人员执行，所有未达到标准的问题必须在受影响设备用于患者检查前纠正。
- 纳入证据：`E1, E2, E3, E4, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E4","E5"],"obligations":["E1","E2","E3","E4","E5"],"regulated_subject":["E1","E5"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`new_install_a_requires_mee, reassembled_c_requires_mee, software_upgrade_d_requires_mee`。
- 风险：`SOFTWARE_AS_MAJOR_REPAIR`。
- 复核说明：设备变化、评估执行者、纠正义务和患者使用前时点均闭合；未将非临床实验室直接表述为法律结论。

### SWOR-R050

- V1.6.2：已按用户授权定点修复，等待本版全量检查；下述旧复核说明为历史记录，不代表新审查通过。
- C1事实：2026年8月4日，密歇根州湖湾健康计划为一名参保人选择负责2026年8月10日至8月16日护理服务的居家护理机构。该患者的护理计划预定于8月7日建立，QCN Home Care、Quality Care Nursing、Amedisys Home Health、CenterWell Home Health、Elara Caring和Residential Home Health六家的所在地许可、服务区域、排班和服务能力材料齐全。
- C2/C3事实：2026年8月4日，密歇根州湖湾健康计划为一名参保人选择负责2026年8月10日至8月16日护理服务的居家护理机构。该患者的护理计划预定于8月8日建立，QCN Home Care、Quality Care Nursing、Amedisys Home Health、CenterWell Home Health、Elara Caring和Residential Home Health六家的所在地许可、服务区域、排班和服务能力材料齐全。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：QCN Home Care位于密歇根州Troy的居家护理机构协议自2026年8月8日起终止；对于治疗计划在2026年8月8日或之后建立的患者，相关项目不为该机构提供的居家护理服务付款。对于治疗计划在2026年8月8日之前建立的患者，终止之后提供的符合付款条件的服务可继续获得最多30天的付款。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`qcn_unavailable_for_new_plan`。
- 风险：`FACT_LABEL_REMOVED, DATE_BOUNDARY`。
- 复核说明：严格保留“on or after August 8”的等号边界，并区分护理计划建立日与服务开始日。

### SWOR-R051

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，亚利桑那州远峰晶圆材料厂拟采购两个光刻胶用光酸发生剂批次用于后续生产。六批材料只在全封闭系统内分装，不产生粉尘、雾或气溶胶，并以溶液形态装在5千克以下密封容器中；A和B分别为题列两种具体化学身份，C至F的取代基、反离子、环卤化或锍结构均与A、B不同。
- C2/C3事实：2026年8月4日，亚利桑那州远峰晶圆材料厂拟采购两个光刻胶用光酸发生剂批次用于后续生产。六批材料均在同类非封闭设备中分装且过程产生气溶胶，此前没有完成该分装流程的外部审查；A为heteroonium, tri(substitutedaromatichydrocarbon)-, nitrate (1:1)，B为sulfonium, triphenyl-, salt with heterosubstituteddifluorosubstitutedalkyl substitutedalkyl trihalosubstitutedcarbomonocycle carboxylate (1:1)，C至F的化学结构与A、B不同。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年7月28日起，heteroonium, tri(substitutedaromatichydrocarbon)-, nitrate (1:1)以及题列triphenyl sulfonium carboxylate两种特定物质，在非封闭流程中以任何产生粉尘、雾或气溶胶的方式加工，属于须事前通知审查的新增用途。此类制造或加工不得在主管机关完成所需通知审查、作出决定并采取该决定要求的行动之前开始；相同加工状态不会把其他化学身份自动纳入。
- 纳入证据：`E1, E2, E3, E4, E5, E6`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E6"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E3","E6"],"object_scope":["E1","E3"],"obligations":["E2","E4","E5"],"regulated_subject":["E2","E4","E5"],"threshold_and_equality":["E2","E4"]}`。
- Patch：`review_a_if_selected, review_b_if_selected`。
- 风险：`DUPLICATE_QUOTE_DISTINCT_NODES, EXACT_CHEMICAL_IDENTITY`。
- 复核说明：E2与E4原文相同但分别支撑A、B两个精确化学身份，不能按quote去重；C至F不得由加工相似性类推纳入。

### SWOR-R052

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，凤凰城医院药品配送中心持有六个Cyclophosphamide注射剂批次。A、B、C、D均为1克规格、NDC 81298-8112-1，批号依次为C23019V2、C24015V2、C23019V7、C24015V7；E、F为2克规格、NDC 81298-8114-1，批号分别为V24010V7和V24011V1，六批储存与放行状态相同。
- C2/C3事实：2026年8月4日，凤凰城医院药品配送中心持有六个Cyclophosphamide注射剂批次。A、B、C、D均为1克规格、NDC 81298-8112-1，批号依次为C23019V1、C24015V1、C23019V7、C24015V7；E、F为2克规格、NDC 81298-8114-1，批号分别为V24010V7和V24011V1，六批储存与放行状态相同。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：Sunny Pharmtech已召回Cyclophosphamide注射剂批号C23019V1、C24015V1和V24010V1，并组织这些批次的退回、核对和销毁；不在这三个精确批号中的库存不因该公告自动进入退货流程。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`return_a_after_recall, return_b_after_recall`。
- 风险：`EXACT_LOT_MATCH`。
- 复核说明：按完整批号匹配，明确区分V24010V1与题内V24010V7，避免前缀误命中。

### SWOR-R053

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年2月5日，星港重型车辆停车场运营公司持有有效停车场许可，准备处理两份车辆停车证签发订单。A、B、C分别对应集装箱拖车新车注册、低架拖车车辆过户和平板拖车路税续期；D、E、F分别涉及刚性重型货车、牵引车和厢式货车，停车位、车辆和客户材料完整。
- C2/C3事实：2026年8月4日，星港重型车辆停车场运营公司持有有效停车场许可，准备处理两份车辆停车证签发订单。A、B、C分别对应集装箱拖车新车注册、低架拖车车辆过户和平板拖车路税续期；D、E、F分别涉及刚性重型货车、牵引车和厢式货车，停车位、车辆和客户材料完整。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：2026年2月6日至2028年2月5日的两年试行期内，集装箱拖车、低架拖车和平板拖车在新车注册、车辆所有权转移和路税续期时不再需要有效车辆停车证；在该期间，重型车辆停车场运营商也不得为其获许可的拖车停车位签发此类证件。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E2","E3"],"obligations":["E2","E3"],"regulated_subject":["E3"],"threshold_and_equality":["E1"]}`。
- Patch：`container_trailer_order_a_unavailable, low_loader_trailer_order_b_unavailable, flat_bed_trailer_order_c_unavailable`。
- 风险：`DATE_BOUNDARY, TRANSACTION_TYPE_BRANCHES`。
- 复核说明：C1位于试行开始日前一日，C2位于试行期内；规则同时覆盖拖车类别、三类交易和运营商签发边界。

### SWOR-R054

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，银轨车辆制造公司从六个已获对应型式批准的批次中排产三个。A至F完工日期依次为2026年11月28日、11月27日、11月26日、11月25日、11月24日和11月20日；D为GB国家小批量M类，E为GB无限系列L类，B为UKNI欧盟小批量N类，其余类别以排产清单为准。
- C2/C3事实：2026年8月4日，银轨车辆制造公司从六个已获对应型式批准的批次中排产三个。A至F完工日期依次为2026年12月2日、12月3日、11月30日、12月4日、12月5日和11月20日；D为GB国家小批量M类，E为GB无限系列L类，B为UKNI欧盟小批量N类，其余类别以排产清单为准。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：从2026年11月29日起，按GB或UKNI体系批准的新制造M、N、O类车辆须提交电子合格证数据，GB中等批量和UKNI欧盟小批量车辆也在范围内。GB或UKNI国家小批量车辆永久免于强制电子提交，可继续使用纸质合格证；L、T、C、R、S类暂不受该要求约束；在2026年11月29日前制造的车辆也没有提交义务。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E4"],"formal_exceptions":["E2","E3","E4"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2","E3","E4"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1","E4"]}`。
- Patch：`batch_a_requires_shared_ecoc_cell, batch_b_requires_shared_ecoc_cell, batch_c_requires_shared_ecoc_cell`。
- 风险：`DATE_AND_SCHEME_CROSS_PRODUCT`。
- 复核说明：规则段同时保留制造日期、车辆类别、批准体系及国家小批量三类正式边界。

### SWOR-R055

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，岬湾承运人为美国州际运输选择一项货运任务及固定检查服务。A至D均使用铅封货厢，承运指令要求司机不得开封，现有装载方式也使司机无法查看货物；四项里程、驾驶时间、固定装置和装载记录按派车单执行。
- C2/C3事实：2026年8月5日，岬湾承运人为美国州际运输选择一项货运任务及固定检查服务。A、B、D装载普通未封闭货物，司机可以进入货厢查看；C使用铅封货厢，承运指令要求司机不得开封且装载方式使检查不可行；A至D里程分别为40、180、180和320英里，到达题列节点前的驾驶时间均少于3小时。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：卡车或牵引车司机须在行程开始后的前50英里内检查货物及固定装置，并在运输途中每驾驶3小时或150英里两者先到时重新检查和作必要调整。若车辆已铅封且司机被要求不得开启，或装载方式使检查实际不可行，上述途中检查要求不适用。
- 纳入证据：`E2, E1, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E3"],"geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1","E2"],"regulated_subject":["E1","E3"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`unsealed40_requires_first50, unsealed180_requires_two_checks, unsealed320_requires_three_checks`。
- 风险：`MULTI_HOP, RECURRING_DISTANCE_OR_TIME`。
- 复核说明：保留前50英里首次检查、3小时或150英里先到的循环节点，以及铅封与不可检查两类例外。

### SWOR-R056

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，蓝岭接驳公司拟在Blue Ridge Parkway六条当日路线中执行两条。A至F的精确里程闭区间依次为62.0—62.5、286.0—287.0、62.8—63.4、276.6—280.0、66.3—76.4和280.9—285.5，路线均须完整经过对应闭区间且不能绕行。
- C2/C3事实：2026年8月4日，蓝岭接驳公司拟在Blue Ridge Parkway六条当日路线中执行两条。A至F的精确里程闭区间依次为63.4—64.0、274.2—276.6、62.8—63.4、276.6—280.0、66.3—76.4和280.9—285.5，路线均须完整经过对应闭区间且不能绕行。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：国家公园管理局于2025年9月2日发布的公告称，James River Bridge所在63.5至63.9英里路段将在2025年9月9日前后开始关闭，工程预计到2026年秋季完成；因此2026年8月4日仍处于公告覆盖的施工关闭期。另一份2026年7月24日公告称Deep Gap Bridge工程于2026年7月27日开始，269.8至276.5英里之间实施全封闭绕行，预计全封闭持续至当年9月下旬。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`exclude_a, exclude_b`。
- 风险：`IMPLICIT_YEAR_RESOLVED_BY_PUBLICATION_DATE, TWO_CLOSURE_WINDOWS`。
- 复核说明：已独立复核日期歧义。E1 URL=https://www.nps.gov/blri/learn/news/critical-repairs-to-james-river-bridge-begin-on-the-blue-ridge-parkway.htm；新闻稿发布日期为2025-09-02，原文“will close on or around September 9”因而指2025-09-09，且同段写明工程预计到Fall of 2026完成，闭合2026-08-04的A。E2发布日期为2026-07-24，工程自2026-07-27起至9月底全封闭，闭合B。年份必须由发布日期和完工时点共同解释，不能把September 9误补成2026年。

### SWOR-R057

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，一名夜间设施操作服务商以独立企业名义按项目开票、自备设备、独立安排人员并可同时服务其他客户，自行选择在松港公用事业公司的候选时段留在设施。四个计划依次为23小时且实际睡眠6小时；24小时且有书面睡眠时段排除协议、排定8小时但报警后实际睡眠6小时；26小时且有同类协议、排定8小时但实际睡眠4小时；24小时且没有明示或默示排除协议、实际睡眠8小时，四处均有安静独立的睡眠房间。
- C2/C3事实：2026年8月4日，松港公用事业公司要求一名按小时计薪、执行设施操作且不承担管理或专业决策职责的雇员留在值守设施。四个计划依次为23小时且实际睡眠6小时；24小时且有书面睡眠时段排除协议、排定8小时但报警后实际睡眠6小时；26小时且有同类协议、排定8小时但实际睡眠4小时；24小时且没有明示或默示排除协议、实际睡眠8小时，操作员不长期居住在值守场所，四处均有安静独立的睡眠房间。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：雇员被要求连续值勤少于24小时时，即使获准睡眠或从事个人活动，全部时间仍计为工作。值勤24小时或以上时，只有雇主与雇员达成协议、提供适当睡眠设施且通常能享受不受打扰的睡眠，才可排除不超过8小时的固定睡眠期；因工作召回中断的时间须计入，实际睡眠不足5小时时整段睡眠期均计为工作。没有明示或默示排除协议时，睡眠和用餐时间全部计为工作。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2","E3","E4"],"geographic_scope":["E1","E2","E3","E4"],"object_scope":["E1","E2","E3","E4"],"obligations":["E1","E2","E3","E4"],"regulated_subject":["E1","E2","E3","E4"],"threshold_and_equality":["E1","E2","E4"]}`。
- Patch：`duty23_forbids_pay16, duty23_forbids_pay18, duty23_forbids_pay22, duty24_interrupted_sleep_forbids_pay16, duty26_under5_sleep_forbids_pay16, duty26_under5_sleep_forbids_pay18, duty26_under5_sleep_forbids_pay22, duty26_under5_sleep_forbids_pay24, duty24_no_agreement_forbids_pay16, duty24_no_agreement_forbids_pay18, duty24_no_agreement_forbids_pay22`。
- 风险：`LARGE_PATCH, SLEEP_TIME_BRANCHES, EMPLOYMENT_STATUS_CHANGE`。
- 复核说明：11个Patch name全部覆盖；规则材料明确少于24小时、24小时以上协议、召回中断、5小时下界和无协议五个分支。

### SWOR-R058

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2024年7月15日，一家铁路运营方为三条专用旅游、观光、历史或游览列车线路选择乘务人数及后续动作。A自2023年1月起按同一范围连续运行，并在2024年6月24日前提交继续单人运行的书面通知；B、C为计划新增服务，三条线路均只用于旅游列车。
- C2/C3事实：2024年7月15日，一家Class I铁路公司为美国一般铁路系统上的三条货运线路选择乘务人数及后续动作。A自2023年1月起按同一范围连续运行，并在2024年6月24日前提交继续单人运行的书面通知；B、C此前从未运营，分别计划于2026年10月和11月首次开行。
- C3规则材料：在2024年7月15日的决策时点，下述规则处于有效期：列车乘务人数制度自2024年6月10日起生效：继续某些既有单人乘务运营与启动新增单人乘务运营适用不同批准路径；既有运营的特别批准申请最迟须在2024年8月7日前提交，新增运营须在启动前取得特别批准。铁路对每一项获得特别批准的单人乘务运营还须提交年度安全报告。仅在专用于旅游、观光、历史或游览列车且不属于一般铁路运输系统的线路上运行时，单人旅游列车可不受这些要求约束。
- 纳入证据：`E2, E4, E3, E1, E5, E6`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2","E4"],"formal_exceptions":["E5","E6"],"geographic_scope":["E5","E6"],"object_scope":["E1","E3","E5","E6"],"obligations":["E1","E2","E3"],"regulated_subject":["E1","E5","E6"],"threshold_and_equality":["E2"]}`。
- Patch：`a_existing_one_requires_continuation, a_not_new_special_path, a_continuation_requires_report, b_not_existing_path, b_new_one_requires_special, b_special_requires_report, c_not_existing_path, c_new_one_requires_special, c_special_requires_report`。
- 风险：`MULTI_HOP, LARGE_PATCH, EXISTING_VS_NEW_OPERATION, TOURIST_EXCEPTION`。
- 复核说明：九个Patch分别覆盖A既有路径、B/C新增路径及三个年度报告后果；旅游线路定义和排除节点仍保留以闭合C1。

### SWOR-R059

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，新加坡海岬通信器材公司持有电信经销商执照和两个当前申报名额。A为5G蜂窝移动终端，B为GMPCS终端，C为电缆调制解调器，D为LTE蜂窝移动终端，E为ADSL调制解调器，F为同轴电缆家庭联网设备；六项均附供应商符合性声明和有效EU型式检验证书。
- C2/C3事实：2026年8月4日，新加坡海岬通信器材公司持有电信经销商执照和两个当前申报名额。A为5G蜂窝移动终端，B为GMPCS终端，C为电缆调制解调器，D为工业UWB资产标签，E为企业PABX设备，F为陆地移动无线电设备；六项均附供应商符合性声明和有效EU型式检验证书。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：简化设备注册要求提交符合相关技术规范的自我声明和有效EU型式检验证书，且设备必须属于封闭列举类别，包括3G、LTE或5G蜂窝移动终端、GMPCS终端、ADSL调制解调器、电缆调制解调器及同轴电缆家庭联网设备。工业UWB资产标签、企业PABX和陆地移动无线电设备不在该列举范围；缺少EU证书或需要审查实验室报告时应走一般设备注册路径。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1","E2"],"object_scope":["E2"],"obligations":["E1","E2"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`model_d_outside_ser_scope, model_e_outside_ser_scope, model_f_outside_ser_scope`。
- 风险：`CLOSED_EQUIPMENT_CATEGORY_LIST`。
- 复核说明：设备身份与文档条件分别处理；未因文档齐全把列表外设备误纳入。

### SWOR-R060

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，云桥呼叫中心只为本集团员工提供内部无障碍来话协助，不向公众或州际用户提供传统文本中继或视频中继服务。每100通构成完整月度样本，不存在网络故障，题列快速传统来话均被立即接通而非排队或保持。
- C2/C3事实：2026年8月5日，云桥呼叫中心持有FCC认证并向州际用户提供传统文本中继和视频中继服务。每100通构成完整月度样本，不存在网络故障，题列快速传统来话均被立即接通而非排队或保持。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：除网络故障期间外，传统文本中继设施须使全部来话中至少85%在10秒内以立即接通且不进入队列或保持的方式得到应答。视频中继提供商按月计算时，须使全部视频中继来话中至少80%在120秒内得到应答。两类服务分别适用各自的百分比和时间门槛。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`voice70_requires_voice_capacity, vrs76_requires_vrs_capacity`。
- 风险：`MULTI_HOP, MULTIPLE_OPTIMA_BOUNDARY, DISTINCT_SERVICE_QUOTAS`。
- 复核说明：传统和视频来话分别保留85%/10秒与80%/120秒门槛；传统分支明确网络故障例外和立即接通口径。

### SWOR-R061

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，波士顿北湾酒店工程部为两名技师分配四盏尚未安装的Currey & Company Nottaway吊灯。A至D型号依次为9000-1128、9000-1129、9000-1253和9000-1130，每盏灯顶部分配器盖外侧均有一枚清晰可见的螺钉。
- C2/C3事实：2026年8月4日，波士顿北湾酒店工程部为两名技师分配四盏尚未安装的Currey & Company Nottaway吊灯。A至D型号依次为9000-1128、9000-1129、9000-1253和9000-1130，每盏灯顶部分配器盖外侧均看不到螺钉。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：Currey & Company Nottaway吊灯型号9000-1129、9000-1130、9000-1254、9000-1255和9000-1314在顶部分配器盖外侧没有可见螺钉时属于召回对象；受影响吊灯应停止使用，并由厂家免费更换且包含安装服务。型号或外观条件任一不匹配时，不因该公告自动进入更换流程。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`recalled_job_b_requires_replacement, recalled_job_d_requires_replacement`。
- 风险：`MODEL_AND_VISIBLE_SCREW_CONJUNCTION`。
- 复核说明：召回由型号与外侧螺钉不可见共同决定，避免把A或C按系列名称误命中。

### SWOR-R062

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，芝加哥镜湖酒店从四盏尚未安装的库存灯具中为宴会厅和大堂各分配一盏。A至D均为Minka Bardon N1844-776，保持原包装，电气容量、风格和施工工期记录与两个房间的施工单一致。
- C2/C3事实：2026年8月4日，芝加哥镜湖酒店从四盏尚未安装的库存灯具中为宴会厅和大堂各分配一盏。B与D分别是最初购入且没有厂家处置完成记录的N1847-776和N1848-776，A与C为N1844-776；四盏均保持原包装，电气容量、风格和施工工期记录与两个房间的施工单一致。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：Minka Bardon型号N1847-776、N1848-776和N1849-776灯具属于召回范围，使用者应停止使用并联系厂家退款。N1844-776为不使用downrod的4-Light Semi Flush灯具，公告明确其不受影响。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_recalled_ballroom_b, exclude_recalled_lobby_b, exclude_recalled_ballroom_d, exclude_recalled_lobby_d`。
- 风险：`ROOM_ASSIGNMENT_EXPANSION, EXPRESS_MODEL_EXCLUSION`。
- 复核说明：同一召回型号须在两个房间匹配边上同时排除；N1844-776的明示排除保留。

### SWOR-R063

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，澄川工业集团从四座美国自有设施中选择下一年度运营对象。A至D的源清单均只记录固定燃烧锅炉，总额定热输入依次为24、25、26和29 mmBtu/小时，年度排放依次为18,000、20,000、23,000和24,000吨CO2e；四座均由集团自营，不供应或进口燃料或温室气体。
- C2/C3事实：2026年8月5日，澄川工业集团从四座美国自有设施中选择下一年度运营对象。A运营己二酸生产线；B运营铁合金生产线且年度排放27,000吨CO2e；C只运行固定燃烧锅炉，总额定热输入35 mmBtu/小时、年度排放27,000吨CO2e；D只运行固定燃烧锅炉，总额定热输入24 mmBtu/小时、年度排放18,000吨CO2e；四座均由集团自营且不供应或进口燃料或温室气体。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：设施含有Table A-3列明源类别时，年度报告须覆盖固定燃烧、碳酸盐使用及全部适用的A-3和A-4源类别；己二酸生产属于A-3。设施含有A-4源类别且固定燃烧、碳酸盐使用及全部适用A-3/A-4源类别的合计年排放达到25,000吨CO2e时，也须按上述全源范围报告；铁合金生产属于A-4。既不进入A-3也不进入A-4分支的设施，只有固定燃烧总额定热输入不少于30 mmBtu/小时且固定燃烧年排放不少于25,000吨CO2e时，才须仅报告固定燃烧源。
- 纳入证据：`E2, E1, E3, E4, E5, E6, E7`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3","E4","E5","E6","E7"],"obligations":["E1","E2","E3"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":["E2","E3"]}`。
- Patch：`a3_requires_all_report, a3_requires_enterprise_monitor, a4_threshold_requires_all_report, a4_threshold_requires_enterprise_monitor, combustion_branch_requires_combustion_report, combustion_branch_requires_meter`。
- 风险：`MULTI_HOP, SEVEN_EVIDENCE_NODES, THREE_REPORTING_BRANCHES`。
- 复核说明：A-3、带25,000吨门槛的A-4、以及30 mmBtu/小时且25,000吨的固定燃烧分支均闭合；监测包与报告包的唯一能力映射仍由优化骨架给出。

### SWOR-R064

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，持联邦船舶许可的海湾蓝线公司规划两次由付费游客带走鱼获的2027年墨西哥湾航次。A至F依次为7月5日scamp与yellowmouth grouper、7月10日black grouper与red grouper、4月15日gag与red grouper、7月10日yellowfin grouper与red grouper、2月20日red grouper与gag、8月5日scamp与black grouper；许可、渔具、尺寸和数量记录完整。
- C2/C3事实：2026年8月4日，持联邦船舶许可的海湾蓝线公司规划两次由付费游客带走鱼获的2027年墨西哥湾航次。A至F依次为2月5日scamp与yellowmouth grouper、3月10日black grouper与red grouper、4月15日gag与red grouper、7月10日yellowfin grouper与red grouper、2月20日red grouper与gag、8月5日scamp与black grouper；许可、渔具、尺寸和数量记录完整。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：墨西哥湾Other SWG复合体由scamp、yellowmouth grouper、black grouper和yellowfin grouper四个鱼种组成，按复合体统一管理。该复合体的休闲捕捞每年1月1日至6月30日关闭，7月1日至12月31日开放；2027年度同样于1月1日关闭并于7月1日重开。一个航次只要包含复合体内任一鱼种，即按该航次日期判断。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2","E3"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2","E3","E4"],"object_scope":["E1","E4"],"obligations":["E2","E3"],"regulated_subject":["E2","E3"],"threshold_and_equality":["E2","E3"]}`。
- Patch：`closed_complex_winter_spring_trips`。
- 风险：`SPECIES_COMPLEX_AND_DATE`。
- 复核说明：规则材料只列官方复合体四鱼种，并保留1月1日和7月1日两个日期边界。

### SWOR-R065

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，青穹注入项目公司从科罗拉多、新墨西哥、蒙大拿、亚利桑那、得克萨斯和路易斯安那六个场站中启动两个。六站均为向含油层注入二氧化碳以提高采收率的Class II井，各自使用现有且当前有效的许可证，本轮没有新申请、修改或转移请求，也没有许可资料工单。
- C2/C3事实：2026年8月4日，青穹注入项目公司从科罗拉多、新墨西哥、蒙大拿、亚利桑那、得克萨斯和路易斯安那六个场站中启动两个。六站均为长期地质封存二氧化碳的新建Class VI井，项目不在部落土地，也没有已转移的历史许可。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：新建Class VI井所在州、领地或部落取得该井类的主要执行权时，由相应州、领地或部落机构发证；未取得时由美国环保署区域办公室直接审查申请并作出许可决定。现行分工中，科罗拉多、蒙大拿和新墨西哥的Class VI由环保署区域办公室实施，亚利桑那、得克萨斯和路易斯安那由州级机构实施。
- 纳入证据：`E2, E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E2"],"regulated_subject":["E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`site_colorado_requires_hq_team, site_new_mexico_requires_hq_team, site_montana_requires_hq_team`。
- 风险：`MULTI_HOP, STATE_BY_STATE_PRIMACY`。
- 复核说明：六州分工由现行官方表逐州闭合；总部资料团队是否为直接审查路径的唯一能力仍来自题内事实。

### SWOR-R066

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月17日，澄居住宅基金责任主体拟在英格兰北区、中区和南区各选择一栋低于11米的多住户住宅申请外墙修复资金。Ash Court、Birch House、Cedar Court、Dale House、Elm Court和Fern House的现场物理施工分别始于2026年7月9日、7月10日、7月10日、7月9日、7月11日和7月10日；每栋至少有两套住宅并有FRAEW生命安全风险报告。
- C2/C3事实：2026年8月17日，澄居住宅基金责任主体拟在英格兰北区、中区和南区各选择一栋低于11米的多住户住宅申请外墙修复资金。Ash Court、Birch House、Cedar Court、Dale House、Elm Court和Fern House的现场物理施工分别始于2026年7月9日、7月8日、7月10日、7月9日、7月8日和7月10日；每栋至少有两套住宅并有FRAEW生命安全风险报告。
- C3规则材料：在2026年8月17日的决策时点，下述规则处于有效期：该资金面向英格兰低于11米、含两套或以上住宅且FRAEW识别出生命安全外墙火灾风险的多住户建筑。对追溯性资助，现场工程在2026年7月9日之前已经开始的建筑不具备申请条件；7月9日当天开始不属于“之前”。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_b, exclude_e`。
- 风险：`STRICT_BEFORE_DATE_BOUNDARY`。
- 复核说明：严格区分before 9 July与on 9 July，B、E为7月8日，A、D为7月9日。

### SWOR-R067

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，Harbor Life Insurance配置一个1亿美元独立资产账户，该账户全部保单负债来自雇主养老金计划团体年金合同。账户在十个互不关联发行人直接发行的固定金额债券块中选择，金额与季度风险调整收益按资产台账记录。
- C2/C3事实：2026年8月5日，Harbor Life Insurance配置一个1亿美元独立资产账户，以支持面向个人销售的非养老金可变年金合同。十个债券块由十个互不关联的发行人直接发行，不含基金或合伙企业底层资产；2026年9月30日的配置持续至10月30日，账户不在启动或清算过渡期。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：支持非养老金可变合同的独立资产账户须在每个日历季度达到充分分散要求；在季度最后一日或其后30日内满足即可视为该季度满足。充分分散要求为：任一项投资不超过账户总资产的55%，任两项合计不超过70%，任三项合计不超过80%，任四项合计不超过90%。这些上限均包含等号；养老金计划合同不进入该季度测试。
- 纳入证据：`E2, E1, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E3"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1"],"threshold_and_equality":["E2","E3"]}`。
- Patch：`diversification_2_1_2, diversification_3_1_2_3, diversification_3_1_2_4, diversification_3_1_2_5, diversification_3_1_2_6, diversification_3_1_2_7, diversification_3_1_2_8, diversification_3_1_2_9, diversification_3_1_2_10, diversification_3_1_3_4, diversification_3_1_3_5, diversification_3_1_3_6, diversification_3_1_3_7, diversification_3_1_3_8, diversification_3_1_4_5, diversification_3_1_4_6, diversification_3_2_3_4, diversification_3_2_3_5, diversification_3_2_3_6, diversification_4_1_2_3_4, diversification_4_1_2_3_5, diversification_4_1_2_3_6, diversification_4_1_2_3_7, diversification_4_1_2_3_8, diversification_4_1_2_3_9, diversification_4_1_2_3_10, diversification_4_1_2_4_5, diversification_4_1_2_4_6, diversification_4_1_2_4_7, diversification_4_1_2_4_8, diversification_4_1_2_4_9, diversification_4_1_2_4_10, diversification_4_1_2_5_6, diversification_4_1_2_5_7, diversification_4_1_2_5_8, diversification_4_1_2_5_9, diversification_4_1_2_5_10, diversification_4_1_2_6_7, diversification_4_1_2_6_8, diversification_4_1_2_6_9, diversification_4_1_2_6_10, diversification_4_1_2_7_8, diversification_4_1_2_7_9, diversification_4_1_2_7_10, diversification_4_1_2_8_9, diversification_4_1_2_8_10, diversification_4_1_2_9_10, diversification_4_1_3_4_5, diversification_4_1_3_4_6, diversification_4_1_3_4_7, diversification_4_1_3_4_8, diversification_4_1_3_4_9, diversification_4_1_3_4_10, diversification_4_1_3_5_6, diversification_4_1_3_5_7, diversification_4_1_3_5_8, diversification_4_1_3_5_9, diversification_4_1_3_5_10, diversification_4_1_3_6_7, diversification_4_1_3_6_8, diversification_4_1_3_6_9, diversification_4_1_3_6_10, diversification_4_1_3_7_8, diversification_4_1_3_7_9, diversification_4_1_3_7_10, diversification_4_1_3_8_9, diversification_4_1_3_8_10, diversification_4_1_4_5_6, diversification_4_1_4_5_7, diversification_4_1_4_5_8, diversification_4_1_4_5_9, diversification_4_1_4_5_10, diversification_4_1_4_6_7, diversification_4_1_4_6_8, diversification_4_1_4_6_9, diversification_4_1_4_6_10, diversification_4_1_4_7_8, diversification_4_1_5_6_7, diversification_4_1_5_6_8, diversification_4_2_3_4_5, diversification_4_2_3_4_6, diversification_4_2_3_4_7, diversification_4_2_3_4_8, diversification_4_2_3_4_9, diversification_4_2_3_4_10, diversification_4_2_3_5_6, diversification_4_2_3_5_7, diversification_4_2_3_5_8, diversification_4_2_3_5_9, diversification_4_2_3_5_10, diversification_4_2_3_6_7, diversification_4_2_3_6_8, diversification_4_2_3_6_9, diversification_4_2_3_6_10, diversification_4_2_3_7_8, diversification_4_2_4_5_6, diversification_4_2_4_5_7, diversification_4_2_4_5_8, diversification_4_2_4_6_7, diversification_4_2_4_6_8, diversification_4_3_4_5_6`。
- 风险：`MULTI_HOP, MASSIVE_101_PATCH_ENUMERATION, QUARTER_END_30_DAY_WINDOW, PENSION_EXCEPTION`。
- 复核说明：保留Gold中全部101个组合上界，不对数学Patch作简化；规则段只陈述四级资产比例和季度测试时点。

### SWOR-R068

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，一个仅通过私募文件向机构投资者募集、没有Investment Company Act注册声明的机构流动性基金选择税务类型、交易后流动性组合及是否收购一只既非日流动也非周流动的证券；四组比例均为交易完成后比例。
- C2/C3事实：2026年8月4日，一个在SEC注册文件中以money market fund运营并向投资者发行份额的基金选择应税或免税类型、交易后流动性组合及是否收购一只既非日流动也非周流动的证券；四组日流动和周流动比例均为交易完成后比例。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：货币市场基金收购并非日流动资产的证券后，日流动资产比例不得低于总资产的25%，但免税基金不受该日流动下限约束。收购并非周流动资产的证券后，所有货币市场基金的周流动资产比例均不得低于50%。判断使用交易完成后的比例，等于25%或50%可以通过。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E2","E3"],"regulated_subject":["E2","E3"],"threshold_and_equality":["E2","E3"]}`。
- Patch：`taxable_acquire_daily_floor, all_acquire_weekly_floor`。
- 风险：`TAX_EXEMPT_DAILY_ONLY_EXCEPTION`。
- 复核说明：免税例外只关闭25%日流动下限，不关闭50%周流动下限；两个下限均保留等号。

### SWOR-R069

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，英国东湾医疗委员会以Direct Award Process B完成一项医疗服务采购；采购档案中没有发布授标意向通知，也没有收到该流程下的书面陈述。
- C2/C3事实：2026年8月2日，英国东湾医疗委员会采用Competitive Process完成一项医疗服务采购。委员会在第0个工作日发布授标意向通知，一家能够提供标的服务的供应商在第1个工作日结束前提交书面陈述，说明其不满授标决定并认为程序执行有误；团队在第8个工作日结束时送达继续授标的进一步决定，之后不再作其他决定。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：采用Competitive Process时，采购机关不得在静默期结束前签订合同；静默期从授标意向通知发布次日开始。能够提供标的服务、对决定不满并认为程序未按规定执行的供应商，可在静默期开始后的第八个工作日午夜前提交书面陈述。机关及时收到陈述后必须复核原决定、考虑陈述、作出并通知进一步决定；在最后一项进一步决定通知后，还须经过不少于5个完整工作日方可结束静默期。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E4"],"object_scope":["E1","E2","E4"],"obligations":["E1","E2","E3","E4"],"regulated_subject":["E1","E2","E4"],"threshold_and_equality":["E3","E4"]}`。
- Patch：`post_decision_standstill, representation_review_required`。
- 风险：`MULTI_HOP, WORKING_DAY_BOUNDARIES, FURTHER_DECISION_CHAIN`。
- 复核说明：规则材料区分通知后的陈述窗口与最后进一步决定后的5个完整工作日，避免把两个时钟合并。

### SWOR-R070

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，山原医疗机构的CMS登记文件标注其为rural emergency hospital，机构只提供门诊和急诊服务，没有住院床位或过夜患者；白班和夜班均营业，题列医生与护士为内部排班选项。
- C2/C3事实：2026年8月2日，山原医疗机构的CMS登记文件标注其为Medicare critical access hospital，白班和夜班均营业且夜间有住院患者。题列MD或DO医生在各自班次全部营业时间可提供患者照护；护士为普通注册护士或执业护士，不是执业护士师、临床护理专家或医师助理，且没有其他临床人员可安排。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：critical access hospital在全部营业时间都须有医学博士、骨科医学博士、执业护士师、临床护理专家或医师助理之一可以提供患者照护；当机构有一名或以上住院患者时，还须有注册护士、临床护理专家或执业护士在岗。营业时间与是否存在住院患者分别触发两项人员要求，等于一名住院患者即触发。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E2"]}`。
- Patch：`physician_day_available, physician_night_available, inpatient_nurse_on_duty`。
- 风险：`FACT_LABEL_REMOVED, TWO_DISTINCT_STAFFING_TRIGGERS`。
- 复核说明：医生覆盖按全部营业时间展开到昼夜，护士要求仅在存在住院患者时触发；资格类别按引文保留。

### SWOR-R071

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，北星餐饮用品仓库为酒店早餐、诊所餐饮和野外作业队三个订单分配Thermos库存。A为2023年6月制造的SK3000，原瓶已安装厂家压力释放塞并有凭证；B为2023年8月制造的SK3000；C为厂家提供且有更换凭证的SK3010 replacement bottle；D为2023年8月制造的SK3020。
- C2/C3事实：2026年8月4日，北星餐饮用品仓库为酒店早餐、诊所餐饮和野外作业队三个订单分配Thermos库存。A为2023年6月制造的SK3000，B为2023年8月制造的SK3000，C为2023年10月制造的SK3010，D为2023年8月制造的SK3020；四件均没有厂家处置完成凭证。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：Thermos Stainless King SK3000和SK3020食物罐只有在2023年7月之前制造时属于召回范围，Sportsman SK3010瓶则不受制造月份限制而全部召回。受影响产品应停止使用；SK3000或SK3020由厂家免费提供压力释放塞，SK3010由厂家更换整瓶。已完成相应厂家处置并有记录的产品不需要重复处置。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`recalled_a_requires_remedy, recalled_c_requires_remedy`。
- 风险：`MODEL_DATE_CONJUNCTION, REMEDY_TYPE_DIFFERS_BY_MODEL`。
- 复核说明：A按SK3000加2023年7月前双条件命中，C按全部SK3010命中；B、D的月份边界保持可核查。

### SWOR-R072

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，伯明翰铸桥制造公司把六批商品编码7208 51 20的热轧非合金钢板分配给车架和机壳订单。A至F合同签署日依次为2026年3月12日、3月13日、2月28日、3月13日、3月11日和3月1日，计划进口日依次为7月15日、7月10日、9月29日、8月4日、8月6日和9月30日；本轮没有普通钢材配额额度。
- C2/C3事实：2026年8月4日，伯明翰铸桥制造公司把六批商品编码7208 51 20的热轧非合金钢板分配给车架和机壳订单。A至F合同签署日依次为2026年3月12日、3月15日、2月28日、3月13日、3月16日和3月1日，计划进口日依次为7月15日、7月10日、10月2日、8月4日、8月6日和9月30日；本轮没有普通钢材配额额度，预留成本通道不能吸收50%配额外关税。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年7月1日起，英国对钢材免税进口设置数量限制，超过配额部分征收50%关税。对商品编码72085120所属的Product Category 7热轧非合金及其他合金厚板，存在限时过渡安排：合同必须在2026年3月14日之前签订，且货物须在2026年7月1日至9月30日之间进口，才可完全免除该50%配额外关税；3月14日当天或之后签约、10月1日或之后进口均不满足。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`bar_frame_b_from_transitional_lane, bar_housing_b_from_transitional_lane, bar_frame_c_from_transitional_lane, bar_housing_c_from_transitional_lane, bar_frame_e_from_transitional_lane, bar_housing_e_from_transitional_lane`。
- 风险：`CONTRACT_AND_IMPORT_DATE_CONJUNCTION, STRICT_BEFORE_BOUNDARY, SIX_ASSIGNMENT_EDGES`。
- 复核说明：过渡安排要求商品分类、合同日和进口日三轴同时满足；每个不合格批次在两个订单边上均覆盖。

### SWOR-R073

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，澄湖食品厂在两种饮料和候选蓝色色素批次间选择生产组合。候选色素为FD&C Blue No. 1，A至D均有逐批认证记录；P1由水、甜味剂和柠檬香料配成碳酸饮料，P2由水、电解质、甜味剂和橙味香料配成运动饮料。
- C2/C3事实：2026年8月5日，澄湖食品厂在两种饮料和Galdieria extract blue批次间选择生产组合。P1为非酒精饮料；P2是由成熟Citrus sinensis取得、去除籽和多余果肉、只冷藏而未冷冻的未发酵橙汁。A的铅、汞、镉分别为0.3、0.02、0.3 ppm，B的铅为0.7 ppm，C的汞为0.08 ppm，D的镉为0.8 ppm，四批砷检测均为0.3 ppm。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：Galdieria extract blue可用于非酒精饮料和饮料基料，但不得用于已有食品身份标准且该标准没有授权添加此色素的食品。由成熟Citrus sinensis取得的未发酵果汁，在去除籽和多余果肉并仅冷藏而未冷冻时属于标准化orange juice，该标准没有列明添加色素。该蓝色色素还须同时满足铅不超过0.5 ppm、汞不超过0.05 ppm、镉不超过0.5 ppm；任一上限超出即不能使用，等于上限可以通过。
- 纳入证据：`E3, E2, E1`。
- 排除的C1专属证据：`E4, E5`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2","E3"],"geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1"]}`。
- Patch：`standardized_food_forbid_blue, high_lead_forbid_blue, high_mercury_forbid_blue, high_cadmium_forbid_blue`。
- 风险：`MULTI_HOP, STANDARDIZED_FOOD_EXCEPTION, MULTIPLE_IMPURITY_CEILINGS, C1_ONLY_EVIDENCE_EXCLUDED`。
- 复核说明：E4/E5只描述C1的FD&C Blue No. 1一般用途和认证，未放入C3；C2所需orange juice身份、色素用途例外和三个杂质上限由E3/E2/E1闭合。

### SWOR-R074

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，英国山谷制造厂为机器和电气设备各选择一条维护作业线。两类设备在资产台账中都没有既有维护日志；A与C的步骤不写设备记录，B与D会建立并写入本次维护记录，四条线完成的维护均有检验记录。
- C2/C3事实：2026年8月2日，英国山谷制造厂为机器和电气设备各选择一条维护作业线。两类设备在资产台账中各有一份现存维护日志；A与C的步骤不更新日志，B与D会把本次维护同步写入日志。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：工作场所机器已经设有维护日志时，雇主须保持该日志为最新状态；没有既有维护日志时，该句本身不要求仅因本次维护新建日志。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`A_stale_log, C_stale_log`。
- 风险：`EXISTING_LOG_CONDITION`。
- 复核说明：规则以“where a machine has a maintenance log”为条件，未扩张成普遍新建日志义务。

### SWOR-R075

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，一个路径规划团队只在离线导航仿真器中评估标称宽度5.1米作业艇从Reading附近到伦敦方向的题列网络，不移动实体船舶，也不申请通航许可；仿真器保留全部河道、公路弧和成本。
- C2/C3事实：2026年8月4日，一家运营方计划把一艘标称宽度5.1米的实体维修作业艇从Reading附近运往伦敦方向，船艇将沿所选河道或公路弧实际移动；除Boulters Lock与Teddington两条候选弧外，题列其他河段在本次运输计划中开放。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：2026年8月3日更新的泰晤士河运行指引把Boulters Lock尾闸通行宽度限制为不超过4.8米；Teddington Launch Lock因维修关闭，而Teddington Barge Lock保持完全运行。宽度等于4.8米可以通过，超过4.8米不能使用Boulters Lock。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`bar_boulters_for_width, bar_teddington_launch_lock`。
- 风险：`CURRENT_OPERATIONAL_STATUS, WIDTH_EQUALITY_BOUNDARY`。
- 复核说明：同一官方更新同时覆盖上游宽度限制和下游锁关闭，并明确Barge Lock仍可用。

### SWOR-R076

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，内华达州星脉电池实验室向科罗拉多州独立测试中心运输一只镍氢测试原型电池。该电池不含金属锂或锂离子电芯，型号年产18只、净重24千克，逐只装在完全包覆的非金属内包装中，再置于达到Packing Group I的4H2实心塑料外箱，周围有不可燃且不导电的缓冲材料并固定，运输文件记录包装与测试信息。
- C2/C3事实：2026年8月5日，内华达州星脉电池实验室向科罗拉多州独立测试中心运输一只尚未完成UN 38.3型式试验的锂离子测试原型电池。该型号年产18只、净重24千克，逐只装在完全包覆的非金属内包装中，再置于经规定试验并达到Packing Group I的4H2实心塑料外箱，周围有不可燃且不导电的缓冲材料并固定，运输文件记录包装与原型测试信息；技术档案没有运输前个案批准。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：年产不超过100只的低产量锂电池或为测试运输的原型锂电池，可在满足专门包装和文件条件时免于通常型式试验与记录要求。每只电池须单独置于非金属内包装，再放入符合规定试验且达到Packing Group I的列明外包装；4H2实心塑料箱属于列明类型，周围须用不可燃、不导电材料缓冲并防止振动、冲击和移位，运输文件还须注明按该原型条款运输。满足这些条件的电池仍不得由客机运输；全货机运输只有在运输前取得主管官员批准时才允许。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E3","E4","E5","E6","E7"],"geographic_scope":["E1","E2"],"object_scope":["E1","E3","E4","E5","E6"],"obligations":["E2","E3","E4","E5","E6","E7"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1"]}`。
- Patch：`prototype_excludes_passenger_air, cargo_air_requires_prior_approval`。
- 风险：`MULTI_HOP, SEVEN_EVIDENCE_NODES, LOW_PRODUCTION_EXCEPTION_CHAIN, AIR_MODE_SPLIT`。
- 复核说明：原型例外的年产量、逐只包装、外箱等级、缓冲固定、文件备注和航空方式后果均由独立节点闭合。

### SWOR-R077

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，俄亥俄州湖湾社区医院为一名病区主管安排下一固定14日工作期。该主管每周固定工资1500美元，不随当期工时变化，主要负责病区运营管理，实际管理两名全职员工并能独立提出聘用建议；四个候选排班依次为7个12小时班、10个8小时班、14个6小时班和9个9小时班。
- C2/C3事实：2026年8月5日，俄亥俄州湖湾社区医院为一名按小时计酬、执行病区物资与患者服务辅助工作且没有管理职责的服务员安排下一固定14日工作期。双方在开始工作前书面采用该14日期，使用同一正常时薪，单日与全期加班小时不重复计算；四个候选排班依次为7个12小时班、10个8小时班、14个6小时班和9个9小时班。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：医院可在雇主与相关雇员于工作开始前达成协议或谅解时，以固定14日期替代逐周计算加班。采用该期间后，每个工作日超过8小时以及整个14日期超过80小时的工作时间，均须按不低于正常工资1.5倍支付。按执行人员豁免处理还须同时满足：以每周至少684美元的salary basis支付、主要职责为管理、经常管理两名或以上员工，并具有聘用解聘权或其人事建议被赋予重要权重；salary basis须是不因工作质量或数量变化而减少的预定金额。
- 纳入证据：`E2, E1, E3, E4, E5, E6, E7`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E3","E4","E5","E6","E7"],"geographic_scope":["E1","E2","E3","E4","E5","E6","E7"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E3","E4","E5","E6","E7"],"threshold_and_equality":["E2","E3","E5"]}`。
- Patch：`s7x12_requires_p28, s10x8_requires_p0, s14x6_requires_p4, s9x9_requires_p9`。
- 风险：`MULTI_HOP, SEVEN_EVIDENCE_NODES, MULTIPLE_OPTIMA_BOUNDARY, DAILY_AND_PERIOD_OVERTIME, EXECUTIVE_EXCEPTION`。
- 复核说明：保留医院14日期前置协议、每日8小时和全期80小时双测试及执行人员正式例外；题内已固定重叠小时不重复。

### SWOR-R078

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，云岸航空一名培训员工完成13小时地面培训值勤，之后安排下一次地面培训；该员工只在教室和模拟舱授课，没有被列入任何航班机组名单，也不执行机上安全、客舱服务或调机任务。
- C2/C3事实：2026年8月4日，云岸航空一名被列入Part 121国内航班机组名单并承担客舱安全职责的客舱机组人员完成13小时计划值勤，下一值勤在所选连续休息后开始；本次值勤不超过14小时，没有不可预见运行或紧急事件，运行批准文件没有特殊变更。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：客舱机组人员的计划值勤期不超过14小时时，在该值勤结束与下一值勤开始之间必须安排至少连续10小时休息，且该休息不得缩短到10小时以下；连续10小时恰好满足要求。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`nine_hour_turnaround_unavailable`。
- 风险：`DUTY_AND_REST_EQUALITY_BOUNDARIES`。
- 复核说明：同时保留值勤期不超过14小时和休息至少10小时两个等号边界。

### SWOR-R079

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，南十字通信服务商为预约提醒、网络中断通知和账单通知选择澳大利亚SMS路由。A至H所有发送配置只显示普通数字电话号码，不发送或显示字母数字发件标识；A、C、D、F、G的提供商已参加sender-ID登记体系，B、E、H的提供商未参加。
- C2/C3事实：2026年8月4日，南十字通信服务商为预约提醒、网络中断通知和账单通知选择澳大利亚SMS路由。A至H均发送并显示字母数字发件标识；A、C、D、F、G的提供商已参加sender-ID登记体系，B、E、H未参加；C、E、F使用本企业已登记标识，B、H使用另一服务商已登记标识，A、D、G使用尚无登记记录的标识。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年7月1日起，承载字母数字sender ID流量的澳大利亚电信商或消息提供商必须申请参加登记体系。未参加的提供商不得发送、转接或终止带sender ID的SMS或MMS，其消息会被阻断。已经参加的提供商承载尚未登记的sender ID时，消息只会被覆盖标注为“Unverified”，不会因此自动阻断；提供商参与状态与标识本身的登记状态须分别判断。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`bar_nonparticipating_orbitmsg, bar_nonparticipating_mira_relay, bar_nonparticipating_south_relay`。
- 风险：`PROVIDER_PARTICIPATION_VS_ID_REGISTRATION`。
- 复核说明：只排除未参加体系的B、E、H路由；参加体系但标识未登记的A、D、G仍可发送并加Unverified。

### SWOR-R080

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，河谷学区中学完全使用学区自有资金采购七类校内宽带服务包，不提交或使用外部资金请求；交换机、路由器和无线接入点均部署于校内教学宽带网络，采购须覆盖交换机生命周期、防火墙、配置或软件支持三类需求且最多选择三个包。
- C2/C3事实：2026年8月4日，河谷学区中学为Funding Year 2026提交Category Two Internal Connections资金请求，表单不申报Basic Maintenance of Internal Connections，也不参加Cybersecurity Pilot；交换机、路由器和无线接入点均部署于校内教学宽带网络。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：Funding Year 2026把当前可支持的bug修复、安全补丁、软件技术协助和远程配置变更，在与相应设备一并采购时归入Eligible Broadband Internal Connections。现场配置和物理维修仍属于按实际工作提供的Basic Maintenance of Internal Connections；高级防火墙服务不纳入，基础防火墙服务及组件仍属于可支持的Category Two内部连接。仅申报Internal Connections时，不能把现场配置、物理维修或高级防火墙计入该请求。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`bar_onsite_configuration_from_ic_request, bar_advanced_firewall, bar_physical_repair_from_ic_request`。
- 风险：`FY2026_CATEGORY_RECLASSIFICATION, IC_VS_BMIC_BOUNDARY`。
- 复核说明：远程软件/配置与设备一并采购、现场服务、基础/高级防火墙三条分类边界均保留；题内资金申报类型决定可选包。

### SWOR-R081

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，爱尔兰科克市议会和都柏林市议会已整理完本年度废物实施资料。本报告周期内，爱尔兰环境署没有向任一议会发出资料需求函，也没有指定资料类别、格式或通知方式；两市仅把电子发送作为内部工作流选项。
- C2/C3事实：2026年8月2日，爱尔兰环境署已分别向科克市议会和都柏林市议会发出年度废物资料函，逐项指定应交资料类别和电子格式；两市底层记录齐备，题列发送动作就是通过环境署指定电子渠道提交资料。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：爱尔兰地方当局和都柏林市议会须按环境署为废物资料报告指定的方式，以书面或电子通知形式向环境署提供资料；报告还须采用欧盟委员会建立的报告格式。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`cork_submission_required, dublin_submission_required`。
- 风险：`无`。
- 复核说明：C2资料函、指定资料及电子格式均由现有E1闭合；两市发送动作由题内语义完成绑定。

### SWOR-R082

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Northmere Metals在英国为Arden、Beck、Cobalt、Dunlin和Ember五份钢材订单安排北区或南区报关组。五份合同分别签于2026年3月14、15、16、17和18日，均在2026年7月1日至9月30日进口或从保税仓放行；书面合同、发票、付款证明和产品台账完整。
- C2/C3事实：2026年8月4日，Northmere Metals在英国为五份钢材订单安排报关组。Arden、Beck、Cobalt、Dunlin和Ember合同分别签于2026年3月13、14、12、11和10日；对应进口或放行日为7月1日、8月25日、9月30日、7月20日和10月1日，Dunlin已于6月30日进入英国保税仓；五单均有可核验合同、发票和付款证明。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：2026年7月22日更新的英国过渡安排规定，2026年3月14日前订立合同且在2026年7月1日至9月30日进口的相关钢材可使用过渡豁免；在该期间从英国保税仓放行的货物，也须源于3月14日前合同。使用该过渡豁免的订单不计入7月1日至9月30日第一季度配额分配；边界日期本身不属于“此前”。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`quarter_one_quota_slot`。
- 风险：`无`。
- 复核说明：保留modify_constraint；合同日、进口日和保税仓放行条件均由E1直接支持。

### SWOR-R083

- V1.6.2：已按用户授权定点修复，等待本版全量检查；下述旧复核说明为历史记录，不代表新审查通过。
- C1事实：2026年8月4日，位于科罗拉多州普韦布洛的Canyon Ridge Coatings在同一连续厂址维护月度台账：每月产生1200 kg非急性危险废物、0 kg急性危险废物、0 kg急性危险废物泄漏清理残余物。P1和P2为计划活动，U为非计划活动，分别持续30日、45日和20日，三项活动彼此独立。
- C2/C3事实：2026年8月4日，位于科罗拉多州普韦布洛的Canyon Ridge Coatings在同一连续厂址维护月度台账：每月产生600 kg非急性危险废物、0 kg急性危险废物、0 kg急性危险废物泄漏清理残余物。P1和P2为计划活动，U为非计划活动，分别持续30日、45日和20日，三项活动彼此独立；企业已备妥年度第一项活动的通知资料；对于与第一项活动类型相反的第二项活动，本题所需petition已获批准，最终方案采用该安排时才启用批准并发生20点内部管理成本。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：40 CFR 260.10将small quantity generator界定为在同一日历月内同时产生大于100 kg且小于1000 kg非急性危险废物、不超过1 kg急性危险废物，并且急性危险废物泄漏清理产生的残余物、受污染土壤、水或其他碎片不超过100 kg的产生者。40 CFR Part 262 Subpart L仅面向very small quantity generator或small quantity generator；每个日历年通常限一次最长60日的独立活动。经petition获准可增加第二次活动，但其类型须与第一次相反：第一次为计划活动时第二次须为非计划活动，第一次为非计划活动时第二次须为计划活动；petition须说明增加活动的理由、性质和预计持续时间。
- 纳入证据：`E1, E2, E3, E4, E5, E6, V161-E7`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["V161-E7"],"formal_exceptions":["E2","E3","E4"],"geographic_scope":["E1","V161-E7"],"object_scope":["E1","E5","E6"],"obligations":["E1","E2","E5"],"regulated_subject":["E3","E4","V161-E7"],"threshold_and_equality":["E1","E2","E6"]}`。
- Patch：`event_p1_active, p1_tank_clean_activates_event_p1_active, p1_lab_pack_activates_event_p1_active, p1_filter_change_activates_event_p1_active, event_p1_active_requires_project, event_u_active, u_spill_soil_activates_event_u_active, u_damaged_drum_activates_event_u_active, u_washwater_activates_event_u_active, event_u_active_requires_project, event_p2_active, p2_inventory_activates_event_p2_active, p2_line_flush_activates_event_p2_active, p2_absorbent_activates_event_p2_active, event_p2_active_requires_project, second_event_petition, one_event_without_petition, at_most_two_events, petition_requires_active_event, at_most_one_planned_event, modify_objective`。
- 风险：`无`。
- 复核说明：针对性修复：删除C1/C2事实中的产生者类别标签，改由同一连续厂址的三类月度产生量表达；新增V161-E7，引用eCFR 2026-07-31版40 CFR 260.10的small quantity generator官方阈值定义，以底层数量闭合主体资格判定。

### SWOR-R084

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，绿环材料中心接收A至F六个金属气雾容器。每个容器均已排空、清洗和吹扫，检测未发现危险残余物，中心将其作为普通空金属容器分类；当日累计持有量低于5000千克。
- C2/C3事实：2026年8月4日，绿环材料中心当日峰值持有4800千克废气雾罐。A和C拟穿刺排空并回收空罐；C和D接收时泄漏，C立即穿刺而D保持完整；B、E、F完整且不泄漏。中心有专用穿刺装置、书面程序、培训人员、通风平整作业区、溢漏程序、清理包和带吸附材料的密闭外包装。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：小量处理者穿刺排空废气雾罐时，须使用专为安全穿刺并容纳残余物和排放而设计的装置，遵循书面程序和制造商说明，由受训员工在能防火、防释放的坚实平整通风区域作业，并回收空罐。出现泄漏的气雾罐须单独置于密闭容器或带吸附材料的外包装中，或者立即按上述要求穿刺排空。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`intact_puncture_a_requires_cell, immediate_puncture_of_leaking_c_requires_cell, leaking_cans_d_kept_intact_require_overpack`。
- 风险：`无`。
- 复核说明：穿刺分支和泄漏二选一处置均由现有引文直接支持；设备能力由题内事实绑定。

### SWOR-R085

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，北湾配送公司为加拿大安大略省的四处工作场所选择设施、永久出口路线和出口门配置。四处设施、雇佣关系和运营主体均在加拿大；工程记录给出各设施安全撤离所需路线数，且设施均不是精神、监狱或矫正机构。
- C2/C3事实：2026年8月5日，北湾配送公司为美国境内一般工业工作场所选择设施、永久出口路线和出口门配置。小办公室、标准仓库、大型配送层和高危险作业室分别容纳12、80、320和60人；工程分析记录所需路线数为1、2、3和2，高危险作业室材料可能极速燃烧；门包分别为内开免钥匙、外开免钥匙和外开需钥匙。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：工作场所通常至少须有两条彼此尽可能远离的出口路线；只有人数、建筑规模、用途和布局允许所有人员安全撤离时才可只设一条。若这些因素使两条路线仍不足，则须提供两条以上。出口路线门必须始终能从内部无需钥匙、工具或特殊知识开启；容纳超过50人或高危险房间的门须沿疏散方向外开。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1","E3","E4"],"obligations":["E1","E2","E3","E4"],"regulated_subject":["E1"],"threshold_and_equality":["E2","E4"]}`。
- Patch：`standard_warehouse_forbids_single_exit, large_floor_forbids_single_exit, large_floor_forbids_two_exits, high_hazard_forbids_single_exit, keyed_inside_exit_door_forbidden, standard_warehouse_requires_outward_door, large_floor_requires_outward_door, high_hazard_requires_outward_door`。
- 风险：`无`。
- 复核说明：三条路线数量分支、免钥匙和外开门分支均由E1-E4闭合。

### SWOR-R086

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一座非运输储油设施的地上固定油罐合计1300美制加仑，完全埋地罐为0；场址坡面和排水沟全部汇入没有外排口的场内衬里集液池。设施准备选择下一轮内部泄漏控制计划复核与改造时序。
- C2/C3事实：2026年8月5日，美国一座非运输储油设施的地上固定油罐合计2400美制加仑，完全埋地罐为0；场址坡面和连续排水沟连接毗邻的美国可航水域岸线。第五年现场复核确认一项已经实地验证且可显著降低排放概率的控制技术。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：对因位置而可能向美国可航水域或相邻岸线有害排油的非运输储油设施，地上总容量不超过1320美制加仑且埋地总容量不超过42000加仑时不进入该制度。进入制度的设施须至少每五年复核一次防油计划；复核发现已现场验证且显著降低排放可能性的技术时，须在复核后六个月内修订计划，并尽快且不迟于修订后六个月实施。
- 纳入证据：`E1, E2, E3, E4, E5`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E3","E4","E5"],"regulated_subject":["E1"],"threshold_and_equality":["E2","E3","E4","E5"]}`。
- Patch：`exclude_late_amendment, exclude_late_review, exclude_late_implementation`。
- 风险：`无`。
- 复核说明：容量、排放路径、五年复核和两个六个月期限均有对应节点。

### SWOR-R087

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年7月25日，在卢森堡注册的Alzette Components以自身名义和自身账户直接配置题列银行、支付平台、国库券及现金头寸；开户、交易与清算路径均与题列对手方一致，没有第三方代理、许可证、授权或撤资安排。
- C2/C3事实：2026年8月20日，在卢森堡注册的Alzette Components以自身名义和自身账户直接配置题列银行、支付平台、国库券及现金头寸；开户、交易与清算路径均与题列对手方一致，没有第三方代理、许可证、授权或撤资安排。
- C3规则材料：在2026年8月20日的决策时点，下述规则处于有效期：欧盟相关交易禁令覆盖成员国境内、成员国设立主体及在欧盟全部或部分开展的业务。自2026年8月13日起，CJSC Eco-Islamic Bank列入禁止直接或间接交易的境外主体清单；Chinggis Khaan Bank、Sberbank India和PilotFinance Ltd同日起列入境外金融或支付服务主体清单。Rapira与Aifory Pro的条目到8月23日才生效，Yelo Bank条目已被删除。
- 纳入证据：`E1, E2, E3, E4, E5, E6`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E4","E5","E6"],"formal_exceptions":["E5","E6"],"geographic_scope":["E1"],"object_scope":["E5","E6"],"obligations":["E2","E3"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`transaction_unavailable_eco_islamic, transaction_unavailable_chinggis, transaction_unavailable_sberbank_india, transaction_unavailable_pilotfinance`。
- 风险：`无`。
- 复核说明：按2026-08-20逐项处理8月13日、8月23日和Yelo删除边界，避免把尚未生效条目提前排除。

### SWOR-R088

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，在挪威注册的Bluehaven Energy从挪威编制2027年液化天然气采购与第三国转运计划；合同签订、履行、付款、船舶和目的地均在欧盟之外，没有欧盟人员、机构、领土、船舶、航空器或清算路径参与。
- C2/C3事实：2026年8月4日，在荷兰注册的Bluehaven Energy编制2027年俄罗斯原产液化天然气采购与第三国转运计划。全部转运目的地在欧盟和俄罗斯之外；GL-17于2021年1月15日签订、期限四年且2023年仅降低采购价格，QP-42于2022年2月23日签订、期限两年且2025年仅变更合同方地址，RT-09于2021年2月10日签订、期限三年且2024年提高合同数量，VN-31于2020年12月1日签订、期限一年且之后未修改。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：至2027年7月25日，并在此后连续一年期间，运往欧盟和俄罗斯之外第三国的液化天然气转运及与之相关的采购，可在转运和采购均依据2022年2月24日前订立、期限超过一年且此后未修改的合同时继续。允许的修改仅包括降低数量、采购价费、保密条款、运营程序、合同方地址、关联企业间义务转移、司法或仲裁要求，以及内陆国采购的国内交付点变化。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`orion_purchase_requires_cedar_transfer, lumen_purchase_requires_maple_transfer, temporary_route_unavailable_purchase_cairn_feb, temporary_route_unavailable_transfer_harbor_mar, temporary_route_unavailable_purchase_vesper_apr, temporary_route_unavailable_transfer_delta_may`。
- 风险：`无`。
- 复核说明：合同日期、期限、修改类型和采购—转运联动均由单一完整条款闭合。

### SWOR-R089

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一家临终关怀机构为2025年10月1日至2026年9月30日的服务窗选择完整服务包。四个包中的全部照护日均由患者自费，机构台账将这些日期与Medicare受益人照护日分开记录。
- C2/C3事实：2026年8月5日，一家Medicare认证临终关怀机构为2025年10月1日至2026年9月30日的同一服务窗选择完整服务包。四个包的总照护日均为Medicare受益人已选择临终关怀的日期，题列住院日均按general inpatient或inpatient respite计费。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：临终关怀报销的cap period是截至9月30日的连续12个月。对Medicare患者，general inpatient和inpatient respite住院日合计不得超过这些患者选择临终关怀总日数的20%；超过20%时须调整住院照护付款，并退还多收款项。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E2"],"regulated_subject":["E2"],"threshold_and_equality":["E2"]}`。
- Patch：`exclude_25_of_100, exclude_18_of_80`。
- 风险：`无`。
- 复核说明：已去掉‘支付制度’标签，改用付款来源、患者类别和同一12个月窗口等可观察台账事实。

### SWOR-R090

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，马来西亚海湾肾脏专科中心为三名患者安排Jinarc启动和化验支持；处方、配药、化验、库存与治疗均在马来西亚完成，产品由马来西亚供应链交付，诊所、医生、药师和患者均无新加坡业务联系。
- C2/C3事实：2026年8月4日，新加坡海湾肾脏专科中心拟为陈先生、林女士和谭先生启动Jinarc，王女士接受不使用该产品的标准治疗。医护人员教育认证及处方清单与库存核验已从本地流程撤下，三名患者的肝转氨酶和胆红素检查仍可在门诊安排。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年7月15日的流程更新起，Jinarc医护人员教育认证以及处方清单与库存余额核验停止；肝转氨酶和胆红素血液检查继续执行。医生须在患者开始Jinarc治疗前进行该项肝功能血液检查。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`jinarc_requires_lab_chen, jinarc_requires_lab_lim, jinarc_requires_lab_tan`。
- 风险：`E2_QUOTE_IS_TRUNCATED_AFTER_PRESTART_AND_EARLY_FOLLOWUP_TEXT`。
- 复核说明：Gold仅需要开始治疗前检查，现有E2完整支持该部分；不据截断内容生成后续复查约束。

### SWOR-R091

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Redwood Freight在美国州际公路运输中从九票题列货物选择四票。每票货物分别置于密封且结构独立的货舱，各舱没有共同装载或储存空间，货物不能相互混合。
- C2/C3事实：2026年8月4日，Redwood Freight把四票题列货物装入美国州际公路车辆的一个未分隔货舱，各包装之间没有阻止相互混合的隔离构造；承运人没有私人承运危险废物安排或其他特别授权。货物分类、包装组、危险区和反应性质均按装载单所列。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：在同一装载或储存空间内，氰化物及其混合物或溶液不得与混合后会产生氰化氢的酸共同装载运输；Division 4.2材料不得与Class 8液体共同装载；Division 6.1、Packing Group I、Hazard Zone A材料不得与Class 3、Class 8液体以及Division 4.1、4.2、4.3、5.1或5.2材料共同装载。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1","E2","E3"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`external_rule_active, activate_external_rule, cyanide_aster_acid_beryl, cyanide_aster_acid_dune, division42_cinder_class8_beryl, division42_cinder_class8_dune, hza_ember_class8_beryl, hza_ember_division42_cinder, hza_ember_class8_dune, hza_ember_class3_flint, hza_ember_division52_grove, hza_ember_division51_iris`。
- 风险：`无`。
- 复核说明：复核了add_variable与11条约束；规则段仅描述三类同舱隔离分支。

### SWOR-R092

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，纽瓦克澄源化工在美国从六个供应批次选择三个。经认证成分记录显示六批四氯乙烯含量均为0%，各批在当天完成题列进口、加工、分销、生产或备货动作。
- C2/C3事实：2026年8月4日，纽瓦克澄源化工在美国从六个供应批次选择三个。前五批含四氯乙烯；第四批仅用于持续干洗，第五批在完整工作场所化学防护计划控制下生产航空用途材料，第六批是不含四氯乙烯的水性清洁剂；全部进口、加工、分销、生产或备货动作当天完成。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：美国对四氯乙烯的制造（包括进口）、加工及商业分销分阶段实施禁令。制造和进口禁令自2026年6月11日起生效，但持续干洗用途以及在完整工作场所控制下继续的工业商业用途除外；加工禁令自2026年9月9日起生效；向零售商分销非干洗用途产品的禁令自2026年12月8日起生效。
- 纳入证据：`E1, E2, E3, E4, E5, E6, E7`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E3","E5","E7"],"formal_exceptions":["E2","E4"],"geographic_scope":["E1"],"object_scope":["E1","E2","E4","E6"],"obligations":["E1","E2","E4","E6"],"regulated_subject":["E1","E2","E4","E6"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`pce_manufacturing_import_domain_on_august_4`。
- 风险：`无`。
- 复核说明：把三个阶段日期全部保留，确保2026-08-04只激活制造/进口域。

### SWOR-R093

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一家制造商为同一PET药品组分批次选择放行包；生产线、组分和批记录均按正电子发射断层扫描药品生产流程运行。
- C2/C3事实：2026年8月5日，美国一家供人使用的非PET、非医用气体成品药制造商，为同一非特殊危险活性组分批次选择放行包；供应商分析报告、厂内身份试验和供应商可靠性验证状态均按题列方案记录。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：成品药生产要求每一组分至少进行一项特异身份试验。制造商可以接受供应商分析报告，但仍须自行完成至少一项特异身份试验，并按适当间隔验证供应商试验结果的可靠性；该制度不覆盖PET药品和医用气体。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E3"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3"],"obligations":["E2","E3"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`exclude_no_identity, exclude_unvalidated_supplier_report`。
- 风险：`无`。
- 复核说明：去除facts中的Part编号，只保留PET/非PET、医用气体和试验记录等可观察属性。

### SWOR-R094

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，加拿大安大略省一家私营包装厂安排雇员班后清洁设备；清洁作业、雇佣关系和设备均在安大略省，工作场所由省级职业安全机构登记。
- C2/C3事实：2026年8月4日，美国华盛顿哥伦比亚特区一家普通私营包装厂安排雇员清除设备表面碎屑；调压后喷嘴压力分别为45、25或20 psi，另有工业吸尘方案。工作场所档案没有其他联邦机构对该工况行使职业安全权限。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：美国一般工业工作场所使用压缩空气清洁时，喷嘴压力必须降低到严格低于30 psi，并且只有同时配置有效碎屑防护和个人防护装备才可使用；等于或高于30 psi不能用于该清洁作业。其他联邦机构已依法管理同一工作条件时不重复适用。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E2"],"obligations":["E2"],"regulated_subject":["E1"],"threshold_and_equality":["E2"]}`。
- Patch：`air_45psi_forbidden, air_25psi_requires_guard_and_ppe, air_20psi_requires_guard_and_ppe`。
- 风险：`无`。
- 复核说明：明确less than 30 psi的严格边界及防护与PPE的合取条件。

### SWOR-R095

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，美国州际商业货运承运人从四辆普通非载客货车中选择车辆和铁路道口动作；调度单未标示危险材料标牌、危险材料罐式车或其他特殊车辆类别。
- C2/C3事实：2026年8月4日，美国州际商业承运人选择车辆和铁路道口动作。车辆A是载客巴士，B是悬挂Division 1.1标牌的货车，C是普通货车，D是运输危险材料的罐式车辆；活动公共道口没有警察、旗手或绿灯，另一道口带州授权Exempt标志。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：载客巴士、按运输规定须悬挂Division 1.1标牌的商业车辆，以及装运危险材料的罐式车辆通过活动铁路平交道口前，须在距轨道不超过50英尺且不少于15英尺处停车，听看两侧并确认没有列车接近。带州授权“Exempt”标志的工业或支线道口属于正式例外。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E3"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E2"],"threshold_and_equality":["E1"]}`。
- Patch：`bus_active_requires_stop, placard_active_requires_stop, tank_active_requires_stop`。
- 风险：`无`。
- 复核说明：车辆类别、15至50英尺停车边界和Exempt道口例外完整保留。

### SWOR-R096

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Harbor Pine Freight在缅因州大陆Cumberland County与Long Island之间选择两项滚装货运订单。每项订单由货物重量超过5 gross tons的滚装车辆承运，装卸不用Casco Bay Island Transit District定班码头；航次依公开固定班表运行，不按客户需求临时开航。
- C2/C3事实：2026年8月4日，Harbor Pine Freight在缅因州大陆Cumberland County与Long Island之间选择两项滚装货运订单。每项订单由货物重量超过5 gross tons的滚装车辆承运，装卸不用Casco Bay Island Transit District定班码头；航次按客户临时需求组成，不依公布班表，也不按固定或预设频率运行。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：在缅因州大陆Cumberland County与Long Island等列明岛屿之间，非定班滚装服务须按需求提供、不得依据公布班表，也不得形成固定或预设频率。车辆货物重量须超过5 gross tons，装卸不得使用Casco Bay Island Transit District的定班码头。可运输散装货物、建筑材料、由牵引式半挂车承运的家庭用品、工程设备或专用车辆；不得运输食品、饮料、易腐品及包裹或装箱货物。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E3"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E3"],"threshold_and_equality":["E1"]}`。
- Patch：`ineligible_carry_order_atlas, ineligible_carry_order_cove, ineligible_carry_order_fjord, ineligible_carry_order_haven`。
- 风险：`无`。
- 复核说明：复核了V1.5.1曾修Gold/model后的四个货类排除；路线、重量、码头和非定班定义均闭合。

### SWOR-R097

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月2日，佛罗里达一家未取得eligible telecommunications carrier身份的电信公司，为三名用户安排公司自筹的可选账单优惠；三人9月1日均完成内部入账准备，首批有两个处理名额。
- C2/C3事实：2026年8月2日，佛罗里达一家eligible telecommunications carrier收到三名用户的Lifeline资格通知；三人9月1日均完成账单抵免准备，首批有两个处理名额，客户材料、系统和人员记录均无延迟。
- C3规则材料：在2026年8月2日的决策时点，下述规则处于有效期：eligible telecommunications carrier收到消费者Lifeline资格通知后，须在实际可行的最早时间把援助抵免计入账单，且最迟不得超过收到通知后的60日。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`credit_deadline, earliest_practicable_batch`。
- 风险：`无`。
- 复核说明：同时保留as soon as practicable和60日终端期限，避免只建deadline。

### SWOR-R098

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，加拿大NAV CANADA空管设施选择两个双班组合；设施、人员和工作地点均在加拿大。Aurora、Delta和Forest在日班后分别休息11、10、11小时进入午夜班，Bay、Cedar、Harbor普通班间隔10、9、11小时，Elm在午夜班后休息10小时，Grove包含连续第7个工作日。
- C2/C3事实：2026年8月4日，美国FAA空管设施为2026 Basic Watch Schedule选择两个双班组合。记录把临时暂停要求限定为午夜班之前的休息间隔；午夜班之后的间隔、普通班间隔和连续工作日数仍按各组合原始时间记录。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：2026 Basic Watch Schedule期间，午夜班之前必须休息12小时的要求暂停。午夜班结束后仍须至少休息12小时；普通值班之间须至少休息10小时，空中交通管制员不得连续工作超过6日，单日工作不得超过10小时。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":["E1"],"geographic_scope":["E1","E3"],"object_scope":["E1","E2","E3","E4"],"obligations":["E2","E3","E4"],"regulated_subject":["E2","E3","E4"],"threshold_and_equality":["E2","E3","E4"]}`。
- Patch：`external_rule_active, activate_external_rule, rule_blocks_assign_pair_cedar, rule_blocks_assign_pair_elm, rule_blocks_assign_pair_grove`。
- 风险：`无`。
- 复核说明：复核V1.5.1大Patch：暂停仅覆盖午夜班前12小时，不扩展到午夜班后、10小时普通间隔或连续工作日。

### SWOR-R099

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，岬湾视频服务运营商为仅在一处私人设施内运行的订户网络选择频道和非关联节目容量；全部线路位于私人土地和建筑内，不使用公共道路通行权，D方案1984年10月30日生效的特许文本也没有商业租赁接入条款。
- C2/C3事实：2026年8月4日，岬湾有线电视运营商为一个社区系统选择激活频道和非关联节目商的全时商业租赁容量。A、B、C分别有50、60、120个激活频道，其中10、20、40个频道附有联邦使用或禁用命令；D有35个频道且1984年10月30日生效的特许文本没有商业租赁接入条款；频道不可拆分，运营商与节目商无关联关系。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：面向社区多个订户且使用公共通行权的有线系统，激活频道为36至54个时，应从未被联邦要求使用或禁止使用的频道中划出10%；55至100个时划出15%；超过100个时按全部激活频道划出15%，频道数按不可拆分整数处理。少于36个频道通常无需划出，除非1984年10月30日生效的特许文本另有要求；完全不使用公共通行权的私人设施不属于该类系统。
- 纳入证据：`E0, E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E4"],"formal_exceptions":["E0","E4"],"geographic_scope":["E0"],"object_scope":["E0"],"obligations":["E1","E2","E3"],"regulated_subject":["E0","E1","E2","E3","E4"],"threshold_and_equality":["E1","E2","E3","E4"]}`。
- Patch：`plan_a_forbids_reserve_0, plan_b_forbids_reserve_0, plan_b_forbids_reserve_4, plan_c_forbids_reserve_0, plan_c_forbids_reserve_4, plan_c_forbids_reserve_6, plan_c_forbids_reserve_12`。
- 风险：`无`。
- 复核说明：对50/60/120/35频道分别得到4/6/18/0的最低容量；保留联邦命令扣除和私人通行权例外。

### SWOR-R100

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一家电信中继服务设施为统一测量窗口选择人员配置；运营日志把题列100通电话全部标记在同一次网络故障期间，没有来自正常运行窗口的电话。
- C2/C3事实：2026年8月5日，美国一家电信中继服务设施为正常运行窗口选择人员配置；题列100通电话均在网络正常期间到达，日志未记录网络故障，所有直接接通均不会进入队列或保持状态。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：为聋人、听力障碍者、聋盲人或言语障碍者提供与普通语音通信功能等同交流的电信中继设施，在非网络故障期间须以能立即接通、不会排队或保持的方式，在10秒内接听至少85%的全部呼叫；网络故障期间属于明确例外。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E2"],"regulated_subject":["E1"],"threshold_and_equality":["E2"]}`。
- Patch：`exclude_80_percent, exclude_75_percent`。
- 风险：`无`。
- 复核说明：85%含等号；网络故障例外与立即接通统计口径均保留。

### SWOR-R101

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，北湾医疗物流公司在阿拉斯加州内为偏远诊所选择一份气瓶配送委托、飞机和处置包。每个气瓶均为空瓶，已清洗吹扫并拆除阀门，检验记录没有压缩氧气、氧化性气体或危险材料残留。
- C2/C3事实：2026年8月4日，北湾医疗物流公司拟向没有陆路或水路通达的阿拉斯加诊所运输压缩氧气瓶。A和C目的地每周至少有一次纯货运航班，B和D没有；客运与纯货运飞机都可调配；加强处置包用耐火或阻燃毯完全覆盖并固定每个气瓶，并向航空器运营人发出通知。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：在阿拉斯加州内，只有航空是实际可行运输方式时，压缩氧气或其他氧化性气体气瓶可使用航空例外，但每个气瓶须由固定到位的耐火或阻燃毯完全覆盖，航空器运营人还须完成相应通知。每周至少有一次纯货运服务的目的地应使用纯货运飞机；没有每周纯货运服务的目的地可使用客运或纯货运飞机。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E3"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3"],"obligations":["E1","E2"],"regulated_subject":["E1"],"threshold_and_equality":["E2","E3"]}`。
- Patch：`weekly_cargo_destination_a_requires_cargo_only_aircraft, weekly_cargo_destination_c_requires_cargo_only_aircraft, all_exception_shipments_require_blanket_and_notification`。
- 风险：`无`。
- 复核说明：周班目的地飞机分支、无陆水路前提、毯包和通知义务由E1-E3闭合。

### SWOR-R102

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，岚道承运人为一辆美国商业机动车选择20分钟停车地点和警示响应；A、B、C三个候选点均完全位于私人场院内，处于公路行车道和路肩之外，并由场院围界与公路交通分隔。
- C2/C3事实：2026年8月5日，岚道承运人为一辆美国商业机动车选择20分钟停车地点和警示响应。A位于公共公路直线路肩，B位于弯道视距受阻且距弯道不足500英尺的公路路肩，C位于私人场院；A和B停车均不是交通流所必需。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：商业机动车因非必要交通停车而停在公路行车道或路肩时，驾驶员须尽快且最迟在10分钟内部署规定警示装置。若停车点距弯道、坡顶或其他视距障碍不足500英尺，还须朝障碍方向在距停车车辆100至500英尺处增加警示，以向其他道路使用者提供充分预警。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`straight_requires_10m_warning, obstructed_requires_advanced_warning`。
- 风险：`无`。
- 复核说明：10分钟、500英尺触发范围和100至500英尺提前点位均显式保留。

### SWOR-R103

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，溪湾实验室为四名候选员工选择岗位和乙肝疫苗服务。四个岗位只使用密封的非生物模拟物，操作中没有皮肤、眼、口腔黏膜或针刺接触血液及其他潜在感染材料的路径。
- C2/C3事实：2026年8月5日，溪湾实验室为一名员工选择岗位和乙肝疫苗服务。甲和乙的岗位存在皮肤、眼、口腔黏膜或针刺接触血液的可预见路径；雇主拟在甲初次分配后第15个工作日、乙初次分配后第8个工作日提供疫苗；丙有有效完整接种系列记录，丁有有效抗体免疫记录，无人有医学禁忌。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：职业暴露是员工履职中可合理预见的皮肤、眼、黏膜或针刺接触血液或其他潜在感染材料。对有此类暴露的员工，雇主须在完成规定培训后、初次分配岗位起10个工作日内提供乙肝疫苗；已完成全系列接种、抗体检测证明免疫或存在医学禁忌者除外。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1","E2"],"object_scope":["E1"],"obligations":["E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E2"]}`。
- Patch：`day15_requires_acceleration`。
- 风险：`无`。
- 复核说明：复核V1.5.1 Gold/model修正后，唯一新增依赖是甲第15日安排须提前；第10工作日边界及三项例外闭合。

### SWOR-R104

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，新泽西州青岬工厂从A、B、C三个岗位和三个辅助包中各选一项。三个岗位均使用非腐蚀性物料和经认证的封闭工艺，工艺单没有眼睛或身体接触有害腐蚀性材料的路径。
- C2/C3事实：2026年8月5日，新泽西州青岬工厂从三个岗位和三个辅助包中各选一项。A为开放式腐蚀性酸液转移且存在飞溅到眼睛或身体的路径，B为全封闭酸液系统，C为无腐蚀性材料的干燥包装；题列冲洗设施位于工作区并可立即使用。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：美国工作场所中，任何人的眼睛或身体可能接触有害腐蚀性材料时，雇主须在工作区提供适合快速冲淋或冲洗眼睛和身体、可立即用于应急的设施。仅有护目镜或面屏不能替代该设施。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E2"],"obligations":["E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`open_acid_requires_flush`。
- 风险：`无`。
- 复核说明：题内开放酸液路径与立即可用冲洗设施直接绑定；PPE不被误当作替代。

### SWOR-R105

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，澄湾工厂选择一条非食品工业品生产线和辅助服务。A包装金属紧固件，B全封闭灌装工业液体，C储存非食品干货，D在非食品工业区使用安保犬；产品、接触面和包装均不用于人或动物食品。
- C2/C3事实：2026年8月5日，澄湾人用食品工厂选择一条生产线和辅助服务。A为开放式即食食品包装线，B为害虫无法进入的全封闭食品灌装线，C是不接触食品、食品接触面或包装的干货仓，D在食品加工区使用巡逻犬。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：食品工厂不得允许害虫进入食品制造、加工、包装和持有区域，并须采取有效措施排除害虫和防止食品受污染。警卫犬、导盲犬或害虫探测犬只有在其存在不太可能污染食品、食品接触面或食品包装材料的区域才可进入。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`open_food_requires_exclusion, dog_requires_segregation`。
- 风险：`无`。
- 复核说明：开放食品线与犬只分支分别由E1、E2支持。

### SWOR-R106

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，路易斯安那州蓝湾炼厂只生产柴油，四个候选计划的产品均在独立于汽油设施的生产、储存和出口系统中运行。
- C2/C3事实：2026年8月5日，路易斯安那州蓝湾炼厂作为国内汽油制造商选择生产期计划和硫控制包。四个计划的产品均为汽油并在制造设施出口交付，没有铁路或卡车进口、下游氧化物调和或其他登记路径。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：汽油制造商每个合规期的平均硫含量不得超过10.00 ppm；制造设施出口的任一加仑汽油硫含量不得超过80 ppm。判断出口峰值时不得把下游添加含氧化合物造成的稀释计入合规。平均值等于10.00 ppm、单加仑等于80 ppm均满足上限。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`average_noncompliance_needs_average_control, peak_noncompliance_needs_peak_control`。
- 风险：`无`。
- 复核说明：平均期上限与设施出口逐加仑峰值分别建模，等号边界明确。

### SWOR-R107

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，西岭铁路公司安排一辆已排空、清洗吹扫且无危险品标牌或危险材料残余的铁路罐车相对机车的位置；B、C、D的中间车辆均为普通无标牌车辆。
- C2/C3事实：2026年8月4日，西岭铁路公司安排一辆仍含危险材料残余的罐车。A中该罐车紧邻机车，B仅由另一辆仍悬挂危险品标牌的罐车隔开，C和D分别已有普通无标牌平车和棚车隔开；所有方案另一端均不靠近有人值守的守车。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：仍含危险材料残余的铁路罐车与机车或有人值守的守车之间，至少须由一辆不是悬挂危险品标牌罐车的铁路车辆隔开。另一辆有标牌罐车不能充当所需隔离车辆，普通无标牌棚车或平车可以。
- 纳入证据：`E1`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`plan_a_requires_plain_buffer_assignment, plan_b_requires_plain_buffer_despite_placarded_tank`。
- 风险：`无`。
- 复核说明：重点保留‘other than a placarded tank car’，避免把B中有标牌罐车误算缓冲。

### SWOR-R108

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，印第安纳州桦港仓库为四名候选人员安排纸面或模拟器练习；叉车未通电、未移动，没有员工控制实体动力工业车辆。
- C2/C3事实：2026年8月5日，印第安纳州桦港仓库选择一名人员实际操作叉车并匹配模式。甲完成本车型与场所培训及操作评估；乙和丙只完成课堂阶段，分别位于隔离训练区和无法封闭的人车混行区；丁未参加培训且未进入学员训练程序。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：员工在非训练情形操作动力工业车辆前，雇主须确保其成功完成规定培训。学员只有在具备知识、培训和经验的人员直接监督下，并且操作不会危及学员或其他员工时，才可实际操作车辆。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E2"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`busy_trainee_operation_ineligible, untrained_operator_ineligible`。
- 风险：`无`。
- 复核说明：隔离区受监督训练与繁忙人车混行区的危险条件分开绑定。

### SWOR-R109

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，密歇根州松汀工厂选择室内应急布局和设备调整包。书面应急行动计划要求所有普通员工立即全部撤离；题列灭火器仅供训练有素的消防队使用或作为自动保护设备，普通员工没有操作权限。
- C2/C3事实：2026年8月5日，密歇根州松汀工厂选择供普通员工使用的灭火器布局和设备调整包。普通员工有操作权限且应急计划没有全员仅撤离安排；A、B为易燃液体危险区，C为普通可燃物区，D加工可燃金属并且金属粉末、薄片或刨屑每月产生一次。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：当便携灭火器供员工使用时，A类普通可燃物区域到任一适用灭火器的行走距离不得超过75英尺，B类易燃或可燃液体危险区不得超过50英尺。D类灭火剂应位于可燃金属作业区75英尺内，但只有每两周至少产生一次金属粉末、薄片、刨屑或类似产品时才强制配置。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E4"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3","E4"],"obligations":["E3","E4"],"regulated_subject":["E1"],"threshold_and_equality":["E3","E4"]}`。
- Patch：`classb65_requires_move`。
- 风险：`无`。
- 复核说明：facts去掉制度标签；规则说明A/B/D阈值，其中D每月一次未达到每两周一次。

### SWOR-R110

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Baltic Corridor Authority为欧盟境内一条封闭私人工业道路选择四个充电项目。道路只供获准进入园区的车辆使用，TEN-T道路登记未列入该走廊，边界池和新池均只向园区车辆开放。
- C2/C3事实：2026年8月4日，Baltic Corridor Authority为一段180公里的TEN-T核心公路走廊选择2027年轻型车辆公共充电项目。两个方向在km0和km180各有一座620 kW且含两个180 kW充电点的公共边界池；每座新池仅服务题列方向，并在2027年12月31日前建成，规格相同。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：到2027年12月31日，TEN-T核心公路网络须在每个行驶方向部署面向轻型电动车的公共充电池，使相邻充电池距离最多为60公里。届时每座充电池总输出功率至少600 kW，并至少包含两个单点功率150 kW以上的充电点。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1"],"threshold_and_equality":["E1","E2"]}`。
- Patch：`cover_east_left, cover_east_middle, cover_east_right, cover_west_left, cover_west_middle, cover_west_right`。
- 风险：`无`。
- 复核说明：六个方向区段覆盖由60公里最大间距和两端既有池确定；功率规格满足2027门槛。

### SWOR-R111

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一家制造商为两个已批准且未过期的PET药品批次选择配送顺序；两个批次的生产和批记录均使用正电子发射断层扫描药品流程。
- C2/C3事实：2026年8月5日，美国一家制造非PET、非医用气体成品药的企业，为1月旧批次和6月新批次选择配送顺序。两批均已批准、未过期且可追溯；B方案的稳定性复核有书面起止记录，复核结束后恢复旧批次优先。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：供人或动物使用的成品药应建立最早获批库存优先配送程序；只有临时且适当的偏离才允许。该制度不覆盖PET药品和医用气体。长期按销售偏好优先新批，或在旧批仍可用时只发新批，均不是临时偏离。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E2"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E2"],"regulated_subject":["E1"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`permanent_new_first_ineligible, new_only_ineligible`。
- 风险：`无`。
- 复核说明：临时且适当的偏离保留，永久销售偏好和本轮只发新批被区分。

### SWOR-R112

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一家直接向消费者提供食品的零售场所，为一批带壳鸡蛋选择收货与储存包。在任何候选收货动作前，全批鸡蛋已完成经验证的专门处理，记录显示每枚鸡蛋中的全部viable Salmonella均已灭活。
- C2/C3事实：2026年8月5日，美国一家直接向消费者提供食品的零售场所，为未做沙门氏菌灭活处理的带壳鸡蛋选择收货与储存包。四个包分别在产蛋后24、40、40和60小时收货，并立即置于50°F、50°F、45°F和42°F环境。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：零售场所是直接向消费者储存、准备、包装、供应、销售或以其他方式提供食品的经营场所。零售场所收到带壳鸡蛋后须及时冷藏，并在持有期间保持环境温度不高于45°F；只有不可避免的短暂延误才可尽快补做冷藏。已专门处理并灭活全部viable Salmonella的鸡蛋免于上述要求。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1","E2"],"geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_24h_50f, exclude_40h_50f`。
- 风险：`无`。
- 复核说明：复核V1.5.1 Gold/model修正：真实边界是收货后及时冷藏且不高于45°F，不恢复旧36小时或45°F以上表述。

### SWOR-R113

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一座工业设施把题列火炬登记为仅供内部安全备用和可靠性测试的设备；设施许可没有用该火炬满足排放限值，也没有把该火炬纳入强制排放控制方案。
- C2/C3事实：2026年8月5日，美国一座工业设施在连续两小时正常运行窗口操作许可中用于排放控制的火炬；日志没有启动、停机、故障或紧急事件，也没有其他替代运行标准。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：用于排放控制的工业火炬须始终保持火焰。在任意连续两小时内，通常不得出现可见排放；允许的可见排放时段累计不得超过5分钟。累计正好5分钟不超限，但任何火焰中断均不满足持续燃烧要求。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E1"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1","E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_more_than5_visible_minutes, exclude_missing_continuous_flame`。
- 风险：`无`。
- 复核说明：facts改为许可和运行记录，不公开40 CFR编号；5分钟等号与持续火焰为独立条件。

### SWOR-R114

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一座陆上非运输储油设施选择内部围堤设计。每个容量单位为10美制加仑，最大单罐1000加仑，地上罐合计1300加仑且埋地罐为0；场址坡面和排水沟全部汇入无外排口的场内衬里集液池。
- C2/C3事实：2026年8月5日，美国一座陆上非运输散装储油设施选择最大单罐围堤设计。每个容量单位为20美制加仑，最大单罐2000加仑，地上罐合计2400加仑且埋地罐为0；场址排水沟连接毗邻的美国可航水域岸线，暴雨设计另需10个容量单位自由高。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：因位置而可能向美国可航水域或相邻岸线有害排油的陆上非运输储油设施进入防油要求；地上总容量不超过1320美制加仑且完全埋地总容量不超过42000加仑的设施不进入。进入要求的散装储油罐安装须提供能容纳最大单罐全部容量的二次围护，并另留足以容纳降水的自由高。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1"],"object_scope":["E1","E2","E3"],"obligations":["E3"],"regulated_subject":["E1"],"threshold_and_equality":["E2","E3"]}`。
- Patch：`exclude_capacity_below110`。
- 风险：`无`。
- 复核说明：容量单位换算、适用门槛、最大单罐和降水自由高均可直接计算。

### SWOR-R115

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，美国一家按Medicare熟练护理机构类别登记和结算的机构，为内部质量审查选择10人队列；机构档案和账单均使用SNF分类及支付代码，本次审查不提交住院康复机构分类或支付申报。
- C2/C3事实：2026年8月5日，美国一家既有住院康复机构为始于2026年的连续12个月审查期选择10人患者组合；机构不是新设机构且期间没有新增床位。患者档案分别记录卒中、脊髓损伤、股骨髋部骨折、烧伤或普通术后去适应，以及需要强化康复的事实。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：既有住院康复机构在2005年7月1日以后开始的报告期内，至少60%的住院患者须因列明病况而需要强化康复。列明病况包括卒中、脊髓损伤、股骨髋部骨折和烧伤；普通术后去适应本身不在列明清单。比例等于60%满足要求。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1","E2"],"object_scope":["E2"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`exclude_five_of_ten, exclude_four_of_ten`。
- 风险：`无`。
- 复核说明：facts从‘支付分类制度’标签改为真实登记、账单、机构状态和患者诊断记录；60%分子定义闭合。

### SWOR-R116

- V1.6.2：已按用户授权定点修复，等待本版全量检查；下述旧复核说明为历史记录，不代表新审查通过。
- C1事实：2027年12月15日，Silver Plains私人乡村诊所选择就诊批次和内部技术或人员组件。诊所未在Medicare登记或认证为RHC或FQHC，全部就诊由患者自费，台账不使用G2025、RHC或FQHC账单代码，Cedar和Delta仅为内部协作服务。
- C2/C3事实：2027年12月15日，Medicare认证的Silver Plains乡村健康诊所选择就诊批次和共享资源。Atlas以G2025登记为非行为健康纯音频就诊；Birch为居家心理健康音视频就诊且最近六个月没有面诊；Cedar和Delta均登记为incident-to服务，远程参与者分别仅用实时音频和使用实时音视频参与，Cedar可以另配置现场监督执业者。
- C3规则材料：在2027年12月15日的决策时点，下述规则处于有效期：RHC和FQHC的非行为健康远程服务可继续以G2025报告至2027年12月31日，包括纯音频服务。远程心理健康服务须在前六个月面诊并每12个月复诊的要求要到2028年1月1日之后才生效。对需要直接监督的服务，监督者可通过实时音视频互动提供监督，但纯音频不满足直接监督。
- 纳入证据：`E1, E2, E3`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E1","E2"],"formal_exceptions":["E1","E2","E3"],"geographic_scope":["E1","E2","E3"],"object_scope":["E1","E2","E3"],"obligations":["E1","E3"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`cedar_needs_onsite`；四条平台技术依赖已进入Base。
- 风险：`无`。
- 复核说明：G2025截止日、心理健康面诊延后和直接监督排除纯音频三个分支分开保留。

### SWOR-R117

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，在瑞士设立并从苏黎世运营的非美国贷款人，为十一份直接与PdVSA签订、在欧洲或亚洲交付的油品合同选择融资。签约、融资、付款和争议履行均在美国境外，使用欧元并经瑞士银行清算，参与者和代理均非美国人员。
- C2/C3事实：2026年8月4日，一家2022年在特拉华州注册的公司，为十一份直接与PdVSA签订并把委内瑞拉原产油品进口美国的合同选择融资。合同选择纽约州法，PdVSA由非中国主体独立控制且未与中国主体共同经营，承运船舶无冻结记录，商业合理的美元付款进入指定账户。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：自2026年6月10日起，美国既有实体为进口美国而从事委内瑞拉原产油品的装运、出口、销售、购买、交付、运输及通常附随且必要的融资交易，可在授权范围内进行。与委内瑞拉政府、PdVSA或其直接间接持股50%以上实体订立的合同，必须适用美国某州或其他美国辖区法律，并把争议解决安排在美国、英国、法国或新加坡。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2"],"formal_exceptions":["E1"],"geographic_scope":["E1"],"object_scope":["E1"],"obligations":["E1"],"regulated_subject":["E1"],"threshold_and_equality":["E1"]}`。
- Patch：`current_forum_ineligible_geneva_forum, current_forum_ineligible_dubai_forum, current_forum_ineligible_toronto_forum`。
- 风险：`无`。
- 复核说明：三个非允许争议地与允许的美国/英国/法国/新加坡边界由GL 46C完整引文支持。

### SWOR-R118

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，青石设备公司按独立check-off授权处理工会会费，款项收至工会账户；工资和授权记录确认该款不是参与者退休计划缴款、参与者贷款还款或员工福利计划资产。
- C2/C3事实：2026年8月4日，青石设备公司为年初有82名参与者的ERISA退休计划处理员工工资代扣缴款，收款人为计划账户；工资核对记录显示最迟可在原应付工资日后的第6个营业日把款项从公司一般资产中分离。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：雇主须在参与者缴款能够合理地从公司一般资产分离后的最早日期，将其存入员工福利计划。对计划年度开始时少于100名参与者的计划，工资代扣款在原本应以现金支付给参与者之日后的第7个营业日以内存入，可选择使用小型计划安全港；第7日包含在内，第9日不在安全港内。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E2"],"geographic_scope":["E1","E2"],"object_scope":["E1","E2"],"obligations":["E1"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E2"]}`。
- Patch：`small_plan_safe_harbor_excludes_day9`。
- 风险：`无`。
- 复核说明：实际最早可分离日为第6日，但安全港仍包含第7日；Gold只排除第9日，与现有模型一致。

### SWOR-R119

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月5日，北岸互联VoIP管理员为封闭企业专用编号网络选择内部呼叫业务和主叫信息策略。四类呼叫均在同一企业专网内起止，不连接PSTN，目的端均为内部分机，也不连接911、ANI订户、公共紧急线路或消费者号码。
- C2/C3事实：2026年8月5日，北岸互联VoIP提供商为PSTN呼叫选择业务和主叫信息策略。A是拨打*67的普通州际SS7住宅呼叫，B由被叫方付费且被叫方订购ANI或计费号码服务，C拨打公共机构911线路，D代表营利商家电话营销；卖方客服号码真实有效，运行记录没有威胁调查。
- C3规则材料：在2026年8月5日的决策时点，下述规则处于有效期：提供CPN服务的公共通信承运人不得覆盖普通州际呼叫的隐私指示；呼叫方要求不传递CPN时，不得向被叫方泄露其号码或姓名。被叫方付费并订购ANI或计费号码服务，以及公共911或列明紧急线路属于隐私指示的正式例外。电话营销不得阻断主叫识别信息，须传CPN或ANI；可使用所代表卖方名称及能在营业时间接收拒接请求的真实客服号码。
- 纳入证据：`E1, E2, E3, E4`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":"NOT_APPLICABLE","formal_exceptions":["E3","E4"],"geographic_scope":["E1","E2","E3","E4"],"object_scope":["E1","E2","E3","E4"],"obligations":["E1","E2","E3"],"regulated_subject":["E1","E2","E3"],"threshold_and_equality":"NOT_APPLICABLE"}`。
- Patch：`ordinary_private_requires_suppression, telemarketing_forbids_privacy_block, telemarketing_requires_permitted_identity`。
- 风险：`无`。
- 复核说明：普通隐私、ANI/911例外和电话营销识别三条分支分别闭合。

### SWOR-R120

- 审查：`READY`；C2完整性：`PASS`。
- C1事实：2026年8月4日，Summit Wireless仅持有日本运营牌照并选择六款在日本销售和供使用的手机；牌照、门店、客户账户和销售目录全部位于日本，美国销售与供使用目录为空。
- C2/C3事实：2026年8月4日，Summit Wireless作为美国全国性数字移动服务商选择六款手机；入选六款构成该公司在美国经所有digital air interface销售或供使用的完整机型清单，题列HAC状态来自当前技术认证记录，决策日在2027年6月14日之前。
- C3规则材料：在2026年8月4日的决策时点，下述规则处于有效期：手机型号组合是制造商或服务提供商在美国销售或供使用的全部手机型号。对美国全国性服务提供商，在2027年6月14日前，组合中至少85%的型号须按当前技术标准具备助听器兼容认证；计算结果向下取至最接近的整数。因此六款完整组合至少须有五款具备该认证。
- 纳入证据：`E1, E2`。
- 排除的C1专属证据：`无`。
- 规则覆盖：`{"effective_date":["E2"],"formal_exceptions":"NOT_APPLICABLE","geographic_scope":["E1"],"object_scope":["E1","E2"],"obligations":["E2"],"regulated_subject":["E1","E2"],"threshold_and_equality":["E2"]}`。
- Patch：`external_rule_active, activate_external_rule, pre_2027_hac_portfolio_floor`。
- 风险：`无`。
- 复核说明：复核非add_constraint内部开关；85%×6向下取整为5，规则段不泄露最终产品组合。
