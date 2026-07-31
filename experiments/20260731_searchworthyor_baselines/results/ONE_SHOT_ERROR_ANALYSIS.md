# GPT-5.6-sol high one-shot 错误分析

日期：2026-07-31

本文件只分析已经完成并由 hardened scorer 重放的 full run。`reasoning=high` 是调用参数，
不是独立验证出的模型内部属性。

## 冻结语料：100 题中的五个最终失败

99 题生成了完整提交；SWOR095 生成了非空响应和代码，但代码存在语法错误，因此保留为 active
model failure，没有重试。其余 95/99 个提交在完整投影可行集与完整最优行动集上和 Gold
decision-equivalent。失败不是一个统一的“建模错误”，而落在不同的图边上。

| 任务 | 找到 Gold evidence | 结构改模 | 失败边 | 具体原因 |
|---|---:|---:|---|---|
| SWOR035 | 是 | 是 | Claim → ModelSlot | Gold 是 `A→¬B` 且 `A→(F∨G)`；提交把第二条正确编码，但把第一条过度扩大成无条件 `B=0`。 |
| SWOR037 | 否 | 是 | OpenSlot → Source；Claim → ModelSlot | Gold 文档不在冻结检索 top-5。提交采用相似的加州休息规则，却只写成 `A∧B→(G∨H)`；Gold 是 `A→¬B` 且 `A→(G∨H)`。提交存在两个并列最优行动，只有一个碰巧等于 Gold incumbent，完整行动集并不等价。 |
| SWOR048 | 否 | 否 | OpenSlot → Source | 采用了“同一车辆不得重复享受两类抵免”的错误规则，并因题面没有同一车辆映射而拒绝加约束；Gold 证据应直接使 `x_0` 不具资格。 |
| SWOR074 | 是 | 是 | Claim → ModelSlot | Gold 是 `A+B≤1` 且 `B→(E∨F)`；提交错误合并为 `A∧B→(E∨F)`，既允许单独选择 B 而无处理服务，也没有直接禁止 A、B 同选。 |
| SWOR095 | 是 | 是 | Equation → CodeRegion | IR 与意图均为 `x_0=0`，但残差列表中把列表推导式直接写在列表字面量内，`model.py` 第 37 行触发 `SyntaxError`。模型已返回非空事件，按预注册规则不重试。 |

这五题给出两个比最终 accuracy 更重要的观察：

1. 三个数学失败中，模型都能复述正确或高度相关的自然语言规则；真正的瓶颈是把条件规则
   绑定到正确变量和作用域，而不是“有没有读懂关键词”。
2. 只比较一个 Gurobi incumbent 会把 SWOR037 错判为成功。必须比较完整最优行动集合和投影
   可行集，才能识别“结果碰巧相同、模型仍然错误”。

## 真实联网：20 题中的四个决策不等价

真实联网条件在 20/20 题中都找到了人工裁决为语义等价的权威来源，但只有 16/20 个模型与
Gold 在完整决策集合上等价：

| 任务 | 来源层 | 建模层 |
|---|---|---|
| SWOR012 | 找到正确 40 CFR 262.17 | 只编码 `A→¬B`，遗漏 A 分支必须选择不超过 90 天的合规方案 E/F。 |
| SWOR035 | 找到正确 21 CFR 101.9 | 把条件性 `A→¬B` 错写为无条件 `B=0`。 |
| SWOR038 | 找到正确加州规则 | 把条件性 `A→(E∨F)` 错写为无条件 `A=0`。 |
| SWOR085 | 找到正确 FDA gluten-free 规则 | 公开题面没有说明产品受 FDA 而非 USDA/TTB 管辖；Agent 因适用主体不唯一而 abstain。该题属于数据歧义，不应简单算作 Agent 错误。 |

因此，按原 Gold 严格计为 16/20；若把 SWOR085 的审慎 abstention 记为可接受，则为 17/20。
这个差异必须和 exact URL 指标分开：20/20 来源语义正确，但 Gold URL 字符串完全相同只有
3/20。

## 对 SearchGraph-OR 的直接约束

错误修复不应路由回一个全局 reflection loop，而应沿失败边局部回退：

- 检索失败：重开 `OpenSlot → Source`，改变查询与来源邻域；
- 来源正确、条件错误：固定 Source/Claim，只重审 `Applicability → ModelSlot`；
- IR 正确、代码错误：禁止重新搜索，只重编译 `Equation → CodeRegion`；
- incumbent 相同但行动集不同：固定代码，扩展 `SolverTest → Decision` 的最优面证书。

这也是 Graph Engineering 相比顺序 pipeline 的实际价值：失败对象和允许重做的子图是显式的，
不会让一次代码语法错误触发重新检索，也不会让一次来源错误污染已经正确的 base model。
