# SearchWorthyOR-100

SearchWorthyOR-100 是一个面向“检索增强运筹优化建模”的中文数据集。

它研究的不是模型能否从一段完整题面翻译出数学规划，而是一个更接近真实工作的过程：

> 企业已经给出了候选方案、收益、资源消耗和本地业务约束，但最终决策还必须遵守某份外部政策、合同或监管规则。建模者需要先找到真正适用的规则，再据此修改模型结构并重新求解。

因此，每道题同时考查信息检索、规则适用性判断、数学建模和优化求解。

> **当前状态：候选审计版，尚未通过严格的搜索评测发布门。** 100 个基础/补丁模型、双求解器结果和行动集证书可以用于模型侧审计；但 vFINAL10 内容红队发现，四候选的组内多数结构仍可在不读取题面的情况下识别适用文档。因此，当前版本不得用于宣称正式的端到端搜索能力。README 保留完整使用与评分协议，是为了明确下一版重构干扰来源后应如何验收。

> **公开仓库边界：本仓库是开放开发集，不是保密测试集。** 仓库中包含
> `private/gold.jsonl`、证据语料和模型复核材料；`private/` 表示评测接口角色，不表示 GitHub
> 访问权限。模型或开发者一旦读过这些文件，就不能在同一 100 题上声称无污染的隐藏测试结果。
> 可复现实验应报告污染状态并在运行时隔离 Gold；正式 leaderboard 必须使用另行冻结、从未公开、
> 不与本仓库共享政策模板和 base 的 held-out 集。

> **许可边界：仓库当前没有 `LICENSE`。** 公开可见不等于自动授予复制、修改或再分发许可；
> `private/web_snapshots/raw/` 中的第三方网页/PDF仍受各原始来源条款约束。选择代码/数据许可证和
> 逐项确认网页快照再分发权之前，本仓库应视为审计性公开，而不是已完成法律清理的正式数据发行版。

## 一道完整题目包含什么

一条完整任务不是单独一段题面，而是由四个相互关联的层组成：

| 层 | 每题内容 | 答题时是否可见 |
|---|---|---|
| 公开题目 | 中文问题、决策日期、主体、辖区、输出要求和检索入口 | 可见 |
| 检索语料 | 1 份适用证据和约 3 份旧版本、错误辖区、错误主体或非权威干扰文档 | 仓库可见；答题进程只通过检索接口访问 |
| Gold | 适用来源、基础模型审计、结构补丁、最终模型、最优行动和证书 | 仓库可见；答题进程不可见 |
| 模型产物 | 基础/最终 canonical IR、Gurobi/COPT 代码、解和残差 | 仓库可见；答题进程不可见 |

四层通过任务 `id`、Gold 中的 `evidence_ids`、模型路径和内容哈希关联。公开题目不会给出证据 ID，因此 Agent 必须使用自然实体、日期、辖区和业务语义检索。

## 问题是什么

一条任务首先给出一个完整的单目标基础优化问题 \(M_0\)：

- 有哪些候选行动；
- 每个行动带来多少收益或成本；
- 消耗哪些资源；
- 已知的覆盖、容量、互斥、选择数量等业务约束；
- 唯一的优化目标。

这些本地数据没有挖空，也不需要通过搜索补一个成本、容量或阈值。仅根据题面，普通 OR 专家已经可以建立并求解基础模型。

但是，题目同时指定了决策日期、经营主体、辖区和业务活动。某份外部规则可能要求：

- 某类行动没有资格进入候选集合；
- 两个跨期决策必须联动；
- 选择某行动后必须激活另一变量或约束；
- 服务组合、风险敞口或采购结构必须满足额外要求；
- 原目标函数必须加入一种新的结构性评价项。

建模者需要从证据库中找出适用版本，排除旧版本、错误辖区、错误主体和非权威来源，并把规则转化成非空的结构补丁，得到最终模型 \(M_1\)。

## 一个直观示例

下面是说明任务形式的虚构示例，不对应数据集中的任何具体答案。

某医院要从若干班次模板中选择本周排班，目标是最大化服务覆盖收益。基础模型包含：

\[
\max \sum_s v_s x_s
\]

以及工时上限、最低覆盖人数和班次互斥约束。只看本地数据时，连续安排两个夜班可能是最优方案。

题目没有直接告诉建模者：决策日适用的劳动协议规定，承担某类夜班后必须在下一周期安排完整休息。建模者需要搜索该医院、辖区和日期适用的协议版本，并确认例外条款不适用。

检索到规则后，模型可能需要加入跨期约束：

\[
x_{i,t}^{\text{night}} + x_{i,t+1}^{\text{work}} \le 1.
\]

