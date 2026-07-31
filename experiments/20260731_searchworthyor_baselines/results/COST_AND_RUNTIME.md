# 调用成本与运行时

## 固定 100 题分母的实际完成事件

下表统计所有 `turn.completed`，包含最后失败的调用，不只统计成功提交。Input token 包含
provider 报告的 cached input；这里只报告原始用量，不换算美元成本。

| 方法 | Model calls | Input tokens | Output tokens | Reasoning tokens |
|---|---:|---:|---:|---:|
| one-shot frozen corpus | 100 | 1,777,010 | 476,454 | 210,120 |
| OPTIMUS-inspired | 400 | 8,651,106 | 839,864 | 365,716 |
| CoE-inspired | 398 | 62,726,738 | 1,882,704 | 946,968 |
| OptiMiner compatibility | 397 | 7,241,908 | 574,555 | 232,404 |

相对 one-shot，OPTIMUS 使用约 `4.87×` input，OptiMiner 使用约 `4.08×`，CoE 使用约
`35.30×`。CoE 与 OptiMiner 的完成调用数几乎相同（398 vs 397），但 CoE input 是后者的
`8.66×`，说明问题主要是专家链反复携带膨胀上下文，而不是单纯“多调用了一次”。

## 成功提交条件下的每题均值

| 方法 | Input | Output | Reasoning | Calls | Search calls | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| one-shot | 17,771 | 4,771 | 2,112 | 1.00 | 1.00 | 105.0 |
| OPTIMUS-inspired | 86,511 | 8,399 | 3,657 | 4.00 | 1.00 | 200.7 |
| CoE-inspired | 772,721 | 28,573 | 14,485 | 6.00 | 1.00 | 698.3 |
| OptiMiner compatibility | 72,882 | 6,091 | 2,453 | 4.00 | 2.00 | 151.4 |

这些 wall-time 均值只覆盖形成 submission 的任务；CoE 只有 13 题，OptiMiner 有 92 题。
不同方法的 timeout、并发与成功覆盖率也不同，因此 wall time 不能当作严格等预算基准。

## 结论

- OPTIMUS 的额外阶段没有带来相对 one-shot 的准确率收益，却增加约 4.9 倍 input；
- OptiMiner 的自主多轮查询在成功题上保持很高决策准确率，但 8 个 active failure 使固定分母
  落后，而且 exact retrieval 没超过固定 metadata-BM25；
- CoE 的主要问题是能力边界与上下文工程失控，不能把其 13 个成功提交的条件准确率外推到全量；
- Graph Engineering 应让确定性节点管理路由、预算、状态裁剪与能力边界，只把 OpenSlot
  发现、适用性判断和 claim binding 留给 LLM。
