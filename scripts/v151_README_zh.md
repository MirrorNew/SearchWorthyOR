# SearchWorthyOR-v1.5.1 数据集说明

## 1. 版本定位

SearchWorthyOR-v1.5.1 以 V1.4.4 为只读输入，对 120 个 source task 的 240 个 C1/C2 case 做逐题语义修复。目标是让 Agent 只从题面读取客观业务事实，自主识别题外知识缺口，再用决策日有效的外部权威证据判断是否修改基础优化模型。

> **重建边界：** 本目录保留 V1.5.1 的生成与跨版本验证逻辑；完整重建需要调用者另行提供只读 V1.4.4 源目录。当前仓库只发布 V1.5.1，不包含旧版数据文件。

每对 case 仅保留两种 scorer-only 状态：

- `RETAIN`：题外规则对当前 case 不产生模型修改作用，返回 Base IR 的最优解；
- `PATCH_CHANGES`：题外规则支持非空 typed Patch，重求解后的最优决策相对 Base IR 改变。

本版本不包含 `PATCH_STABLE`，不盲化 `C1/C2` 后缀，不运行新的大模型实验，也不把格式纠错或微调写入数据集 Gold。

## 2. 数据规模与配对合同

| 项目 | 数量 |
|---|---:|
| source task | 120 |
| 公开 case | 240 |
| `RETAIN` / C1 | 120 |
| `PATCH_CHANGES` / C2 | 120 |
| Single / Multi | 60 / 60 |

同一 source task 的 C1/C2 共用优化骨架、公开 action schema 和官方证据；差异只放在 `case_facts` 的客观日期、辖区、主体或对象属性中。

## 3. 公开输入与私有 Gold

模型调用只能接收 `id`、`case_id`、`prompt_zh`。`prompt_zh` 是唯一完整任务正文，按以下顺序确定性渲染：

1. `【本 case 权威事实】`；
2. `【基础优化语义合同】`；
3. `【解释优先级】`；
4. `【优化骨架】`；
5. 公开 `output_schema`。

`private/` 中的 decision state、官方证据 Gold、typed Patch、IR、行动 Gold、目标 Gold 和变量映射只供验证器与 scorer 使用，不得注入 Agent 输入。

## 4. 题内事实与题外规则边界

- 题外官方证据只定义对象/主体范围、辖区、有效日期、阈值、正式例外和法定义务；
- 题内优化骨架定义候选行动、成本、收益、预算、互斥关系以及行动可以提供的本地业务能力；
- 外部规则不能直接发明题内行动或题内成本；题面也不能提前写出适用性、豁免、分支触发或 Patch 结论；
- 对无需修改的正确内容保持原样，不为风格变化重写背景。

## 5. 目录结构

```text
SearchWorthyOR-v1.5.1/
├─ README.md
├─ MODEL_IO_CONTRACT_zh.md
├─ V151_CASE_REPAIR_SPEC_zh.md
├─ V151_REPAIR_RECORDS_zh.md
├─ validation_report.json
├─ public/
│  ├─ tasks_zh.jsonl
│  └─ applicability_cases_zh.jsonl
├─ private/
│  ├─ applicability_gold.jsonl
│  ├─ decision_state_spec.json
│  ├─ evidence_node_omissions.jsonl
│  ├─ gold.jsonl
│  ├─ multi_hardening_manifest.jsonl
│  ├─ search_necessity.jsonl
│  ├─ task_assets.jsonl
│  └─ v151_case_repair_records.jsonl
└─ models/SWOR-Rxxx/
   ├─ base_ir.json
   ├─ patched_ir.json
   └─ solve_result.json
```

## 6. 本轮关键修复

- 逐题删除显式“须遵守/查询某法规”等搜索触发提示；
- 将法律结论式 C1/C2 描述改为可观察事实，并清除依赖“历史描述冲突作废”的兜底；
- 将法规后果与题内候选行动的本地能力映射分开表达；
- 对 action meaning 与 case 对象冲突的题目做最小泛化，并同步 IR 变量 meaning；
- 将旧版仅写“第 N 项（按出现顺序）”的公开 action meaning 确定性替换为 Base IR 中已有的明确业务语义，并逐题记录实际映射；
- 按公开 `accepted_units` 的换算因子重建目标值等价单位，修正旧 Gold 中把万元/万美元数值原样误写为元/美元的记录；
- 修正 R001 的 50 吨严格边界：只有年度累计质量严格大于 50 吨才进入相关分支；
- 重新生成 240 个最终 `prompt_zh`，同步全部 private Gold，并完整枚举 120 个 Base IR 与 120 个 patched IR。

## 7. 全量逐题修复索引

下表及后续逐题明细由三个互斥机器可读修复分片和构建器中的确定性 action-meaning 展开规则共同生成。`V151_REPAIR_RECORDS_zh.md` 与 `private/v151_case_repair_records.jsonl` 另保存包含官方来源和重求解结果的执行后记录。

{{REPAIR_TABLE}}

## 8. 可重建逐题修复明细

以下 120 条记录完整保存 source 精确替换、两个 case 的客观事实、schema meaning 修改、证据复核、Gold 处理和人工说明；README 与构建器读取同一组分片，并从 V1.4.4 Base IR 确定性展开遗留占位 action meaning，不另写一份不可重建的手工表。

{{REPAIR_DETAILS}}

## 9. 验收边界

`scripts/validate_searchworthyor_v151.py` 必须检查：

- 120/240 数量、C1/C2 一一配对、公开字段与 private 字段隔离；
- 三个修复分片恰好覆盖 R001–R120，README 与详细修复记录可重建；
- `problem_zh` 与 `prompt_zh` 能从 source、case facts 与 schema 确定性重建；
- source 与 case facts 不含显式搜索指令、适用性答案或旧的冲突兜底；
- Gold Patch 应用于 Base IR 后，按变量名与约束名规范化的结构等于 patched IR；
- 240 个 IR 独立完整枚举，行动集合和目标值与 Gold 一致；
- C1 全部 `RETAIN` 且 Patch 为空，C2 全部 `PATCH_CHANGES` 且最优行动改变；
- 官方证据节点、Patch slot、搜索资料与派生文件闭合；
- R001 回归结果为 Base 69、Patched 65，且 Patched 唯一选择 B+C+E、P=0。

通过编译或某个旧版 `validation_report.json` 不代表本版本通过；以当前 V1.5.1 验证器新生成的报告为准。

## 10. 构建与验证

```text
scripts/build_searchworthyor_v151.py
scripts/validate_searchworthyor_v151.py
```

构建器读取三个 `v151_case_repairs_*.json` 分片，拒绝遗漏、重复或非精确 source 替换，并把遗留的顺序占位 action meaning 展开为其公开—私有映射所指向的 Base IR 业务含义。首次构建拒绝覆盖已有目标；仅在协调修复后使用 `--update-existing` 对同一组确定性输出原位更新，不删除目录。

## 11. 版本限制

- `C1/C2` 后缀仍泄露状态，因此本版本不是盲适用性分类集；
- 官方证据以 publisher、URL 和 quote 保存，没有统一网页快照；
- 证据节点遗漏实验仍为 `NOT_RUN`，不能把结构绑定当作实证必要性；
- 本版本不声称完成新的模型基线实验。