这不是把“最多工作多少小时”填进一个空白参数，而是新增了时间索引之间的耦合关系。最终可行域和最优排班都会发生变化。

SearchWorthyOR-100 中的每道题都遵循这一逻辑：搜索得到的信息必须改变优化模型结构，并且搜索前后的可接受最优行动不存在公共解。

## 解一道题需要做什么

建议把每条任务理解为以下五步。

1. **建立基础模型**  
   从中文题面识别集合、参数、决策变量、唯一目标和全部本地约束，得到 \(M_0\)。

2. **提出检索需求**  
   根据自然实体、决策日期、辖区和业务活动描述需要查找的规则。不能使用隐藏的文档 ID 或任务—答案映射。

3. **判断规则是否适用**  
   比较来源权威性、版本、有效期、辖区、主体范围和例外条款，拒绝近似但不适用的文档。

4. **修改模型结构**  
   说明规则改变了哪些变量、索引、变量域、约束、条件逻辑或目标项，并给出完整最终模型 \(M_1\)。

5. **求解并解释决策**  
   报告最优行动和目标值，同时给出“证据主张 → 模型位置 → 方程 → 实现区域”的对应关系。

公开题目要求输出：

- 适用来源与理由；
- 结构性模型补丁；
- 最终单目标模型；
- 最优行动与目标值；
- claim-to-model-slot 映射。

## 它与普通 OR 文本建模数据集有什么不同

| 普通 OR 建模题 | SearchWorthyOR-100 |
|---|---|
| 题面包含建立最终模型所需的全部规则 | 题面只包含完整基础模型，最终规则必须检索 |
| 主要考查自然语言到数学模型的翻译 | 同时考查检索、适用性裁决、模型修改和求解 |
| 外部知识通常只是背景常识 | 外部证据必须对应一个可验证的结构补丁 |
| 找错来源可能仍能写出形式相似的模型 | 旧版本、错误辖区和错误主体会产生错误模型 |
| 常用目标值或单个 incumbent 判断答案 | 本数据集比较完整的可接受最优行动集合 |
| “补一个数字”也可能被视为知识增强 | 纯参数填空和 fogging 不进入主数据 |

## 数据覆盖

数据集包含 100 条任务，每条对应一个不同的基础模型。

| OR 家族 | 数量 | 典型决策 |
|---|---:|---|
| 路径与运输 | 10 | 路径包、运输服务或车队方案选择 |
| 排班与劳动力 | 10 | 班次模板和人员覆盖 |
| 生产与容量规划 | 10 | 生产模式和容量配置 |
| 分配与匹配 | 10 | 对象分配和匹配方案 |
| 设施选址与网络设计 | 10 | 设施、节点和网络覆盖 |
| 库存与供应链 | 10 | 补货、供应模式和跨期配置 |
| 能源与环境 | 10 | 能源项目和环境合规组合 |
| 医疗资源配置 | 10 | 服务单元和医疗资源组合 |
| 金融与组合选择 | 10 | 投资方案和风险组合 |
| 通信与服务系统 | 10 | 服务模块和网络资源配置 |

四类模型变化各有 25 条：

- 资格、动作可用性和变量域；
- 时间窗、先后关系和跨期耦合；
- 条件激活、分段规则和辅助变量；
- 配额、风险、服务组合和目标项结构。

## 如何读取公开任务

公开输入位于 `public/tasks_zh.jsonl`。每行是一条 JSON 记录：

| 字段 | 含义 |
|---|---|
| `id` | 任务标识，仅用于提交和评测 |
| `problem_zh` | 完整中文题面，包括候选数据和基础业务约束 |
| `decision_time` | 判断规则版本是否有效的决策日期 |
| `entity` | 作出决策的自然业务主体 |
| `jurisdiction` | 需要判断规则适用性的辖区 |
| `required_output` | 期望提交的答案组成 |
| `allowed_retrieval_interfaces` | 允许使用的语义检索入口 |

`public/tasks_zh.jsonl` 不包含适用规则正文、证据 ID、patch 类型、参考代码、最优值或答案映射。

如果只评测一个 Agent，应只向它提供公开题目和允许的检索接口，不应直接提供 `private/` 或 `models/`。

公开记录的结构如下：

```json
{
  "id": "SWOR...",
  "problem_zh": "完整中文问题文本",
  "decision_time": "YYYY-MM-DD",
  "entity": "自然业务主体",
  "jurisdiction": "规则适用辖区",
  "required_output": [
    "适用来源与理由",
    "结构性模型补丁",
    "最终单目标模型",
    "最优行动与目标值",
    "claim-to-model-slot映射"
  ],
  "allowed_retrieval_interfaces": [
    "unified_evidence_semantic_search"
  ]
}
```

