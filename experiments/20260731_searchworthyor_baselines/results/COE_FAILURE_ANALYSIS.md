# CoE-inspired 全量失败分析

## 结论

CoE-inspired compatibility adapter 在固定 100 题中只产生 13 份可评分提交，87 题在形成最终
Gurobi 提交前失败。按固定分母计算：

| 指标 | 结果 |
|---|---:|
| 完整提交 | 13/100 |
| Base model success | 13/100 |
| 代码与提交 IR 一致 | 13/100 |
| 非空结构改模 | 12/100 |
| 完整决策模型等价 | 12/100 |
| Decision E2E | 8/100 |
| Semantic E2E | 4/100 |

条件于已经形成提交的 13 题，12 题决策模型等价；主要瓶颈不是最终 Gurobi 建模，而是专家节点
无法稳定遵守受控执行边界。

## 失败位置

| 节点 | 失败数 |
|---|---:|
| ProgrammingExpert | 44 |
| CodeReviewer | 24 |
| ParameterExtractor | 16 |
| TerminologyInterpreter | 2 |
| ModelingExpert | 1 |
| 合计 | 87 |

失败原因是 85 个禁止的 `mcp_tool_call` 和 2 个无响应 CLI 进程退出。越权调用覆盖五类专家，
说明问题不是某个单一角色提示词，而是提示词没有构成运行时 capability boundary。

两条无响应 CLI 失败 SWOR078、SWOR087 各允许一次恢复：

- SWOR078 复用前三个已有专家输出后，在 ProgrammingExpert 产生禁止 MCP 调用；
- SWOR087 新完成 ParameterExtractor 和 TerminologyInterpreter 后，在 ModelingExpert 再次无响应
  CLI 退出；
- 两者均保留原 `failure.json`，另存恢复失败与 `resume_resolution.json`，且不再重试。

## 成本口径

只对 13 个成功提交的 `submission.json` 求均值，会漏掉 87 个失败流程已经消耗的模型调用。
因此同时从所有不可变 `*events.jsonl` 的 `turn.completed` 事件汇总尝试成本：

| 方法 | 尝试模型调用 | 输入 token | 输出 token | reasoning token |
|---|---:|---:|---:|---:|
| One-shot frozen corpus | 100 | 1,777,010 | 476,454 | 210,120 |
| OPTIMUS-inspired | 400 | 8,651,106 | 839,864 | 365,716 |
| CoE-inspired | 398 | 62,726,738 | 1,882,704 | 946,968 |

CoE 在未完成全部计划节点的情况下，输入 token 已约为 one-shot 的 35.3 倍、OPTIMUS 的 7.25 倍。
原因之一是部分专家违反工具边界后仍生成很长的工具事件与响应。该表是本地事件的审计总量，不是
统一价格或统一 timeout 下的成本排名。

## 方法解释边界

这不是对上游 Chain-of-Experts 方法本身的原样复现结论。实际运行是本地
`coe_inspired_cli_adapter`，使用 GPT-5.6-sol、冻结证据候选、严格事件审计和不同于其他基线的
stage timeout。它支持的结论是：

> 线性专家链若只用提示词约束工具权限，并在单次检索之后不可回到 Source 节点，会把运行时越权
> 和检索候选缺失放大为整条链失败。

因此 SearchGraph-OR 必须提供运行时最小权限、节点级失败边和
`validation failure → OpenSlot → Source` 的显式回边，而不只是增加更多专家角色。
