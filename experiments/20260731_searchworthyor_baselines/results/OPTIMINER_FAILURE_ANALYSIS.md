# OptiMiner training-free compatibility 错误分析

## 终态

原始 100 题运行产生 89 个提交和 11 个 failure。冻结原始状态后，只对同时满足
“目标阶段 response 缺失、events=0、stderr=0”的基础设施失败执行一次恢复：

- SWOR039、SWOR026、SWOR040：各恢复一次并成功，原 failure 与空事件证据保留；
- SWOR095：虽然同为 `0xC0000374`，但 stderr 有 401 B 的插件同步网络警告，不满足门，
  不恢复；
- 7 个 `max_research_turns_without_final`：方法失败，不恢复。

最终固定分母为 100：92 个提交、8 个 active failure、3 个 recovered failure。92 个提交均
完成 base 建模、非空结构变化、Gurobi 代码与 IR 一致性；89 个与 Gold 的完整投影可行集及完整
最优行动集合等价。

## 失败来源

| 层 | 数量 | 含义 |
|---|---:|---|
| Controller 停止失败 | 7 | 第 4 个 controller 回合仍请求搜索，超过 3 轮预算且没有 final |
| CLI 进程失败 | 1 | SWOR095，无 response/events，但 stderr 非空，因此不进入恢复门 |
| Evidence identity 失败 | 2/92 | SWOR048、SWOR088 未选择 exact Gold 文档，但决策模型仍等价 |
| Claim-evidence 不一致 | 15/92 | 规则主张、作用域或 canonical binding 未通过过程评分 |
| 决策模型不等价 | 3/92 | SWOR042、SWOR006、SWOR058 |

Controller 的停止失败是 Graph Engineering 问题，不是“再写一句请停止”即可解决。当前 runner
在最后检查轮仍向模型暴露同一个允许 `search` 的 action schema；预算边界应由运行时删除
`Controller → Search` 边，只留下 `final-with-certificate` 与 `abstain/escalate`。

## 三个决策不等价提交

- **SWOR042**：Gold 是条件组合约束 `A → ¬B`；Agent 把 A、B 各自都禁用，属于条件作用域
  过度扩大。
- **SWOR058**：Gold 是同一机组的 A、B 不能组合；Agent 直接令 B 不可用，把组合冲突误写成
  单动作禁用。
- **SWOR006**：Gold 把节点 A 定义为“建设并申领抵免”的复合动作并固定 `x_A=0`；Agent
  另外增加抵免申领变量，只禁用申领、不禁建设。它与 Gold 决策不等价，但暴露了公开题面的动作
  粒度歧义：若建设和申领本应可分，Agent 的建模更合理；若候选动作本来就是复合动作，Gold
  才成立。鉴于当前 Gold 盲审状态为 reject，不能把这一例无条件归为模型错误。

前两例说明主要语义错误不是“没搜到数值”，而是
`Claim → ModelSlot` 的条件作用域错误；第三例说明 benchmark 必须在搜索前冻结 action ontology
与投影，不能事后用 Gold 粒度压制合理的变量拆分。

## 固定分母与条件准确率

- 固定分母：`89/100` decision-model-equivalent；
- 只看形成提交的任务：`89/92 = 96.7%`；
- exact evidence selected：`90/100`；
- semantic E2E：`39/100`。

因此该方法的最终建模能力不弱，主要损失来自控制器可靠性和来源/绑定过程，而非 Gurobi 编译。
但条件准确率不能替代固定分母成绩；否则会把 8 个 pipeline failure 隐藏掉。