注意：`family`、`evidence_mode` 和 `patch_class` 有意不出现在公开记录中，避免把任务类别或答案结构泄漏给被测系统。

## 检索语料字段

检索语料位于 `private/evidence_corpus.jsonl`，共 400 条，即每个任务对应一个四文档检索包。搜索系统可以索引这些记录，但不应向 Agent 暴露任务到证据 ID 的 Gold 映射。

| 字段 | 含义 |
|---|---|
| `id` | 证据文档内部标识 |
| `content` | 完整政策、合同或官方规则文本 |
| `content_sha256` | 证据正文的 SHA-256 |
| `source_kind` | 中性文档类型；正式语料统一为 `policy_document`，不编码适用/干扰角色 |
| `applicability.predicate_fields` | 检索与适用性判断可使用的自然语义字段 |
| `applicability.gold_status_exposed` | 是否把适用/干扰答案直接暴露给搜索系统；正式数据中不得据此泄漏 Gold |

检索语料不暴露结构化 `source_passport`。权威方、版本、有效期、辖区、主体范围和例外必须从 `content` 正文中读取。每份候选的完整来源护照只保存在对应 Gold 的 `applicability.comparison[].source_passport`，其核心字段包括：

- `authority`、`issuer`、`authoritative`：谁发布、是否具有规则权限；
- `version`、`effective_from`、`effective_to`：版本和有效期；
- `jurisdiction`、`subject_scope`：适用辖区和主体范围；
- `content_sha256`：护照所绑定的正文哈希。

例外条款保留在 `content` 正文中，由 Agent 阅读和判断；完整的例外核验过程只在 Gold 中保存。检索 metadata 不单列 `exceptions`，避免“是否存在列表、列表长度或默认文案”成为角色标签。

网页证据还会在 `private/web_source_snapshots.jsonl` 和 `private/web_snapshots/` 中保存 URL、抓取时间、HTTP 状态、原始响应路径、原始字节哈希、支持片段和中文释义。

检索语料的 400 条记录使用完全相同的顶层字段、值类型、空值结构和列表长度，并且不暴露 `source_passport` 或 `snapshot_ref`。网页快照、抓取细节和四份候选的完整来源护照只保存在评测侧的 Gold/快照审计链中，不能作为被测系统的输入。这样可以避免系统仅凭字段结构或结构化元数据值识别正确来源；从正文判断权威方、版本、日期、辖区、主体和例外仍是任务要求的一部分。

## Gold 字段

评测答案位于 `private/gold.jsonl`，每行对应一个公开任务。它不是 Agent 输入。

| 字段 | 含义 |
|---|---|
| `id` | 与公开任务连接的任务 ID |
| `base_id` | 独立基础模型 ID |
| `split` | 数据划分 |
| `family` | OR 问题家族 |
| `evidence_mode` | `fresh-private` 或 `real-web` |
| `patch_class` | 四类结构补丁之一 |
| `base_audit` | 基础模型的单目标性、语义映射、扰动和来源审计 |
| `evidence_ids` | 本题检索包中的证据 ID |
| `source_passport` | 最终采用来源的完整护照 |
| `applicability` | 权威性、日期、辖区、主体、例外和唯一适用来源裁决 |
| `typed_patch` | 对变量、索引、变量域、约束或目标项的结构化增删改 |
| `claim_to_model_mapping` | 证据主张到模型槽、方程和代码区域的映射 |
| `model_hashes` | 基础和最终 IR 的文件路径、文件哈希及 canonical hash |
| `action_projection` | 预注册的业务行动变量与数值容差 |
| `solver_results` | Gurobi 与 COPT 的状态、目标、行动、残差和整数性 |
| `decision_certificate` | 搜索前后完整可接受行动集及空交集证书 |
| `reviews` | 两位独立盲审员的逐题结论 |
| `adjudication` | 冲突裁决和最终接收状态 |

`typed_patch.ops` 是理解模型究竟怎样变化的入口；`pure_numeric_parameter_fill` 必须为假，`structural` 必须为真。

`decision_certificate.worlds` 分别保存基础世界和证据世界；`intersection_empty` 表示两者的可接受最优行动集合没有公共解。

## 每题模型目录

`models/<task_id>/` 对每个任务保存五个文件：

| 文件 | 内容 |
|---|---|
| `base_ir.json` | 只使用公开题面建立的基础模型 |
| `patched_ir.json` | 加入适用外部规则后的最终模型 |
| `gurobi_model.py` | 从 canonical IR 生成并求解 Gurobi 模型 |
| `copt_model.py` | 从同一 canonical IR 生成并求解 COPT 模型 |
| `solver_results.json` | 双求解器结果、完整行动集及其交集证书 |

