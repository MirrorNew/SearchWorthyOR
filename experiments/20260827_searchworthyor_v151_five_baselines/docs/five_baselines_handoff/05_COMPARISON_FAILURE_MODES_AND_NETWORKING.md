# 05｜横向比较、联网实现与失败模式

## 1. 五方法架构总表

| 维度 | Direct | Search-First | CoE | OptiMUS | optiminer-training-free |
|---|---|---|---|---|---|
| 先做 formal Base | 是 | 否 | native | native | 否 |
| 搜索前实际 Solve | 是 | 否 | 非此设计 | 非此设计 | 非此设计 |
| 是否有搜索边界 | 简单、模型感知 | 简单、prompt-only | 无网页搜索 | 无网页搜索 | Agent 自主选择 arXiv search |
| 搜索源 | hosted public web | 同左 | 无 | 无 | arXiv |
| 查询上限 | 3/case | 3/case | 0 | 0 | 最多 3 research turns |
| 证据形态 | 核验引用 + Base 上下文 | 核验引用 Raw-NL | 无 | 无 | 论文摘要/PDF 文本 |
| Patch | RETAIN/PATCH_CHANGES | RETAIN/PATCH_CHANGES | 通常 NOT_OBSERVED | 通常 NOT_OBSERVED | 适配观察 |
| 最终执行 | Gurobi | Gurobi | native 代码后执行 | native 代码后执行 | native Python loop |
| 主要科学作用 | 模型感知搜索 | 搜索前置 | 多专家参照 | 模块化参照 | 信息搜寻参照 |

## 2. Direct/Chain1 与 Chain2 到底如何联网

联网分成两个独立层：

```mermaid
flowchart LR
    A[规划 query] --> B[Shubiaobiao /responses + web_search]
    B --> C[title / URL / snippet]
    C --> D[本地 HTTP 逐页打开 URL]
    D --> E[HTML/PDF 正文抽取]
    E --> F[相关性与 site: 合规]
    F --> G[逐字引用核验]
    G --> H[证据充分性判断]
```

第一层由 Shubiaobiao hosted search 发现候选 URL。第二层由本地程序用 HTTP 打开页面，并用 HTML/PDF 解析器取得可核验正文。搜索引擎能返回一个 URL，不代表本地一定能读取该网页。

## 3. 为什么网页打开/证据失败率会高

失败可能发生在七个不同关口：

1. **搜索调用失败**：provider、响应格式或 tool call 不合规。
2. **URL 打开失败**：403、404、429、5xx、TLS、DNS、timeout、remote disconnect、重定向异常。
3. **正文不可抽取**：动态 JavaScript、登录/CAPTCHA、反爬页面、空内容、过短 HTML、PDF 无可读文本、未知格式。
4. **相关性不足**：页面可读，但与 query 的关键术语不匹配。
5. **`site:` 不合规**：模型要求特定官方域，但返回 URL 不在该域。
6. **引用核验失败**：LLM 给出的句子不在正文中逐字出现。
7. **证据未闭合**：引用是真的，但没有同时证明当前 case 所需的日期、辖区、主体、条件、阈值或行为后果。

只有第 1 层适合直接叫“hosted search 联网失败”。第 2–3 层是页面访问/抽取失败，第 4–6 层是核验失败，第 7 层是证据充分性失败。

当前 Smoke 中观察到的网页失败类型是 `PAGE_EMPTY_CONTENT`：hosted search 已返回页面，但正文未达到可用标准。这不能归因成 Shubiaobiao 完全没联网。

## 4. 当前过滤与核验是怎样实现的

- **查询相关性**：从 query 提取有信息量的词项，检查 title/snippet/URL 或正文中的词项覆盖；这是词法启发式，不是深语义 entailment。
- **`site:` 合规**：解析 query 的域名约束，对最终 URL host 做显式匹配。
- **页面可读性**：拒绝异常状态、空/过短内容、明显 JS/login/CAPTCHA/error 页面和无法提取文字的 PDF。
- **逐字证据**：对网页正文与候选 quote 做空白归一化，只有正文包含该 quote 才准入。
- **充分性**：LLM 根据现有核验证据输出一个全局 `evidence_sufficient`。这是当前最弱的一环。

“逐字出现”只能证明来源真的说过这句话，不能自动证明该规则适用于当前 case，更不能证明 Patch 改对了数学模型。

## 5. Multi 问题为什么容易失败

例如一个 case 同时需要确认：

- 规则在目标日期是否生效；
- 是否属于目标辖区；
- 当前主体是否被覆盖；
- 某个阈值如何计算；
- 违反后果是否形成硬约束。

当前 gate 可以列出多个 `external_unknowns`，但：

- 整个 case 只有最多 3 次 query；
- 每轮只产生一个 query；
- 没有 `unknown × evidence atom` 覆盖矩阵；
- 证据最终只有一个全局 sufficiency 布尔值；
- Final 没有被强制逐项绑定每个 Patch。

因此正确方向不是机械地把次数无限增加，而是先把复合缺口拆成原子，按 decision criticality 分配预算，并对每个原子记录 `UNRESOLVED / SUPPORTED / CONTRADICTED / NOT_APPLICABLE`。三轮是否足够，应成为预算约束下的可检验问题。

## 6. 无论失败在哪一层，为什么仍要 Final

这两个 baseline 被设计为“失败可归因且始终给出建模尝试”：

- 搜索没触发：仍建模求解。
- 搜索触发但页面打不开：仍建模求解，另记 retrieval failure。
- 引用未闭合：仍给出 best-defensible Final，明确限制。
- Final 代码失败：保留 solver/output failure。

这样可避免把检索能力和基本 OR 建模能力混成一个终止错误。但论文报告不能把“有 Final”解释为“现实证据已经支持 Final”。

## 7. 需要同时报告的失败标准

| 类别 | 例子 | 是否覆盖掉其他信息 |
|---|---|---|
| CONFIGURATION | 模型/provider/权限变更 | 是，实验不可比 |
| PROVIDER | API 调用失败或实际模型不符 | 标记调用失败 |
| RUNNER | native 进程崩溃 | 标记 runner |
| PARSE | 输出无法解析 | 标记 parse |
| OUTPUT_CONTRACT | 字段/动作/目标契约不满足 | 标记 contract |
| SOLVER | 代码未执行或无合法解 | 单独记录 |
| RETRIEVAL | 搜索、页面、核验或充分性不完整 | **独立标记，不抹掉 Final** |

## 8. 现有策略的漏洞与修复方向

| 漏洞 | 会造成什么误判 | 下一版最小修复 |
|---|---|---|
| “可能影响决策”由 LLM 直接判断 | 过搜或漏搜 | 对候选 Gap 做反事实/区间求解 |
| 全局 evidence bool | Multi 问题假闭合 | 原子覆盖账本 |
| Raw-NL 无绑定 | 引用正确但 Patch 错位 | EvidenceCard + typed model slot |
| Patch 最小性靠 prompt | 顺带改了无关参数 | 白名单 Patch compiler + diff validator |
| Direct 比较声明动作 | 与 solver 真实动作不一致 | 以 solver capture 为主并校验声明 |
| 共享三次 query 无优先级 | 低价值缺口耗尽预算 | decision-critical priority queue |
| V1.5.1 几乎都需现实规则 | 无法检验“何时不搜” | 增加 Search/No-search 混合触发集 |

修复时一次只替换一个机制并做消融，不能同时加更多 Agent、更多搜索、更多 token 和新 scorer 后把增益归因给某个单点 idea。
