# SearchWorthyOR-Rapid-v0

SearchWorthyOR-Rapid-v0 是一个中文运筹优化评测集。每道题先给出一个完整、可独立建模和求解的单目标 OR 场景，同时要求决策遵守在指定日期、辖区和主体下有效的外部规则。答题系统需要自行找到权威网页，理解规则是否适用，并把规则带来的结构变化纳入模型，最后给出最优决策和目标值。

这里的“搜索”不是查一个缺失数字。外部规则会改变可选动作、变量域、时序关系、条件逻辑、配额或目标项等模型结构；忽略搜索结果时得到的最优行动，与正确使用规则后的可接受最优行动没有公共解。

## 数据集包含什么

数据集共有 100 道题，对应 100 个不同的 base 模型，覆盖以下 10 个领域，每类 10 题：

- 路径与运输
- 排班与劳动力
- 生产与容量规划
- 分配与匹配
- 设施选址与网络设计
- 库存与供应链
- 能源与环境
- 医疗资源配置
- 金融与组合选择
- 通信与服务系统

每题只优化一个目标。100 个规则补丁分为 4 类，每类 25 题：资格或变量域变化、时间与耦合关系、条件激活与辅助变量、配额风险服务组合或目标结构。

公开题面包含现实背景、候选行动、目标系数、基础运营约束、决策日期与辖区，以及一句自然的合规要求。题面不会给出法规结论、来源地址、受影响的变量或 Gold 补丁。

## 文件与字段

答题时只应向系统提供 `public/tasks_zh.jsonl`。每行格式为：

```json
{
  "id": "SWOR-R001",
  "problem_zh": "完整中文题面"
}
```

内部评测材料不能暴露给答题系统：

- `private/rapid_audit.jsonl`：来源、支持段落、适用性、规则声明、题面本地事实、模型绑定、求解状态和审核状态。
- `private/independent_review.jsonl`：非生成者逐题复核结果；每条带 `artifact_fingerprint`，绑定复核时看到的题面、审计、base/patched IR 与求解结果，修改任一工件后旧复核自动失效。
- `private/source_recheck.jsonl`：封版时的网页可访问性和支持段落复查；每条收据同时绑定来源候选、文档、规则原子、请求 URL 和支持段落哈希，修改证据后旧收据自动失效。
- `batches/batch_*/models/<id>/base_ir.json`：只根据题面运营信息建立的模型。
- `batches/batch_*/models/<id>/patched_ir.json`：正确应用外部规则后的模型。
- `batches/batch_*/models/<id>/solve_result.json`：两个模型的完整最优行动集合和目标值。
- `manifest.json`：递归记录公开/私有数据、5个批次全部模型、schema、config 和验证脚本的内容哈希；它用于精确识别 Rapid-v0 工件，不代表严格版的长期网页存证。

`rapid_audit.jsonl` 的核心字段含义如下：

| 字段 | 含义 |
|---|---|
| `source_url`, `final_url`, `accessed_at` | 官方来源地址、最终地址和访问时间 |
| `authority`, `jurisdiction`, `decision_date` | 发布主体、辖区和题目决策日期 |
| `support_excerpt`, `rule_claim` | 网页原始支持段落和从中得到的规则声明 |
| `applicability_reason` | 规则为何适用于题目中的主体、时间和业务 |
| `task_local_fact_alignment` | 题面本地事实与 Gold 补丁元素的逐项绑定 |
| `numeric_alignment` | 题面数值在 base 或证据规则中的用途 |
| `variable_alignment`, `constraint_alignment` | base 变量和约束在题面中的直接依据 |
| `patch_class`, `patch_summary` | 结构补丁类别和摘要 |
| `base_solve`, `patched_solve` | 搜索前后模型的求解状态 |
| `common_optimal_action_feasible` | 两个可接受最优行动集合是否存在公共行动；合格题必须为 `false` |

独立复核不是对生成者自检的复述。复核者需要重新确认当前网页、原文直接性、日期/辖区/主体及例外、规则到补丁的推导、题面与 base 的一致性、泄漏、求解结果和完整最优行动集合。`artifact_fingerprint` 不构成发布级哈希链，只用于拒绝把修改前的 PASS 套到修改后的题目上。

每个批次的复核者由 `config/rapid_contract.json` 预先指定，验收脚本同时检查“不是生成者”和“符合该批次指定复核者”。这是可审计的流程来源记录，不是密码学身份认证。

## 如何使用

### 1. 运行答题系统

逐行读取 `public/tasks_zh.jsonl`，只把 `id` 和 `problem_zh` 交给待测系统，并允许它访问公开网页。系统最终至少返回：

```json
{
  "id": "SWOR-R001",
  "decision": {},
  "objective_value": 0
}
```

`decision` 应使用题面中的行动名称表达。研究者可以另外保存网页查询、访问页面、引用片段、规则判断、模型和求解日志，但不要通过追加提示告诉系统应该搜索哪个结论或修改哪个变量。

### 2. 保持评测隔离