两个 IR 都包含：

- `variables`：变量名、类型和上下界；
- `objective` 与 `sense`：唯一目标及方向；
- `constraints`：线性约束族；
- `action_projection`：实际业务行动变量；
- `family`、`task_id`、`base_id`、`world`：模型身份与世界标识；
- `metadata`：构建和补丁相关的辅助元数据。

比较 `base_ir.json` 与 `patched_ir.json` 可以直接复核 Gold 中声明的结构 diff。

## 证据库

数据集包含两种证据任务。

### fresh-private E+：80 条

适用规则是在基础模型冻结后生成的完整业务政策，包含适用范围、多个条款和例外。它们与旧版本、错误辖区和错误主体文档共同进入检索库。

该部分用于测试：当规则确实不在模型原有知识中时，Agent 能否通过检索找到并正确建模。

### real-web E?：20 条

适用规则来自官方网页或官方版本化接口，覆盖运输与机组工时、食品营养、清洁车辆、排放与危险废物、劳动休息等主题。

该部分用于测试真实网页上的版本、时效、辖区和适用性判断。由于公开规则可能已存在于预训练语料中，这 20 条不声称对所有离线模型都绝对未知。

## 如何使用这个数据集

### 用法一：作为普通 OR 专家阅读题

只读取 `public/tasks_zh.jsonl`。先不检索外部规则，独立建立基础模型；然后使用允许的检索接口寻找规则，修改模型并比较决策变化。

下面的代码可以读取公开任务：

```python
import json
from pathlib import Path


def load_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


tasks = load_jsonl("public/tasks_zh.jsonl")
task = tasks[0]

print(task["id"])
print(task["problem_zh"])
print(task["required_output"])
```

如果目的是人工分析，可以先自己完成答案，再从 `private/gold.jsonl` 找到相同 `id` 的记录，逐项比较适用来源、模型补丁、方程、最优行动和错误位置。

### 用法二：评测一个带搜索能力的 OR Agent

这是数据集的主要使用方式。

被测 Agent 可接触：

- 当前任务对应的公开记录；
- 一个建立在 `private/evidence_corpus.jsonl` 上的语义搜索接口；
- 优化求解器或代码执行环境。

被测 Agent 不可直接接触：

- `private/gold.jsonl`；
- `models/`；
- `private/evidence_commitments.jsonl`；
- 任务到适用证据 ID 的映射；
- 其他任务的 Gold 标签。

构建检索索引时，建议使用：

```python
evidence = load_jsonl("private/evidence_corpus.jsonl")

search_documents = [
    {
        "doc_id": row["id"],
        "text": row["content"],
        "metadata": {
            "source_kind": row["source_kind"],
        },
    }
    for row in evidence
]
```

不要根据文件位置恢复四文档包，不要使用 Gold 的 `evidence_ids` 预过滤语料，也不要在检索前把适用来源直接注入上下文。400 条证据已经独立打散，`source_kind` 和文档 ID 都是角色中性的。

评测服务还应在送入索引前丢弃值为 `null` 的技术性来源字段，或对所有文档使用相同的字段投影。不要把文件路径、快照关联、构建时间、Gold 哈希、行号或四文档分组关系加入可检索 metadata。

主评测流程为：

1. 将一条公开任务交给 Agent；
2. 记录 Agent 发出的每条自然语言检索 query；
3. 记录搜索接口每次返回的文档 ID、排名和分数；
4. 记录 Agent 选择、排除证据的理由；
5. 保存基础模型、结构补丁和最终模型；
6. 保存求解结果及 claim-to-model-slot 映射；
7. 使用相同 `id` 的 Gold 做分层评测。

### 用法三：只评测某一个组件

完整端到端结果无法说明错误发生在哪里。建议同时运行以下四种条件：

| 条件 | 给系统什么 | 主要回答的问题 |
|---|---|---|
| Closed-book | 只给公开题目，不允许搜索 | 系统能否建立基础模型；是否依赖记忆或猜测规则 |
| Retrieval-only | 给公开题目和完整检索库，只要求返回证据排序 | 搜索组件是否能找到适用规则 |
| Oracle-evidence | 给公开题目和正确证据正文 | 找到证据后，系统能否理解并修改模型 |
| Search-enabled | 给公开题目和语义检索接口 | 端到端搜索、建模和求解能力 |

四种条件可以定位：

- Closed-book 就错：基础 OR 建模失败；
- Retrieval-only 未命中：检索失败；
- 已命中但 Search-enabled 选错：适用性裁决失败；
- Oracle-evidence 仍建错：规则到模型的翻译失败；
- 模型正确但答案错：求解或行动读取失败。

