# SearchWorthyOR 实验结论

日期：2026-07-31
状态：全部预注册运行、恢复裁决、可信重放与四方法成对统计已完成。

## 结论先行

当前最稳健的结论分为三句：

1. **外部证据确实能改变模型，而且强模型拿到相关证据后大多能正确改模。**
   GPT-5.6-sol high one-shot 从无搜索的 0/100 完整决策模型等价，提高到冻结语料的
   95/100；在同一 20 条网页题上，冻结快照和真实联网均为 16/20。
2. **当前数据没有证明高级搜索 Agent 必要。**
   不看题面的候选全文 medoid 可 100% 选中 Gold，metadata top-5 + medoid 为 96%，80 条
   private 题在给定 Gold base IR 后可被四类固定模板 80/80 解出。Gold patch 只有 7 种匿名
   结构签名，96/100 是很小的 append-only patch。
3. **更长的 Agent 流程没有超过 one-shot，主要新错误来自编排而非优化建模。**
   决策模型等价为 one-shot 95、OPTIMUS 93、OptiMiner 89、CoE 12；后三者分别消耗约
   `4.87×`、`4.08×`、`35.30×` 的 one-shot input。

因此当前 insight 是：

> SearchWorthyOR 测到了“外部规则到小型模型补丁”的 evidence-to-formulation binding；它尚未
> 测到开放环境中发现未知模型槽位、多来源冲突裁决和复杂 Graph Rewrite。搜索内容有决策价值，
> 但复杂搜索本身的必要性被候选设计与补丁模板泄漏削弱。

## 1. 实际运行身份

- actual model：`gpt-5.6-sol`；
- requested reasoning：`high`，未独立验证；
- final solver：Gurobi 12.0.2；
- one-shot：每题一次最终建模调用；
- one-shot frozen-corpus：runner 用实体、辖区和决策时间执行固定本地 BM25，将 top-5 候选
  直接放入模型提示；它不联网，也不是模型自主检索；
- one-shot no-search：受控 evidence ablation，提示合同要求没有证据时 base/patched IR 相同；
- live-web：20 条 real-web 任务真实 web search；
- prompt adapters 与 training-free runner 都是 compatibility/inspired 实现，不是上游仓库未修改
  复现。

## 2. GPT-5.6-sol high one-shot 全量

| 指标 | 无搜索 | 冻结语料 |
|---|---:|---:|
| 预注册分母 | 100 | 100 |
| 完整提交 | 100 | 99 |
| Base model success | 100 | 99 |
| 生成代码与提交 IR 一致 | 100 | 99 |
| EvidenceHit@1 | N/A | 36 |
| EvidenceHit@5 | N/A | 97 |
| Exact evidence selected | N/A | 97 |
| 非空结构改模 | 0 | 98 |
| 完整投影可行集匹配 | 0 | 95 |
| 完整最优行动集匹配 | 0 | 95 |
| 完整决策模型等价 | 0 | 95 |
| Decision E2E | 0 | 89 |
| Semantic E2E | 0 | 47 |
| Strict exact E2E | 0 | 0 |

冻结语料对完整决策模型等价的成对差值为 +95 个百分点，task bootstrap 95% CI 为
[+90,+99]，McNemar 精确双侧 `p=5.049e-29`。这不是由分母缩小得到：一个代码语法失败仍作为
false 保留在 100 题分母内。

但 `0→95` 不能解释成自主搜索策略的提升。无搜索组被合同性地禁止猜测外部规则并要求空补丁，
冻结语料组则由 runner 预先提供 metadata-BM25 top-5；该对照证明“外部证据候选供给有价值”，
不测量模型是否知道何时搜索、如何改写查询或何时停止。

`Strict exact E2E=0` 不等于最终模型全部错误。它要求变量名、IR 表示、typed patch 和
claim mapping canonical exact；`Decision model equivalent=95` 则直接比较完整投影可行集和
完整最优行动集合。两者共同说明：当前模型经常在决策意义上正确，但过程表示并未严格复现 Gold。

### 2.1 五个最终失败

| 任务 | 失败位置 | 原因 |
|---|---|---|
| SWOR035 | Claim → ModelSlot | 把条件性 `A→¬B` 过度扩大为无条件 `B=0`。 |
| SWOR037 | Retrieval + binding | Gold 不在 top-5；相似规则被写成 `A∧B→(G∨H)`，而非 `A→¬B` 与 `A→(G∨H)`。 |
| SWOR048 | Retrieval | 采用错误的“双重抵免”规则后 abstain，没有执行 Gold 的 `x_0=0`。 |
| SWOR074 | Claim → ModelSlot | 把 `A+B≤1` 与 `B→(E∨F)` 错并为 `A∧B→(E∨F)`。 |
| SWOR095 | Equation → Code | IR 意图正确，残差列表的非法 comprehension 导致 `SyntaxError`；非空模型响应不重试。 |

