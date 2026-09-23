# SearchWorthyOR-v1.6.1 C1/C2/C3 修订规范（执行版）

## 1. 来源与范围

- `SearchWorthyOR-v1.5.1` 是只读来源。
- 对120个 source task 各生成 C1、C2、C3，共360个 case。
- 本轮只构建和验证数据集，不运行正式 Agent 实验。
- 任一题若发现原 C2 的证据、Gold、Patch 或 Full IR 错误，必须先阻断并记录，不能从错误 C2 自动生成 C3。

## 2. 三状态合同

| Role | State | 搜索 | 适用性 | 初始模型 | 最终模型 | Patch | 模型改变 | 决策改变 |
|---|---|---:|---:|---|---|---|---:|---:|
| C1 | RETAIN | true | false | base | base | `[]` | false | false |
| C2 | PATCH_CHANGES | true | true | base | full | 非空 | true | true |
| C3 | NO_SEARCH | false | true | full | full | `[]` | false | false |

初始模型的时点是读完该 case 的全部可见输入之后。`patch=[]` 既可能是 RETAIN，也可能是 NO_SEARCH，不能脱离其他状态字段评分。

## 3. 公开事实与 prompt

每个公开 case 使用一个 `case_facts_zh` 字符串。它必须是自然语言现实场景，包含建模所需的具体日期、真实地名/设施或机构、主体角色、实际行为或路径、对象、材料、编码与数量；不得显示 JSON 分类标签，不得以规范分类替代底层事实，也不得直接给出适用性结论或待搜索规则。

C3 的事实由构建器字节级复制 C2。单题 prompt 顺序固定为：

1. 本 case 权威事实；
2. 仅 C3 出现的随题规则材料；
3. 优化骨架；
4. 公开 output schema。

不在单题中重复数据集设计说明。正式模型输入只有盲化 `eval_id` 与 `prompt_zh`；内部 case ID、source task、triplet 和 role 只在 private 映射中。公开 tasks 按 `id` 严格排序，公开 cases 按随机 `eval_id` 严格排序。

## 4. C3 规则材料

`rule_information_zh` 是 C2 实际需要检索的信息的简明自然语言浓缩，不是答案、Patch 或网页摘抄。它必须在与本题建模相关时覆盖：

- 生效日期；
- 地理范围；
- 适用主体；
- 对象范围；
- 阈值方向与等号边界；
- 义务；
- 正式例外；
- Multi 题的全部独立规则分支。

某一轴在该规则中确实不存在时，private coverage 可写 `NOT_APPLICABLE`。公开规则材料不得包含 URL、证据节点、case/state 标签、搜索结论、Patch 名、私有变量、正确行动或目标值。官方 publisher、URL、原文与节点只保存在 private provenance。

逐题修订分片只编写核心规则文本。构建器必须从只读 V1.5.1 `private/v151_case_repair_records.jsonl` 读取同一 source task 的 C2 ISO `decision_date`，并在所有120条最终规则前统一添加：

```text
在YYYY年M月D日的决策时点，下述规则处于有效期：
```

月份和日期不得补前导零。该前缀只闭合下述规则在决策时点是否有效，不判断本 case 的主体、对象、地域、阈值或例外是否命中，不能用履约截止日、报告期边界或历史特许日期替代。规范化后的完整文本必须在公开 C3、private provenance、`v161_revision_records.jsonl`、README 和 `V161_REVISION_RECORDS_zh.md` 中保持一致；验证器须独立从 C2 日期重算并检查精确前缀。

## 5. 证据准入与模型关系

- 每条公开规则材料必须显式列出纳入的 official evidence source node。
- C1 专属排除证据必须单独列出，不能进入 C3 provenance。
- coverage 的每个非空轴必须映射到已纳入节点。
- 纳入节点的 `supported_patch_slots` 并集必须覆盖全部 Base-to-Full Patch 名称。
- C2 满足 `apply(base_ir, patch) ≡ full_ir`。
- C3 满足 `initial_ir = final_ir = full_ir` 且 `patch=[]`。
- C2 的最终完整最优行动集合与目标必须等于 C3 的初始和最终结果。
- 所有新增official evidence与verification记录动态一一对应，task/node/URL/quote精确一致且均为PASS；本源码快照当前为6个，不把数量写死在代码门中。