## 建议保存的 Agent 过程记录

只保存最终答案不足以判断 Agent 是否真的搜索、是否找对来源、是否把来源用进了模型。建议每题输出一条 trace：

```json
{
  "id": "SWOR...",
  "queries": [
    {
      "query": "自然语言检索词",
      "returned_doc_ids": ["DOC-..."],
      "scores": [0.82],
      "latency_ms": 120
    }
  ],
  "selected_evidence_ids": ["DOC-..."],
  "applicability_decision": {
    "authority": "pass",
    "effective_at_decision": "pass",
    "jurisdiction": "pass",
    "subject_scope": "pass",
    "exception_state": "pass",
    "rejected_documents": [
      {
        "doc_id": "DOC-...",
        "reason": "版本在决策日前失效"
      }
    ]
  },
  "base_formulation": {},
  "typed_patch": {
    "ops": []
  },
  "final_formulation": {},
  "solution": {
    "optimal_action": [],
    "objective_value": 0
  },
  "claim_to_model_mapping": [],
  "usage": {
    "search_calls": 0,
    "solver_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "wall_time_ms": 0
  }
}
```

这是一份建议的实验输出格式，不是当前 release gate 已实现的 Agent submission API。首版提供 Gold、模型和验证材料，但没有内置统一 Agent scorer；研究者可以依据下面的口径实现 scorer。

## 完整评测指标

### 1. 检索是否真的成功

Gold 的 `applicability.selected_evidence_id` 是适用文档。

| 指标 | 计算方式 | 能发现什么 |
|---|---|---|
| Hit@k / Recall@k | 适用文档是否出现在前 \(k\) 个结果 | 是否搜到 |
| MRR | 适用文档排名倒数 | 是否尽早搜到 |
| First Relevant Rank | 第一次出现适用文档的名次 | 排名质量 |
| Query Success Rate | 至少一条 query 命中适用文档的任务比例 | 多轮搜索是否最终成功 |
| Time to First Evidence | 从任务开始到首次命中的时间 | 检索效率 |
| Search-call Count | 每题调用搜索接口次数 | 工具成本 |
| Retrieved-document Count | 实际读入上下文的文档数 | 上下文成本 |
| Prohibited-query Rate | 是否使用精确隐藏 ID、任务映射或 Gold 泄漏词 | 是否把搜索退化成查表 |

只看最终引用的来源不够。Agent 可能在第一次检索时已经找到正确文档，却因为后续推理错误而放弃它；也可能从未搜到，只凭记忆猜出相似规则。这两种情况需要通过 query/result trace 区分。

### 2. 来源适用性判断是否正确

除了“最终选中的文档 ID 是否正确”，还应分别评价五个判断谓词：

- 权威方是否有效；
- 规则在 `decision_time` 是否生效；
- 辖区是否匹配；
- 主体和业务活动范围是否匹配；
- 例外是否激活或已正确排除。

可以报告：

- Selected-source Exact Accuracy；
- 五类 applicability predicate 的 Accuracy / Macro-F1；
- 三份干扰文档的拒绝准确率；
- Distractor-reason Macro-F1；
- 唯一适用来源判断准确率。

这样可以区分“碰巧选对文档”和“真正给出了正确适用理由”。

### 3. 基础模型是否正确

在评价搜索贡献前，应先验证 Agent 对公开题面的建模：

- 决策变量和变量域是否完整；
- 唯一目标及优化方向是否正确；
- 本地约束是否完整；
- 单位是否一致；
- 是否错误加入了尚未检索的规则；
- 基础模型是否可行、有界；
- 基础最优目标和完整最优行动集合是否与 Gold 一致。

可报告：

- Base Variable/Constraint/Objective Accuracy；
- Base IR Exact Match 或规范化结构匹配；
- Base Feasibility Rate；
- Base Optimal-action-set Jaccard；
- Base Objective Gap。

基础模型错误的任务不应被归因于“搜索没有帮助”。

### 4. 结构补丁是否正确

对 `typed_patch.ops` 做结构化比较：

- 新增、删除或修改了哪些变量；
- 是否改变索引集或变量域；
- 新增、删除或修改了哪些约束；
- 是否加入条件激活、辅助变量或分段逻辑；
- 是否改变目标项结构。

建议报告：

- Patch Operation Precision / Recall / F1；
- Patch-class Accuracy；
- Structural-patch Success Rate；
- Patch Minimality；
- Unsupported-edit Rate；
- Pure-numeric-fogging Rate。

一个补丁只有在规则确实要求时才应修改模型。多加一个“看似合理”的约束也属于错误。

### 5. 最终模型是否语义正确