详细证据见 `ONE_SHOT_ERROR_ANALYSIS.md`。

## 3. 同一 20 条网页题的三条件比较

| 指标 | 无搜索 | 冻结快照 | 真实联网 |
|---|---:|---:|---:|
| Base model success | 20/20 | 20/20 | 20/20 |
| 非空结构改模 | 0/20 | 19/20 | 19/20 |
| 完整决策模型等价 | 0/20 | 16/20 | 16/20 |
| Gold ID/URL exact | 0/20 | 18/20 | 3/20 |
| 人工权威来源语义等价 | N/A | 未单独裁决 | 20/20 |

冻结与真实联网的完整决策模型等价率完全相同，且成对 discordance 为 3 对 3，McNemar
`p=1`。这不表示两种条件逐题完全相同，而是总错误数相同。

`3/20 exact URL` 不能解释成“真实联网只有 15% 找对”：人工裁决为 20/20 都找到了支持同一
规则的权威来源。冻结条件比较 exact document ID，live-web 比较 exact Gold URL，两者语义不同，
不应做来源质量排名。

真实联网的代价很高：平均每题约 8 次完成的 web search、平均输入约 47.6 万 token、平均 wall
time 约 239 秒。它没有在这 20 题上超过冻结快照的 16/20 决策等价，说明当前题目没有把开放
网页发现优势转化为更高的建模准确率。

### 3.1 数据歧义

SWOR085 没有在公开题面说明食品由 FDA 而非 USDA/TTB 管辖。FDA 官方说明其 gluten-free 规则
适用于 FDA-regulated packaged foods，而 USDA/TTB 产品不在该规则范围。Agent 因主体不唯一而
abstain 是合理的；若把该 abstention 计为可接受，真实联网为 17/20，而非原 Gold 的 16/20。

## 4. 全量 100 题确定性审计

| 项目 | 结果 |
|---|---:|
| 任务 / Gold / 文档 | 100 / 100 / 400 |
| 当前 Gold adjudication | reject 100/100 |
| 非空结构补丁 | 100/100 |
| 增加变量 | 25 |
| 修改变量域 | 25 |
| 增加约束 | 75 |
| 删除变量/约束 | 0 |
| 修改既有约束 | 0 |
| 修改目标结构 | 0 |
| 直接小型 append patch | 96/100 |
| patch op 数量 | 均值 1.55，中位数 1，最大 4 |
| 匿名 patch 签名 | 7 |
| base/patched 最优行动集合不相交 | 100/100 |
| 最小行动 Hamming 距离 | 均值 2.04，中位数 2，最大 5 |
| 目标值绝对相对变化 | 均值 6.77%，中位数 5.70% |

数据不是纯 fogging：Gold patch 的确改变可行域或变量域，并让最优行动集合不相交。但“有决策
变化”只是必要条件，不是高难度搜索或复杂建模的充分条件。

## 5. 搜索与补丁捷径

### 5.1 不看任务的候选攻击

| 方法 | Gold 文档选择率 |
|---|---:|
| 随机 | 25% |
| 条款多数 + 最新日期 tie-break | 90% |
| 候选组全文 medoid | 100% |

该攻击完全不读取 public task，因此 corpus-search 命中 Gold 不能全部归因为实体、时间、辖区、
主体和例外推理。

### 5.2 BM25

| 查询 | Hit@1 | Hit@5 | Hit@10 | MRR |
|---|---:|---:|---:|---:|
| 完整 public task | 12% | 48% | 62% | 0.312 |
| 仅实体 + 辖区 + 决策时间 | 37% | 98% | 100% | 0.673 |

metadata 查询反而明显优于完整 OR 题面，说明数学建模信息没有形成主要检索难点。

### 5.3 Oracle-base patch-only

在 80 个 fresh-private 题上，给定 Gold base IR 后，
`metadata BM25 top-5 + medoid + 四类固定 patch 模板` 得到证据、patch class、行动和目标
80/80。它不是端到端 baseline，但直接反证了当前 patch 层的非平凡性。

## 6. 四方法冻结语料结果

| 方法 | 提交 | Base / code | 决策模型等价 | Decision E2E | Semantic E2E |
|---|---:|---:|---:|---:|---:|
| one-shot | 99 | 99 | 95 | 89 | 47 |
| OPTIMUS-inspired | 100 | 100 | 93 | 84 | 44 |
| CoE-inspired | 13 | 13 | 12 | 8 | 4 |
| OptiMiner compatibility | 92 | 92 | 89 | 72 | 39 |