## 6. 私有元数据 override

- 构建输入 `scripts/v161_private_metadata_overrides.json` 使用固定 schema，只允许一条 R112 记录及 `old_value`、`new_value`、`evidence_source_node_ids`、`reason`、`review_notes` 五个字段。
- 构建器必须先确认 `old_value` 与只读 V1.5.1 R112 `task_assets.applicability_decision.reason` 字节级相同，并确认 E1/E2 均存在；随后只能替换该 reason，其他字段不得变化。
- override 文件必须原样复制到 `private/v161_private_metadata_overrides.json`，并在 README 与全量修订记录中写明 old/new、证据和限定路径。
- 验证器必须独立重查 target override schema、R112 new value、old value 消失、E1/E2、公开字段与逐题修订合同、Gold/Patch/模型合同，以及其他119题 reason 未受 override 影响。

## 7. R001 校准

R001 必须满足：

```text
C1: base 69 -> base 69, patch=[]
C2: base 69 -> full 65, patch non-empty
C3: full 65 -> full 65, patch=[]
```

Base 有40个可行赋值，唯一最优为 A/B/C 且 P=0；Full 有31个可行赋值，唯一最优为 B/C/E 且 P=0。C2/C3 的最终完整最优行动集合与目标相同。现有只支持 C1 排除的证据节点不得进入 C3。

## 8. Opaque ID 与盲审快照合同

- 360 个公开 `eval_id` 必须由密码学随机源首次生成，不得从 `case_id`、role 或 state 推导；每个 ID 使用 `SWOR-E-` 加20位大写十六进制 token，互不重复。
- 构建侧持久映射固定为 `scripts/.private/v161_opaque_eval_ids.json`，schema 与360个 canonical `case_id` 覆盖必须精确。后续构建稳定复用；验证器必须读取它并核对 public、identity，且拒绝全部旧无盐 BLAKE2 ID。
- 该持久映射不得复制到 public、不得进入 prompt 或模型上下文，也不得被构建器打印。它只用于构建与 scorer 身份绑定。
- 每题 public 快照 payload 是 canonical JSON：完整公开 task 加三条完整公开 case，case 按 opaque `eval_id` 排序；payload 包含公开 case 的全部字段。
- 每题 private cross-check 快照绑定最终 revision/provenance（含证据与 Patch 覆盖）、修改后 task asset、task Gold、Base/Full/solve、三条 case Gold/search contract、相关 `v161_new_evidence_verification.json` 记录和该题 metadata override（无则 null）。新证据 verification 必须与 evidence addition 的 task/node/URL/quote 精确对应且状态为 `PASS`。
- 两个 digest 均固定使用 BLAKE2b-256，并共同写入 `private/public_review_snapshot_manifest.jsonl`。验证器必须分别从最终 target public+identity 与 private+models 独立重建。
- 源审查分片 schema 固定为 `searchworthyor.v161.public_first_review.v3`，每条同时记录 `public_snapshot_id` 与 `private_crosscheck_snapshot_id`。正式构建必须在触碰 target 前重算120组双快照，并要求每条审查精确绑定当前两个 digest、`PASS`、五项 status 全 `PASS`、`issues=[]`、reviewer/review_notes 非空。
- 三个revision shard是case层修改的外部授权源，三个v3 review shard是target外部审查信任锚；验证器必须安全读取并要求target revision/review逐题精确投影，禁止只信任target内可同步重算的无密钥摘要。
- 最终 reviewer 固定为：A=`Codex final blind reviewer A`、B=`Codex final blind reviewer B`、C=`Codex final blind reviewer C`；三者 `reviewer_generated_shard` 均为 `NONE`，并且三者均未参与 revision 或 builder/validator 修改。
- 固定 reviewer 字符串和 `NONE` 是可审计的流程声明，不是密码学身份认证。机器验证只能证明声明、公开快照与记录一致，不能证明键盘后的真实身份；也不能替代人类法律复核。
- 草案迁移命令为 `python "20260710_Align Opt-Miner Agent Workflow/scripts/build_searchworthyor_v161.py" --allow-pending-blind-review --update-existing`。v1/缺失记录的两个 digest 均为 `UNBOUND`；v2 保留 public digest、private digest 为 `UNBOUND`；v3 stale 双 digest 原样保留。构建器不得自动填入当前 digest。全新 reviewer 完成 public-first 后再 cross-check private，手工更新源分片为 v3；最后去掉 allow flag 正式重建。

