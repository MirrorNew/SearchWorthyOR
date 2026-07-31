# Live-web 来源与适用性独立裁决

裁决对象是 `gpt-5.6-sol` high-requested one-shot live-web 的 20 条公开网页题。
裁决者未参与这些提交的生成。每题同时核对公开题面、模型实际选择的 URL、Gold source
passport、官方页面的操作性规则以及最终模型的完整行动集合。

这里区分三件事：

1. `exact`：模型选择的文档 ID 或 URL 与 Gold 字符串完全相同；
2. `equivalent`：URL 不同，但属于同一官方条款、官方法规版本或直接的成文法来源，并支持同一操作性规则；
3. `model`：来源正确之后，模型是否正确完成适用性和 evidence-to-formulation binding。

| Task | 来源裁决 | 适用性裁决 | 决策模型 | 主要说明 |
|---|---|---|---|---|
| SWOR003 | equivalent | pass | equivalent | FDA 官方 overview 与 Gold menu-labeling 页面支持同一 20+ 连锁门店规则 |
| SWOR006 | equivalent | pass | equivalent | Public Law 117-169 直接给出低收入或非城市 census tract 条件 |
| SWOR008 | exact | pass | equivalent | 精确命中 EPA 2024 CHDV NOFO |
| SWOR012 | equivalent | pass | mismatch | 找到 40 CFR 262.17，但只建 `A→¬B`，遗漏 A 分支所需的 90-day 合规选项 |
| SWOR013 | equivalent | pass | equivalent | eCFR §395.3/§395.1 与 2020 Final Rule 等价于 Gold 的版本化 XML |
| SWOR035 | equivalent | pass | mismatch | 找到 21 CFR 101.9，却把条件排除写成无条件 `B=0` |
| SWOR037 | exact | pass | equivalent | 精确命中 California rest-period FAQ |
| SWOR038 | equivalent | pass | mismatch | 找到 Labor Code §512、Wage Order 和 FAQ，却把 `A→(E∨F)` 误写为 `A=0` |
| SWOR042 | equivalent | pass | equivalent | DOL Fact Sheet 22 支持 bona-fide meal period 的完全解除职责条件 |
| SWOR048 | equivalent | pass | equivalent | Public Law 119-21 直接把 30D acquisition cutoff 改为 2025-09-30 |
| SWOR055 | equivalent | pass | equivalent | EPA HWC NESHAP 页面与 2026 Federal Register 支持同一适用范围 |
| SWOR058 | equivalent | pass | equivalent | eCFR Part 117 的具体 section 与 FAA Final Rule 等价于 Gold 版本化 XML |
| SWOR062 | equivalent | pass | equivalent | 40 CFR 260.10/262.14 直接定义 generator category 与对应规则 |
| SWOR069 | equivalent | pass | equivalent | eCFR §395.3/§395.1、FMCSA 与 Final Rule 支持 8-hour interruption 规则 |
| SWOR074 | equivalent | pass | equivalent | 40 CFR Part 268 的具体条款直接支持 untreated hazardous waste 的 land-disposal restriction |
| SWOR080 | equivalent | pass | equivalent | 26 USC §45W(d)(3) 直接规定 45W 与 30D 不得双重获益 |
| SWOR085 | equivalent | unresolved task | abstain | 找到 21 CFR 101.91 和 FDA Q&A；但公开题面未说明产品受 FDA 而非 USDA/TTB 管辖，Agent 的 abstain 有依据 |
| SWOR088 | equivalent | pass | equivalent | FMCSA HOS 与 2020 Final Rule 支持 11-hour driving limit |
| SWOR092 | exact | pass | equivalent | 精确命中 WAC 296-126-092 |
| SWOR099 | equivalent | pass | equivalent | eCFR §210.10 与完整 CFR PDF 支持至少一种 fruit/vegetable 规则 |

## 汇总

- 严格文档 ID/URL 完全相同：`3/20`。
- 同一官方规则或直接成文法的语义等价来源：`20/20`。
- 原 Gold 口径下完整决策模型等价：`16/20`。
- 明确的 claim/binding/作用域错误：`3/20`（SWOR012、SWOR035、SWOR038）。
- 公开题面适用范围无法唯一裁决：`1/20`（SWOR085）。
- 排除歧义题后的完整决策模型等价：`16/19 = 84.2%`。
- 把有依据的 abstain 视为可接受行为：`17/20 = 85.0%`。

因此，原生 web 事件的 `Hit@k` 和 Gold URL 精确匹配都严重低估了实际来源质量；但来源正确
也不意味着模型正确。当前 live-web 的主要实质错误发生在条件作用域和
claim-to-model-slot binding，而不是找不到官方材料。

## SWOR085 的数据集问题

FDA 官方问答说明 21 CFR 101.91 适用于 FDA-regulated packaged foods，同时明确排除由
USDA 或 TTB 管理标签的食品。公开题面仅说明“包装食品制造商”和“美国联邦食品标签监管”，
没有给出产品类别或监管机构，也没有声明不属于 USDA/TTB 范围。因此 Gold 的
`unique_applicable_source=true` 缺少公开题面依据。修复方式是在题面中明确“该最终包装食品
由 FDA 管理，且不属于 USDA/TTB 标签范围”，或者把 Gold 改为允许 `abstain`。