one-shot 与 OPTIMUS 的决策模型等价差值为 `+2pp`，95% CI `[-2,+6]`、McNemar
`p=0.625`；one-shot 与 OptiMiner 为 `+6pp`，bootstrap CI `[+1,+12]`，但 McNemar
`p=0.0703`。在当前 100 题上，没有证据表明分阶段 OPTIMUS 或自主检索 OptiMiner 优于固定
metadata-BM25 top-5 的一次建模。

OptiMiner 的条件准确率为 `89/92=96.7%`，说明形成 final 后建模通常正确；固定分母损失主要来自
7 个停止失败和 1 个未恢复 CLI failure。CoE 的 13 个提交中 12 个决策等价，但 85 个被门禁
拒绝的 MCP 调用和 2 个 CLI 失败使固定分母只有 12/100。它说明专家角色本身有表达能力，同时也
说明 prompt 中的“不要调用工具”不能代替运行时 capability graph。

实际完成事件的 input token 为：

| one-shot | OPTIMUS | CoE | OptiMiner |
|---:|---:|---:|---:|
| 1,777,010 | 8,651,106 | 62,726,738 | 7,241,908 |

OPTIMUS、OptiMiner 和 CoE 分别为 one-shot 的 `4.87×`、`4.08×`、`35.30×`。CoE 与
OptiMiner 的完成调用几乎相同（398 vs 397），但 input 是后者的 `8.66×`，直接支持图状态裁剪
与 typed node boundary，而不是继续把全部专家历史串入一个循环。

这些 bootstrap 与 McNemar 统计只按任务配对；100 题共享少量生成与补丁模板，不能把 task-level
CI 当作 100 个独立自然问题的总体推断。

## 7. SearchGraph-OR：Graph Engineering 路线

“Graph Engineering”目前是形成中的工程标签，不是已有统一定义的学术范式。可验证的共识是：
现代 Agent 正在把工作流图、任务状态/知识图和跨任务经验图作为一等对象。

SearchGraph-OR 维护两张核心图：

- **Work Graph**：知识边界检测、并行来源搜索、适用性 veto、patch proposals、graph merge、
  Gurobi 编译、solver test 和反事实证书；
- **Evidence-Model State Graph**：
  `Source → Claim → Applicability → ModelSlot → Equation → CodeRegion → SolverTest → Decision`。

每次改模是局部 Graph Rewrite，必须声明来源 claim、命中的 model slot、受保护 base 节点、
前后 hash 与代码 diff。错误沿具体边回退：

- 找错文档，只重开 `OpenSlot → Source`；
- 文档正确、条件作用域错，只重审 `Claim → ModelSlot`；
- IR 正确、代码语法错，只重编译 `Equation → CodeRegion`；
- incumbent 相同但行动集不同，只扩展 `SolverTest → Decision`。

Experience Graph 只吸收经 evidence removal、wrong-version swap、binding permutation 和完整行动集
验证通过的子图；不能把最终 reward、数据泄漏或偶然 incumbent 直接强化成经验。

完整设计见 `docs/GRAPH_OR_SEARCH_AGENT.md`。

## 8. 当前回答

- **这个数据集有用吗？**
  有，用于测“外部规则能否被绑定成结构补丁并改变 OR 决策”；作为开放世界高级搜索 benchmark，
  当前版本不够。
- **联网搜索到的内容真的改变模型吗？**
  是。无搜索 0/100、冻结语料 95/100 完整决策模型等价，且 98/100 发生非空结构改模。
- **改变是否 trivial？**
  决策效果不 trivial，但建模操作大多 trivial：96% 是小型 append-only，只有 7 种匿名 patch
  签名，没有删除、既有约束重写或目标重构。
- **现在能否判断 OPTIMUS/CoE/OptiMiner 谁最好？**
  在本次 compatibility 实现、固定分母和不等预算下，one-shot 最强且最省；OPTIMUS 没有带来
  准确率收益，OptiMiner 的成功提交质量高但控制器可靠性更差，CoE 被运行时越权和上下文膨胀
  主导。这个结论不能冒充上游未修改复现排名。

## 9. 下一版数据集优先级

1. 消除候选 medoid、日期、长度、版式和 Gold role 泄漏；
2. 一题包含多个相互依赖 OpenSlot、多来源支持/冲突/例外；
3. 加入删除变量、重索引、修改既有约束作用域、跨期/跨实体耦合、分段逻辑和目标重构；
4. 同一政策在不同 task facts 下绑定不同 ModelSlot，阻断固定模板；
5. release gate 加入 task-blind、source-style、template classifier、GitHub contamination、
   distractor-only、counterfactual swap 与 binding permutation；
6. 修复 SWOR085 适用主体，并重新裁决当前 100/100 reject；
7. 用 graph-edge Gold 评过程，URL 和单个 incumbent 只作局部指标。
