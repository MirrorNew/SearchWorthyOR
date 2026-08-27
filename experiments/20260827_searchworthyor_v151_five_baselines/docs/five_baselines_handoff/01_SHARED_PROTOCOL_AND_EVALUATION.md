# 01｜共享实验协议与评价口径

## 1. 实验单位

SearchWorthyOR V1.5.1 包含 120 个源任务，每题有 C1/C2 两个公开 case，共 240 个 case。五种方法各运行一次时，正式矩阵为：

```text
240 cases × 5 methods = 1,200 independent method-case instances
```

当前 Smoke 固定为 `SWOR-R001-C1/C2 × 5`，只用于验证 10 条链路是否能终止、是否守住输入和 provider 契约。Smoke 不是正式性能实验。

## 2. 所有方法共同锁定的部分

| 项目 | 固定值 |
|---|---|
| 模型 | `gpt-5.6-luna` |
| 推理强度 | `xhigh` |
| temperature | `1` |
| Provider | Shubiaobiao |
| Provider fallback | 禁止 |
| 模型可见输入 | `id`、`case_id`、规范 `prompt_zh` |
| Gold | 仅 scorer 可见，runner 不可见 |
| 最终执行 | 生成的 Gurobi 代码必须在本地实际执行 |
| 输出 | 统一为同一结果契约并分层计分 |

公开仓库中的 `private` 表示“运行时角色隔离”，不等于 GitHub 保密。任何读过 Gold、修复记录、`models/` 或私有评分文件的人/Agent，都不能再把这 240 个 case 声称为隐藏且无污染测试。

## 3. 刻意保留的方法差异

| 方法 | 被允许的信息工具 | 为什么保留 |
|---|---|---|
| Direct | 条件触发的 hosted public-web search | 研究 Base-Solve 后的模型感知搜索 |
| Search-First | 与 Direct 完全相同的 hosted search | 构成顺序配对对照 |
| CoE | 无网页搜索 | 保留原生多专家建模能力 |
| OptiMUS | 无网页搜索 | 保留原生模块化 OR 建模能力 |
| optiminer-training-free | 仅 `arxiv_document` | 保留该 training-free runner 的建模知识检索形态 |

因此，“五方法总榜”回答的是端到端方法效果；只有 Direct vs Search-First 适合较强地解释建模/搜索顺序。CoE、OptiMUS 与 optiminer-training-free 不具备相同检索权，不能被解释成单一组件的公平消融。

## 4. Direct 与 Search-First 的共享搜索合同

两条链使用同一份 [检索实现](../../scripts/web_retrieval.py) 与固定配置：

- Shubiaobiao `/responses` + `web_search`。
- 每个 case 最多 3 次查询。
- 每次最多向后续流程暴露 6 条搜索结果。
- 每次最多尝试打开 6 个页面，最多计入 3 个成功可读页面。
- 每个 case 最多尝试打开 18 页，最多计入 9 个成功可读页面。
- 打开失败不占“成功可读页面”预算，但占页面尝试预算。
- 一条 query 最多使用一个 `site:`。
- 标题和 snippet 不能直接成为证据；引用必须能在页面正文中逐字核验。

三次查询不是三个缺口各三次，而是**整个 case 共享最多三次**。这对 Multi 问题尤其重要：若有多个规则原子，一个全局布尔值和三轮总预算可能不足以闭合所有缺口。

## 5. 统一输出与分层评价

每种 native 输出都由 adapter 转成统一记录。缺失字段写作 `NOT_OBSERVED`，不能根据最终动作或答案数量反推 applicability/Patch。

建议按以下层级读结果：

1. **协议层**：模型/provider 是否一致，是否有 Gold/API key 泄漏，搜索权限是否越界。
2. **运行层**：provider、runner、解析、输出契约、solver 是否成功。
3. **检索层**：是否触发、是否真实调用搜索、页面是否可读、引用是否核验、证据是否充分。
4. **模型修订层**：RETAIN/PATCH_CHANGES、applicability、Patch exact/precision/recall。
5. **决策层**：action IDs、目标值、方向、单位是否正确。
6. **联合层**：final-answer joint 与 full-agent joint。
7. **成本层**：调用、token、查询、页面、墙钟时间。

`retrieval_failure` 与最终答案状态相互独立：检索未闭合，但 Final 仍可能成功建模求解；反之，检索成功也不保证模型或代码正确。

## 6. 当前 Smoke 事实

根据 [Smoke 汇总](../../reports/smoke_validation_summary.json)：

| 方法 | 终态 | 解释 |
|---|---|---|
| Direct | 2/2 `OK` | 两个 case 均完成真实 Base Solve 与 Final Solve |
| Search-First | 2/2 `OK` | 两个 case 均完成 Final Solve |
| optiminer-training-free | 2/2 `OK` | native loop 能终止并适配输出 |
| CoE | 1 `OK`；1 `OUTPUT_CONTRACT_FAILURE` | 不是 runner 崩溃 |
| OptiMUS | 2 `OUTPUT_CONTRACT_FAILURE` | 原生输出未满足 V1.5.1 契约 |

总计 10/10 有终态，严格门禁 PASS；配置违规、Gold 泄漏、API key 泄漏、身份错配均为 0。Formal 1,200 实例尚未执行。

## 7. 可复核入口

- [实验总说明](../../README_zh.md)
- [冻结配置](../../EXPERIMENT_CONFIG.json)
- [离线协议门禁](../../scripts/offline_gate.py)
- [阶段验证器](../../scripts/validate_phase.py)
- [统一评分](../../scripts/score_report.py)
- [协议测试](../../tests/test_protocol.py)