- 不向待测系统提供 `private/`、`models/`、`solve_result.json` 或来源候选表。
- 不把 Gold URL、规则原文、补丁类别或参考目标值写入提示。
- 每次运行记录数据集 manifest、搜索时间、模型版本、工具权限和随机种子。
- 网页不可访问时单独记为基础设施失败，不把它混同为建模错误。

### 3. 建议的三种设置

- `No-search`：禁止联网，测量仅凭题面建模时的性能。
- `Open-web`：允许自由搜索，是本数据集的主要设置。
- `Oracle-evidence`：直接提供正确支持段落，但不给模型补丁，用于区分检索错误与规则建模错误。

三者的差值可以回答：失败主要来自没有找到证据、错误判断适用性，还是找到了规则却不会修改模型。

## 如何评测

### 最终答案

1. **可行性**：把预测行动代回 patched 模型，检查变量边界、整数性和全部约束残差。
2. **最优性**：预测目标值与 Gold 最优值在预设容差内一致。
3. **行动正确性**：预测行动属于完整 Gold 最优行动集合。不能只和一个求解器 incumbent 比较，因为题目可能有多个最优解。
4. **完整成功率**：可行、最优、行动正确三项同时通过才记为该题答对。

Gold 中的 `action_projection` 覆盖 base 模型的全部非固定决策变量，验收时比较这一投影上的完整最优行动集合；补丁新增的纯辅助变量可以不进入最终业务行动。

### 搜索过程

在不改变公开题目提示的前提下，从工具日志评估：

- 是否访问了权威的一手来源，而非搜索摘要、博客或过期二手解释；
- 是否找到了直接支持 Gold 规则的段落；
- 是否识别正确辖区、有效日期和适用主体；
- 是否采用了错误版本、错误辖区、错误主体或干扰文档；
- 首次有效证据出现前的查询数、页面访问数和时间；
- 找到证据后是否继续无效搜索，或过早停止。

可以报告 `Authoritative Source Hit`、`Support Passage Recall`、`Applicability Accuracy`、错误来源采用率、查询成本和检索延迟。URL 字符串不完全相同但落到同一官方文档时，应按规范化文档身份判定，不应机械判错。

### 规则到模型的过程

若系统输出模型或中间轨迹，可继续评估：

- `claim → local fact → model slot` 的绑定是否完整；
- 是否增加、删除或修改了正确的变量、变量域、约束、索引或目标项；
- 是否遗漏规则例外、条件激活、时间作用域或主体边界；
- 是否引入题面和证据都没有提供的参数或候选属性；
- patch 后模型是否仍为单目标、可行、有界；
- 预测补丁与 Gold 补丁是否语义等价。

模型比较应优先使用 canonical IR 的变量域、约束支持集、关系方向和行动投影，而不是比较变量名或代码文本。对于不同写法但可证明等价的模型，可通过双向可行域检查或小实例穷举判为正确。

### 诊断分解

推荐按以下顺序定位错误：

1. `BASE_ERROR`：仅根据题面建立的 base 已不等价。
2. `RETRIEVAL_ERROR`：未找到权威支持段落。
3. `APPLICABILITY_ERROR`：找到规则，但日期、辖区或主体判断错误。
4. `RULE_INTERPRETATION_ERROR`：支持段落被误读。
5. `BINDING_ERROR`：规则正确，但没有绑定到正确的题面事实或模型位置。
6. `PATCH_ERROR`：补丁缺失、多加或结构错误。
7. `SOLVER_ERROR`：模型正确但编码、求解或结果读取错误。
8. `ANSWER_ERROR`：内部过程正确，但最终行动或目标值报告错误。

除总体成功率外，建议同时报告各阶段条件成功率，例如 `P(找到证据)`、`P(适用性正确 | 已找到证据)`、`P(补丁正确 | 规则判断正确)` 和 `P(最优答案正确 | 模型正确)`。这比单一正误更能说明 Agent 的真实短板。

## 复现内部验收

在安装 `coptpy`、`jsonschema`、`requests`、`beautifulsoup4` 和 `PyMuPDF` 的 Python 环境中，从数据集根目录执行：

```powershell
python -m pytest -p no:cacheprovider .\tests -q
python .\scripts\recheck_release_sources.py --rapid-root .
python .\scripts\validate_release.py --rapid-root .
```

前两步分别检查验证工具和100条实时来源；最后一步会重新运行5个批次的 schema、题面泄漏、模型、COPT、完整枚举、来源绑定、独立复核、重复度和覆盖配额门。只有全部通过后，才运行：

```powershell
python .\scripts\validate_release.py --rapid-root . --write-release
```

`--write-release` 不能与 `--skip-batch-solves` 同时使用。写出前的验证会生成聚合公开/私有文件和完整 manifest；任何来源、模型、题面或复核工件变化后都应重新执行全流程。

## 本版本边界

Rapid-v0 只要求封版时一次验证当前官方网页、一个求解器和一名独立复核者。它不包含严格正式版的双网页路径、24/72 小时连续探测、Gurobi/COPT 双认证、复杂身份认证或发布级哈希链。实验报告中应明确写作 Rapid-v0，不能把其证据强度描述为严格正式版。