不能只比较模型文本字符串。等价方程可能有不同写法，例如移项、缩放或辅助变量展开。

建议按以下顺序判断：

1. 规范化变量、目标和约束；
2. 比较 canonical IR；
3. 对小型二元模型枚举可行行动；
4. 比较可行域或业务行动投影；
5. 最后比较最优行动集合和目标值。

可报告：

- Final IR Structural Match；
- Constraint-family Precision / Recall；
- Feasible-action-set Exact Match / Jaccard；
- Solver Status Accuracy；
- Objective Gap；
- Constraint Violation；
- Integrality Violation。

### 6. 最终决策是否正确

Gold 保存的是完整可接受最优行动集合，不应只比较某一个 incumbent。

建议报告：

- Predicted Action 是否属于 Gold 可接受行动集合；
- Complete Optimal-action-set Exact Match；
- Optimal-action-set Precision / Recall / Jaccard；
- 目标值绝对误差和相对误差；
- 不可行行动率；
- 多最优解遗漏率。

如果 Agent 只返回一个行动，而 Gold 有多个等价最优行动，可以评价该行动是否可接受，但不能声称 Agent 恢复了完整最优面。

所有 100 条主任务都满足：

\[
A_0^\epsilon \cap A_1^\epsilon = \varnothing.
\]

因此，只求解基础模型不可能偶然给出一个同时可接受的最终最优行动。

### 7. 证据是否真正进入模型

`claim_to_model_mapping` 用于检查完整链路：

\[
\text{source excerpt}
\rightarrow
\text{claim}
\rightarrow
\text{model slot}
\rightarrow
\text{equation}
\rightarrow
\text{code region}.
\]

建议报告：

- Evidence-claim Precision / Recall；
- Claim-to-slot Coverage；
- Equation-support Accuracy；
- Code-region Binding Accuracy；
- Unsupported Claim Rate；
- Unsupported Model-edit Rate。

还应区分：

- **找到且正确使用**：检索命中，规则解释和补丁都正确；
- **找到但忽略**：检索结果包含正确文档，但最终没有采用；
- **找到但误读**：选对文档，却错误理解范围、例外或结构含义；
- **未找到但猜对**：最终模型正确，但 trace 中没有证据支持；
- **找到错误来源并碰巧答对**：决策正确但证据链错误。

后两类不能计为严格的搜索增强成功。

### 8. 效率指标

在正确性之外，可以报告：

- 总搜索调用数；
- 总读取文档数；
- 检索和建模 token 数；
- 首次命中时间；
- 总 wall-clock time；
- 求解器调用数和求解时间；
- 每个严格成功任务的平均成本。

效率指标应在正确性之后比较。用更少调用得到错误模型不是有效改进。

### 9. 鲁棒性评测

可在不改变 Gold 的情况下运行：

- 打乱证据库物理顺序；
- 改变干扰文档的返回排名；
- 把旧版本放在检索第一名；
- 限制 top-k；
- 对公开题面和 query 做语义保持改写；
- 隐去部分非必要元数据；
- 改变同义的方程表达；
- 分别报告 private 与 web 任务；
- 分别报告十个 OR 家族和四种 patch 类型。

如果系统依赖文档位置、ID 前缀、固定模板或特定方程字符串，鲁棒性测试会显著下降。

### 10. 无题面负对照：搜索评测的必要前置门

在评价任何 Agent 前，维护者必须先证明“证据库本身不能泄漏答案”。这个检查由评测者离线使用 Gold 分组完成，不把分组映射提供给 Agent。

至少运行以下负对照：

| 负对照 | 输入 | 合理结果 |
|---|---|---|
| Metadata-only | 文档 ID、字段结构、空值、类型、长度和哈希特征，不给题面和正文语义 | 接近四选一随机基线 0.25 |
| Surface-only | 字节数、字符数、ASCII 数、标点、括号、固定短语和字符 n-gram | 不应稳定高于随机 |
| Pack medoid / mode | 只比较同题四候选的逐行众数、编辑距离、Hamming 距离或语义中心性 | 不应确定性选中正确来源 |
| Shuffled-task | 把证据包与错误题面随机配对 | 适用来源准确率应降至随机 |
| Task-blind classifier | 不给题面，按任务、OR 家族和来源主题分组交叉验证 | 不得存在跨组稳定解码规则 |
| Generator-aware attack | 已知模板和构造代码，尝试剥离版式、占位段和角色词 | 不应恢复角色标签 |

只有这些负对照通过，Hit@k、MRR 和端到端成功率才有解释意义。否则 Agent 可能只是在识别生成模板，而不是真正搜索和判断适用性。

