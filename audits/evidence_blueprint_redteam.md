# Evidence blueprint 红队审计

审计日期：2026-07-30  
审计对象：`scripts/build_evidence_blueprints.py` 与生成的
`staging/evidence_blueprints.jsonl`

## 结论

**PASS（蓝图层）**。100 条蓝图的结构、分层、平衡、适用性槽位、干扰类型、
官方来源域名和防泄漏边界均满足冻结合同。该结论只覆盖“证据蓝图是否可作为后续
构建输入”，不替代后续证据正文冻结、网页快照与哈希、公开题面导出检查、typed
patch、双求解器或完整 release gate。

## 实测分布

| 维度 | 实测结果 |
|---|---|
| 总行数 | 100 |
| OR family | 冻结 allowlist 的 10 类，每类 10 |
| 每类 evidence mode | 8 `fresh-private` + 2 `real-web` |
| 全局 evidence mode | 80 `fresh-private` + 20 `real-web` |
| `eligibility_domain` | 25 |
| `temporal_coupling` | 25 |
| `conditional_auxiliary` | 25 |
| `quota_risk_service_objective` | 25 |
| 私有项的类内分布 | 每个 family 的四个 patch class 各 2 |
| 运输和机组 | 4 个官方网页蓝图 |
| 食品营养 | 4 个官方网页蓝图 |
| 清洁车辆 | 4 个官方网页蓝图 |
| 排放与危险废物 | 4 个官方网页蓝图 |
| 劳动休息 | 4 个官方网页蓝图 |
| 私有干扰 | 80 旧版 + 80 错辖区 + 80 错主体 |
| 真实网页 URL | 20 个互异 HTTPS URL，全部命中官方域名白名单 |

冻结 family allowlist：

`routing_transport`、`scheduling_workforce`、`production_capacity`、
`assignment_matching`、`facility_network`、`inventory_supply_chain`、
`energy_environment`、`healthcare_resources`、`finance_portfolio`、
`telecom_service`。

## Loophole 循环与修复

### 0. 蓝图自创 family 枚举，倒逼主合同迁就

- **攻击**：生成器内部保持“10 类各 10”仍可能使用与主合同、独立 gate 不同的十个名字；
  仅靠总数检查无法发现契约漂移。
- **修复**：在生成器中加入独立的 `FAMILY_ALLOWLIST` 常量，并断言配置顺序、每行
  `family` 与最终计数均严格命中上述十类；蓝图服从主合同，不要求 gate 适配。
- **复验**：新 allowlist 每类恰好 10；旧枚举字符串在三个授权文件中零残留；PASS。

### 1. 用全局总数掩盖 family 内失衡

- **攻击**：即使全局为 80/20，仍可能让某些 family 全是私有题、另一些全是网页题；
  patch class 也可能集中在少数 family。
- **修复**：生成器逐 family 断言 10 条、8/2；私有八条中四个 patch class 各 2。
- **复验**：PASS。

### 2. “fresh-private” 只有标签，没有多条款适用性

- **攻击**：单一规则句或单一阈值会退化为 exact lookup，不能测试联合适用性。
- **修复**：每个私有蓝图固定包含至少四个条款槽位，并同时登记 `jurisdiction`、
  `entity_scope`、`effective_period`、`exception_scope` 与解析顺序。
- **复验**：80/80 私有蓝图均有四个条款槽位和非空例外；PASS。

### 3. 干扰文档只是主题无关噪声

- **攻击**：无关文档太容易排除，无法检验适用性错误。
- **修复**：每个私有项恰有三个同主题干扰：同主体同辖区的旧版、同主体的错辖区
  现行版、同辖区的错主体现行版；每个干扰都给出拒绝依据。
- **复验**：三类顺序和数量逐行断言，80/80 通过。

### 4. 当前网页被错误当成决策时点规则

- **攻击**：网页会更新；当前页面不必然描述历史决策日适用规则。
- **修复**：每个 web 蓝图都有 `decision_time`、实体范围、辖区、例外和
  point-in-time 核验步骤；旧版/提案被显式列为干扰，而不是自动采纳。
- **复验**：20/20 具备完整 applicability 槽位；PASS。后续构建仍须冻结正文、
  抓取时间和内容哈希。