## 9. 构建与验证门槛

- V1.5.1只读源必须同时命中375 files、7,062,812 bytes、123 directories和固定BLAKE2b树指纹 `34c96a3e70665fbe297e5270c037f6ce3dad922591169cc0f7bf2ed5bc27b25f`；树摘要锁文件路径/大小/内容，目录计数阻断额外空目录。
- V1.6.1 exact closure为386 files、124 directories（不计根）：root5/public2/private16/models360/inherited3；拒绝任何extra/missing路径。
- source/target/datasets root固定名、resolve不相交；Windows inventory用`os.scandir`+`os.lstat`且不跟随链接，拒绝symlink/junction/reparse/special/hardlink。revision/review/template/override/evidence和opaque map也必须是plain、非reparse、single-link regular file。
- 既有target首个实质写入必须是`BUILD_IN_PROGRESS` marker与同状态报告；源后指纹和带marker闭包通过后才可写NOT_RUN并删除marker。验证器对unsafe/incomplete/marker目标零写，对安全目标先原子写VALIDATION_IN_PROGRESS；任一parse/字段异常必须写FAIL，不能遗留旧PASS。
- 120 tasks、360 public cases、360 private Gold、120 triplets。
- 每题恰有 C1/C2/C3；随机盲 ID 唯一、不含类别或状态、与构建侧持久映射严格一致，旧无盐可枚举 ID 为硬失败。
- public tasks/cases 分别按 `id`/`eval_id` 严格排序。
- C2/C3 facts 字节级相同，优化骨架和 schema 相同。
- prompt 可由公开字段独立确定性重建。
- 每条 C3 规则以同题 V1.5.1 C2 `decision_date` 对应的统一中文规则有效期前缀开头，且该前缀不得断言本 case 适用。
- public 对所有nested key/value递归检查，无private/Gold/state/search/model/evidence/provenance键族、case/triplet/role/state标识、URL、节点ID、长官方原文、答案或IR路径；私有变量/constraint/Patch token只能继承V1.5.1原公开骨架/schema白名单。
- 每个 task 只有 Base/Full/solve result；无 patched IR。
- 全120 Base精确继承V1.5.1 Base，Full精确继承V1.5.1 patched并仅改variant=full；不接受越权的语义等价重写。
- 独立重放全部 Patch，并完整枚举全部 Base/Full。
- solve_result使用精确字段与完整枚举合同；Gold boolean必须是真bool，C1/C3 Patch必须是list且严格为空，C2 Patch精确，official_support及search pages/quotes/object按source node有序精确投影。
- 全部 UTF-8 文件可解码且无替换字符。
- 机器检查之后再由三位未参与生成/代码修改的固定全新 reviewer 执行 public-first 独立盲审；Codex 审查不得冒充人类复核。
- 不带 `--allow-pending-blind-review` 的正式构建必须120题 v3 盲审全部 `PASS`、空 issues、固定 reviewer 声明并精确绑定独立重算的当前 public/private 两个 BLAKE2b-256 快照。带 flag 的草案构建只迁移或保留原状态/旧 digest，不得伪造 `PASS` 或当前快照。