当前候选版在这一门失败：不看题面时，按候选中的发布者、权限、辖区和主体取组内多数，再在剩余文档中选择较晚的有效期，可对 100 条任务全部命中。因此，下一版必须使用彼此独立的真实/私有来源构造干扰文档，不能继续把三份干扰文档写成正确文档的单字段扰动。

### 11. 搜索带来的真实增益

仅报告 Search-enabled 的最终正确率，不能证明搜索产生了作用。应在相同模型、提示、求解器和预算下，对 Closed-book、Oracle-evidence 与 Search-enabled 做逐题配对比较：

- `Search Gain = Search-enabled − Closed-book`：外部搜索是否改善最终建模与决策；
- `Retrieval Loss = Oracle-evidence − Search-enabled`：多少错误来自没搜到或选错来源；
- `Reasoning Loss = Gold-model/solver upper bound − Oracle-evidence`：多少错误来自读懂规则、改模型或求解；
- `Unsupported Guess Rate`：Closed-book 或未命中证据时，系统是否猜出了无法由 trace 支持的规则；
- `Negative Search Rate`：基础模型本来正确，但搜索后因错误来源或错误补丁而变差的比例。

对每个差值应给出逐题配对 bootstrap 置信区间，而不是把两组独立均值直接相减。

### 12. 过程忠实性与可审计性

过程判定依赖 trace，因此还要检查 trace 自身是否可信：

- 每次 query、返回结果、读取正文、求解器调用都带单调时间戳；
- 返回文档 ID 必须确实来自当次搜索结果；
- 被引用片段必须能在对应证据正文中定位；
- 结构补丁的每个操作必须在首次读取支持证据之后发生；
- 最终模型哈希应与实际送入求解器的模型一致；
- 求解器状态、目标值和行动应能由保存的模型重放；
- 超出允许接口的文件读取、精确 ID 查询或 Gold 访问一律标为 protocol violation；
- 缺失 trace 时可以报告答案正确率，但不得报告“搜索过程正确”或严格端到端成功。

若框架支持，应由评测器在工具层自动记录 trace，而不是完全信任 Agent 自报。

### 13. 置信度、弃权与错误严重度

建议让系统分别输出来源选择、补丁和最终行动的置信度。除准确率外，可报告 Brier score、ECE、risk-coverage curve 和选择性准确率。无法唯一判断适用性时，明确弃权通常优于自信地采用错误规则。

错误严重度也不相同：

- 采用过期或错误辖区规则；
- 生成不可行或无界模型；
- 返回违反硬约束的行动；
- 漏掉一个等价最优行动；
- 证据链不完整但最终行动碰巧正确。

建议把前三类列为关键失败，单独报告，不用平均分掩盖。

### 14. 可复现性、污染与时间有效性

一次正式比较至少应冻结：模型版本、提示、搜索索引、embedding/reranker、top-k、随机种子、求解器版本、时间和 token 预算。对有随机性的系统运行多个种子，并同时报告均值、标准差和逐题结果。

还应记录：

- 是否使用本 release 的 Gold、模型或生成模板训练/调参；
- private E+ 语料是否在评测前被模型或开发者访问；
- real-web E? 使用的是哪个冻结快照和决策时间；
- live web 结果是否与冻结快照发生漂移；
- 失败是由网页不可达、索引未收录、规则冲突还是 Agent 推理造成。

如果改用实时网页搜索，应把“网页获取失败”和“在已获取页面上推理失败”分开统计，并保留原始页面或内容哈希，避免日后无法复现。

## 推荐的总分与错误归因

不建议只给一个混合平均分。至少同时报告：

1. Retrieval Hit@k / MRR；
2. Applicability Exact Accuracy；
3. Base-model Pass Rate；
4. Patch F1；
5. Final-model Semantic Pass Rate；
6. Optimal-action-set Jaccard；
7. Claim-binding Pass Rate；
8. End-to-End Strict Success。

其中一条任务的 End-to-End Strict Success 只有在以下条件全部满足时才为 1：

\[
\text{retrieved}
\land
\text{applicable}
\land
\text{base-correct}
\land
\text{patch-correct}
\land
\text{final-model-correct}
\land
\text{decision-correct}
\land
\text{binding-complete}.
\]

建议采用以下错误优先级，只记录第一个阻断阶段：

1. 未调用搜索或违规查表；
2. 调用搜索但未命中；
3. 命中但来源适用性判断错误；
4. 来源正确但基础模型错误；
5. 来源和基础模型正确但结构补丁错误；
6. 最终模型正确但求解或行动读取错误；
7. 答案正确但证据到模型绑定不完整；
8. 全链路成功。

聚合结果时应：