### 5. 把 `real-web` 夸大成普遍 E+

- **攻击**：参数记忆可能已包含公开网页，不能证明所有模型都“必须搜索”。
- **修复**：20 条统一标为 `real-web`，`anti_fogging_reason` 明确其只属于 E?；
  URL 用于来源与适用性审计，不作为普遍不可知证书。
- **复验**：PASS。

### 6. 蓝图泄漏 gold、求解结果或公开 source id

- **攻击**：把最终参数、最优值、参考答案、solver 状态或内部 source id 写入蓝图，
  会污染后续公开题面。
- **修复**：递归禁止 `source_id`、`gold`、`answer`、`reference_answer`、
  `solution`、`objective_value`、`solver_result` 等键。条款槽位只描述“检索什么”，
  不写最终政策数值或适用结论。
- **复验**：100/100 无禁用键；PASS。日期、法规标题中的编号和 URL 路径仅用于
  适用性/来源定位，不是优化 gold。

### 7. URL 或页面标题被复制到公开题面

- **攻击**：即使没有 `source_id`，把 `web_source_url`、`retrieval_anchor` 或
  `patch_class` 原样导出也会泄漏检索目标。
- **修复**：这些字段只存在于 `staging` 蓝图；`required_resolution_order` 与
  `anti_fogging_reason` 均要求公开导出时剔除 URL、页面标题和 patch 标签。
- **复验**：本脚本不生成 `public/tasks_zh.jsonl`，因此未产生公开泄漏。最终
  release gate 仍必须扫描公开文件，这是蓝图层无法替代的下游门。

### 8. 官方来源类别靠重复 URL 凑数

- **攻击**：同一入口重复四次会制造虚假来源多样性。
- **修复**：20 个 web 蓝图使用 20 个互异 URL，并按五个主题各四个；域名仅允许
  FMCSA/eCFR、FDA/USDA FNS、IRS/EPA、EPA、DOL/州劳工机构等官方站点。
- **复验**：20 个互异 HTTPS URL，官方域名白名单检查通过。浏览器于审计日直接
  抽取到 18 个页面；USDA FNS 与 DOL Fact Sheet 两页在一次批量打开中返回工具
  内部错误，但均已由官方域名搜索结果返回标题与正文摘要。此处不把可访问性检查
  冒充冻结快照；后续构建必须实际抓取并哈希。

### 9. 合成私有政策被误读为真实组织规则

- **攻击**：拟真的机构名和条款可能被误传播为现实政策。
- **修复**：私有蓝图的 `document_type` 固定声明为冻结后生成的合成私有政策，
  辖区名称带“（合成）”；数据集说明不得把它们作为现实组织陈述。
- **复验**：80/80 通过。

### 10. 手工修改 JSONL 导致脚本与产物漂移

- **攻击**：生成后手改一行仍可能保留表面计数，却破坏可复现性。
- **修复**：`--check-only` 同时验证现有 JSONL、重新生成期望对象并要求逐对象相等。
- **复验**：确定性重建 PASS。

## 执行证据

使用固定的本地 Python 运行时，以 UTF-8 执行：

```powershell
python scripts/build_evidence_blueprints.py
python scripts/build_evidence_blueprints.py --check-only
```

两次分别返回 `BUILT` 与 `PASS`，并报告 100 行及上述全部分布。另用 PowerShell
独立解析 JSONL，得到 `Rows=100`、`UniqueWebUrls=20`、
`PrivateBadClauses=0`、`PrivateBadDistractors=0`。

UTF-8 检查：

- 100 个非空 JSONL 行；
- 首字节为 `{`（123），无 UTF-8 BOM；
- U+FFFD replacement character 为 0；
- 连续三个以上问号的乱码模式为 0；
- JSON 读取与写回对象逐项相等。

## 剩余边界

蓝图已经闭合“如何构造和审计证据”的结构，但尚未声称下列工作完成：私有正文已经
冻结、真实网页已经形成 point-in-time 快照、网页内容不会漂移、typed patch 已产生
action-disjoint gold、或双求解器已经通过。这些必须由后续 evidence corpus、commitment、
gold、manifest 与统一 release gate 单独证明，不能由本 PASS 外推。
