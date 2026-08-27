# SearchWorthyOR V1.5.1 五个 Baseline：架构与 Idea 交接包

> 版本快照：2026-08-27
> 面向对象：准备理解现有实验、提出新科学问题和设计下一版 Agent 的同学
> 实验规模：120 个源任务、240 个公开 case、5 个方法、计划 1,200 个正式实例

## 先读结论

这五个 baseline 不是五种等价的“联网 Agent”。它们刻意覆盖五种不同能力：

| 方法 | 核心思路 | Base 先建模并求解 | 开放网页 | 原生 arXiv | 主要检验对象 |
|---|---|---:|---:|---:|---|
| Direct / Chain1 | Base → Solve → 判断是否搜索 → 证据 → Patch → Re-solve | 是 | 条件触发 | 否 | 模型感知的搜索与最小修改 |
| Search-First / Chain2 | 判断是否搜索 → 证据 Raw-NL → 一次建模求解 | 否 | 条件触发 | 否 | 搜索前置是否减轻 Base 锚定 |
| CoE | Conductor → 多专家 → Reducer | 原生流程决定 | 否 | 否 | 多专家 OR 建模分工 |
| OptiMUS | 参数、目标、约束、代码的模块化流水线 | 原生流程决定 | 否 | 否 | 专用 OR 建模与代码生成 |
| optiminer-training-free | 搜索/编程交替的 training-free loop | 否 | 否 | 是 | 建模知识型信息搜寻 |

最重要的实验配对是 **Direct vs Search-First**。两者固定使用相同模型、provider、hosted-search 后端、查询预算、网页预算和证据核验；主要变化是“先建模求解再搜索”还是“先搜索再建模”。其余三种方法是能力参照，不是相同检索权下的严格因果对照。

当前只完成 Smoke 链路验证，1,200 个正式实例尚未运行，因此本包不宣称任何方法在 V1.5.1 上更好。

## 推荐阅读顺序

1. [共享协议与评价](01_SHARED_PROTOCOL_AND_EVALUATION.md)：先理解什么被固定、什么允许不同。
2. [Direct / Chain1](02_DIRECT_CHAIN1.md)：理解 Base-Solve 后如何触发搜索。
3. [Search-First / Chain2](03_SEARCH_FIRST_CHAIN2.md)：理解 Raw-NL 搜索前置链路。
4. [CoE、OptiMUS、optiminer-training-free](04_NATIVE_BASELINES.md)：区分论文方法与本实验实际配置。
5. [横向比较、联网与失败模式](05_COMPARISON_FAILURE_MODES_AND_NETWORKING.md)：理解“联网失败”到底发生在哪一层。
6. [下一版 Agent 的 Idea Brief](06_IDEA_BRIEF_FOR_NEXT_AGENT.md)：带着可证伪问题提出新框架。
7. [来源与实现索引](REFERENCES.md)：核对论文和本地实现入口。

## 阅读时必须区分三层

- **原论文思想**：作者提出的方法全貌。
- **当前 baseline 实现**：本实验真正执行的配置，可能主动关闭论文中的某些模块。
- **下一版 Agent 候选设计**：研究假设，不是已实现功能或已有实验结论。

如果三层混写，就会产生两类错误：把论文能力误报成本实验能力，或把未来设计误报成已经超过 baseline 的结果。

## 给 Idea 设计者的任务

请不要只提出“多搜索几次”“再加一个 Reviewer”或“把证据打一个总分”。优先回答：

1. Agent 如何证明某个现实知识缺口足以改变 OR 决策，因此值得搜索？
2. 多个缺口并存时，如何逐项表示、排序、检索和停止？
3. 网页证据如何证明来源有效、适用于当前题、覆盖完整，并且能绑定到具体模型槽位？
4. Patch 如何做到可追踪、最小化、可执行，并能由求解结果验证是否真的改变决策？
5. 哪个对照实验能证伪你的机制，而不是只展示一个更长的 Agent 链？

请使用 [Idea 提交模板](06_IDEA_BRIEF_FOR_NEXT_AGENT.md#给学弟的-idea-提交模板)。