- 对 100 条任务做 micro average；
- 对十个 OR 家族做 macro average；
- 分开报告 80 条 `fresh-private E+` 和 20 条 `real-web E?`；
- 分开报告四类结构补丁；
- 给出 bootstrap 置信区间；
- 报告各阶段错误数量，而不只报告最终准确率。

当前 100 条均属于 `release` split，应视为评测集。不要使用 `private/gold.jsonl` 或 `models/` 微调被测模型后再在同一批任务上报告无污染结果。如果需要训练集，应另行生成并冻结互不共享 base、政策模板和证据文档的派生 split。

## 研究者文件

| 路径 | 用途 |
|---|---|
| `public/tasks_zh.jsonl` | Agent 的公开输入 |
| `private/evidence_corpus.jsonl` | 语义检索语料及干扰文档 |
| `private/gold.jsonl` | 适用来源、结构补丁、模型和决策证书 |
| `models/` | 每题的基础/最终 canonical IR、生成代码、解和残差 |
| `private/web_snapshots/raw/` | 20 个官方来源的冻结原始响应 |
| `manifest.json` | 发布文件的 SHA-256、数量和构建环境 |

`private/` 和 `models/` 是评测与审计材料。它们在本公开仓库中可下载，但不应挂载、检索或注入
被测答题进程；运行前还应声明模型、Agent 开发者和调参流程是否曾访问这些材料。

## 复现与维护

如果只是使用数据集，无需重新构建或重新抓取网页。

维护者可以在已安装 Gurobi、COPT 和项目依赖的环境中运行：

```powershell
python scripts/run_release_gate.py --root .
```

该命令检查数据结构、证据与模型绑定、重复与元数据泄漏、来源完整性、双审状态及文件哈希。网页快照不会在普通验证过程中联网更新。

`reports/release_gate.json` 是验证 `manifest.json` 后生成的审计报告，因此不再被
`manifest.json` 反向哈希，避免报告与被验证清单形成不可满足的自引用；Git 提交仍固定该报告
本身。临时 stdout/stderr、缓存和 `staging/` 同样不属于发布内容清单。

为避免 Windows/Linux checkout 的 CRLF/LF 差异制造假哈希失败，`manifest.json` 对可解码的
UTF-8 文本按 LF 规范化后计算 SHA-256 和字节数；冻结网页原始响应、拒绝快照和二进制文件仍按
原始字节计算。具体策略写在 `manifest.json.file_hash_policy`，并由 schema validator 强制核对。
`.gitattributes` 另外固定网页原始响应不做文本转换，并保持公开实验子包自身的原始哈希合同。

详细的数据合同、构造记录和最终审计结果分别位于：

- `docs/release_gate_contract.md`
- `docs/dev_log.md`
- `reports/release_gate.json`

题目来源、生成过程、网页冻结和审计边界已移至 `生成方法.md`，不再与数据字段说明混在 README 正文中。

## 已完成的基线实验

仓库同时提供一份可复核实验包：

`experiments/20260731_searchworthyor_baselines/`

它包含 GPT-5.6-sol high 的无搜索 one-shot、冻结语料 one-shot、20 条真实联网题，
OPTIMUS-inspired、Chain-of-Experts-inspired 和 training-free OptiMiner compatibility
六个条件的权威汇总，以及 520 个 task-condition 的逐题公开快照。公开快照保存
`submission.json`、生成的 Gurobi `model.py`、失败记录与受限恢复 provenance；不包含原始
prompt、逐事件 telemetry 或本地机器路径。

在仓库根目录运行：

```powershell
python experiments/20260731_searchworthyor_baselines/scripts/verify_public_bundle.py `
  --root experiments/20260731_searchworthyor_baselines

python experiments/20260731_searchworthyor_baselines/scripts/verify_public_run_snapshot.py `
  --root experiments/20260731_searchworthyor_baselines/public_run_snapshot_v3
```

需要重新评分时，可直接读取公开逐题快照：

```powershell
python experiments/20260731_searchworthyor_baselines/scripts/summarize_full_run.py `
  --dataset-root . `
  --run-root experiments/20260731_searchworthyor_baselines/public_run_snapshot_v3/optiminer `
  --label "OptiMiner training-free compatibility" `
  --output optiminer_rescore.json `
  --markdown optiminer_rescore.md
```

实验结论、错误来源、成本和 Graph Engineering 框架分别见该目录中的
`results/EXPERIMENT_FINDINGS.md`、`results/OPTIMINER_FAILURE_ANALYSIS.md`、
`results/COST_AND_RUNTIME.md` 和 `docs/GRAPH_OR_SEARCH_AGENT.md`。由于 Gold 与候选语料已经
公开，这些结果只能作为开发集/审计集上的可复现实验，不能解释为长期无污染的隐藏榜单成绩。
