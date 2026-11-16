# 第一项疑问：案例采集与描述性输入示例

回复重点是：我们已开始取得并整理杉数提供的 ORLM 相关优化任务材料，后续扩充将把规整规格改写为更贴近业务用户的描述，并让模型主动获取分散在操作规程、产品规范等材料中的适用规则。下面给出一个已完成的叙述改写示例；这些材料尚未构成独立真实部署验证。

## 示例：L500 多品种换模排产

来源为 `SFT1991_sample20/REAL6_complexified(1)/REAL6_complexified/REAL_RB-CO-00/requirements.md` 及其 CSV：单条生产线、12 种产品、8 个生产日，目标是满足交付与生产要求并降低日末库存持有成本。

**描述性输入示例（基于所提供规格改写，非客户原话）：**

> 帮我们把这条线接下来八天的生产安排一下，总共十二个产品。订单、现有库存、生产速度和每天能开多久，我先给你。每天该交的货都得交出去，也别为了省事提前做一大堆，把库存费用压下来。产品不能一直放，换产品还得准备和清洗；跨天接着做时也别把上一批的状态弄丢。具体批次要求、产品保存要求和清洗料怎么领，要结合对应的工艺、产品和仓库说明查清楚。最后给班组一个每天按什么顺序、各做多少的计划。

初始输入只需提供订单、期初库存、生产速度、可用工时等业务数据；不把以下约束阈值全部列在用户问题中。现有规整规格可用于整理独立的待获取材料，并保留条件到原始条款的对应关系：

| 需要获取／确认的信息 | 现有规格中已有的依据 | 对数学模型的作用 |
|---|---|---|
| 批次与换模操作规程 | §2–3：每批至少5件、每天最多6批、批次不得跨日；空闲不重置上一真实批次状态；换模时间有方向 | 批次数量与时间约束、有向换模时间、跨日状态传递。 |
| 产品保存及发料规范 | §4.1 与 `products.csv/shelf_days`：不同产品可保存3或4天；期初库存按前一日生产；按先进先出交付 | 分批龄库存、到期约束、先进先出关系，避免只用总库存平衡。 |
| 清洗物料领取和仓储规则 | §3.1 与清洗物料两张CSV：整箱领取、当日额度、领取后仓容、清洗逐次消耗和跨日结存 | 整数领取变量、库存动态、仓容和逐次资源可行性约束。 |

这类扩充的关键不是单纯增加产品或约束数量，而是让建模系统从业务描述识别信息缺口，找到适用材料，再把规则绑定到正确的批次、日期、产品或仓储状态。

本例中的规则是已有材料中的业务规则，不是新编法规。上表中的工艺／仓储说明是拟从现有规格整理出的检索材料，不能称为已经取得的原始企业文件，也不能默认它们可由公开网页检索到。若用于后续评测，需提供可访问且固定版本的材料及检索入口；本次只展示改写示例，未对该版本运行 SWAgent 或报告成绩。

来源明确注明该实例数值独立合成，`data/parameters.csv` 的 `data_origin` 为 `synthetic; complexify pilot; no customer data reproduced`。因此对外可写“基于所提供业务材料改编的示例，使用合成数值”，不能写成客户原始对话、真实客户数值或已完成独立真实场景验证。当前已运行的20题是另一批完整信息的 C3 案例，不能将其成绩记在本例之下。

## 第一项回复建议——中文

关于外部有效性，我们已经开始从杉数取得并整理 ORLM 相关优化任务材料，计划持续扩充。整理工作不仅包括完整信息条件下的补充评测，也包括把规整的训练规格改写为更贴近业务用户的描述，并将适用规则放回需要获取的配套材料中。例如，我们选取了一个涉及12种产品、8个生产日的换模排产案例，将输入重述为“按时完成订单、安排每日生产顺序和数量，并降低库存费用”的业务诉求。系统随后需要获取批次与换模要求、产品保质与发料规范、清洗物料领取规则，才能完整构建跨日生产和库存模型。这展示了我们正在推进的案例整理方向：从业务任务出发，评测信息缺口识别、适用规则获取及数学模型更新。该展示例基于所提供材料改编并使用合成数值；我们将继续扩充来源明确、规则材料可核查的案例。

## Suggested reply — English

Regarding external validity, we have begun obtaining and organizing ORLM-related optimization task materials from Cardinal Operations and plan to continue expanding this collection. Alongside evaluation with complete information, we are working toward business-user descriptions in which applicable rules must be obtained from accompanying materials. For example, we have recast a production-scheduling case involving 12 products over eight days as a request to fulfill daily orders, choose production quantities and sequences, and reduce inventory costs. Completing the model then requires obtaining batch and changeover requirements, product shelf-life and issuing rules, and cleaning-material replenishment policies. This illustrates the direction of our ongoing collection effort: evaluating information-gap identification, applicable-rule acquisition, and model updates in richer business tasks. This illustrative adaptation uses synthetic numerical data from the supplied material; we will continue expanding the collection with documented provenance and verifiable rule sources.
