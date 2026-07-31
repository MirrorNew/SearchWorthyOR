# Contamination and release boundary

## 当前 100 题的身份

SearchWorthyOR-100 的 GitHub 仓库同时发布公开题目、证据语料、Gold 和模型复核材料。因此该版本是
开放开发/审计集，不是可长期维持保密性的隐藏测试集。目录名 `private/` 只表示运行时接口角色，
不提供访问控制。

同日发布降低了“模型已从既有训练语料记住本版本”的可能性，但不能仅凭时间线证明模型快照的
训练边界。运行时工具还可能访问 GitHub，所以必须额外审计工具轨迹。CoE 全量事件和 one-shot
live-web 的 prompt/response/search event 中均未发现 `MirrorNew`、`SearchWorthyOR-100`、
`github.com/MirrorNew` 或 `private/gold.jsonl` 命中；产生 GitHub MCP 事件的 CoE 专家输出被
统一事件门禁拒绝，没有作为成功提交继续评分。该检查只能排除这些可观察的显式访问，不能证明
不可观察缓存、未来模型或后续调参没有污染。

## 可以报告什么

- 可以报告本次固定模型、固定日期、固定 runner 下的可复现实验；
- 可以把该 100 题用作开发、错误分析、scorer 回归和 Graph Engineering 原型；
- 必须声明 Gold 已公开、候选存在 task-blind 泄漏，且结果不是无污染 leaderboard 排名；
- 不得把读过 Gold 后的调参结果称为 held-out。

## 正式 leaderboard 的最低条件

正式测试集必须：

1. 在公开开发集之后生成并冻结；
2. 不公开题目—Gold 映射、证据包分组、模型与生成模板；
3. 与本仓库不共享 base、政策模板、实体命名模板和匿名 patch 签名；
4. 通过 task-blind、source-style、template classifier 和互联网精确文本搜索；
5. 由受控检索服务提供证据，不允许通用 GitHub/文件工具访问评测 Gold；
6. 记录模型版本、cutoff、运行日期、工具清单和所有搜索事件；
7. 评测结束后只发布聚合结果和承诺哈希，延迟公开完整 Gold。

因此当前公开仓库解决的是“可复核开发”，真正的 benchmark validity 还需要一个独立的
未公开 v2 held-out 轨道。
