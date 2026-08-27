# SearchWorthyOR-v1.5.1 数据集说明

## 1. 版本定位

SearchWorthyOR-v1.5.1 以 V1.4.4 为只读输入，对 120 个 source task 的 240 个 C1/C2 case 做逐题语义修复。目标是让 Agent 只从题面读取客观业务事实，自主识别题外知识缺口，再用决策日有效的外部权威证据判断是否修改基础优化模型。

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

| 任务 | 结论 | L 类别 | 主差异轴 | source 精确修改 | schema meaning | Gold |
|---|---|---|---|---:|---:|---|
| SWOR-R001 | FIX | L1,L2,L4,L5,L6,L7 | boundary_facts | 4 | 7 | 修改 |
| SWOR-R002 | FIX | L1,L2,L4,L5,L6,L7 | boundary_facts | 2 | 0 | 修改 |
| SWOR-R003 | FIX | L1,L2,L4,L7 | boundary_facts | 2 | 0 | 保持 |
| SWOR-R004 | FIX | L1,L2,L4,L7 | boundary_facts | 2 | 0 | 保持 |
| SWOR-R005 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 4 | 保持 |
| SWOR-R006 | FIX | L1,L2,L5,L6,L7 | boundary_facts | 3 | 1 | 修改 |
| SWOR-R007 | FIX | L1,L2,L7 | regulated_subject | 2 | 0 | 保持 |
| SWOR-R008 | FIX | L1,L2,L6,L7 | regulated_subject | 3 | 0 | 修改 |
| SWOR-R009 | FIX | L1,L2,L4,L7 | boundary_facts | 2 | 6 | 保持 |
| SWOR-R010 | FIX | L2,L3,L5 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R011 | FIX | L1,L2,L4,L7 | jurisdiction | 3 | 2 | 保持 |
| SWOR-R012 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 7 | 保持 |
| SWOR-R013 | FIX | L1,L2,L4,L5,L7 | regulated_subject | 2 | 0 | 保持 |
| SWOR-R014 | FIX | L1,L2,L3,L5 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R015 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 7 | 保持 |
| SWOR-R016 | FIX | L1,L2,L3,L5,L6,L7 | boundary_facts | 3 | 3 | 修改 |
| SWOR-R017 | FIX | L1,L2,L7 | boundary_facts | 2 | 0 | 保持 |
| SWOR-R018 | FIX | L1,L2,L4,L5,L6,L7 | regulated_subject | 3 | 0 | 修改 |
| SWOR-R019 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R020 | FIX | L1,L2,L3,L4,L5,L6,L7 | regulated_subject | 3 | 8 | 修改 |
| SWOR-R021 | FIX | L1,L2,L3,L4,L5,L6,L7 | regulated_subject | 3 | 5 | 修改 |
| SWOR-R022 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 8 | 保持 |
| SWOR-R023 | FIX | L1,L2,L3,L4,L5,L7 | regulated_subject | 4 | 8 | 保持 |
| SWOR-R024 | FIX | L1,L2,L3,L4,L5,L6,L7 | regulated_subject | 4 | 7 | 修改 |
| SWOR-R025 | FIX | L1,L2,L3,L4,L5,L6,L7 | boundary_facts | 3 | 8 | 修改 |
| SWOR-R026 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R027 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 16 | 保持 |
| SWOR-R028 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R029 | FIX | L1,L2,L4,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R030 | FIX | L1,L2,L4,L7 | boundary_facts | 2 | 6 | 保持 |
| SWOR-R031 | FIX | L1,L2,L4,L7 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R032 | FIX | L1,L2,L4,L5,L6,L7 | regulated_subject | 4 | 8 | 修改 |
| SWOR-R033 | FIX | L1,L2,L4,L7 | boundary_facts | 5 | 16 | 保持 |
| SWOR-R034 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 8 | 保持 |
| SWOR-R035 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 8 | 保持 |
| SWOR-R036 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R037 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 7 | 保持 |
| SWOR-R038 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 4 | 6 | 保持 |
| SWOR-R039 | FIX | L1,L2,L3,L4,L5,L7 | regulated_subject | 5 | 7 | 保持 |
| SWOR-R040 | FIX | L1,L2,L4,L5,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R041 | FIX | L1,L2,L3,L7 | boundary_facts | 2 | 0 | 保持 |
| SWOR-R042 | FIX | L1,L2,L3,L4,L7 | boundary_facts | 2 | 15 | 保持 |
| SWOR-R043 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 5 | 保持 |
| SWOR-R044 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 5 | 4 | 保持 |
| SWOR-R045 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R046 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 3 | 0 | 保持 |
| SWOR-R047 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 5 | 10 | 保持 |
| SWOR-R048 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 5 | 12 | 保持 |
| SWOR-R049 | FIX | L1,L2,L3,L7 | regulated_subject | 3 | 0 | 保持 |
| SWOR-R050 | FIX | L1,L2,L3,L7 | boundary_facts | 3 | 0 | 保持 |
| SWOR-R051 | FIX | L1,L2,L5,L7 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R052 | FIX | L2,L7 | boundary_facts | 2 | 12 | 保持 |
| SWOR-R053 | FIX | L2,L7 | decision_date | 2 | 0 | 保持 |
| SWOR-R054 | FIX | L2,L7 | boundary_facts | 2 | 6 | 保持 |
| SWOR-R055 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 4 | 8 | 保持 |
| SWOR-R056 | FIX | L2,L5,L7 | boundary_facts | 4 | 6 | 保持 |
| SWOR-R057 | FIX | L1,L2,L7 | regulated_subject | 6 | 5 | 保持 |
| SWOR-R058 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 4 | 15 | 保持 |
| SWOR-R059 | FIX | L1,L2,L7 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R060 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 5 | 8 | 保持 |
| SWOR-R061 | FIX | L2,L7 | boundary_facts | 4 | 4 | 保持 |
| SWOR-R062 | FIX | L2 | boundary_facts | 2 | 8 | 保持 |
| SWOR-R063 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 5 | 10 | 保持 |
| SWOR-R064 | FIX | L1,L2,L5,L7 | boundary_facts | 4 | 6 | 保持 |
| SWOR-R065 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 5 | 12 | 保持 |
| SWOR-R066 | FIX | L1,L2,L7 | boundary_facts | 4 | 6 | 保持 |
| SWOR-R067 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 10 | 保持 |
| SWOR-R068 | FIX | L1,L2,L7 | regulated_subject | 2 | 2 | 保持 |
| SWOR-R069 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 2 | 保持 |
| SWOR-R070 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 4 | 保持 |
| SWOR-R071 | FIX | L2,L5 | boundary_facts | 4 | 16 | 保持 |
| SWOR-R072 | FIX | L1,L2,L4,L5,L7 | boundary_facts | 4 | 12 | 保持 |
| SWOR-R073 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 5 | 8 | 保持 |
| SWOR-R074 | FIX | L2,L7 | boundary_facts | 2 | 0 | 保持 |
| SWOR-R075 | FIX | L1,L2,L7 | regulated_subject | 2 | 0 | 保持 |
| SWOR-R076 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 6 | 4 | 保持 |
| SWOR-R077 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 9 | 保持 |
| SWOR-R078 | FIX | L1,L2,L7 | regulated_subject | 3 | 0 | 保持 |
| SWOR-R079 | FIX | L1,L2,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R080 | FIX | L1,L2,L7 | regulated_subject | 5 | 3 | 保持 |
| SWOR-R081 | FIX | L1,L2,L5,L6,L7 | boundary_facts | 2 | 0 | 修改 |
| SWOR-R082 | FIX | L1,L2,L5,L7 | boundary_facts | 4 | 0 | 保持 |
| SWOR-R083 | FIX | L1,L2,L5,L7 | regulated_subject | 4 | 0 | 保持 |
| SWOR-R084 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 8 | 保持 |
| SWOR-R085 | FIX | L2,L3,L5,L7 | jurisdiction | 3 | 10 | 保持 |
| SWOR-R086 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 4 | 4 | 保持 |
| SWOR-R087 | FIX | L1,L2,L5,L7 | decision_date | 4 | 0 | 保持 |
| SWOR-R088 | FIX | L2,L7 | jurisdiction | 3 | 0 | 保持 |
| SWOR-R089 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 5 | 4 | 保持 |
| SWOR-R090 | FIX | L2,L5,L7 | jurisdiction | 2 | 0 | 保持 |
| SWOR-R091 | FIX | L1,L2,L5,L7 | boundary_facts | 4 | 0 | 保持 |
| SWOR-R092 | FIX | L1,L2,L4,L7 | boundary_facts | 4 | 6 | 保持 |
| SWOR-R093 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 3 | 4 | 保持 |
| SWOR-R094 | FIX | L2,L3,L5,L7 | jurisdiction | 3 | 8 | 保持 |
| SWOR-R095 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 8 | 保持 |
| SWOR-R096 | FIX | L2,L4,L5,L6,L7 | regulated_subject | 2 | 0 | 修改 |
| SWOR-R097 | FIX | L1,L2,L5,L7 | regulated_subject | 4 | 0 | 保持 |
| SWOR-R098 | FIX | L2,L5,L7 | jurisdiction | 2 | 0 | 保持 |
| SWOR-R099 | FIX | L1,L2,L4,L5,L7 | boundary_facts | 5 | 4 | 保持 |
| SWOR-R100 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 3 | 4 | 保持 |
| SWOR-R101 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 5 | 8 | 保持 |
| SWOR-R102 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 6 | 保持 |
| SWOR-R103 | FIX | L1,L2,L3,L4,L6,L7 | boundary_facts | 3 | 7 | 修改 |
| SWOR-R104 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 3 | 6 | 保持 |
| SWOR-R105 | FIX | L1,L2,L3,L4,L7 | regulated_subject | 4 | 7 | 保持 |
| SWOR-R106 | FIX | L1,L2,L3,L4,L5,L7 | regulated_subject | 5 | 8 | 保持 |
| SWOR-R107 | FIX | L1,L2,L4,L7 | boundary_facts | 4 | 4 | 保持 |
| SWOR-R108 | FIX | L1,L2,L3,L4,L5,L7 | regulated_subject | 5 | 8 | 保持 |
| SWOR-R109 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 6 | 8 | 保持 |
| SWOR-R110 | FIX | L1,L2,L3,L4,L5,L7 | jurisdiction | 5 | 10 | 保持 |
| SWOR-R111 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 3 | 8 | 保持 |
| SWOR-R112 | FIX | L1,L2,L4,L5,L6,L7 | boundary_facts | 3 | 4 | 修改 |
| SWOR-R113 | FIX | L1,L2,L3,L5,L7 | regulated_subject | 4 | 4 | 保持 |
| SWOR-R114 | FIX | L1,L2,L3,L4,L5,L7 | boundary_facts | 4 | 4 | 保持 |
| SWOR-R115 | FIX | L1,L2,L3,L4,L5,L7 | regulated_subject | 4 | 4 | 保持 |
| SWOR-R116 | FIX | L1,L2,L4,L5,L7 | regulated_subject | 3 | 4 | 保持 |
| SWOR-R117 | FIX | L1,L2,L4,L5,L6,L7 | regulated_subject | 3 | 0 | 修改 |
| SWOR-R118 | FIX | L1,L2,L3,L5,L7 | boundary_facts | 5 | 8 | 保持 |
| SWOR-R119 | FIX | L1,L2,L3,L4,L5,L7 | regulated_subject | 4 | 8 | 保持 |
| SWOR-R120 | FIX | L1,L2,L3,L4,L5,L7 | jurisdiction | 5 | 9 | 保持 |

## 8. 可重建逐题修复明细

以下 120 条记录完整保存 source 精确替换、两个 case 的客观事实、schema meaning 修改、证据复核、Gold 处理和人工说明；README 与构建器读取同一组分片，并从 V1.4.4 Base IR 确定性展开遗留占位 action meaning，不另写一份不可重建的手工表。

### SWOR-R001

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L6, L7。
- 保持：保留2026-01-02、同一进口人、六批重量与价值、三选一结构、action ID、P的8点成本和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "批次A为CN 3105 60 00磷钾肥料，B为CN 7202 30 00硅锰铁，C为CN 7202 50 00硅铬铁，D为CN 7202 70 00钼铁，E为CN 7202 80 00钨铁及硅钨铁，F为CN 7204 10 00铸铁废碎料；该主体2026年的候选组合仅由这六批构成。", "decision_date": "2026-01-02", "jurisdiction": "欧盟CBAM海关领域", "regulated_subject": "在欧盟设立并以同一进口人名义安排2026年度进口的企业"}`
- C2：`{"boundary_facts": "批次A为CN 2523 10 00水泥熟料，B为CN 2523 21 00白色硅酸盐水泥，C为CN 2523 29 00其他硅酸盐水泥，D为CN 2523 30 00矾土水泥，E为CN 2523 90 00其他水硬性水泥，F为CN 2814 20 00氨水；该主体2026年的候选组合仅由这六批构成。", "decision_date": "2026-01-02", "jurisdiction": "欧盟CBAM海关领域", "regulated_subject": "在欧盟设立并以同一进口人名义安排2026年度进口的企业"}`
- C1 不适用原因：C1六个CN编码均位于Annex I明确列出的例外或范围之外，年度质量门槛不约束这些批次，故保留Base IR与基础解。
- 题内行动映射：P提供账户、记录、申报和凭证操作能力并固定消耗8点；批次商品属性只由case facts给出，P何时进入组合由外部边界与年度总质量共同决定。
- source 精确替换：
  - 旧：`六批货物均由同一进口主体报关，依次为：20吨钢材A，商业价值24点；18吨铝材B，23点；17吨水泥C，22点；16吨肥料D，21点；15吨钢制紧固件E，20点；14吨铝型材F，19点。`
  - 新：`六批货物均由同一进口主体报关；批次A至F的净重和商业价值依次为20吨、24点，18吨、23点，17吨、22点，16吨、21点，15吨、20点和14吨、19点；各批次商品名称和八位CN编码由本case事实给出。`
  - 旧：`公司还可把所选组合切换到年度集中进口运营模式P，使用该模式会使组合净价值减少8点。`
  - 新：`年度进口运营方案P提供监管账户办理、年度记录保存、年度申报以及凭证购买和交回的执行能力，启用P会使组合净价值减少8点。`
  - 旧：`六批货物均属于欧盟碳边境调节机制覆盖的商品，不涉及电力、氢、原产地豁免或退运情形。`
  - 新：``
  - 旧：`进口组合须遵守决策日有效的欧盟碳边境调节机制规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r001_a01": "选择20吨批次A", "swor_r001_a02": "选择18吨批次B", "swor_r001_a03": "选择17吨批次C", "swor_r001_a04": "选择16吨批次D", "swor_r001_a05": "选择15吨批次E", "swor_r001_a06": "选择14吨批次F", "swor_r001_a07": "启用年度进口运营方案P"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"official_evidence": [{"information_responsibility": "确认单一进口人每个日历年的严格大于50吨边界。", "node_id": "E1", "omission_effect": "无法确定annual_mass_branch的严格阈值。", "publisher": "European Commission, Directorate-General for Taxation and Customs Union", "quote": "EU importers who import more than the single mass-based threshold of 50 tonnes of CBAM goods into the EU", "role": "threshold", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["annual_mass_branch"], "supported_patch_slots": ["annual_mass_branch"], "url": "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-definitive-regime_en"}, {"information_responsibility": "确认C2批次A的CN 2523 10 00在Annex I水泥表列示。", "node_id": "E2", "omission_effect": "无法确认C2批次A属于Annex I列示商品。", "publisher": "European Union / EUR-Lex", "quote": "2523 10 00 – Cement clinkers", "role": "applicability", "source_node_id": "E2", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C2批次B的CN 2523 21 00在Annex I水泥表列示。", "node_id": "E3", "omission_effect": "无法确认C2批次B属于Annex I列示商品。", "publisher": "European Union / EUR-Lex", "quote": "2523 21 00 – White Portland cement, whether or not artificially coloured", "role": "applicability", "source_node_id": "E3", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C2批次C的CN 2523 29 00在Annex I水泥表列示。", "node_id": "E4", "omission_effect": "无法确认C2批次C属于Annex I列示商品。", "publisher": "European Union / EUR-Lex", "quote": "2523 29 00 – Other Portland cement", "role": "applicability", "source_node_id": "E4", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C2批次D的CN 2523 30 00在Annex I水泥表列示。", "node_id": "E5", "omission_effect": "无法确认C2批次D属于Annex I列示商品。", "publisher": "European Union / EUR-Lex", "quote": "2523 30 00 – Aluminous cement", "role": "applicability", "source_node_id": "E5", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C2批次E的CN 2523 90 00在Annex I水泥表列示。", "node_id": "E6", "omission_effect": "无法确认C2批次E属于Annex I列示商品。", "publisher": "European Union / EUR-Lex", "quote": "2523 90 00 – Other hydraulic cements", "role": "applicability", "source_node_id": "E6", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C2批次F的CN 2814氨品目在Annex I肥料表列示。", "node_id": "E7", "omission_effect": "无法确认C2批次F属于Annex I列示商品。", "publisher": "European Union / EUR-Lex", "quote": "2814 – Ammonia, anhydrous or in aqueous solution", "role": "applicability", "source_node_id": "E7", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C1批次A的CN 3105 60 00是Annex I肥料表的明列例外。", "node_id": "E8", "omission_effect": "无法确认C1批次A处于Annex I列示例外。", "publisher": "European Union / EUR-Lex", "quote": "Except: 3105 60 00 – Mineral or chemical fertilisers containing the two fertilising elements phosphorus and potassium", "role": "applicability", "source_node_id": "E8", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}, {"information_responsibility": "确认C1批次B至F的CN 7202 30/50/70/80和7204均在Annex I钢铁表的Except清单中。", "node_id": "E9", "omission_effect": "无法确认C1批次B至F处于Annex I列示例外。", "publisher": "European Union / EUR-Lex", "quote": "72 – Iron and steel Except: 7202 2 – Ferro-silicon 7202 30 00 – Ferro-silico-manganese 7202 50 00 – Ferro-silico-chromium 7202 70 00 – Ferro-molybdenum 7202 80 00 – Ferro-tungsten and ferro-silico-tungsten 7202 91 00 – Ferro-titanium and ferro-silico-titanium 7202 92 00 – Ferro-vanadium 7202 93 00 – Ferro-niobium 7202 99 – Other: 7202 99 10 – Ferro-phosphorus 7202 99 30 – Ferro-silico-magnesium 7202 99 80 – Other 7204 – Ferrous waste and scrap; remelting scrap ingots and steel", "role": "applicability", "source_node_id": "E9", "support_target_type": "applicability_gate", "support_targets": ["covered_cn_codes"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}], "patch_element": {"after": {"coefficients": {"lot_a": 20, "lot_b": 18, "lot_c": 17, "lot_d": 16, "lot_e": 15, "lot_f": 14, "trade_support_p": -5}, "meaning": "同一进口人同一日历年所选CBAM货物总净重超过50吨时，运营方案P提供本题所列执行能力", "name": "annual_mass_branch", "rhs": 50, "sense": "<="}, "name": "annual_mass_branch", "op": "add_constraint"}, "patched_objective": 65, "patched_optimal_action_set": [{"lot_a": 0, "lot_b": 1, "lot_c": 1, "lot_d": 0, "lot_e": 1, "lot_f": 0, "trade_support_p": 0}], "reason": "V1.4.4把等于50吨也当作进入门槛，且用-51P、rhs=49；官方页面明确为more than 50 tonnes。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "European Commission, Directorate-General for Taxation and Customs Union", "url": "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-definitive-regime_en"}, {"publisher": "European Union / EUR-Lex", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R0956-20251020"}], "notes": "欧委会页面使用more than 50 tonnes，确认严格大于50吨；EUR-Lex Annex I按CN编码确定商品范围。"}`
- 复核说明：固定阈值等号回归题；C1/C2只改变CN编码，未改重量、价值、日期或行动结构。

### SWOR-R002

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L6, L7。
- 保持：保留日期、路线、四个接收端、1至3个接收端约束、成本、action ID和最小化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "当次列车货物清单仅列普通机械零件、纸制品和食品，均使用普通商业运单；运行事件日志为零，三个地方调度单位没有该列车的事故派遣记录。", "decision_date": "2026-08-02", "jurisdiction": "美国铁路运输", "regulated_subject": "运营该线路并维护电子列车编组信息的美国一级铁路公司"}`
- C2：`{"boundary_facts": "电子编组清单列有多票带UN编号和危险类别的材料；列车依次经过三地，消防、急救和警务调度均由当地政府授权并保持路线事件响应值班。", "decision_date": "2026-08-02", "jurisdiction": "美国铁路运输", "regulated_subject": "运营该线路并维护电子列车编组信息的美国一级铁路公司"}`
- C1 不适用原因：C1列车未运输需要危险材料运输单据的货物，也没有事故、释放或疑似释放事件，三项外部接收约束不进入本case模型。
- 题内行动映射：消防、急救和警务接收端分别把编组信息送达对应政府调度单位；铁路内部控制室只提供公司内部接收能力。
- source 精确替换：
  - 旧：`五大湖一级铁路公司为1趟载运危险品并依次经过海湾县、松林县和河口市的列车选择电子编组信息接收端。`
  - 新：`五大湖一级铁路公司为1趟依次经过海湾县、松林县和河口市的列车选择电子编组信息接收端。`
  - 旧：`分发安排还须按适用于该辖区、主体和业务的现行外部要求定案。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "千美元", "value": 1.0}, {"unit": "美元", "value": 1000.0}], "canonical_unit": "千美元", "canonical_value": 1.0}, "old": {"accepted_equivalents": [{"unit": "千美元", "value": 1.0}, {"unit": "美元", "value": 1.0}], "canonical_unit": "千美元", "canonical_value": 1.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "US Pipeline and Hazardous Materials Safety Administration", "url": "https://www.govinfo.gov/content/pkg/FR-2024-06-24/pdf/2024-13474.pdf"}, {"publisher": "U.S. Pipeline and Hazardous Materials Safety Administration", "url": "https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2025-04/PHMSA%20Notice%20of%20Enforcement%20Discretion%20-%20Real%20Time%20Train%20Consist%20Information.pdf"}], "notes": "已复核V1.4.4保存的PHMSA发布者、URL和quote；补入临时执法裁量于2026-06-24届满的官方原句，确认2026-08-02决策日不再处于该临时窗口。", "official_evidence_node_overrides": [{"information_responsibility": "确认Class I铁路临时执法裁量在本题2026-08-02决策日前已经届满。", "node_id": "E2", "omission_effect": "缺少该节点时，无法排除决策日仍处于临时不执法窗口的可能，三项接收端Patch的时点适用性不闭合。", "publisher": "U.S. Pipeline and Hazardous Materials Safety Administration", "quote": "This Notice of Enforcement Discretion expires June 24, 2026.", "role": "effective_date", "source_node_id": "E2", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2025-04/PHMSA%20Notice%20of%20Enforcement%20Discretion%20-%20Real%20Time%20Train%20Consist%20Information.pdf"}]}`
- 复核说明：删除载运危险品的共通结论，让货物清单产生C1/C2差异；补齐临时执法裁量的届满日期；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R003

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留五名员工、四个HSA名额、两种福利、全部价值、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "五人均未满65岁、均以本人身份申报，且仅持有所列计划或HRA。A的交易所外个人铜级计划与交易所内版本相同；B的SHOP自付合同写明个人年度免赔额2000美元、年度最高自付额8000美元；C和D的ICHRA都只报销保费；E参加美洲印第安人铜级费用分担减免变体，并在此前三个月接受过IHS服务。", "decision_date": "2026-02-02", "jurisdiction": "美国联邦税务", "regulated_subject": "为五名员工安排2026年度福利的美国雇主"}`
- C2：`{"boundary_facts": "五人均未满65岁、均以本人身份申报，且仅持有所列计划或HRA。A的交易所外个人铜级计划与交易所内版本相同；B的SHOP自付合同写明个人年度免赔额1500美元、年度最高自付额9000美元；C的ICHRA只报销保费；D的ICHRA报销保费和就医共付额；E参加美洲印第安人铜级费用分担减免变体，并在此前三个月接受过IHS服务。", "decision_date": "2026-02-02", "jurisdiction": "美国联邦税务", "regulated_subject": "为五名员工安排2026年度福利的美国雇主"}`
- C1 不适用原因：C1中B独立达到普通HDHP数值条件，D的ICHRA仅报销保费；两个Gold排除条件均不存在，保留Base IR。
- 题内行动映射：每名员工的HSA行动表示实际向其HSA缴款；对应现金行动表示支付应税现金，二者对同一员工互斥。
- source 精确替换：
  - 旧：`A购买了交易所以外销售的个人铜级计划，该计划与交易所内的一款计划完全相同；B参加小企业健康选择计划SHOP提供的铜级计划，且该计划不满足通常HDHP的免赔额和最高自付额限制；C通过只报销保费的ICHRA购买交易所个人铜级计划；D参加个人灾难性计划，其ICHRA同时报销保费和就医共付额；E参加面向美洲印第安人的铜级费用分担减免变体，并在此前三个月接受过IHS医疗服务。`
  - 新：`A至E的保险计划类别、免赔额与最高自付额记录、HRA报销项目和近期IHS服务记录由本case事实给出。`
  - 旧：`福利安排须遵守决策日有效的美国联邦HSA规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Internal Revenue Service", "url": "https://www.irs.gov/irb/2026-02_IRB"}], "notes": "已复核V1.4.4保存的IRS Q&A quote，覆盖SHOP、premium-only ICHRA、交易所外相同计划和IHS变体；同一IRS公告给出2026年个人普通HDHP最低免赔额1700美元、最高自付额8500美元。"}`
- 复核说明：把会变化的计划属性移到case facts；未改福利价值或名额。

### SWOR-R004

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留日期、N/R取值范围、回复先后、25日内部窗口、收益系数、action ID和目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "已完成的集群研究和复研均记录邻区系统影响为零，后续研究也没有新增影响记录；邻区运营商没有提交受影响系统请求，题列消息作为自愿的预案协调消息。", "decision_date": "2026-08-02", "jurisdiction": "美国跨区输电", "regulated_subject": "按委员会已接受并网资费管理项目的输电运营商"}`
- C2：`{"boundary_facts": "第0个工作日的研究记录标明一个潜在邻区系统影响，所列邻区运营商是当前资费流程中的受影响系统参与方。", "decision_date": "2026-08-02", "jurisdiction": "美国跨区输电", "regulated_subject": "按委员会已接受并网资费管理项目的输电运营商"}`
- C1 不适用原因：C1没有识别出潜在受影响系统，也没有邻区请求，10日通知和20日回复Patch没有作用对象。
- 题内行动映射：N是初始通知发送日，R是邻区书面回复日；两个整数行动直接表达两个外部时限作用的业务事件。
- source 精确替换：
  - 旧：`山谷输电运营商已在第0个工作日确认风场并网可能影响邻区电网，项目受委员会已接受并生效的并网资费管辖。`
  - 新：`山谷输电运营商为一个风场并网项目安排邻区协调消息，项目的研究结果和邻区参与状态由本case事实给出。`
  - 旧：`排程还须与决策日有效且适用于上述运营事实的外部规范相容。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "US Federal Energy Regulatory Commission", "url": "https://www.govinfo.gov/content/pkg/FR-2024-04-16/pdf/2024-06563.pdf"}], "notes": "已复核V1.4.4保存的FERC quote，支持首次识别潜在影响后的10日通知和通知后20日书面回复。"}`
- 复核说明：删除共通背景中的影响识别结论，保留内部25日窗口。

### SWOR-R005

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留240个车位、四个完整方案、车位数量与效用、action ID和单选最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "240个位置全部按车队调度台账分配给配送卡车和其他商用车辆，入口尺寸、地面标线和调度记录均为商用车专用；该车队设施不对公众开放，员工与访客使用另一座固定客车停车设施。", "decision_date": "2026-08-04", "jurisdiction": "美国商业园区", "regulated_subject": "为一栋商业建筑管理一座240位地面停车设施的运营方"}`
- C2：`{"boundary_facts": "240个位置供办公楼员工和访客的普通乘用车使用；该停车设施为单一新建设施，园区台账没有与其合并计数的其他设施。", "decision_date": "2026-08-04", "jurisdiction": "美国商业园区", "regulated_subject": "为一栋新建办公楼配置一座240位地面停车设施的业主"}`
- C1 不适用原因：C1全部位置属于卡车等商用车的车队专用空间，乘用车停车位数量规则不修改题列设施包，故采用Base IR。
- 题内行动映射：方案A至D分别提供0、7、7、7个无障碍车位，并提供0、1、2、3个厢式车位；所有数量均在候选方案内闭合。
- source 精确替换：
  - 旧：`该设施服务普通员工与访客，不是住宅、医疗门诊或代客泊车设施，也不是既有设施的局部改造；园区没有可与本设施合并计算的其他停车场。`
  - 新：`该设施的车辆用途、建筑状态和与园区其他停车设施的关系由本case事实给出。`
  - 旧：`配置须符合决策日适用于该新建商业设施的美国联邦无障碍设计标准。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r005_a01": "选择全部240个均为普通车位的方案A", "swor_r005_a02": "选择6个普通无障碍加1个厢式车无障碍的方案B", "swor_r005_a03": "选择5个普通无障碍加2个厢式车无障碍的方案C", "swor_r005_a04": "选择4个普通无障碍加3个厢式车无障碍的方案D"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of Justice", "url": "https://www.ada.gov/law-and-regs/design-standards/2010-stds/"}], "notes": "已复核DOJ 2010 ADA Standards的208.1例外、Table 208.2与每六个或不足六个至少一个van space的原文。", "official_evidence_node_overrides": [{"information_responsibility": "支持商用卡车专用停车位的208.1例外及公众可进入时的503装卸区条件。", "node_id": "E3", "omission_effect": "缺少该节点时，C1卡车专用且不对公众开放的设施不能从普通乘用车位数量规则中排除，RETAIN判断不闭合。", "publisher": "U.S. Department of Justice", "quote": "EXCEPTION: Parking spaces used exclusively for buses, trucks, other delivery vehicles, law enforcement vehicles, or vehicular impound shall not be required to comply with 208 provided that lots accessed by the public are provided with a passenger loading zone complying with 503.", "role": "applicability_gate", "source_node_id": "E3", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ada.gov/law-and-regs/design-standards/2010-stds/"}]}`
- 复核说明：用正面车辆用途替代排除项列表，并补明设施不对公众开放及208.1商用车专用例外；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R006

- 结论：`FIX`；问题类型：L1, L2, L5, L6, L7。
- 保持：保留日期、五个模块、成本、至少二项、数据总线和岗位互斥、action ID及最小化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "公司另有一套固定控制系统持续运行，已提供实时监控、历史数据记录、消息与报警回溯，以及按管线复杂度、运行方式和原油特性设计的泄漏检测；题列五项均为附加分析模块。", "decision_date": "2026-08-02", "jurisdiction": "加拿大联邦陆上管道领域", "regulated_subject": "运营复杂原油管线并采购可选分析模块的加拿大管道公司"}`
- C2：`{"boundary_facts": "该资产输送原油，题列模块构成本期唯一控制系统；实时监控、历史记录、报警回溯和按复杂度、运行方式及产品特性设计的泄漏检测均由相应候选模块提供。", "decision_date": "2026-08-02", "jurisdiction": "加拿大联邦陆上管道领域", "regulated_subject": "为复杂原油管线配置唯一控制系统的加拿大管道公司"}`
- C1 不适用原因：C1的固定外部系统已经提供全部四项能力，题列可选分析模块不承担这些功能，Gold的四个必选约束不进入决策模型。
- 题内行动映射：前四个模块分别提供监控、历史数据、报警回溯和按管线特征设计的泄漏检测能力；普通人工巡线不提供这些控制系统能力。
- source 精确替换：
  - 旧：`北原管道公司为受加拿大联邦陆上管道条例约束的1条复杂原油管线选择控制系统模块。`
  - 新：`北原管道公司为一条管线选择本期控制系统模块；管线产品、复杂度和既有固定系统能力由本case事实给出。`
  - 旧：`符合CSA Z662并按该管线复杂度和所输原油设计的泄漏检测子系统`
  - 新：`按该管线复杂度、运行方式和所输产品特性设计的泄漏检测子系统`
  - 旧：`控制系统还须符合主管机关在相应决定或执行时点适用于该业务的现行要求。`
  - 新：``
- output_schema meaning 修改：`{"swor_r006_a04": "配置按管线复杂度、运行方式和所输产品特性设计的泄漏检测子系统"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "百万加元", "value": 5.0}, {"unit": "加元", "value": 5000000.0}], "canonical_unit": "百万加元", "canonical_value": 5.0}, "old": {"accepted_equivalents": [{"unit": "百万加元", "value": 5.0}, {"unit": "加元", "value": 5.0}], "canonical_unit": "百万加元", "canonical_value": 5.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Department of Justice Canada, Justice Laws Website", "url": "https://laws-lois.justice.gc.ca/eng/regulations/SOR-99-294/section-37.html"}], "notes": "已复核V1.4.4保存的section 37 quote，覆盖监控、历史记录、报警回溯与输油管线泄漏检测。"}`
- 复核说明：通过是否已有固定系统这一客观边界形成pair；移除题面和action meaning中对CSA Z662的直接点名；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R007

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留六只债券、发行人/地区/评级、融资价值、三选一、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "六只债券的发行人类型、发行地区和外部评级与题列一致；双方合同附件逐一列出六个ISIN，本次融资由私人交易对手提供。", "decision_date": "2026-08-04", "jurisdiction": "英国私人回购市场", "regulated_subject": "按双方合同清单开展自营回购且不参加英格兰银行操作的私人交易对手"}`
- C2：`{"boundary_facts": "六只债券的发行人类型、发行地区和外部评级与题列一致；参与者的英格兰银行结算账户处于开放状态，六个ISIN及发行人资料已上传至本次操作文件。", "decision_date": "2026-08-04", "jurisdiction": "英格兰银行英镑货币框架", "regulated_subject": "在英格兰银行操作中选择三只债券的在册SMF参与者"}`
- C1 不适用原因：C1不是SMF参与者且不在英格兰银行操作中融资，SMF B级抵押品范围不修改其私人合同清单。
- 题内行动映射：每个债券行动直接代表把该债券纳入本次三只抵押组合，融资价值由题面给定。
- source 精确替换：
  - 旧：`泰晤士流动性公司作为英格兰银行英镑货币框架参与者，需要从六只已完成结算准备的债券中恰好质押三只。`
  - 新：`泰晤士流动性公司需要从六只已完成结算准备的债券中恰好质押三只；交易对手和操作类型由本case事实给出。`
  - 旧：`质押选择须遵守决策日有效的英格兰银行英镑货币框架关于政府关联债务作为B级抵押品的资格规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Bank of England", "url": "https://www.bankofengland.co.uk/markets/market-notices/2026/june/collateral-eligibility-in-the-smf-11-june-2026"}], "notes": "已复核V1.4.4保存的BoE market notice quote，支持G10/澳大利亚地区、政府或政策银行及约AA-质量条件。"}`
- 复核说明：只移动参与者身份，债券属性完全保持。

### SWOR-R008

- 结论：`FIX`；问题类型：L1, L2, L6, L7。
- 保持：保留三种交易、四个时点、贡献与成本、各选一项、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "三类证券与四个付款交付时点均按题列合同执行；市政证券身份和大宗交易成交时写入的替代交收日保持不变。", "decision_date": "2026-08-05", "jurisdiction": "美国证券交易", "regulated_subject": "为自身账户交易、未注册为broker或dealer的自营投资机构"}`
- C2：`{"boundary_facts": "普通上市股票没有替代交收协议；市政证券身份和大宗交易成交时写入的替代交收日保持不变。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦broker-dealer交收领域", "regulated_subject": "代表客户订立一项证券买卖合同的注册broker-dealer"}`
- C1 不适用原因：C1主体不是broker或dealer且仅为自营账户订立合同，Gold中的普通上市股票T+1约束不作用于该主体。
- 题内行动映射：前三个行动选交易，后四个行动选付款交付日；大宗交易的替代时点由题内成交协议提供。
- source 精确替换：
  - 旧：`纽约州海岳经纪商须选择一项交易和一个付款交付时点。`
  - 新：`纽约州海岳机构须选择一项交易和一个付款交付时点；本次账户角色由本case事实给出。`
  - 旧：`市政证券属于题列排除类别；大宗交易的延后时点已在成交时明确约定；普通上市股票没有另行约定。`
  - 新：`一项候选交易为市政证券；大宗交易的延后时点由双方在成交时写入协议；普通上市股票交易没有另行时点协议。`
  - 旧：`安排须遵守决策日有效的美国联邦经纪商标准交收规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_element": {"after": {"coefficients": {"listed_stock": 1, "next_business_day": -1, "same_day": -1}, "meaning": "普通上市股票须在成交当日或下一营业日完成交收", "name": "listed_stock_requires_t1", "rhs": 0, "sense": "<="}, "name": "listed_stock_requires_t1", "op": "add_constraint"}, "reason": "17 CFR 240.15c6-1要求不晚于成交后第一营业日，允许成交当日交收；旧Patch错误地强制恰好T+1。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Securities and Exchange Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-17.xml?section=240.15c6-1"}], "notes": "已复核V1.4.4保存的17 CFR 240.15c6-1 quote，覆盖broker/dealer主体、T+1、列举证券及成交时明示协议。"}`
- 复核说明：把“排除类别”改为客观证券类型，并修正普通上市股票不得晚于T+1而非必须恰好T+1的Gold边界。

### SWOR-R009

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留三个名额、六名候选、预计获益、三选一、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A为3岁且有反复血管闭塞危象的镰状细胞病患者；B为4岁输血依赖型β地中海贫血患者；C为11岁且有反复血管闭塞危象的镰状细胞病患者；D为13岁且有反复血管闭塞危象的镰状细胞病患者；E为2岁输血依赖型β地中海贫血患者；F为8岁输血依赖型β地中海贫血患者。六人均已完成预处理、细胞采集和安全性准备。", "decision_date": "2026-08-04", "jurisdiction": "美国FDA批准使用领域", "regulated_subject": "分配Casgevy名额的美国儿童细胞治疗中心"}`
- C2：`{"boundary_facts": "A为3岁且有反复血管闭塞危象的镰状细胞病患者；B为4岁输血依赖型β地中海贫血患者；C为11岁但没有反复血管闭塞危象的镰状细胞病患者；D为13岁且有反复血管闭塞危象的镰状细胞病患者；E为1岁输血依赖型β地中海贫血患者；F为8岁非输血依赖型β地中海贫血患者。六人均已完成预处理、细胞采集和安全性准备。", "decision_date": "2026-08-04", "jurisdiction": "美国FDA批准使用领域", "regulated_subject": "分配Casgevy名额的美国儿童细胞治疗中心"}`
- C1 不适用原因：C1六名患者均达到两岁并具有相应疾病记录，C、E、F的三个Gold排除约束均不成立，使用Base IR。
- 题内行动映射：六个行动分别把对应患者放入三个锁定名额之一；题面不增加任何治疗前置包。
- source 精确替换：
  - 旧：`患者A为3岁、有反复血管闭塞危象的镰状细胞病患者，预计获益7点；患者B为4岁输血依赖型β地中海贫血患者，预计获益8点；患者C为11岁镰状细胞病患者，但没有反复血管闭塞危象，预计获益13点；患者D为13岁、有反复血管闭塞危象的镰状细胞病患者，预计获益9点；患者E为1岁输血依赖型β地中海贫血患者，预计获益12点；患者F为8岁β地中海贫血患者，但不依赖输血，预计获益11点。`
  - 新：`患者A至F的年龄、诊断、血管闭塞危象和输血依赖记录由本case事实给出，预计获益依次为7、8、13、9、12、11点。`
  - 旧：`名额分配须遵守决策日有效的美国FDA对Casgevy适应症的批准范围。`
  - 新：``
- output_schema meaning 修改：`{"swor_r009_a01": "为候选患者A安排Casgevy", "swor_r009_a02": "为候选患者B安排Casgevy", "swor_r009_a03": "为候选患者C安排Casgevy", "swor_r009_a04": "为候选患者D安排Casgevy", "swor_r009_a05": "为候选患者E安排Casgevy", "swor_r009_a06": "为候选患者F安排Casgevy"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration", "url": "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapy-young-children-sickle-cell-disease"}], "notes": "已复核V1.4.4保存的FDA quote，支持2岁及以上、反复VOC的SCD或TDT两个客观分支。"}`
- 复核说明：行动含义泛化，避免C1/C2年龄与疾病记录冲突。

### SWOR-R010

- 结论：`FIX`；问题类型：L2, L3, L5。
- 保持：保留日期、两次就诊、六条申报行、三选一、预计追回评分、action ID和目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B两次就诊各有一条固定且不在三条重提决策中的90480主程序行；该行与对应90481属于同一患者、同一服务日期和同一机构。", "decision_date": "2026-08-04", "jurisdiction": "美国Medicare机构门诊申报", "regulated_subject": "重提两次2026年7月门诊接种记录的医院结算组"}`
- C2：`{"boundary_facts": "A、B两次就诊的可提交代码行仅为题列六项；每次就诊均没有决策外的非附加主程序行。", "decision_date": "2026-08-04", "jurisdiction": "美国Medicare机构门诊申报", "regulated_subject": "重提两次2026年7月门诊接种记录的医院结算组"}`
- C1 不适用原因：C1每次就诊已有固定90480主程序行，选择90481无需再选择题列G0008/G0009，两个Gold蕴含约束不修改模型。
- 题内行动映射：G0008和G0009分别是A、B就诊中可选的非附加配对代码行；固定90480是否已存在由case facts给出。
- source 精确替换：
  - 旧：`同一次就诊记录内的申报行属于同一患者、同一服务日期和同一机构；两次就诊均已满足承保、医疗必要性和病历材料要求。`
  - 新：`同一次就诊记录内的申报行属于同一患者、同一服务日期和同一机构；若选择G0008或G0009，其申报行可与对应就诊的90481组成同次就诊代码行组合；两次就诊均已满足承保、医疗必要性和病历材料要求。`
  - 旧：`申报方案须遵守决策日有效的美国CMS Medicare门诊整合代码编辑规则。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r010_a01": "提交A就诊记录的HCPCS 90481申报行", "swor_r010_a02": "提交A就诊记录的HCPCS 90471申报行", "swor_r010_a03": "提交A就诊记录的HCPCS G0008申报行", "swor_r010_a04": "提交B就诊记录的HCPCS 90481申报行", "swor_r010_a05": "提交B就诊记录的HCPCS 90471申报行", "swor_r010_a06": "提交B就诊记录的HCPCS G0009申报行"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Centers for Medicare & Medicaid Services", "url": "https://www.cms.gov/files/zip/i-oce-quarterly-data-files-v272-r0.zip"}, {"publisher": "Centers for Medicare & Medicaid Services", "url": "https://www.cms.gov/files/document/r13844cp.pdf"}], "notes": "已复核V1.4.4保存的I/OCE数据和CMS变更请求quote，覆盖90481配对及2026-07-01生效日。"}`
- 复核说明：仅补清题内代码行桥梁并删除显式规则提示；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R011

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留五个农林产品批次、价值、二选一、两种数据提交路线及其成本、action ID和最大化目标。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "两个入选批次直接运往摩洛哥境内买方；合作社为本次投放维护产地、地理定位和风险材料，并可使用题列两条内部数据提交路线。", "decision_date": "2027-08-02", "jurisdiction": "摩洛哥国内商品市场", "regulated_subject": "把自有农林产品投放摩洛哥市场的葡萄牙微型初级经营者"}`
- C2：`{"boundary_facts": "五个候选批次为合作社自行生产的可可豆、咖啡豆、大豆、天然橡胶和原木，两个入选批次进入欧盟市场；合作社于2023年设立，产地、地理定位和风险材料已经备齐。", "decision_date": "2027-08-02", "jurisdiction": "欧盟商品市场", "regulated_subject": "把自有可可豆、咖啡豆、大豆、天然橡胶和原木投放欧盟市场的葡萄牙微型初级经营者"}`
- C1 不适用原因：C1投放目的地不是欧盟市场，EUDR声明路线不约束该市场投放决策，使用Base IR。
- 题内行动映射：前五个行动决定投放批次；后两个行动是合作社现有系统可执行的两种数据提交路线，路线成本由题面直接计入。
- source 精确替换：
  - 旧：`欧盟初级农林产品投放。2027年8月2日，葡萄牙林海合作社从可可豆、咖啡豆、大豆、天然橡胶和原木五个自有生产批次中恰好选择两个投放欧盟市场，批次价值分别为20、18、16、15、14点。`
  - 新：`初级农林产品投放。2027年8月2日，葡萄牙林海合作社从可可豆、咖啡豆、大豆、天然橡胶和原木五个自有生产批次中恰好选择两个投放目标市场，批次价值分别为20、18、16、15、14点；目标市场由本case事实给出。`
  - 旧：`合作社于2023年设立，属于微型初级经营者，过去不受Regulation (EU) No 995/2010约束。五个批次均属于EUDR相关产品，产地信息、地理定位和风险材料均已准备完毕。`
  - 新：`合作社于2023年设立，属于微型初级经营者；五个批次的产地信息、地理定位和风险材料均已准备完毕。`
  - 旧：`投放方案须遵守决策日有效的欧盟无毁林产品规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r011_a06": "提交一次性简化数据声明", "swor_r011_a07": "提交完整尽职调查数据声明"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "European Union / EUR-Lex", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02023R1115-20251226"}], "notes": "已复核V1.4.4保存的EUR-Lex合并文本quote，覆盖微型或小型初级经营者的一次性简化声明及2027-06-30日期分支。"}`
- 复核说明：只把目标市场和欧盟边界移入case facts，保留产品与路线能力。

### SWOR-R012

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四批禽肉、批次价值、四种冷藏或入冻包、成本、物理温控能力、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B、C的包装均只写普通frozen且没有暗示由鲜品快速转冻的其他文字；A、B在初冷后50小时入冻，C在初冷后44小时入冻。D在入冻前已经冷却并完成包装，屠宰后3小时入冻。四批均在入冻后70小时内达到题列内部温度。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦检查禽肉生产", "regulated_subject": "官方场所安排一个待烹禽肉批次的冻结过程"}`
- C2：`{"boundary_facts": "A和C包装写有quick frozen，A在初冷后50小时入冻；C在初冷后44小时入冻且包装后等待温度高于36华氏度。B只写普通frozen且在初冷后50小时入冻。D为温包装禽肉并采用厂内冷冻机立即冷却流程，屠宰后3小时入冻。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦检查禽肉生产", "regulated_subject": "官方场所安排一个待烹禽肉批次的冻结过程"}`
- C1 不适用原因：C1的A、B、C均无快速冻结标签，D也不是温包装立即入冻流程；除共同的70小时降温事实外，Gold的48小时、等待温度和2小时约束均不加入。
- 题内行动映射：前四项选择批次；后三项分别是能把A/B提前并保冷、把C等待温度降至36°F以下、把D提前至1.5小时入冻的题内物理能力。
- source 精确替换：
  - 旧：`A标签使用“quick frozen”，计划在初次冷却后50小时进入冷冻机，价值120点；B标签只使用普通“frozen”，标签审核确认没有表示从鲜品快速转为冻品的其他词语，计划在初次冷却后50小时入冻，价值110点；C标签使用“quick frozen”，计划在初次冷却后44小时入冻，但包装后等待期间温度高于36华氏度，价值115点；D为拟通过厂内冷冻机立即冷却的温包装禽肉，计划在屠宰后3小时入冻，价值118点。`
  - 新：`A、B、C、D四批的价值分别为120、110、115、118点；标签措辞、初冷或屠宰至入冻的时间、等待温度和包装状态由本case事实给出。`
  - 旧：`四批均为受规则覆盖的待烹禽肉，不属于法规列明的例外产品，也没有书面个案搬运许可。`
  - 新：``
  - 旧：`排程必须遵守决策日有效的美国联邦待烹禽肉冻结规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r012_a01": "执行标注quick frozen且计划初冷后50小时入冻的禽肉批次A", "swor_r012_a02": "执行仅标注frozen且计划初冷后50小时入冻的禽肉批次B", "swor_r012_a03": "执行标注quick frozen、44小时入冻但延迟期间高于36华氏度的批次C", "swor_r012_a04": "执行屠宰后3小时进入直接冻结流程的温包装批次D", "swor_r012_a05": "为A或B启用46小时入冻并维持不高于36华氏度的加速冷藏包", "swor_r012_a06": "为C启用入冻前不高于36华氏度的冷藏包", "swor_r012_a07": "为D启用屠宰后1.5小时进入合格冷冻机的快速入冻包"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of Agriculture Food Safety and Inspection Service / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-9.xml"}], "notes": "已复核V1.4.4保存的9 CFR quote，分别覆盖quick frozen等标签的48小时与36°F条件、温包装禽肉2小时入冻条件及ready-to-cook定义。"}`
- 复核说明：标签和工艺状态移至case facts；未改动批次值和冷藏包效果；将7个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R013

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L7。
- 保持：保留十个原汁批次、体积、Brix、贡献、恰好100升、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "所有候选批次均为未发酵原汁，体积可相加；成品标签和广告只使用orange-flavored juice beverage名称，不使用pasteurized orange juice名称。", "decision_date": "2026-08-25", "jurisdiction": "美国食品市场", "regulated_subject": "调配100升橙味果汁饮料并仅以orange-flavored juice beverage名称销售的美国制造商"}`
- C2：`{"boundary_facts": "所有候选批次均为未发酵原汁，体积可相加；生产批记录没有水、甜味剂、浓缩调节成分或题列十批以外的其他原料。", "decision_date": "2026-08-25", "jurisdiction": "美国食品市场", "regulated_subject": "调配100升产品并以pasteurized orange juice名称销售的美国制造商"}`
- C1 不适用原因：C1产品不以巴氏杀菌橙汁身份名称销售，该身份标准的最低Brix和reticulata比例不修改配料模型。
- 题内行动映射：十个行动各自表示把对应不可拆分批次加入100升配方，题面的体积、Brix和品种属性直接进入加权配料计算。
- source 精确替换：
  - 旧：`巴氏杀菌橙汁配料。2026年8月25日，佛罗里达州朝湾果汁厂要从十个不可拆分的原汁批次中选料，配成恰好100升并以巴氏杀菌橙汁名称在美国销售。`
  - 新：`橙味产品配料。2026年8月25日，佛罗里达州朝湾果汁厂要从十个不可拆分的原汁批次中选料，配成恰好100升产品；产品销售名称由本case事实给出。十批原汁在题内计量精度下密度相同，成品°Brix按所选批次体积加权平均计算。`
  - 旧：`配方须遵守生产日有效的美国FDA巴氏杀菌橙汁身份标准。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration", "url": "https://www.fda.gov/about-fda/economic-impact-analyses-fda-regulations/food-standards-identity-modernization-pasteurized-orange-juice-final-rule"}, {"publisher": "U.S. Food and Drug Administration / Federal Register", "url": "https://www.govinfo.gov/content/pkg/FR-2026-07-20/pdf/2026-14573.pdf"}], "notes": "已复核V1.4.4保存的FDA quote，支持巴氏杀菌橙汁最低10.0°Brix和Citrus reticulata或其杂交种最高15%体积；补入最终规则生效日原句，确认其在2026-08-25决策日前生效。", "official_evidence_node_overrides": [{"information_responsibility": "确认巴氏杀菌橙汁身份标准最终规则于2026-08-19生效并进入合规期。", "node_id": "E2", "omission_effect": "缺少E2时，无法确认最低Brix和reticulata比例规则在本题2026-08-25决策日已经生效。", "publisher": "U.S. Food and Drug Administration / Federal Register", "quote": "This rule is effective August 19, 2026. This compliance date is August 19, 2026.", "role": "effective_date", "source_node_id": "E2", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.govinfo.gov/content/pkg/FR-2026-07-20/pdf/2026-14573.pdf"}]}`
- 复核说明：只把成品销售身份从共通source移入case facts。

### SWOR-R014

- 结论：`FIX`；问题类型：L1, L2, L3, L5。
- 保持：保留四种班组规模、四种设施包、贡献与成本、固定工厂、单一性别、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "厂内已有一组不在决策变量中的永久水冲式坐便设施；其可用数量在四种班组规模下均达到4个，员工在工作时段可随时使用。题列设施包仅为新增便利单元。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦一般工业场所", "regulated_subject": "选择一个单性别班组规模的固定制造场所"}`
- C2：`{"boundary_facts": "题列设施包是员工在本次生产时段可用的唯一水冲式坐便设施；员工人数由所选班组决定，工厂为固定场所且只有一个性别的员工。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦一般工业场所", "regulated_subject": "选择一个单性别班组规模和厕所包的固定制造场所"}`
- C1 不适用原因：C1已有固定厕所银行覆盖全部候选人数，Gold中班组规模对新增设施包数量的约束不修改模型。
- 题内行动映射：前四项选择员工人数档位，后四项新增1至4个水冲式坐便设施；case facts说明是否另有固定设施供给。
- source 精确替换：
  - 旧：`必须各选一项，以生产贡献减设施成本后的净效用最大。`
  - 新：`必须各选一项；所选设施包表示本次决策内新增的水冲式坐便设施数量，以生产贡献减设施成本后的净效用最大。`
  - 旧：`配置须遵守决策日有效的美国联邦一般工业卫生规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r014_a01": "启用14名员工的生产班组", "swor_r014_a02": "启用28名员工的生产班组", "swor_r014_a03": "启用48名员工的生产班组", "swor_r014_a04": "启用70名员工的生产班组", "swor_r014_a05": "配置1个水冲式坐便设施", "swor_r014_a06": "配置2个水冲式坐便设施", "swor_r014_a07": "配置3个水冲式坐便设施", "swor_r014_a08": "配置4个水冲式坐便设施"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "已复核V1.4.4保存的29 CFR quote，覆盖固定工作场所及Table J-1的1—15、16—35、36—55、56—80人数档位。"}`
- 复核说明：补足题内设施供给桥梁，未改变任何档位数值；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R015

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留三辆车、制动器与喇叭状态、三条路线贡献、四种维修服务、成本、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "三辆车只在同一封闭场地内运行，不进入公共道路或跨州运输；它们是轻型工具车。题列故障记录、匹配维修效果和其他部件状态保持不变。", "decision_date": "2026-08-05", "jurisdiction": "美国私人封闭工业场地", "regulated_subject": "在围栏封闭场地内选择轻型工具车和场内路线的工业运营方"}`
- C2：`{"boundary_facts": "三辆候选车均为执行公共道路跨州运输的商业机动车；题列故障记录在匹配维修前持续存在，匹配维修恢复对应部件，完整包恢复制动器和喇叭。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦跨州机动车运输", "regulated_subject": "选择商业机动车执行跨州路线并安排出车前维修的motor carrier"}`
- C1 不适用原因：C1车辆不是联邦商业机动车且行驶完全位于封闭场地，Gold的制动器与喇叭出车前维修约束不修改模型。
- 题内行动映射：前三项选定车辆与路线；后四项分别提供零维修、制动器修复、喇叭修复或两部件同时修复能力。
- source 精确替换：
  - 旧：`美国跨州商业机动车路线与出车前维修选择。2026年8月5日，岬岭承运人须选择一辆车执行路线并选择一个辅助维修服务。`
  - 新：`车辆路线与出车前维修选择。2026年8月5日，岬岭运营方须选择一辆车执行路线并选择一个辅助维修服务；车辆与路线的运营场景由本case事实给出。`
  - 旧：`其他法定部件均合格。`
  - 新：`其他检查清单部件没有故障记录。`
  - 旧：`方案须遵守决策日有效的美国联邦商业机动车部件状态规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r015_a01": "安排服务制动器已报告故障的车辆执行跨州路线A", "swor_r015_a02": "安排喇叭已报告故障的车辆执行跨州路线B", "swor_r015_a03": "安排所列部件均处于良好工作状态的车辆执行路线C", "swor_r015_a04": "不实施出车前维修", "swor_r015_a05": "出车前修复制动器并确认良好", "swor_r015_a06": "出车前修复喇叭并确认良好", "swor_r015_a07": "出车前实施完整部件维修包"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Motor Carrier Safety Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "已复核V1.4.4保存的49 CFR quote，支持商业机动车驾驶前服务制动器和喇叭处于良好工作状态。"}`
- 复核说明：只移动商业机动车主体边界；维修物理效果保持；将7个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R016

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L6, L7。
- 保持：保留STB裁定主体、驳回/延后/签发命令三项行动、行政成本、完整性审查、action ID和最小化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "申请人与两家承运人已签署可自行执行的互惠换装和解；案卷内2026-06-15委员会命令逐项记录该和解条款，并指示书记员按这些条款签发和解命令。", "decision_date": "2026-08-02", "jurisdiction": "美国联邦铁路监管", "regulated_subject": "审理互惠换装申请的美国地面运输委员会"}`
- C2：`{"boundary_facts": "申请书明确请求委员会沿49 CFR part 1145所述inadequate-service路径签发实体互惠换装命令；案卷没有承运人和解，也没有基于其他独立授权形成的竞争行为或服务不足认定。", "decision_date": "2026-08-02", "jurisdiction": "美国联邦铁路监管", "regulated_subject": "审理互惠换装申请的美国地面运输委员会"}`
- C1 不适用原因：C1签发的是已依其他当前权限批准的和解命令，无需依赖被撤销的Part 1145；C2不能依据该撤销规则即时签发互惠换装命令。
- 题内行动映射：三项候选分别映射为驳回、延后调查和签发互惠换装命令；case facts决定第三项是和解命令的行政签发还是依赖已撤销规则的实体命令。
- source 精确替换：
  - 旧：`该工厂位于换装终端区，实际仅接入北陆一家一级铁路承运人；现有案卷只记录该承运人在既有指标上的持续服务失败，未形成其他竞争行为或服务不足的独立认定。`
  - 新：`该工厂位于换装终端区，实际仅接入北陆一家一级铁路承运人；申请的协议状态、当前裁定依据以及案卷中的竞争与服务事实由本case事实给出。`
  - 旧：`该裁定还须符合决策日在美国联邦铁路监管体系下对本案有效的现行法律要求。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r016_a01": "驳回互惠换装申请", "swor_r016_a02": "延后互惠换装裁定", "swor_r016_a03": "签发互惠换装命令"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "models/solve_result.json", "new": {"accepted_equivalents": [{"unit": "万美元", "value": 2.0}, {"unit": "美元", "value": 20000.0}], "canonical_unit": "万美元", "canonical_value": 2.0}, "old": {"accepted_equivalents": [{"unit": "万美元", "value": 2.0}, {"unit": "美元", "value": 2.0}], "canonical_unit": "万美元", "canonical_value": 2.0}}, {"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "万美元", "value": 1.0}, {"unit": "美元", "value": 10000.0}], "canonical_unit": "万美元", "canonical_value": 1.0}, "old": {"accepted_equivalents": [{"unit": "万美元", "value": 1.0}, {"unit": "美元", "value": 1.0}], "canonical_unit": "万美元", "canonical_value": 1.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Surface Transportation Board", "url": "https://www.stb.gov/proceedings-actions/case-status/"}, {"publisher": "U.S. Court of Appeals for the Seventh Circuit", "url": "https://media.ca7.uscourts.gov/cgi-bin/OpinionsWeb/processWebInputExternal.pl?Path=Y2025%2FD07-08%2FC%3A24-1811%3AJ%3AScudder%3Aaut%3AT%3AfnOp%3AN%3A3394224%3AS%3A0&Submit=Display"}], "notes": "已复核V1.4.4保存的STB case-status与第七巡回法院quote，前者标示Post-Judicial Review，后者明确VACATE并REMAND最终规则。"}`
- 复核说明：把案件授权状态移出共通source；未发现模型系数错误；将3个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R017

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留八个连续3小时时段、价值、选四个、跨午夜条件、15日固定排班时间线、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "一项突发且有记录的船舶与人员生命安全事件要求恰好执行本日选中的四个值班块；船长已记录事件与值班，后续补偿休息已经固定在决策时域之外。", "decision_date": "2026-08-04", "jurisdiction": "美国boundary line外船舶运行", "regulated_subject": "为同一名轮机值班和指定安全职责船员安排四个值班块的货船船长"}`
- C2：`{"boundary_facts": "本日没有突发安全事件、召回或演练。每个入选块全程值班，未选块全程连续休息；前后各七个完整日均全程下班，完整记录覆盖所有受本日选择影响的24小时和7日窗口。", "decision_date": "2026-08-04", "jurisdiction": "美国boundary line外船舶运行", "regulated_subject": "为同一名轮机值班和指定安全职责船员安排四个值班块的货船船长"}`
- C1 不适用原因：C1的四个值班块由已记录的船舶和生命安全紧急事件所必需，紧急偏离分支使Gold的通常10小时、77小时、分段和间隔约束不加入本日模型；C2使用通常休息约束。
- 题内行动映射：八个二元行动直接表示对应3小时块为值班；未选行动即该块休息，因而可由同一24小时环形时间线计算连续休息。
- source 精确替换：
  - 旧：`不发生紧急情况、临时召回、例外授权或其他中止。`
  - 新：`本日事件记录、船长记录和决策时域外的补偿休息安排由本case事实给出。`
  - 旧：`安排须遵守决策日有效的美国联邦船舶值班人员休息规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States Coast Guard", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-46.xml?part=15"}], "notes": "已复核V1.4.4保存的46 CFR quote，覆盖任何24小时10小时、任何7日77小时、最多两段且一段至少6小时、连续休息间隔不超14小时。"}`
- 复核说明：删除共通source对紧急分支的预先排除。

### SWOR-R018

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L6, L7。
- 保持：保留五张包装数据表、编制成本、至少一张至多四张、action ID和最小化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "公司本年度经审计营业额为800万新元；在新加坡进口或使用塑料瓶20吨、纸盒12吨、金属罐8吨、玻璃罐0吨。董事会数据任务单写明表格只进入内部采购系统，截至决策日没有向NEA传送这些表格。", "decision_date": "2026-08-02", "jurisdiction": "新加坡企业内部包装管理", "regulated_subject": "为内部采购和减量分析准备包装数据表的饮料公司"}`
- C2：`{"boundary_facts": "公司本年度经审计营业额为1200万新元；在新加坡进口或使用塑料瓶120吨、纸盒80吨、金属罐40吨、玻璃罐0吨。每种实际材料—形式组合均有独立称重记录，年度工作日历列有向NEA提交包装数据和3R计划的任务。", "decision_date": "2026-08-02", "jurisdiction": "新加坡包装年度报告体系", "regulated_subject": "在新加坡进口和使用包装并准备当前年度数据表的饮料公司"}`
- C1 不适用原因：C1低于法定门槛且仅制作内部表格，按材料与形式逐项报送的Gold约束不修改内部成本模型。
- 题内行动映射：总重量行动建立汇总表；其余四项分别建立对应材料—形式组合的重量表，表格成本由题面给定。
- source 精确替换：
  - 旧：`新加坡年度包装数据表配置。2026年8月2日，达到强制包装报告门槛的星湾饮料公司配置本报告年度的数据表。`
  - 新：`新加坡年度包装数据表配置。2026年8月2日，星湾饮料公司配置本年度的数据表；营业额、包装数量与报送用途由本case事实给出。`
  - 旧：`公司在新加坡实际进口或使用塑料瓶、纸盒和金属罐3种包装组合，不使用玻璃罐。`
  - 新：`公司可能在新加坡进口或使用塑料瓶、纸盒、金属罐和玻璃罐；本年度实际使用的材料与形式由本case事实给出。`
  - 旧：`数据配置必须遵守新加坡当日适用的强制包装年度报告规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "千新元", "value": 1.0}, {"unit": "新元", "value": 1000.0}], "canonical_unit": "千新元", "canonical_value": 1.0}, "old": {"accepted_equivalents": [{"unit": "千新元", "value": 1.0}, {"unit": "新元", "value": 1.0}], "canonical_unit": "千新元", "canonical_value": 1.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Singapore National Environment Agency", "url": "https://www.nea.gov.sg/our-services/waste-management/mandatory-packaging-reporting"}], "notes": "已复核V1.4.4保存的NEA quote，并于访问日复核同一官方页面：补入MPR主体与年度营业额严格大于1000万新元的完整门槛原句；年度包装重量按塑料、纸、金属、玻璃等材料和形式拆分，并提交包装数据与3R计划。", "official_evidence_node_overrides": [{"information_responsibility": "给出MPR适用主体、严格大于1000万新元的年度营业额门槛以及进口或使用指定包装三项累积判据。", "node_id": "E2", "omission_effect": "缺少E2时，无法仅凭800万与1200万新元及包装活动判断两个case是否进入MPR报告范围。", "publisher": "Singapore National Environment Agency", "quote": "Companies that meet all the following criteria are required to comply with the MPR requirements under the Resource Sustainability Act (RSA): Carries on a business of supplying regulated goods in Singapore; Meet the prescribed threshold criteria which is an annual turnover of more than S$10 million; Imports or uses specified packaging.", "role": "applicability_gate", "source_node_id": "E2", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.nea.gov.sg/our-services/waste-management/mandatory-packaging-reporting"}]}`
- 复核说明：门槛与实际材料组合均移入case facts；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R019

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四类业务方、各两个交付周期与价值、13个月实验室互斥、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "四份请求文件均没有技术准备认证；业务方没有补交认证，提供商也没有签署把这些文件作为完整请求接收的协议；案卷没有替代交付协议或争议裁定。", "decision_date": "2026-08-04", "jurisdiction": "美国NG911工程交付", "regulated_subject": "为四家业务方安排IP交付的共享工程承包商"}`
- C2：`{"boundary_facts": "全国性CMRS的Phase 1请求于2025-01-10接收，非全国性CMRS的Phase 1请求于2024-08-01接收；互联VoIP的Phase 2请求于2025-09-01接收且Phase 1在2025-08-01完成，RLEC的Phase 2请求于2025-07-15接收且Phase 1在2025-06-30完成。两份Phase 1请求所列911 Authority的基础SIP接收与PSAP转送基础设施均已安装运行；两份Phase 2请求所列911 Authority的标准SIP接收与PSAP转送基础设施均已安装运行，ESInet已连接可提供LVF并与相应LIS或等效系统接口的运行中NGCS网络。四份请求均由有权911 Authority发出，注明指定NG911 Delivery Point，并连同上述认证以书面方式送达对应业务方；双方没有替代协议。", "decision_date": "2026-08-04", "jurisdiction": "美国NG911工程交付", "regulated_subject": "为四家covered originating service provider安排交付的共享工程承包商"}`
- C1 不适用原因：C1文件缺少构成valid request所需的技术准备认证，法定Phase 1/2期限尚未由这些文件启动，使用Base IR。
- 题内行动映射：每类业务方的两个行动是承包商可承诺的两个交付周期；期限均从题面请求或Phase 1锚点计算，13个月方案共享一座长期验收实验室。
- source 精确替换：
  - 旧：`四项请求均有效，规则生效后的最早合规日期已经过去，不存在替代协议或争议。`
  - 新：`四项请求的技术准备文件、接收记录、替代协议和争议状态由本case事实给出。`
  - 旧：`排期须遵守决策日有效的美国FCC NG911转换规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r019_a01": "全国CMRS一期采用5.9个月方案", "swor_r019_a02": "全国CMRS一期采用11.9个月方案", "swor_r019_a03": "非全国CMRS一期采用11.9个月方案", "swor_r019_a04": "非全国CMRS一期采用13个月方案", "swor_r019_a05": "互联VoIP二期采用后锚点后5.9个月方案", "swor_r019_a06": "互联VoIP二期采用后锚点后11.9个月方案", "swor_r019_a07": "农村本地交换商二期采用后锚点后11.9个月方案", "swor_r019_a08": "农村本地交换商二期采用后锚点后13个月方案"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Federal Communications Commission", "url": "https://docs.fcc.gov/public/attachments/FCC-24-78A1.pdf"}], "notes": "已复核V1.4.4保存的FCC-24-78期限quote；补入valid request的技术准备、授权、通知、Phase 1/2基础设施认证与NG911 Delivery Point完整原句，使期限Patch的启动条件闭合。", "official_evidence_node_overrides": [{"information_responsibility": "给出Phase 1和Phase 2请求有效性的技术准备、授权和通知三项一般前提。", "node_id": "E5", "omission_effect": "缺少E5时，仅有接收日期不能证明法定交付期限已经由有效请求启动。", "publisher": "U.S. Federal Communications Commission", "quote": "For both Phases 1 and 2, we adopt the three general prerequisites for a valid request proposed in the LBR Notice and NG911 Notice: technical readiness, authorization, and notification.", "role": "applicability_gate", "source_node_id": "E5", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://docs.fcc.gov/public/attachments/FCC-24-78A1.pdf"}, {"information_responsibility": "给出Phase 1有效请求所需的基础SIP接收与PSAP转送基础设施认证。", "node_id": "E6", "omission_effect": "缺少E6时，两个Phase 1请求的有效性及其六个月或十二个月期限无法闭合。", "publisher": "U.S. Federal Communications Commission", "quote": "In order for a Phase 1 request to be valid for purposes of our rules, the requesting 911 Authority must certify that it has all of the necessary infrastructure installed and operational to receive 911 traffic in a basic SIP format and transmit such traffic to the PSAP(s) connected to it.", "role": "applicability_gate", "source_node_id": "E6", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://docs.fcc.gov/public/attachments/FCC-24-78A1.pdf"}, {"information_responsibility": "给出Phase 2有效请求所需的标准SIP、PSAP转送、ESInet、NGCS、LVF与LIS接口认证。", "node_id": "E7", "omission_effect": "缺少E7时，两个Phase 2请求的有效性及其六个月或十二个月期限无法闭合。", "publisher": "U.S. Federal Communications Commission", "quote": "For a Phase 2 request to be deemed valid, the requesting 911 Authority must certify that it has all of the necessary infrastructure installed and operational to receive 911 traffic in SIP format that complies with NG911 commonly accepted standards and to transmit such traffic to the PSAP(s) connected to it. The 911 Authority also must certify that its ESInet is connected to a fully functioning NGCS network that can provide access to a LVF and interface with a LIS or its functional equivalent provided by the OSP.", "role": "applicability_gate", "source_node_id": "E7", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://docs.fcc.gov/public/attachments/FCC-24-78A1.pdf"}, {"information_responsibility": "要求有效请求注明911 Authority指定的NG911 Delivery Point位置。", "node_id": "E8", "omission_effect": "缺少E8时，四份请求仍缺少有效请求所需的交付点信息。", "publisher": "U.S. Federal Communications Commission", "quote": "In order to facilitate communication between 911 Authorities and OSPs, valid requests must indicate the location of NG911 Delivery Point(s) designated by the 911 Authority.", "role": "applicability_gate", "source_node_id": "E8", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://docs.fcc.gov/public/attachments/FCC-24-78A1.pdf"}]}`
- 复核说明：请求完整性和替代协议状态移入case facts；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R020

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L6, L7。
- 保持：保留四个业务场景贡献、四个批准包成本、合作保险商关系、各选一项、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "四个工作流均只读取不可逆聚合数据；数据不能识别个别客户，也不能合理链接回个别客户。向合作保险商交付的也是同一聚合结果，不传送行级记录。", "decision_date": "2026-08-05", "jurisdiction": "美国电信客户分析", "regulated_subject": "选择一个不可逆聚合数据工作流的电信承运人"}`
- C2：`{"boundary_facts": "在不启用“仅使用不识别个别客户的汇总信息”包时，四个工作流读取按姓名和账户号关联的行级记录，字段含订阅服务类别、数量、技术配置、位置和使用量；用途依次为同类别增值包营销、移动无线服务营销、向独立合作保险商联合营销、室内布线维修。保险商与承运人没有控制关系。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦电信客户信息领域", "regulated_subject": "选择一项客户账户记录使用或披露的电信承运人"}`
- C1 不适用原因：C1只处理不可识别个别客户的聚合信息，不进入个别可识别CPNI批准分支，Gold中的退出式或加入式批准约束不修改模型。
- 题内行动映射：前四项选择数据工作流；后四项选择不批准、退出式批准、加入式批准或聚合处理包，贡献与成本均由题面给定。
- source 精确替换：
  - 旧：`美国电信运营商CPNI使用与客户批准选择。2026年8月5日，伊利诺伊州星湾电信公司须选择一个CPNI使用场景和一个批准包。场景为向现有本地电话客户营销同类别增值包（58点）、向仅订阅本地电话的客户营销移动无线服务（72点）、向无公司控制关系的合作保险商披露个别客户CPNI用于联合营销（79点）或使用CPNI提供客户室内布线维修服务（52点）。`
  - 新：`美国电信运营商客户数据工作流与批准包选择。2026年8月5日，伊利诺伊州星湾电信公司须选择一个客户数据工作流和一个批准包。四个工作流的业务贡献依次为58、72、79、52点；各工作流使用的数据粒度、业务用途和接收方由本case事实给出。`
  - 旧：`安排须遵守决策日有效的美国联邦CPNI规则。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r020_a01": "向现有本地电话客户营销同类别本地电话增值包", "swor_r020_a02": "向仅订阅本地电话的客户营销移动无线服务", "swor_r020_a03": "向合作保险商披露个别客户CPNI用于联合营销", "swor_r020_a04": "使用CPNI提供客户室内布线维修服务", "swor_r020_a05": "不取得客户批准", "swor_r020_a06": "取得有效退出式批准", "swor_r020_a07": "取得有效加入式批准", "swor_r020_a08": "仅使用不识别个别客户的汇总信息"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_elements": [{"after": {"coefficients": {"different_category": 1, "no_approval": 1}, "meaning": "使用个别客户信息开展不同类别服务营销时不得选择无批准包", "name": "different_category_needs_optout_or_optin", "rhs": 1, "sense": "<="}, "name": "different_category_needs_optout_or_optin", "op": "add_constraint"}, {"after": {"coefficients": {"joint_partner": 1, "no_approval": 1, "optout_approval": 1}, "meaning": "向无控制关系合作方披露个别客户信息时仅可选择加入式批准", "name": "partner_disclosure_requires_optin", "rhs": 1, "sense": "<="}, "name": "partner_disclosure_requires_optin", "op": "add_constraint"}], "reason": "旧Patch把个别CPNI的批准约束无条件施加到聚合信息包，并把向独立合作方披露错误地允许opt-out；应允许aggregate_only绕开个别CPNI分支，合作方个别披露仅允许opt-in。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml"}, {"publisher": "U.S. Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-64/subpart-U/section-64.2007"}, {"publisher": "Office of the Law Revision Counsel, U.S. House of Representatives", "url": "https://uscode.house.gov/view.xhtml?req=%28title%3A47+section%3A222+edition%3Aprelim%29"}], "notes": "E1/E2继续支持个别可识别CPNI的partner opt-in与跨类别营销opt-out/opt-in两条slot；新增47 U.S.C. 222(h)(2)聚合信息完整定义及(c)(3)使用/披露许可，闭合aggregate_only与C1的RETAIN边界。", "official_evidence_node_overrides": [{"information_responsibility": "定义聚合客户信息为已移除个别客户身份和特征的群组或类别数据，与C1和aggregate_only的题内粒度一致。", "node_id": "E3", "omission_effect": "缺少E3时，无法确认题内不可识别汇总结果属于法定aggregate customer information边界。", "publisher": "Office of the Law Revision Counsel, U.S. House of Representatives", "quote": "The term \"aggregate customer information\" means collective data that relates to a group or category of services or customers, from which individual customer identities and characteristics have been removed.", "role": "definition", "source_node_id": "E3", "support_target_type": "exception_boundary", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://uscode.house.gov/view.xhtml?req=%28title%3A47+section%3A222+edition%3Aprelim%29"}, {"information_responsibility": "确认承运人可以使用、披露或允许访问aggregate customer information，故聚合包不应被个别CPNI批准约束误杀。", "node_id": "E4", "omission_effect": "缺少E4时，aggregate_only保留以及C1不施加两条个别信息Patch没有直接法源闭合。", "publisher": "Office of the Law Revision Counsel, U.S. House of Representatives", "quote": "A telecommunications carrier that receives or obtains customer proprietary network information by virtue of its provision of a telecommunications service may use, disclose, or permit access to aggregate customer information other than for the purposes described in paragraph (1). A local exchange carrier may use, disclose, or permit access to aggregate customer information other than for purposes described in paragraph (1) only if it provides such aggregate information to other carriers or persons on reasonable and nondiscriminatory terms and conditions upon reasonable request therefor.", "role": "exception", "source_node_id": "E4", "support_target_type": "exception_boundary", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://uscode.house.gov/view.xhtml?req=%28title%3A47+section%3A222+edition%3Aprelim%29"}]}`
- 复核说明：把个别信息与聚合信息状态移至case facts；修正Gold，使aggregate_only保持可选且独立合作方个别披露只能搭配opt-in；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R021

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L6, L7。
- 保持：保留两个职责包、各两家承包商、费用、目标设定行动、外包采购限制、action ID和最小化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "试点资金全部来自环境部门预算，部门签署并控制两份承包合同；生产者不出资，合同名册中没有生产者代表组织。两个职责包只服务该市政试点。", "decision_date": "2026-08-02", "jurisdiction": "爱尔兰市政包装废物试点", "regulated_subject": "采购两个内部承包商职责包的爱尔兰环境部门"}`
- C2：`{"boundary_facts": "在爱尔兰市场投放包装产品的生产者为计划出资并指定代表组织；登记、联络、报告以及包装废物分类、回收和处理两个职责包均在本期发生，本期废物管理目标栏为空。", "decision_date": "2026-08-02", "jurisdiction": "爱尔兰包装废物计划", "regulated_subject": "为由包装产品生产者出资的责任计划安排职责包和废物管理目标的爱尔兰环境部门"}`
- C1 不适用原因：C1是部门自筹自控的市政试点，不是生产者承担财务和组织责任的EPR计划，Gold的两个生产者责任包和目标设定约束不修改采购模型。
- 题内行动映射：前两项承接登记联络报告包，中两项承接分类回收处理包，最后一项在本期计划中写入废物管理目标；题面采购规则仍要求每个外包包恰选一家。
- source 精确替换：
  - 旧：`该计划由在爱尔兰市场投放包装产品的生产者出资；生产者通过代表组织安排登记、联络和报告，并安排废物运营方完成包装废物分类、回收和处理，本地登记确认上述2类职责均会在本期实际发生，废物管理目标尚未设定。`
  - 新：`计划的出资和控制主体、代表组织指定状态、两个职责包的本期用途及废物管理目标状态由本case事实给出。`
  - 旧：`唯一目标是最小化年度总成本，定案还须遵循在计划执行期对上述业务具有法律效力的现行要求。`
  - 新：`唯一目标是最小化年度总成本。`
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r021_a01": "委托GreenCycle承担生产者与代表组织之间的登记联络和报告职责", "swor_r021_a02": "委托HarbourWorks承担生产者与代表组织之间的登记联络和报告职责", "swor_r021_a03": "委托RiverSort承担包装废物的分类回收和处理职责", "swor_r021_a04": "委托EcoDepot承担包装废物的分类回收和处理职责", "swor_r021_a05": "正式设定本期废物管理目标"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "models/solve_result.json", "new": {"accepted_equivalents": [{"unit": "万元", "value": 9.0}, {"unit": "元", "value": 90000.0}], "canonical_unit": "万元", "canonical_value": 9.0}, "old": {"accepted_equivalents": [{"unit": "万元", "value": 9.0}, {"unit": "元", "value": 9.0}], "canonical_unit": "万元", "canonical_value": 9.0}}, {"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "万元", "value": 7.0}, {"unit": "元", "value": 70000.0}], "canonical_unit": "万元", "canonical_value": 7.0}, "old": {"accepted_equivalents": [{"unit": "万元", "value": 7.0}, {"unit": "元", "value": 7.0}], "canonical_unit": "万元", "canonical_value": 7.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Government of Ireland / Irish Statute Book", "url": "https://www.irishstatutebook.ie/eli/2020/si/323/made/en/print"}], "notes": "将V1.4.4截断的目标短语拆为法规主句引导语和连续完整的(b)项，并保留EPR定义；三节点共同闭合环境部门在EPR计划中设置目标的主体、谓词和适用边界。", "official_evidence_override": [{"information_responsibility": "给出EPR计划建立时承担后续列举职责的主体是部长或相关政府部长。", "node_id": "E1", "omission_effect": "缺少E1时，E2的目标谓词没有可绑定到题面环境部门的法定主语。", "publisher": "Government of Ireland / Irish Statute Book", "quote": "Where extended producer responsibility schemes are established in accordance with Regulation 30, including pursuant to other legislative acts of the Union, the Minister or any Minister of the Government concerned shall:", "role": "operative_rule_actor", "source_node_id": "E2a", "support_target_type": "patch_slot", "support_targets": ["waste_target_set"], "supported_patch_slots": ["waste_target_set"], "url": "https://www.irishstatutebook.ie/eli/2020/si/323/made/en/print"}, {"information_responsibility": "给出为EPR计划设置废物管理目标及相关定量或定性目标的完整谓词。", "node_id": "E2", "omission_effect": "缺少E2时，无法推出本期空白目标栏须由target_commitment行动补足。", "publisher": "Government of Ireland / Irish Statute Book", "quote": "(b) in line with the waste hierarchy, set waste management targets, aiming to attain at least the quantitative targets relevant for the extended producer responsibility scheme as laid down in the Waste Directive, 94/62/EC, Directive 2000/53/EC, Directive 2006/66/EC and Directive 2012/19/EU of the European Parliament and of the Council, and set other quantitative targets and/or qualitative objectives that are considered relevant for the extended producer responsibility scheme;", "role": "operative_rule", "source_node_id": "E2b", "support_target_type": "patch_slot", "support_targets": ["waste_target_set"], "supported_patch_slots": ["waste_target_set"], "url": "https://www.irishstatutebook.ie/eli/2020/si/323/made/en/print"}, {"information_responsibility": "把由生产者承担废物阶段财务或财务兼组织责任的计划识别为extended producer responsibility scheme。", "node_id": "E3", "omission_effect": "缺少E3时，无法把C2生产者出资并组织两个废物职责包的计划绑定到E1和E2。", "publisher": "Government of Ireland / Irish Statute Book", "quote": "‘extended producer responsibility scheme’ means a set of measures taken by Member States to ensure that producers of products bear financial responsibility or financial and organisational responsibility for the management of the waste stage of a product’s life cycle.", "role": "definition", "source_node_id": "E1", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.irishstatutebook.ie/eli/2020/si/323/made/en/print"}]}`
- 复核说明：出资主体和目标状态移入case facts，C2法定行动主体改为环境部门；用完整主语引导语、完整(b)项与EPR定义替换截断证据；将5个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R022

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留四名候选的任职、培训、能力、登记和服务间隔记录，四个任务包、成本、配对限制、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "入选人员本班次只执行前台接待、送餐和陪伴，不进行护理或护理相关操作；全部临床与护理相关工作由另行排班的持证人员完成。", "decision_date": "2026-08-05", "jurisdiction": "美国Medicare/Medicaid专业护理机构", "regulated_subject": "选择一名非临床支持工作人员和一个支持任务包的专业护理机构"}`
- C2：`{"boundary_facts": "入选人员本班次执行护理相关服务且不是持证护士；四人的任职月数、州项目培训证书、能力评估、登记与连续25个月有偿服务记录均与题列一致。", "decision_date": "2026-08-05", "jurisdiction": "美国Medicare/Medicaid专业护理机构", "regulated_subject": "选择一名非持证工作人员执行护理相关任务的专业护理机构"}`
- C1 不适用原因：C1岗位不提供护理或护理相关服务，候选人不以nurse aide身份执行本任务，Gold的培训、能力认定与24个月重训约束不修改该非临床分配模型。
- 题内行动映射：前四项选择工作人员；后四项分别提供普通支持、同步州批准项目的督导、派遣资质核验或重新培训与能力评估能力。
- source 精确替换：
  - 旧：`美国专业护理机构护理员与任务包选择。2026年8月5日，宾夕法尼亚州澄岭专业护理机构须选择一名nurse aide和一种任务包。`
  - 新：`美国专业护理机构工作人员与任务包选择。2026年8月5日，宾夕法尼亚州澄岭专业护理机构须选择一名工作人员和一种任务包；本次岗位的实际工作内容由本case事实给出。`
  - 旧：`机构没有人员配置豁免。`
  - 新：`候选人的本次岗位、任务边界和护理相关工作分工由本case事实给出。`
  - 旧：`指派须遵守决策日有效的美国联邦专业护理机构规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r022_a01": "指派任职2个月且全职参加州批准项目的永久护理员陈芳", "swor_r022_a02": "指派任职2个月但仅完成院内导向的永久护理员赵宁", "swor_r022_a03": "指派已满足能力与培训条件的派遣护理员周凯", "swor_r022_a04": "指派曾合格但连续25个月未提供有偿护理服务的护理员林洁", "swor_r022_a05": "安排普通住民照护班次", "swor_r022_a06": "安排与州批准项目同步的督导班次", "swor_r022_a07": "安排派遣资质核验班次", "swor_r022_a08": "安排重新培训与能力评估班次"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-G/part-483/subpart-B/section-483.35"}, {"publisher": "Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-G/part-483/subpart-A/section-483.5"}], "notes": "已复核V1.4.4保存的42 CFR quote，覆盖nurse aide定义、四个月训练窗口、州批准项目与连续24个月未提供有偿护理服务后的重训。"}`
- 复核说明：岗位工作内容移入case facts，候选人的历史记录不变；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R023

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四批气雾罐贡献、四种处理方式与成本、专用穿孔装置能力、A的当天窗口、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A至D均经独立检测为完全空、已泄压且没有危险残留；四批进入金属回收流，穿孔时没有残余内容物或排放逸出。", "decision_date": "2026-08-05", "jurisdiction": "美国气雾容器回收作业", "regulated_subject": "分拣经独立检测的空气雾容器并送往金属回收的维修中心"}`
- C2：`{"boundary_facts": "A为需当天处理的泄漏批次，B为普通泄漏批次，C未泄漏但仍有残液，D经确认完全空；专用密闭穿孔装置和题列程序、培训、通风、转移、鉴别与清理能力均已备齐。", "decision_date": "2026-08-05", "jurisdiction": "美国废气雾罐管理", "regulated_subject": "现场累计存放不足5000千克废气雾罐并选择处理批次的维修中心"}`
- C1 不适用原因：C1四批均为空且无危险残留，不是通用废物气雾罐，Gold的泄漏容器与残液穿孔处理约束不修改回收模型。
- 题内行动映射：前四项选处理批次；后四项分别提供敞口周转、吸附密闭、专用密闭穿孔回收或手工穿孔混放能力。
- source 精确替换：
  - 旧：`A为需当天处理的泄漏批次，贡献59点；B为普通泄漏批次，贡献54点；C未泄漏但仍有残液，贡献51点；D已确认完全空，贡献39点。`
  - 新：`A、B、C、D四批的贡献分别为59、54、51、39点；各批的压力、残液、泄漏和废物状态由本case事实给出。`
  - 旧：`合规穿孔方案包含书面程序、制造商说明、员工培训、通风平整场地、残液立即转入合规容器、危险废物鉴别及泄漏清理包；A因当天作业窗口不能等待独立包装线。`
  - 新：`专用穿孔方案包含书面程序、制造商说明、员工培训、通风平整场地、残液立即转入密闭容器、残液鉴别及泄漏清理包；A因当天作业窗口不能等待独立包装线。`
  - 旧：`方案须遵守决策日有效的美国联邦通用废物气雾罐规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r023_a01": "处理高优先级泄漏气雾罐批次A", "swor_r023_a02": "处理普通泄漏气雾罐批次B", "swor_r023_a03": "处理未泄漏但仍有残液的批次C", "swor_r023_a04": "处理已确认空罐批次D", "swor_r023_a05": "放入普通敞口周转箱", "swor_r023_a06": "放入带吸附材料的独立密闭容器", "swor_r023_a07": "使用合规装置穿孔排空并回收空罐", "swor_r023_a08": "使用手工工具穿孔后混放残液"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "已复核V1.4.4保存的40 CFR quote，覆盖泄漏罐单独密闭包装、专用装置穿孔及书面程序、培训、通风、残液转移和清理条件。"}`
- 复核说明：容器状态移入case facts，并去掉题内“合规”结论标签；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R024

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L6, L7。
- 保持：保留四项年度计划、提交日期、记录状态、贡献、三种时序服务、成本、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "设施档案含EPA于2025-12-15签发的停止报告通知接受函和文号，EPA账户页面自该日显示closed；题列计划只生成内部年度摘要。决策涉及的全部旧档案距相应提交日均已满三年六个月。", "decision_date": "2026-08-05", "jurisdiction": "美国工业设施内部温室气体数据管理", "regulated_subject": "选择自愿年度摘要和档案服务、EPA报告账户已关闭的工业设施"}`
- C2：`{"boundary_facts": "报告覆盖2025日历年；设施持续运行，EPA GHGRP账户页面显示active并列有facility ID，案卷登记表没有延期函或停止报告通知。题列记录状态覆盖本报告涉及的全部记录。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦温室气体报告", "regulated_subject": "选择年度报告时间和记录服务、EPA GHGRP账户处于active状态的工业设施"}`
- C1 不适用原因：C1的停止报告通知已获批且旧记录均超过保留期，本年度内部摘要不受3月31日和三年档案约束，使用Base IR。
- 题内行动映射：前四项选择提交日与自带档案状态；后三项分别不变、更改至3月31日或建立至少三年完整档案。
- source 精确替换：
  - 旧：`美国设施年度温室气体报告时序选择。2026年8月5日，云浦工业设施已确定受40 CFR第98部分约束，须选择一项下一年度报告计划和一个时序服务。`
  - 新：`美国设施年度温室气体数据时序选择。2026年8月5日，云浦工业设施须选择一项下一年度数据计划和一个时序服务；设施的Part 98报告状态由本case事实给出。`
  - 旧：`报告覆盖上一日历年，不存在获批延期或停止报告例外。`
  - 新：`数据计划所涉年份、停止通知和既有档案年龄由本case事实给出。`
  - 旧：`方案须遵守决策日有效的美国联邦温室气体报告时序规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r024_a01": "年度温室气体报告计划4月5日提交且不建档", "swor_r024_a02": "计划3月31日提交且记录保留三年", "swor_r024_a03": "计划3月20日提交但不保留记录", "swor_r024_a04": "计划3月25日提交且记录保留三年", "swor_r024_a05": "不增加时序合规服务", "swor_r024_a06": "将提交日提前到3月31日并完成提交", "swor_r024_a07": "建立自提交日起至少三年的记录保留服务"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_element": {"after": {"coefficients": {"april5_no_archive": 1, "retain_records_three_years": -1}, "meaning": "4月5日且未建档的计划还须配置三年记录保留服务", "name": "april5_no_archive_requires_retention", "rhs": 0, "sense": "<="}, "name": "april5_no_archive_requires_retention", "op": "add_constraint"}, "reason": "旧Patch只约束3月20日未建档计划，遗漏同样无档案的4月5日计划；记录保留要求与提交日是否逾期无关。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "已复核V1.4.4保存的40 CFR Part 98 quote；三年记录保留规则同时支持3月20日和4月5日两个未建档计划，补齐遗漏的april5_no_archive约束。", "official_evidence_node_overrides": [{"information_responsibility": "受Part 98约束的设施须从报告提交日起保留所需记录至少三年，覆盖两个未建档计划。", "node_id": "E2", "omission_effect": "缺少E2时，march20_no_archive与april5_no_archive是否都需三年保留服务无法确定。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "The owner or operator of a facility or supplier that is subject to the requirements of this part must retain all required records for at least 3 years from the date of submission of the annual GHG report for the reporting year in which the record was generated.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["march20_no_archive_requires_retention", "april5_no_archive_requires_retention"], "supported_patch_slots": ["march20_no_archive_requires_retention", "april5_no_archive_requires_retention"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}]}`
- 复核说明：报告主体状态和停止通知移入case facts；补齐4月5日未建档计划的三年记录保留约束；将7个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R025

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L6, L7。
- 保持：保留四条通道效用、四种改造与成本、A/B专用包限制、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A沿全程远离所有高危险区；B沿途房间的锁和锁具已经永久拆除；C连续通向出口并有贯通平面图；D为直接无障碍通道。", "decision_date": "2026-08-05", "jurisdiction": "美国制造场所出口通道", "regulated_subject": "选择一条出口通道和改造包的制造企业"}`
- C2：`{"boundary_facts": "A朝高危险反应区方向经过，连续实体隔墙可把该区域与通道屏蔽；B穿过一间工作时开启但硬件仍可上锁的更衣室；C通向死胡同后折返；D为直接无障碍通道。", "decision_date": "2026-08-05", "jurisdiction": "美国制造场所出口通道", "regulated_subject": "选择一条出口通道和改造包的制造企业"}`
- C1 不适用原因：C1的A远离危险区、B房间已不可上锁、C不是死胡同，Gold对A/B/C的改造要求均不加入。
- 题内行动映射：前四项选通道；后四项分别不改造、实体隔墙屏蔽、永久拆锁或重建绕行，题面明确前两种专用改造的对象。
- source 精确替换：
  - 旧：`A朝高危险反应区方向经过，效用62点；B穿过一间工作时保持开启但仍可上锁的更衣室，效用70点；C通向死胡同后再折返出口，效用58点；D为直接无障碍通道，效用49点。`
  - 新：`A、B、C、D四条通道的效用分别为62、70、58、49点；危险区方向、沿途房间锁具和通道终点状态由本case事实给出。`
  - 旧：`方案须遵守决策日有效的美国联邦工作场所出口通道规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r025_a01": "采用朝高危险反应区方向经过的出口通道A", "swor_r025_a02": "采用穿过可上锁更衣室的出口通道B", "swor_r025_a03": "选择通向死胡同后再折返出口的通道C", "swor_r025_a04": "采用直接无障碍出口通道D", "swor_r025_a05": "不改造通道", "swor_r025_a06": "增设连续实体隔墙有效屏蔽高危险区", "swor_r025_a07": "永久拆除更衣室锁具使房间不可上锁", "swor_r025_a08": "重建通道绕开原房间或死胡同"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_element": {"after": {"coefficients": {"dead_end": 1, "reroute": -1}, "meaning": "通向死胡同的出口通道须采用重建绕行包", "name": "dead_end_requires_reroute", "rhs": 0, "sense": "<="}, "name": "dead_end_requires_reroute", "op": "add_constraint"}, "reason": "旧Patch引用的法规原句明确禁止出口通道进入死胡同，却只约束可上锁房间，遗漏C通道的reroute要求。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Occupational Safety and Health Administration / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "已复核V1.4.4保存的29 CFR quote；同一句同时禁止穿过可上锁房间和进入死胡同，补齐C通道必须reroute的遗漏Patch。", "official_evidence_node_overrides": [{"information_responsibility": "出口通道不得穿过可上锁房间，也不得进入死胡同走廊。", "node_id": "E1", "omission_effect": "缺少E1时，B通道的拆锁或改道要求与C通道的改道要求均无法确定。", "publisher": "U.S. Occupational Safety and Health Administration / Electronic Code of Federal Regulations", "quote": "The exit access must not go through a room that can be locked, such as a bathroom, to reach an exit or exit discharge, nor may it lead into a dead-end corridor.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["lockable_route_requires_remove_or_reroute", "dead_end_requires_reroute"], "supported_patch_slots": ["lockable_route_requires_remove_or_reroute", "dead_end_requires_reroute"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}]}`
- 复核说明：三项通道边界事实移入case facts；补齐死胡同通道必须reroute的约束；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R026

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留六票运输价值与时段、选三票、日夜两个即时接听值班台及成本、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B外包装展示limited quantity标记，C、D外包装展示excepted quantity标记，E也展示limited quantity标记；F运单的proper shipping name栏填写Dry ice。两个值班台为可选内部服务。", "decision_date": "2026-08-04", "jurisdiction": "美国公路危险材料运输", "regulated_subject": "选择运输票次和内部应急值班覆盖的美国offeror"}`
- C2：`{"boundary_facts": "A至D运单分别列有UN编号、proper shipping name、危险类别和packing group，外包装没有limited quantity或excepted quantity标记，运输时段与题列一致；E外包装展示limited quantity标记，F运单的proper shipping name栏填写Dry ice。日夜值班台均由掌握材料应急资料的人员即时接听。", "decision_date": "2026-08-04", "jurisdiction": "美国公路危险材料运输", "regulated_subject": "选择危险材料票次和应急值班覆盖的美国offeror"}`
- C1 不适用原因：C1六票分别进入limited/excepted quantity或Dry ice分支，Section 172.604电话值守义务不加入，使用Base IR。
- 题内行动映射：前六项选运输票次；日间与夜间行动分别提供07:00—19:00和19:00—次日07:00的即时接听能力，可覆盖所选票次与值班时段的重叠区间。
- source 精确替换：
  - 旧：`A至D均为需要危险品运输单据的受管材料，所列时段覆盖各票处于运输中的全部时间。`
  - 新：`A至D所列时段覆盖各票处于运输中的全部时间；六票的材料分类、运输名称和例外标记由本case事实给出。`
  - 旧：`运输安排须遵守决策日有效的美国联邦危险材料应急响应信息规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r026_a01": "执行08:00至12:00的运输A", "swor_r026_a02": "执行10:00至21:00的运输B", "swor_r026_a03": "执行13:00至22:00的运输C", "swor_r026_a04": "执行21:00至次日02:00的运输D", "swor_r026_a05": "执行按limited quantity条款交运的运输E", "swor_r026_a06": "执行正确描述为Dry ice的运输F", "swor_r026_a07": "启用07:00至19:00日间应急信息值班台", "swor_r026_a08": "启用19:00至次日07:00夜间应急信息值班台"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States eCFR / Pipeline and Hazardous Materials Safety Administration", "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-172/subpart-G/section-172.604"}], "notes": "已复核V1.4.4保存的49 CFR 172.604；E1/E2完整支持limited/excepted quantity边界及A—D六个值班Patch，E3改为从(2)引导语至(ix) Dry ice的连续逐字引文，删除跨项省略号拼接。", "official_evidence_node_overrides": [{"information_responsibility": "完整列出§172.604(2)运输名称例外并确认proper shipping name为Dry ice的F位于该例外。", "node_id": "E3", "omission_effect": "缺少E3时，无法确认F不需要日间或夜间值班台，可能产生不受支持的额外Patch。", "publisher": "United States eCFR / Pipeline and Hazardous Materials Safety Administration", "quote": "The requirements of this section do not apply to— (2) Materials properly described under the following shipping names: (i) Battery powered equipment. (ii) Battery powered vehicle. (iii) Carbon dioxide, solid. (iv) Castor bean. (v) Castor flake. (vi) Castor meal. (vii) Castor pomace. (viii) Consumer commodity. (ix) Dry ice.", "role": "exception", "source_node_id": "E3", "support_target_type": "exception_boundary", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-172/subpart-G/section-172.604"}]}`
- 复核说明：材料分类和例外标记移入case facts，时间覆盖保持；E3改为无省略号的连续完整例外引文，现有六个Patch仍由E2完整支持；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R027

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四类机构账户、证券持有额、审计日期、四批票据、16项分配负担、一一分配、action ID和最小化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "I、D、B30和B20的实体类型、酌情持有金额、审计报表日期均与题列一致；B20经审计净值为2500万美元。Q1至Q3只向QIB出售，R为公开票据。", "decision_date": "2026-08-04", "jurisdiction": "美国SEC Rule 144A转售", "regulated_subject": "把三个受限票据批次和一个公开票据批次分配给四个机构自营账户的证券商"}`
- C2：`{"boundary_facts": "I为保险公司，D为section 15注册交易商，B30和B20为美国银行；B20经审计净值为2000万美元，其余题列持有额和12个月审计日期保持。Q1至Q3只向QIB出售，R为公开票据。", "decision_date": "2026-08-04", "jurisdiction": "美国SEC Rule 144A转售", "regulated_subject": "把三个受限票据批次和一个公开票据批次分配给四个机构自营账户的证券商"}`
- C1 不适用原因：C1的B20净值达到2500万美元银行分支，三个QIB票据分配排除约束不加入；C2的B20净值仅2000万美元，不能接收Q1至Q3。
- 题内行动映射：16个行动按题面顺序构成账户×票据批次分配矩阵；每个账户和每个批次各恰好出现一次，负担直接取对应单元。
- source 精确替换：
  - 旧：`B20也是美国银行，证券金额与报表日期相同，但经审计净值为2000万美元。`
  - 新：`B20也是美国银行，证券金额与报表日期相同；其经审计净值由本case事实给出。`
  - 旧：`分配须遵守决策日有效的美国SEC Rule 144A。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r027_a01": "将Q1 Rule 144A受限票据批次分配给保险公司账户I：酌情拥有并投资1.05亿美元非关联发行人证券", "swor_r027_a02": "将Q2 Rule 144A受限票据批次分配给保险公司账户I：酌情拥有并投资1.05亿美元非关联发行人证券", "swor_r027_a03": "将Q3 Rule 144A受限票据批次分配给保险公司账户I：酌情拥有并投资1.05亿美元非关联发行人证券", "swor_r027_a04": "将R已注册公开票据批次分配给保险公司账户I：酌情拥有并投资1.05亿美元非关联发行人证券", "swor_r027_a05": "将Q1 Rule 144A受限票据批次分配给注册交易商账户D：酌情拥有并投资1200万美元非关联发行人证券", "swor_r027_a06": "将Q2 Rule 144A受限票据批次分配给注册交易商账户D：酌情拥有并投资1200万美元非关联发行人证券", "swor_r027_a07": "将Q3 Rule 144A受限票据批次分配给注册交易商账户D：酌情拥有并投资1200万美元非关联发行人证券", "swor_r027_a08": "将R已注册公开票据批次分配给注册交易商账户D：酌情拥有并投资1200万美元非关联发行人证券", "swor_r027_a09": "将Q1 Rule 144A受限票据批次分配给美国银行账户B30：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值3000万美元", "swor_r027_a10": "将Q2 Rule 144A受限票据批次分配给美国银行账户B30：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值3000万美元", "swor_r027_a11": "将Q3 Rule 144A受限票据批次分配给美国银行账户B30：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值3000万美元", "swor_r027_a12": "将R已注册公开票据批次分配给美国银行账户B30：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值3000万美元", "swor_r027_a13": "将Q1 Rule 144A受限票据批次分配给美国银行账户B20：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值2000万美元", "swor_r027_a14": "将Q2 Rule 144A受限票据批次分配给美国银行账户B20：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值2000万美元", "swor_r027_a15": "将Q3 Rule 144A受限票据批次分配给美国银行账户B20：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值2000万美元", "swor_r027_a16": "将R已注册公开票据批次分配给美国银行账户B20：酌情拥有并投资1.20亿美元非关联发行人证券，最近12个月内年度财务报表所示经审计净值2000万美元"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Electronic Code of Federal Regulations / Securities and Exchange Commission", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-17.xml"}], "notes": "已复核V1.4.4保存的17 CFR Rule 144A quote，覆盖机构持有额分支、银行2500万美元经审计净值和不超过16个月的年度财务报表日期。"}`
- 复核说明：只移动B20净值这一case轴，分配矩阵保持；将16个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R028

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留六项投资行动、cETN/LTAF/普通基金/上市股票产品、效用、选两项、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B、C三只cETN在2026年4月6日前已存于同一账户并连续持有至决策日；A、B行动只是继续持有下的账面分配，不发生新购或转入。D为新购LTAF，E为FCA授权OEIC份额，F为伦敦证券交易所主板上市普通股。", "decision_date": "2026-08-04", "jurisdiction": "英国股票和股份ISA", "regulated_subject": "为同一个stocks and shares ISA选择两个账面行动的ISA经理"}`
- C2：`{"boundary_facts": "A为决策日新购cETN，B为决策日从普通应税账户新转入另一只cETN，C在2026年4月6日前已存于同一账户并连续持有；D为新购LTAF。", "decision_date": "2026-08-04", "jurisdiction": "英国股票和股份ISA", "regulated_subject": "为同一个stocks and shares ISA选择两个交易或持有行动的ISA经理"}`
- C1 不适用原因：C1的A、B、C均属于截止日前已在同一ISA连续持有的cETN，Gold对A新购和B新转入的排除不加入；C2仅C走存量持有分支。
- 题内行动映射：六项行动直接选择纳入同一ISA的两项交易或持有动作；case facts解释A—C的交易时间性质。
- source 精确替换：
  - 旧：`A是在决策日新购一只加密资产交易所交易票据cETN，组合效用76点；B是在决策日从普通应税账户新转入另一只cETN，效用72点；C是继续持有一只在2026年4月5日已经存在于该账户内、此后从未转出的cETN，效用68点。`
  - 新：`A、B、C分别涉及一只cETN，组合效用为76、72、68点；三项行动是新购、转入还是连续持有由本case事实给出。`
  - 旧：`组合调整须遵守决策日有效的英国个人储蓄账户合资格投资规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r028_a01": "在股票和股份ISA中新购cETN产品A", "swor_r028_a02": "将cETN产品B转入股票和股份ISA", "swor_r028_a03": "继续持有2026年4月6日前已在同一账户内的cETN产品C", "swor_r028_a04": "在股票和股份ISA中新购LTAF产品D", "swor_r028_a05": "在股票和股份ISA中新购认可基金E", "swor_r028_a06": "在股票和股份ISA中新购合资格上市普通股F"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Legislation / HM Revenue & Customs", "url": "https://www.legislation.gov.uk/uksi/2026/248/made/data.xml"}, {"publisher": "UK Government, HM Revenue & Customs", "url": "https://www.gov.uk/government/publications/tax-free-savings-newsletter-21/tax-free-savings-newsletter-21-june-2026"}], "notes": "已复核V1.4.4保存的2026/248修订法规与HMRC newsletter；E3由孤立名词短语扩为包含regulation 7修改位置、插入项与LTAF完整条文的连续引文。", "official_evidence_node_overrides": [{"information_responsibility": "确认2026年修订在stocks and shares component的合资格投资清单中加入long-term asset fund投资。", "node_id": "E3", "omission_effect": "缺少E3时，无法确认新购LTAF行动D仍可保留在模型中。", "publisher": "UK Legislation / HM Revenue & Customs", "quote": "In regulation 7 (qualifying investments for a stocks and shares component)— (a) in paragraph (2)— (i) at the beginning of sub-paragraph (b) insert “subject to paragraphs (2G) and (2H),”; (ii) after sub-paragraph (r) insert— “(s) investments in a long-term asset fund.”;", "role": "incorporated_standard", "source_node_id": "E3", "support_target_type": "retained_action", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://www.legislation.gov.uk/uksi/2026/248/made/data.xml"}]}`
- 复核说明：A—C交易性质移入case facts，产品和效用不变；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R029

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留四张订单、每单两条路径及价值、共享闭环保障和安全配送服务及成本、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B、D均由诊所通过闭环系统直接传送处方；C为普通处方药。药房已经持续运行覆盖全部候选的闭环保障系统和安全到家配送系统，题列两个服务行动只是额外审计升级。", "decision_date": "2026-08-04", "jurisdiction": "新加坡零售药房与电子药房服务", "regulated_subject": "由合格药剂师负责四张订单的持牌零售药房"}`
- C2：`{"boundary_facts": "A和D为处方药，B为药房专售药，C为受控药品；A/B路径1为诊所直传闭环并到家，路径2为患者PDF并到家；C路径1为电子配方到家，路径2所用纸质处方写有开方者签名、日期、患者、药品和剂量并在柜台领取；D路径1为诊所直传闭环处方并在柜台领取，路径2为患者PDF并在柜台领取。HSA授权登记表没有该药房对C进行电子配方或到家配送的条目。", "decision_date": "2026-08-04", "jurisdiction": "新加坡零售药房与电子药房服务", "regulated_subject": "由合格药剂师负责四张药品订单的持牌零售药房"}`
- C1 不适用原因：C1没有患者PDF或受控药品，且闭环和配送能力已在决策外固定，Gold的六个路径—服务约束均不修改模型。
- 题内行动映射：前八项为每张订单二选一的具体履约路径；后两项分别提供全批次闭环处方保障和安全到家配送能力。
- source 精确替换：
  - 旧：`处方药A可采用由诊所直接传入药房系统的闭环电子处方并送药到家，或采用患者电邮来的PDF并送药到家，履约价值23、28点；药房专售药B采用相同两种到家路径，价值22、27点；受控药品C可采用电子配方并送药到家，或持有效纸质处方到实体柜台领取，价值29、18点；处方药D可采用诊所直传闭环并在柜台领取，或采用患者电邮PDF并在柜台领取，价值21、26点。`
  - 新：`订单A、B、C、D各有路径1和路径2，履约价值依次为23/28、22/27、29/18、21/26点；各订单的药品类别、处方传输、交付地点和已有保障能力由本case事实给出。`
  - 旧：`药房持有新加坡零售药房许可并由合格药剂师负责；患者电邮PDF没有经过诊所到药房的直接传输；药房没有受控药品电子配方或到家配送的特别授权。`
  - 新：`药房持有新加坡零售药房许可并由合格药剂师负责；订单文件来源、电子配方授权和交付授权由本case事实给出。`
  - 旧：`履约须遵守决策日有效的新加坡HSA电子药房规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r029_a01": "订单A采用路径1", "swor_r029_a02": "订单A采用路径2", "swor_r029_a03": "订单B采用路径1", "swor_r029_a04": "订单B采用路径2", "swor_r029_a05": "订单C采用路径1", "swor_r029_a06": "订单C采用路径2", "swor_r029_a07": "订单D采用路径1", "swor_r029_a08": "订单D采用路径2"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Singapore Health Sciences Authority", "url": "https://www.hsa.gov.sg/other-regulations/retail-pharmacy-licence/supply-of-registered-therapeutic-products-through-e-pharmacy/"}], "notes": "已复核V1.4.4保存的HSA quote，覆盖处方须由开方者直接传给药房、药房专售药和受控药品的电子药房与配送条件。"}`
- 复核说明：行动含义泛化，避免C1/C2药品和路径状态冲突；补明D两条柜台路径各自的处方传输方式。

### SWOR-R030

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留六名首次ASYE候选、统一开始日、支付期、申请价值、选两人、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至F在项目开展、完成和申报期间均由申报机构直接雇用，岗位记录均写明成人社会照护或NHS成人社会工作；六人的资格证书编号都出现在Social Work England登记册，首次登记日期分别距2026-05-01为2、2、1、3、4、1年。", "decision_date": "2026-08-04", "jurisdiction": "英格兰成人社会工作服务", "regulated_subject": "选择两项2026—2027年度ASYE资助申请的成人社会服务机构"}`
- C2：`{"boundary_facts": "A、D、F由机构直接雇用并从事成人社会工作，注册年限分别为2、3、1年；B在全部项目期由劳务机构派驻，C只从事儿童社会工作，E取得资格并注册5年。六人均于2026年5月1日首次开始ASYE。", "decision_date": "2026-08-04", "jurisdiction": "英格兰成人社会工作服务", "regulated_subject": "选择两项2026—2027年度ASYE资助申请的成人社会服务机构"}`
- C1 不适用原因：C1六人均满足直接雇佣、成人社会工作和不超过四年三个分支，Gold对B、C、E的排除均不加入；C2保留三项排除。
- 题内行动映射：六个行动分别把对应候选纳入两项锁定申请；申请价值直接计入组合目标。
- source 精确替换：
  - 旧：`A由机构在英格兰直接雇用，从事成人社会工作，2年前取得Social Work England认可资格并注册，申请价值85点。B在2年前取得相同认可资格并注册，从事成人社会工作，但在项目开展、完成和申报期间始终由劳务机构派驻，不与申报机构建立直接雇佣关系，价值92点。C由机构直接雇用，1年前取得认可资格并注册，但只从事儿童社会工作，不提供成人社会工作，价值88点。D由机构在英格兰直接雇用，在NHS服务中从事成人社会工作，3年前取得认可资格并注册，首次参加ASYE，价值80点。E由机构直接雇用并从事成人社会工作，5年前取得认可资格并在Social Work England注册，首次参加ASYE，价值78点。F由机构直接雇用并从事成人社会工作，1年前取得认可资格并注册，首次参加ASYE，价值75点。`
  - 新：`A、B、C、D、E、F六名候选的申请价值分别为85、92、88、80、78、75点；各人的雇佣关系、服务对象、服务场所、认可资格和注册年限由本case事实给出。`
  - 旧：`申请必须遵守决策日有效的英格兰成人社会工作ASYE资助条件。`
  - 新：``
- output_schema meaning 修改：`{"swor_r030_a01": "提交候选A的ASYE资助申请", "swor_r030_a02": "提交候选B的ASYE资助申请", "swor_r030_a03": "提交候选C的ASYE资助申请", "swor_r030_a04": "提交候选D的ASYE资助申请", "swor_r030_a05": "提交候选E的ASYE资助申请", "swor_r030_a06": "提交候选F的ASYE资助申请"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Department of Health and Social Care", "url": "https://www.gov.uk/government/publications/adults-assessed-and-supported-year-in-employment-grant-determination-2026-to-2027/adults-assessed-and-supported-year-in-employment-grant-determination-2026-to-2027"}], "notes": "已复核V1.4.4保存的DHSC grant determination quote，覆盖直接雇佣、成人社会工作、认可资格、Social Work England注册不超过四年和项目日期条件。"}`
- 复核说明：候选人资格轴移入case facts并泛化行动含义。

### SWOR-R031

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留六辆已登记无边车摩托车、贡献、购入两辆、A/B名额互斥、共享安装单元及成本、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A于2026年4月30日按普通摩托车登记并持续持有该登记，B也在2026年5月1日前按普通摩托车登记；A、B各只有一面镜。C按经典车辆登记，E按普通古董车辆登记，二者各有一面镜；D、F左右各有一面镜。", "decision_date": "2026-08-04", "jurisdiction": "新加坡道路摩托车租赁", "regulated_subject": "购入两辆已登记摩托车投入道路租赁的公司"}`
- C2：`{"boundary_facts": "A于2026年6月按普通摩托车登记且仅右侧有一面镜；B于2026年4月按普通摩托车登记且仅左侧有一面镜；C按经典车辆登记，E按普通古董车辆登记，二者各有一面镜；D、F左右各有一面镜。", "decision_date": "2026-08-04", "jurisdiction": "新加坡道路摩托车租赁", "regulated_subject": "购入两辆已登记摩托车投入道路租赁的公司"}`
- C1 不适用原因：C1的A在2026-05-01前已按普通摩托车登记，和B一样不进入新登记普通摩托车的双镜分支，Gold的A→安装单元约束不加入。
- 题内行动映射：前六项选择采购车辆；共享安装单元能在道路运营前为所有入选缺镜车辆补装缺失侧的一面技术合格后视镜。
- source 精确替换：
  - 旧：`A是2026年6月按普通车辆登记、仅在右侧装有一面合格后视镜的摩托车，车队贡献91点；B是2026年4月按普通车辆登记、仅在左侧装有一面合格后视镜的摩托车，贡献74点。C是2026年6月按经典车辆登记、仅有一面合格后视镜的摩托车，贡献86点；D是2026年6月按普通车辆登记、左右两侧各有一面合格后视镜的摩托车，贡献80点；E是2026年7月按普通古董车辆登记、仅有一面合格后视镜的摩托车，贡献77点；F是2026年7月按普通车辆登记、左右两侧各有一面合格后视镜的摩托车，贡献69点。`
  - 新：`A、B、C、D、E、F六辆车的车队贡献分别为91、74、86、80、77、69点；登记日期、登记类别和已安装后视镜数量由本case事实给出。`
  - 旧：`在投入道路运营前为全部需要加装的所选车辆在缺失一侧安装符合rule 20(3A)适用技术标准的合格后视镜`
  - 新：`在投入道路运营前为全部需要加装的所选车辆在缺失一侧安装一面构造和安装均能帮助骑手观察车辆后方交通的合格后视镜`
  - 旧：`采购车辆必须符合决策日有效的新加坡摩托车后视镜装备规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r031_a01": "购入摩托车A", "swor_r031_a02": "购入摩托车B", "swor_r031_a03": "购入摩托车C", "swor_r031_a04": "购入摩托车D", "swor_r031_a05": "购入摩托车E", "swor_r031_a06": "购入摩托车F"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Singapore Land Transport Authority", "url": "https://assets.egazette.gov.sg/2026/Legislative%20Supplements/Subsidiary%20Legislation%20Supplement/275.pdf"}], "notes": "已复核V1.4.4保存的新加坡Government Gazette quote，覆盖2026-05-01生效、普通新登记摩托车两侧各一镜及经典/古董登记分支。"}`
- 复核说明：登记日和车辆类别移入case facts，并泛化六个车辆行动；删除题面rule 20(3A)编号，保留可观察的镜面业务能力。

### SWOR-R032

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L6, L7。
- 保持：保留八票贡献、恰装三票、G/H隔离舱板及成本、不经水路、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A至H均为不含危险材料的惰性测试样品；托运说明和包装检验记录没有危险类别、次要危险、危险标签或标牌。G与H隔离舱板只是可选的防破损混合设备。", "decision_date": "2026-08-04", "jurisdiction": "美国公路工业样品运输", "regulated_subject": "在一辆非水路货车上拼装三票惰性工业测试样品的承运人"}`
- C2：`{"boundary_facts": "A为与酸混合释放氰化氢的氰化物溶液，B为Class 8硫酸，C为Division 4.2，D为Class 8碱液，E为Division 6.1/PG I/Hazard Zone A，F和G为Class 3，H为Division 5.1；包装展示对应标签或车辆标牌。", "decision_date": "2026-08-04", "jurisdiction": "美国公路危险材料运输", "regulated_subject": "在一辆非水路货车上拼装三票危险材料的承运人"}`
- C1 不适用原因：C1八票均为无危险分类的惰性样品，隔离表和危险反应组合约束不修改拼车模型，使用Base IR。
- 题内行动映射：前八项选三票货物；第九项只在G和H同时入选时安装能阻止通常泄漏混合的舱板，题内对其他货物组合没有可用分隔行动。
- source 精确替换：
  - 旧：`美国危险品拼车组合。2026年8月4日，IronRoute Hazmat要在一辆不经水路运输的公路货车上从八票均需标签或标牌的货物中恰好装载三票。`
  - 新：`美国公路货物拼车组合。2026年8月4日，IronRoute Logistics要在一辆不经水路运输的公路货车上从八票货物中恰好装载三票；货物运输分类和外包装标记由本case事实给出。`
  - 旧：`A是氰化物溶液，若与酸混合会释放氰化氢，贡献38点；B是Class 8硫酸，37点；C是Division 4.2自燃固体，36点；D是Class 8碱性腐蚀液，35点；E是Division 6.1、Packing Group I、Hazard Zone A剧毒液体，34点；F是Class 3易燃液体，33点；G是另一票Class 3易燃液体，32点；H是Division 5.1氧化剂，31点。`
  - 新：`A、B、C、D、E、F、G、H八票的贡献分别为38、37、36、35、34、33、32、31点；物质属性、主次危险类别和混合反应由本case事实给出。`
  - 旧：`承运人可为G与H安装成本12点的核定隔离舱板；该装置能在通常运输泄漏条件下阻止两票货物混合，且只有两票都装载时才安装。`
  - 新：`承运人可为G与H安装成本12点的核定隔离舱板；该装置能在通常运输泄漏条件下阻止两票货物混合，且只有两票都装载时才安装；这是本轮唯一可用的防通常泄漏混合分隔能力，对其他货物组合没有舱板、隔舱或替代车辆/储存设施。`
  - 旧：`装载须遵守决策日有效的美国联邦公路危险品隔离规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r032_a01": "装载货物A", "swor_r032_a02": "装载货物B", "swor_r032_a03": "装载货物C", "swor_r032_a04": "装载货物D", "swor_r032_a05": "装载货物E", "swor_r032_a06": "装载货物F", "swor_r032_a07": "装载货物G", "swor_r032_a08": "装载货物H"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_elements": [{"after": {"coefficients": {"select_b": 1, "select_c": 1}, "meaning": "Division 4.2货物C与Class 8硫酸B不能同车", "name": "division42_sulfuric_acid_conflict", "rhs": 1, "sense": "<="}, "name": "division42_sulfuric_acid_conflict", "op": "add_constraint"}, {"after": {"coefficients": {"select_b": 1, "select_e": 1}, "meaning": "Zone A货物E与Class 8硫酸B不能同车", "name": "zonea_class8_sulfuric_conflict", "rhs": 1, "sense": "<="}, "name": "zonea_class8_sulfuric_conflict", "op": "add_constraint"}, {"after": {"coefficients": {"select_c": 1, "select_e": 1}, "meaning": "Zone A货物E与Division 4.2货物C不能同车", "name": "zonea_division42_conflict", "rhs": 1, "sense": "<="}, "name": "zonea_division42_conflict", "op": "add_constraint"}, {"after": {"coefficients": {"select_d": 1, "select_e": 1}, "meaning": "Zone A货物E与Class 8碱液D不能同车", "name": "zonea_class8_alkali_conflict", "rhs": 1, "sense": "<="}, "name": "zonea_class8_alkali_conflict", "op": "add_constraint"}, {"after": {"coefficients": {"select_e": 1, "select_g": 1}, "meaning": "Zone A货物E与另一票Class 3货物G不能同车", "name": "zonea_second_class3_conflict", "rhs": 1, "sense": "<="}, "name": "zonea_second_class3_conflict", "op": "add_constraint"}, {"after": {"coefficients": {"select_e": 1, "select_h": 1}, "meaning": "Zone A货物E与Division 5.1货物H不能同车", "name": "zonea_division51_conflict", "rhs": 1, "sense": "<="}, "name": "zonea_division51_conflict", "op": "add_constraint"}, {"after": {"coefficients": {"select_b": 1, "select_h": 1}, "meaning": "硫酸B与氧化剂H需要题内未提供的专用分隔，故不能同车", "name": "class8_sulfuric_oxidizer_requires_unavailable_separation", "rhs": 1, "sense": "<="}, "name": "class8_sulfuric_oxidizer_requires_unavailable_separation", "op": "add_constraint"}, {"after": {"coefficients": {"select_d": 1, "select_h": 1}, "meaning": "碱液D与氧化剂H需要题内未提供的专用分隔，故不能同车", "name": "class8_alkali_oxidizer_requires_unavailable_separation", "rhs": 1, "sense": "<="}, "name": "class8_alkali_oxidizer_requires_unavailable_separation", "op": "add_constraint"}, {"after": {"coefficients": {"select_f": 1, "select_h": 1}, "meaning": "Class 3货物F与氧化剂H需要题内未提供的专用分隔，故不能同车", "name": "class3_f_oxidizer_requires_unavailable_separation", "rhs": 1, "sense": "<="}, "name": "class3_f_oxidizer_requires_unavailable_separation", "op": "add_constraint"}], "reason": "旧Patch只为每种法定危险类别关系抽取一个代表组合，遗漏同一类别中其他题列货物的九个交叉约束；题内唯一分隔舱板只服务G/H，其他O组合在可用行动集内不能分隔。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml?part=177"}, {"publisher": "U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration", "url": "https://www.phmsa.dot.gov/regulations/title49/interp/17-0064"}, {"publisher": "U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration", "url": "https://www.phmsa.dot.gov/regulations/title49/interp/03-0300"}], "notes": "以§177.848(a)闭合标签/标牌适用入口，以完整(c)项同时覆盖氰化物/酸、Division 4.2/Class 8及Zone A与Class 3、Class 8、4.2、5.1的全部题列组合；以完整O定义及PHMSA 17-0064、03-0300分别闭合Class 3/5.1与Class 8/5.1。旧Gold只抽取每类一对，现补齐9条遗漏约束。", "official_evidence_override": [{"information_responsibility": "确认题列带相应标签或车辆标牌的危险材料包件进入§177.848隔离规则。", "node_id": "E1", "omission_effect": "缺少E1时，无法把C2的包装标记和危险分类绑定到后续隔离条款。", "publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "quote": "This section applies to materials which meet one or more of the hazard classes defined in this subchapter and are: (1) In packages that must be labeled or placarded in accordance with part 172 of this subchapter; (2) In a compartment within a multi-compartmented cargo tank subject to the restrictions in § 173.33 of this subchapter; or (3) In a portable tank loaded in a transport vehicle or freight container.", "role": "applicability_gate", "source_node_id": "E1", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml?part=177"}, {"information_responsibility": "一次性给出氰化物与酸、Division 4.2与全部Class 8液体、以及Zone A与题列Class 3、Class 8、Division 4.2和5.1货物的禁同车组合。", "node_id": "E2", "omission_effect": "缺少E2时，A/B、B/C、C/D以及E与B/C/D/F/G/H的九个禁同车关系均不能完整推出。", "publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "quote": "In addition to the provisions of paragraph (d) of this section and except as provided in § 173.12(e) of this subchapter, cyanides, cyanide mixtures or solutions may not be stored, loaded and transported with acids if a mixture of the materials would generate hydrogen cyanide; Division 4.2 materials may not be stored, loaded and transported with Class 8 liquids; and Division 6.1 Packing Group I, Hazard Zone A material may not be stored, loaded and transported with Class 3 material, Class 8 liquids, and Division 4.1, 4.2, 4.3, 5.1 or 5.2 materials.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["cyanide_acid_conflict", "division42_class8_conflict", "division42_sulfuric_acid_conflict", "zonea_class3_conflict", "zonea_second_class3_conflict", "zonea_class8_sulfuric_conflict", "zonea_class8_alkali_conflict", "zonea_division42_conflict", "zonea_division51_conflict"], "supported_patch_slots": ["cyanide_acid_conflict", "division42_class8_conflict", "division42_sulfuric_acid_conflict", "zonea_class3_conflict", "zonea_second_class3_conflict", "zonea_class8_sulfuric_conflict", "zonea_class8_alkali_conflict", "zonea_division42_conflict", "zonea_division51_conflict"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml?part=177"}, {"information_responsibility": "定义隔离表O为只有物理分隔足以防止通常泄漏混合时才可同车。", "node_id": "E3", "omission_effect": "缺少E3时，不能把两份PHMSA解释中的O关系转成G/H须启用唯一舱板、而B/H、D/H、F/H因无对应分隔能力而禁同车。", "publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "quote": "The letter “O” in the table indicates that these materials may not be loaded, transported, or stored together in the same transport vehicle or storage facility during the course of transportation unless separated in a manner that, in the event of leakage from packages under conditions normally incident to transportation, commingling of hazardous materials would not occur.", "role": "operative_rule", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["class3_oxidizer_separation", "class8_sulfuric_oxidizer_requires_unavailable_separation", "class8_alkali_oxidizer_requires_unavailable_separation", "class3_f_oxidizer_requires_unavailable_separation"], "supported_patch_slots": ["class3_oxidizer_separation", "class8_sulfuric_oxidizer_requires_unavailable_separation", "class8_alkali_oxidizer_requires_unavailable_separation", "class3_f_oxidizer_requires_unavailable_separation"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml?part=177"}, {"information_responsibility": "确认Class 3与Division 5.1的表格交叉项为O。", "node_id": "E4", "omission_effect": "缺少E4时，F/H禁同车以及G/H使用防混合舱板缺少对应表格单元的官方解释。", "publisher": "U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration", "quote": "The letter \"O\" appears in the entry on the Segregation Table for Class 3 and Division 5.1 materials, which indicates that these materials must be separated to prevent commingling if packages were to leak.", "role": "incorporated_standard", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["class3_oxidizer_separation", "class3_f_oxidizer_requires_unavailable_separation"], "supported_patch_slots": ["class3_oxidizer_separation", "class3_f_oxidizer_requires_unavailable_separation"], "url": "https://www.phmsa.dot.gov/regulations/title49/interp/17-0064"}, {"information_responsibility": "确认Class 8液体与Division 5.1的表格关系要求防泄漏混合分隔，并说明额外的上下或相邻限制。", "node_id": "E5", "omission_effect": "缺少E5时，B/H与D/H因题内没有对应分隔能力而禁同车缺少官方交叉项支持。", "publisher": "U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration", "quote": "The table in § 177.848(d) prohibits a Class 8 corrosive liquid and a Division 5.1 oxidizer from being loaded, transported, or stored together in the same transport vehicle unless the packages are separated so that, in the event of leakage from the packages during transportation, commingling of the hazardous materials will not occur. Further, despite the method of separation employed, Class 8 liquids may not be loaded above or adjacent to Division 5.1 materials (see § 177.848(e)(3)).", "role": "incorporated_standard", "source_node_id": "E5", "support_target_type": "patch_slot", "support_targets": ["class8_sulfuric_oxidizer_requires_unavailable_separation", "class8_alkali_oxidizer_requires_unavailable_separation"], "supported_patch_slots": ["class8_sulfuric_oxidizer_requires_unavailable_separation", "class8_alkali_oxidizer_requires_unavailable_separation"], "url": "https://www.phmsa.dot.gov/regulations/title49/interp/03-0300"}]}`
- 复核说明：危险分类全部移入case facts并泛化货物行动；新增9条遗漏类别交叉约束，修正后的唯一最优组合应为A+C+F、目标107点。

### SWOR-R033

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留八个campaign、基础价值、执行三个、每项32点内部价值、16个action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A在美国生产并于本年度售给无关联客户；B保留俄亥俄生产销售记录；C于本年度售给无关联客户；D在内华达对矿物精矿执行破碎、浸出、分离和精炼后出售；E关联方购入后集成并于本年度售给无关联客户；F设施没有48C申领记录；G在波多黎各生产且已提交关联方选择文件；H在加州从晶圆开始完成电池扩散、金属化、电连接、层压、封装和接线盒组装后出售。", "decision_date": "2026-08-04", "jurisdiction": "美国先进制造生产与销售", "regulated_subject": "选择三个先进制造campaign并记录本年度税务价值的制造商"}`
- C2：`{"boundary_facts": "A在加拿大生产后售给无关联客户；B在俄亥俄生产并出售；C只转入本公司库存且没有下游集成或关联方选择文件；D在内华达对矿物精矿执行破碎、浸出、分离和精炼后出售；E关联方购入后集成并售给无关联客户；F设施有48C申领记录；G在波多黎各生产并已提交关联方选择文件；H仅把进口成品组件换入新纸箱并贴上新标签后出售。", "decision_date": "2026-08-04", "jurisdiction": "美国先进制造生产与销售", "regulated_subject": "选择三个先进制造campaign并记录本年度税务价值的制造商"}`
- C1 不适用原因：C1中A、C、F、H的生产、销售和48C事实均满足45X分支，四个Gold禁止计值约束不加入；C2保留这四项限制。
- 题内行动映射：每个campaign有一个执行行动和一个32点内部价值行动；内部价值行动只可随对应执行行动选择。
- source 精确替换：
  - 旧：`美国先进制造campaign选择。2026年8月4日，Red Mesa Components要从八个campaign中执行三个，并为依法可进入本年度45X申报的每项计入32点内部税务价值。`
  - 新：`美国先进制造campaign选择。2026年8月4日，Red Mesa Components要从八个campaign中执行三个，并可为每个入选campaign选择是否计入32点本年度内部税务价值。`
  - 旧：`A在加拿大生产太阳能组件并于本年度销售给无关联客户，基础净价值35点；B在俄亥俄州生产逆变器并于本年度销售给无关联客户，基础31点；C在美国生产电极材料，但本年度只转入本公司库存，没有对外销售、下游集成或关联方选择，基础34点；D在内华达州对关键矿物完成实质性转化并于本年度销售给无关联客户，基础29点；E在得克萨斯州生产风能部件并销售给关联企业，该部件随后集成到本年度向无关联客户销售的合格风机组件中，基础30点；F在亚利桑那州生产并销售电池部件，但同一设施已经申领48C Advanced Energy Project Credit，基础33点；G在波多黎各生产合格电池组件并销售给关联企业，企业已作出把该关联方视为无关联方的有效选择，基础28点；H在加利福尼亚州仅重新包装进口太阳能组件后于本年度销售给无关联客户，基础32点。`
  - 新：`A、B、C、D、E、F、G、H八个campaign的基础净价值分别为35、31、34、29、30、33、28、32点；生产地点、生产活动、销售链条、关联方申报和48C记录由本case事实给出。`
  - 旧：`所有未述的组件类别和经营条件均满足。`
  - 新：``
  - 旧：`唯一目标是最大化三个campaign的基础净价值与依法可计入45X内部价值之和。`
  - 新：`唯一目标是最大化三个campaign的基础净价值与所选本年度内部税务价值之和。`
  - 旧：`组合须遵守决策日有效的美国Advanced Manufacturing Production Credit规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r033_a01": "执行campaign A", "swor_r033_a02": "为campaign A计入本年度32点内部价值", "swor_r033_a03": "执行campaign B", "swor_r033_a04": "为campaign B计入本年度32点内部价值", "swor_r033_a05": "执行campaign C", "swor_r033_a06": "为campaign C计入本年度32点内部价值", "swor_r033_a07": "执行campaign D", "swor_r033_a08": "为campaign D计入本年度32点内部价值", "swor_r033_a09": "执行campaign E", "swor_r033_a10": "为campaign E计入本年度32点内部价值", "swor_r033_a11": "执行campaign F", "swor_r033_a12": "为campaign F计入本年度32点内部价值", "swor_r033_a13": "执行campaign G", "swor_r033_a14": "为campaign G计入本年度32点内部价值", "swor_r033_a15": "执行campaign H", "swor_r033_a16": "为campaign H计入本年度32点内部价值"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States Internal Revenue Service", "url": "https://www.irs.gov/credits-deductions/advanced-manufacturing-production-credit"}], "notes": "已复核V1.4.4保存的IRS quote，覆盖美国或属地生产、本年度销售、关联方选择/下游销售、实质转化以及48C设施排除。"}`
- 复核说明：八个campaign的分类事实移入case facts并泛化16个行动。

### SWOR-R034

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四个托盘、Red/Blue二选一分配、八个处理价值、Red至少处理A/C/D中两个、车辆结构、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至D的外包装和运输文件分别标明limited quantity或excepted quantity；外包装没有危险标签，车辆没有危险标牌。两辆车内没有独立运输车辆或储存设施。", "decision_date": "2026-08-04", "jurisdiction": "美国公路化工成品运输", "regulated_subject": "把四个密封成品托盘分配到两辆封闭货车的工厂"}`
- C2：`{"boundary_facts": "A仅为Class 3，B仅为Division 6.1/PG I/Hazard Zone A，C仅为Division 5.2，D仅为Division 4.1；托盘展示对应危险标签。两辆车内没有独立运输车辆或储存设施。", "decision_date": "2026-08-04", "jurisdiction": "美国公路危险材料运输", "regulated_subject": "把四个危险材料托盘分配到两辆封闭运输车的工厂"}`
- C1 不适用原因：C1四票均以limited/excepted quantity形式交运且没有独立标签或标牌，Gold的六个车辆内隔离组合约束不加入。
- 题内行动映射：八项行动按A至D顺序分别表示分配至Red或Blue；每托盘恰选一线，并保留Red线客户批次下限。
- source 精确替换：
  - 旧：`危险品出厂装载线分配。2026年8月4日，美国星港化工厂要把四个已按所述危险类别贴签、均为待售成品而非废物的密封成品托盘分别且仅分配给Red或Blue两条出厂装载线；每条线对应一辆普通封闭运输车，托盘一经分配即装入该车；根据既定客户批次，Red线至少处理A、C、D中的两个。`
  - 新：`出厂装载线分配。2026年8月4日，美国星港工厂要把四个密封成品托盘分别且仅分配给Red或Blue两条出厂装载线；每条线对应一辆普通封闭运输车，托盘一经分配即装入该车；托盘运输分类和包装标记由本case事实给出，根据既定客户批次，Red线至少处理A、C、D中的两个。`
  - 旧：`A仅属于Class 3易燃液体，分配给Red或Blue线的出厂处理价值分别为60点、55点；B仅属于Division 6.1、包装等级I、危险区A的有毒液体，对应价值59点、49点；C仅属于Division 5.2有机过氧化物，对应价值58点、50点；D仅属于Division 4.1易燃固体，对应价值57点、51点。`
  - 新：`A、B、C、D分配给Red/Blue线的处理价值分别为60/55、59/49、58/50、57/51点；各托盘的物质属性、危险类别和数量包装标记由本case事实给出。`
  - 旧：`装载方案须遵守决策日有效的美国联邦公路危险材料隔离规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r034_a01": "将Class 3托盘A装上Red车", "swor_r034_a02": "将Class 3托盘A装上Blue车", "swor_r034_a03": "将Division 6.1托盘B装上Red车", "swor_r034_a04": "将Division 6.1托盘B装上Blue车", "swor_r034_a05": "将Division 5.2托盘C装上Red车", "swor_r034_a06": "将Division 5.2托盘C装上Blue车", "swor_r034_a07": "将Division 4.1托盘D装上Red车", "swor_r034_a08": "将Division 4.1托盘D装上Blue车"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States Pipeline and Hazardous Materials Safety Administration", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "已复核V1.4.4保存的49 CFR quote，覆盖隔离表的X组合、普通车辆内共同装载以及limited/excepted quantity标签边界。"}`
- 复核说明：危险类别与数量包装标记移入case facts；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R035

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留七个取件点、价值、选四个、共享处理单元H及成本、同一路线、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B均已清除残留并吹扫蒸气；C已重新装入非危险材料；D只留有限数量残留；E、F只留无次要危险的Division 2.2非易燃气体且都不是无水氨，20°C表压均为180 kPa；G从未装料。A至G原危险标记均已移除或覆盖。", "decision_date": "2026-08-04", "jurisdiction": "美国空包装公路回收", "regulated_subject": "在同一路线上选择四个空包装取件点的私人车队"}`
- C2：`{"boundary_facts": "A仍有危险残留且原标记可见；B已清除残留并吹扫；C已重新装入非危险材料；D只有limited quantity残留且标记已移除；E为非无水氨Division 2.2残留、20°C表压180 kPa且标记已移除；F含无水氨残留；G从未装料但原标记可见。", "decision_date": "2026-08-04", "jurisdiction": "美国空包装危险材料运输", "regulated_subject": "在同一路线上选择四个空包装取件点的私人车队"}`
- C1 不适用原因：C1的A、F、G也具备清洁、气体种类/压力或去标记事实，三个Gold的H处理蕴含约束均不加入；C2仍对A、F、G使用H。
- 题内行动映射：前七项选取件点；H是一套能同时覆盖所有入选容器的准备、单证、标记和操作能力。
- source 精确替换：
  - 旧：`A是仍有危险材料残留、原危险标记完整且运输中可见的空桶，取件价值60点；B已充分清除残留并吹扫蒸气，危险标记已移除，57点；C已重新装入非危险材料，使残留不再造成危险，危险标记已移除，56点；D只含限量危险材料残留，不属于危险物质、危险废物或海洋污染物，危险标记已移除，45点；E只含无次要危险性的2.2项非易燃气体残留，不是无水氨，在20摄氏度时表压低于200 kPa，也不属于危险物质、危险废物或海洋污染物，危险标记已移除，44点；F含无水氨残留，59点；G从未装料，但运输中可见且原危险标记仍暴露，58点。除上述事实外不适用其他空包装例外。`
  - 新：`A、B、C、D、E、F、G七个取件点的价值分别为60、57、56、45、44、59、58点；各容器的残留、吹扫、重新装料、压力、气体种类和运输标记由本case事实给出。`
  - 旧：`启用H会完成仍按原装物运输时所需的准备、单证、标记和操作，使净路线价值减少30点。`
  - 新：`启用H会为全部入选容器提供一套共享的准备、单证、标记和操作服务，使净路线价值减少30点。`
  - 旧：`方案须遵守决策日有效的美国联邦危险材料空包装运输规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r035_a01": "提取带残留空桶A", "swor_r035_a02": "提取清洗吹扫空桶B", "swor_r035_a03": "提取安全再填充空桶C", "swor_r035_a04": "提取限量残留空桶D", "swor_r035_a05": "提取低压2.2项气瓶E", "swor_r035_a06": "提取无水氨残留气瓶F", "swor_r035_a07": "提取标记未移除的未用包装G", "swor_r035_a08": "启用完整危险品运输处理单元H"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States Pipeline and Hazardous Materials Safety Administration", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "已复核V1.4.4保存的49 CFR quote，覆盖空包装按原内容物运输、清洁吹扫、重新装料、limited quantity、Division 2.2压力/无水氨及去标记分支。"}`
- 复核说明：七个容器状态移入case facts并去除source中的法律结论；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R036

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留六名司机独立计划、收益、重型货车、欧盟境内、接受两项、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A为日常正常休息，两次移动各0.4小时并有卧铺客舱；B为日常正常休息，两次各0.4小时并有卧铺；C为缩短周休，两次0.5/0.4小时并有卧铺；D、E、F均为正常周休、两次各0.4小时、航程9小时并有卧铺客舱或床铺。", "decision_date": "2026-08-04", "jurisdiction": "欧盟境内重型货车轮渡运输", "regulated_subject": "选择两项不同司机轮渡休息计划的欧盟公路承运人"}`
- C2：`{"boundary_facts": "A为日常正常休息且两次移动共1.2小时；B为日常正常休息且共0.8小时；C为缩短周休且共0.9小时；D为正常周休、航程7小时并有卧铺；E为正常周休、航程9小时但无卧铺客舱、床铺或卧铺；F为正常周休、航程9小时并有卧铺。", "decision_date": "2026-08-04", "jurisdiction": "欧盟境内重型货车轮渡运输", "regulated_subject": "选择两项不同司机轮渡休息计划的欧盟公路承运人"}`
- C1 不适用原因：C1的A总中断0.8小时、D/E航程9小时且有睡眠设施，Gold对A、D、E的三个排除均不加入；C2保留三项排除。
- 题内行动映射：六个行动分别接受一名司机的完整独立计划；计划收益直接相加且必须恰选两项。
- source 精确替换：
  - 旧：`A在日常正常休息中两次移动车辆上下轮渡，每次0.6小时，共1.2小时，司机有独立卧铺客舱，运输收益75点。B也使用日常正常休息，两次各0.4小时，共0.8小时，司机有卧铺，收益68点。C使用缩短周休，两次分别0.5小时和0.4小时，司机有卧铺客舱，收益65点。D使用正常周休，两次各0.4小时，司机有卧铺客舱，但轮渡计划航程为7小时，收益72点。E使用正常周休，两次各0.4小时，计划航程9小时，但船上不向司机提供卧铺客舱、床铺或卧铺，收益70点。F使用正常周休，两次各0.4小时，计划航程9小时并提供卧铺客舱，收益62点。`
  - 新：`A、B、C、D、E、F六项计划的运输收益分别为75、68、65、72、70、62点；休息类型、两次移动时长、轮渡航程和睡眠设施由本case事实给出。`
  - 旧：`计划选择须遵守决策日有效的欧盟轮渡或列车运输期间驾驶员休息规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r036_a01": "接受日常正常休息被两次各0.6小时打断的轮渡计划A", "swor_r036_a02": "接受日常正常休息被两次各0.4小时打断且有卧铺的轮渡计划B", "swor_r036_a03": "接受缩短周休被0.5小时和0.4小时打断且有客舱的轮渡计划C", "swor_r036_a04": "接受航程7小时且有客舱的正常周休轮渡计划D", "swor_r036_a05": "接受航程9小时但没有卧铺设施的正常周休轮渡计划E", "swor_r036_a06": "接受航程9小时且有客舱的正常周休轮渡计划F"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "European Union, Your Europe", "url": "https://europa.eu/youreurope/citizens/work/work-abroad/rules-working-road-transport/index_en.htm"}], "notes": "已复核V1.4.4保存的Your Europe quote，覆盖轮渡期间最多两次中断、总计不超1小时、正常周休航程至少8小时及睡眠设施条件。"}`
- 复核说明：计划物理事实移入case facts，收益不变；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R037

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留七个空乘排班、覆盖价值、计划时长、选两个、part-121主体、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "每个排班所用机型的运行规格表列明基础空乘人数4。A为13小时/4人/休10小时；B、C为15小时/5人/休12小时；D、E为17小时/6人/休12小时；F、G为19小时/7人/休12小时，且两者都含有在48个相邻州及DC之外起飞或降落的航班。", "decision_date": "2026-08-04", "jurisdiction": "美国14 CFR Part 121航空运行", "regulated_subject": "选择两个计划空乘排班的Part 121合格证持有人"}`
- C2：`{"boundary_facts": "每个排班所用机型的运行规格表列明基础空乘人数4。A为13小时/4人/休10小时；B为15小时/5人/休12小时，C为15小时/4人/休12小时；D为17小时/6人/休12小时，E为17小时/5人/休12小时；F、G均为19小时/7人/休12小时，F有域外航班，G全部航班仅在48个相邻州及DC内起降。", "decision_date": "2026-08-04", "jurisdiction": "美国14 CFR Part 121航空运行", "regulated_subject": "选择两个计划空乘排班的Part 121合格证持有人"}`
- C1 不适用原因：C1的C、E补足增员，G也具有域外航班事实，Gold对C、E、G的三个排除均不加入；C2保留。
- 题内行动映射：七个行动各自选择一个完整空乘排班，题面要求恰选两个，覆盖价值直接相加。
- source 精确替换：
  - 旧：`A值勤13小时，按最低人数配备，随后连续休息10小时，覆盖价值60点；B值勤15小时，比最低人数多1名空乘，随后连续休息12小时，价值58点；C同样值勤15小时但只按最低人数配备，随后连续休息12小时，价值73点。D值勤17小时，比最低人数多2名空乘，随后连续休息12小时，价值57点；E值勤17小时，只比最低人数多1名，随后连续休息12小时，价值71点。F值勤19小时，比最低人数多3名，排班中包含在美国48个相邻州和哥伦比亚特区之外起飞或降落的航班，随后连续休息12小时，价值56点；G也值勤19小时并多3名空乘，但所有航班都只在美国48个相邻州和哥伦比亚特区内起降，随后连续休息12小时，价值72点。`
  - 新：`A、B、C、D、E、F、G七个排班的覆盖价值分别为60、58、73、57、71、56、72点；计划值勤时长、超过最低编制的人数、连续休息和航班地理范围由本case事实给出。`
  - 旧：`所有时长都是事先计划值，不存在承运人无法控制的延误，也没有题面未列出的减休安排。`
  - 新：`所有时长都是事先计划值；运行记录中没有承运人无法控制的延误，排班记录中也没有其他减休安排。`
  - 旧：`排班须遵守决策日有效的美国联邦空乘值勤与休息规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r037_a01": "选择候选排班A", "swor_r037_a02": "选择候选排班B", "swor_r037_a03": "选择候选排班C", "swor_r037_a04": "选择候选排班D", "swor_r037_a05": "选择候选排班E", "swor_r037_a06": "选择候选排班F", "swor_r037_a07": "选择候选排班G"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States eCFR / Federal Aviation Administration", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml"}, {"publisher": "U.S. Federal Aviation Administration / eCFR", "url": "https://www.ecfr.gov/current/title-14/section-121.467"}], "notes": "已复核V1.4.4保存的14 CFR quote，覆盖13/15/17/19小时计划值勤所需增员、连续休息和19小时域外航班边界。"}`
- 复核说明：排班编制与航班地理事实移入case facts；把题面排除性法律结论改为运行与排班记录中的可观察事实；将7个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R038

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留14/15小时值勤收益、两种编制包及成本、10/12小时休息及成本、各选一项、action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "机型运行规格表列明基础空乘人数4；编制包M安排5人，编制包E安排6人。以所选15小时值勤结束为t=0，连续休息排在t=0—10，下一段值勤排在t=10—20且长度10小时，随后连续休息排在t=20—34。", "decision_date": "2026-08-04", "jurisdiction": "美国国内航空承运人运行", "regulated_subject": "选择一段空乘值勤、编制包和连续休息的国内合格证持有人"}`
- C2：`{"boundary_facts": "机型运行规格表列明基础空乘人数4；编制包M安排4人，编制包E安排5人。以所选15小时值勤结束为t=0，连续休息排在t=0—10；从t=10起的后续72小时排班没有长度达到14小时的连续休息。", "decision_date": "2026-08-04", "jurisdiction": "美国国内航空承运人运行", "regulated_subject": "选择一段空乘值勤、编制包和连续休息的国内合格证持有人"}`
- C1 不适用原因：C1的M已自带一名增员，且10小时休息后有固定14小时补偿，Gold的15小时→E和10小时→12小时两个约束均不加入。
- 题内行动映射：前两项选择值勤长度，中两项选择编制包M/E，后两项选择连续休息10/12小时；case facts给出包内实际增员和后续补偿安排。
- source 精确替换：
  - 旧：`最低乘务员编制成本0点，增加一名乘务员成本4点；10小时休息成本0点，12小时休息成本5点。`
  - 新：`编制包M成本0点，编制包E成本4点；M和E相对监管最低编制的实际人数由本case事实给出。10小时休息成本0点，12小时休息成本5点。`
  - 旧：`没有安排缩短休息后的补偿性14小时休息，其余长值勤所需运行条件均满足。`
  - 新：`缩短休息后的后续排班记录与其他长值勤运行条件由本case事实给出。`
  - 旧：`排班须符合决策日适用于国内承运人和值勤长度的美国联邦规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r038_a01": "安排14小时值勤", "swor_r038_a02": "安排15小时值勤", "swor_r038_a03": "采用最低乘务员编制", "swor_r038_a04": "增加一名乘务员", "swor_r038_a05": "安排10小时连续休息", "swor_r038_a06": "安排12小时连续休息"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Aviation Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml"}], "notes": "已闭合V1.4.4的例外节点缺口：保留原E1—E3，并新增E4完整覆盖121.467(b)(8)—(9)。C1的14小时后续休息在t=20开始，满足t≤24；t=10—20的下一值勤为10小时，不超过14小时。Gold模型不变。", "official_evidence_override": [{"information_responsibility": "超过14小时且不超过20小时的值勤期后通常须安排至少12小时连续休息。", "node_id": "E1", "omission_effect": "缺少E1时，无法得到duty15_requires_rest12的通常分支。", "publisher": "Federal Aviation Administration / eCFR", "quote": "Except as provided in paragraph (b)(8) of this section, a flight attendant scheduled to a duty period of more than 14 hours but no more than 20 hours, as provided in paragraphs (b)(4), (b)(5), and (b)(6) of this section, must be given a scheduled rest period of at least 12 consecutive hours.", "role": "aggregation_scope", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["duty15_requires_rest12"], "supported_patch_slots": ["duty15_requires_rest12"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml"}, {"information_responsibility": "§121.1确认题面国内承运人的运行位于Part 121主体范围。", "node_id": "E2", "omission_effect": "缺少E2时，无法把题面国内承运人绑定到§121.467。", "publisher": "U.S. Federal Aviation Administration / eCFR", "quote": "This part prescribes rules governing the domestic, flag, and supplemental operations of each person who holds or is required to hold an Air Carrier Certificate or Operating Certificate under part 119 of this chapter.", "role": "jurisdiction", "source_node_id": "E3", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml"}, {"information_responsibility": "超过14小时且不超过16小时的空乘值勤期须增加至少1名空乘。", "node_id": "E3", "omission_effect": "缺少E3时，无法得到duty15_requires_extra。", "publisher": "Federal Aviation Administration / eCFR", "quote": "A certificate holder conducting domestic, flag, or supplemental operations may assign a flight attendant to a scheduled duty period of more than 14 hours, but no more than 16 hours, if the certificate holder has assigned to the flight or flights in that duty period at least one flight attendant in addition to the minimum flight attendant complement required for the flight or flights in that duty period under the certificate holder's operations specifications.", "role": "operative_rule", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["duty15_requires_extra"], "supported_patch_slots": ["duty15_requires_extra"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml"}, {"information_responsibility": "确认12小时休息可在后续14小时休息于缩短休息开始后24小时内开始且该24小时内后续值勤不超过14小时时缩短为10小时。", "node_id": "E4", "omission_effect": "缺少E4时，无法判断C1是否从duty15_requires_rest12的通常分支转入(b)(8)—(9)例外。", "publisher": "Federal Aviation Administration / eCFR", "quote": "(8) The rest period required under paragraph (b)(7) of this section may be scheduled or reduced to 10 consecutive hours if the flight attendant is provided a subsequent rest period of at least 14 consecutive hours; this subsequent rest period must be scheduled to begin no later than 24 hours after the beginning of the reduced rest period and must occur between the completion of the scheduled duty period and the commencement of the subsequent duty period. (9) Notwithstanding paragraphs (b)(4), (b)(5), and (b)(6) of this section, if a certificate holder conducting domestic, flag, or supplemental operations elects to reduce the rest period to 10 hours as authorized by paragraph (b)(8) of this section, the certificate holder may not schedule a flight attendant for a duty period of more than 14 hours during the 24-hour period commencing after the beginning of the reduced rest period.", "role": "exception", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["duty15_requires_rest12"], "supported_patch_slots": ["duty15_requires_rest12"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml"}]}`
- 复核说明：已用E4闭合121.467(b)(8)—(9)证据缺口，并把C1改成t=0—10休息、t=10—20十小时值勤、t=20—34补偿休息的完整时序；Gold模型不变；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R039

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留六项零售服务、价值、上线两项、共享互联协商与接入实施包及成本、非BT小型提供商、action ID和最大化目标。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A至F全部只在公司的封闭客户专网内传输；没有呼叫在公共交换电话网发起或终止，服务不分配公共编号，也没有与其他英国网络互联的技术接口或请求。", "decision_date": "2026-08-04", "jurisdiction": "英国托管通信服务市场", "regulated_subject": "上线两个零售托管包的非BT小型通信提供商"}`
- C2：`{"boundary_facts": "A为可跨英国网络互拨的固定语音，B为可跨网互拨的移动语音，C使用070号码并接收和发出英国固定或移动网络来话；D至F只传数据。其他英国网络已向A、B、C分别提交书面互联请求，三份请求文件分别写明仅在对应业务入选上线时生效，响应期限均落在本期；公司没有其他互联协商人员、流程或技术实施设施。", "decision_date": "2026-08-04", "jurisdiction": "英国公共固定和移动通信市场", "regulated_subject": "上线两项公共零售服务的非BT小型通信提供商"}`
- C1 不适用原因：C1六项均为封闭专网托管服务且不与PSTN或其他网络互联，也没有外部互联请求，Gold对A/B/C启用互联包的约束不修改模型。
- 题内行动映射：前六项选择两项零售服务；第七项是对所有入选A/B/C的书面互联请求开展协商、缔结协议并实施跨网终止与呼叫互联的唯一共享包。
- source 精确替换：
  - 旧：`并决定是否启用一套批发通话互联接入网关。`
  - 新：`并决定是否启用一套批发通话互联协商与接入实施包。`
  - 旧：`A是可与其他英国网络互拨的固定语音服务，服务价值78点；B是可与其他英国网络互拨的移动语音服务，75点；C是需要接收和发出英国固定或移动网络来话的070个人号码通话服务，72点。D是仅传输数据的企业光纤服务，69点；E是仅传输数据的托管物联网服务，66点；F是仅传输数据的云连接服务，62点。`
  - 新：`A、B、C三项通信服务的价值分别为78、75、72点，网络端点、编号资源和互联路径由本case事实给出。D、E、F分别为企业光纤、托管物联网和云连接数据服务，价值69、66、62点。`
  - 旧：`三项通话业务均通过公司自有公共电子通信网络向英国公众提供，其他英国网络已分别提出合理互联请求；公司当前没有其他可用于英国跨网来话终止或呼叫互联的设施；启用题列网关可同时支撑全部所选通话服务，对净服务价值的贡献为-45点，即消耗45点。`
  - 新：`题列互联包是公司对入选A、B、C业务的书面互联请求开展协商、缔结协议并实施英国跨网来话终止和呼叫互联的唯一资源，对净服务价值的贡献为-45点，即消耗45点；公司的现有网络和外部请求记录由本case事实给出。`
  - 旧：`服务组合须遵守2026年4月1日起适用于本公司的英国通话终止、网络接入和互联规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r039_a01": "上线英国固定语音服务A", "swor_r039_a02": "上线英国移动语音服务B", "swor_r039_a03": "上线英国070个人号码通话服务C", "swor_r039_a04": "上线仅数据的企业光纤服务D", "swor_r039_a05": "上线仅数据的托管物联网服务E", "swor_r039_a06": "上线仅数据的云连接服务F", "swor_r039_a07": "启用唯一的互联协商与接入实施包（含书面请求响应、协议缔结与技术互联实施）"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Office of Communications (Ofcom)", "url": "https://www.ofcom.org.uk/siteassets/resources/documents/phones-telecoms-and-internet/information-for-industry/general-authorisation-regime/general-conditions-of-entitlement---unofficial-consolidate-version.pdf?v=415458"}, {"publisher": "UK Office of Communications (Ofcom)", "url": "https://www.ofcom.org.uk/phones-and-broadband/telecoms-infrastructure/consultation-reviews-call-termination-markets"}], "notes": "以Ofcom General Condition A1.2完整原句替换页面摘要，明确Regulated Provider在其他公共网络提供商提出请求时须协商并以缔结互联协议为目标；E2继续定义固定、移动及070来话终止。题内唯一互联包把协商、缔约和技术实施能力闭合到三条现有Patch。", "official_evidence_node_overrides": [{"information_responsibility": "要求Regulated Provider在其他公共网络提供商请求范围内协商，并以在合理期间内缔结互联协议为目标。", "node_id": "E1", "omission_effect": "缺少E1时，三份条件生效的书面请求不能推出A、B、C各自必须占用唯一互联协商与实施包。", "publisher": "UK Office of Communications (Ofcom)", "quote": "Any Regulated Provider shall, to the extent requested by any other provider of a Public Electronic Communications Network, negotiate with that provider with a view to concluding an agreement for Interconnection (or an amendment to an existing agreement for Interconnection) within a reasonable period.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["fixed_voice_requires_interconnection_gateway", "mobile_voice_requires_interconnection_gateway", "personal_070_requires_interconnection_gateway"], "supported_patch_slots": ["fixed_voice_requires_interconnection_gateway", "mobile_voice_requires_interconnection_gateway", "personal_070_requires_interconnection_gateway"], "url": "https://www.ofcom.org.uk/siteassets/resources/documents/phones-telecoms-and-internet/information-for-industry/general-authorisation-regime/general-conditions-of-entitlement---unofficial-consolidate-version.pdf?v=415458"}]}`
- 复核说明：公共/封闭网络事实移入case facts；把a07、source、IR同步为唯一互联协商与接入实施包，并把C2请求写成随对应业务入选生效的本期书面请求；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R040

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L7。
- 保持：保留八个响应包贡献、恰选三个、每包10点立即停止加速、类别其他条件、16个action ID和最大化目标。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B为包裹配送通知，均在请求后第6个工作日前停止；C为服刑人员collect call计费安排通知、D为金融机构欺诈通知，二者均在收到请求时立即停止；E医疗提醒立即停止；F、G传真广告均在请求后第30天停止；H包裹通知第5个工作日停止。", "decision_date": "2026-08-04", "jurisdiction": "美国自动通信与传真服务", "regulated_subject": "选择三个退订响应包的通信合规中心"}`
- C2：`{"boundary_facts": "A、B为包裹配送通知，分别在请求后第7和第6个工作日停止；C为服刑人员collect call计费安排通知、D为金融机构欺诈通知，均在请求次日停止；E医疗提醒立即停止；F、G的传真收件人均通过通知中列明的退订号码提交停止传真请求，系统记录含接收日期和号码，二者分别在第30和31天停止；H包裹通知第5个工作日停止。", "decision_date": "2026-08-04", "jurisdiction": "美国自动通信与传真服务", "regulated_subject": "选择三个退订响应包的通信合规中心"}`
- C1 不适用原因：C1的A/C/D/G停止时间分别改为第6工作日、立即、立即和第30天，Gold要求这四包联动加速的约束均不加入；C2保留。
- 题内行动映射：前八项选择三个响应包；后八项与A—H一一对应，把该包原停止计划改为收到请求时立即停止并扣10点。
- source 精确替换：
  - 旧：`若原停止日期不符合适用要求，可执行成本10点的立即停止加速；未承接响应包不能加速。`
  - 新：`可为任一已承接响应包执行成本10点的立即停止加速；未承接响应包不能加速。`
  - 旧：`A是包裹配送通知，在收件人退订请求后第7个工作日停止，贡献35点；B同类通知在第6个工作日停止，31点；C是未成功服刑人员collect call后的计费安排通知，在退订请求后次日停止，34点；D是金融机构欺诈风险通知，在客户退订请求后次日停止，33点；E是医疗预约提醒，收到患者退订请求时立即停止，30点；F是有既有业务关系的传真广告，在合格退订请求后第30天停止，29点；G同类传真广告在第31天停止，32点；H包裹配送通知在第5个工作日停止，28点。`
  - 新：`A、B、C、D、E、F、G、H八个响应包的贡献分别为35、31、34、33、30、29、32、28点；通知类别、退订请求记录和原计划停止时间由本case事实给出。`
  - 旧：`执行须遵守决策日有效的美国联邦通信退订处理规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r040_a01": "选择响应包A", "swor_r040_a02": "选择响应包B", "swor_r040_a03": "选择响应包C", "swor_r040_a04": "选择响应包D", "swor_r040_a05": "选择响应包E", "swor_r040_a06": "选择响应包F", "swor_r040_a07": "选择响应包G", "swor_r040_a08": "选择响应包H"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml?part=64"}], "notes": "已复核V1.4.4保存的47 CFR quote；E1/E2改为带完整法定主语、请求对象和期限的连续原句，E3—E5继续支持collect-call、金融欺诈和医疗提醒分支。", "official_evidence_node_overrides": [{"information_responsibility": "传真广告发送方收到合格停止请求后须在最短合理时间且不超过30日内执行，并在后续明示许可前停止发送。", "node_id": "E1", "omission_effect": "缺少E1时，G在第31日停止为何必须联动立即停止加速无法确定。", "publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "quote": "A sender that receives a request not to send future unsolicited advertisements that complies with paragraph (a)(4)(v) of this section must honor that request within the shortest reasonable time from the date of such request, not to exceed 30 days, and is prohibited from sending unsolicited advertisements to the recipient unless the recipient subsequently provides prior express invitation or permission to the sender.", "role": "operative_rule", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["required_preparation_g"], "supported_patch_slots": ["required_preparation_g"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml?part=64"}, {"information_responsibility": "包裹配送公司须提供退订能力，并在请求日起合理时间且不超过六个工作日内执行。", "node_id": "E2", "omission_effect": "缺少E2时，A原定第七工作日停止为何必须联动立即停止加速无法确定。", "publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "quote": "The package delivery company must offer package recipients the ability to opt out of receiving future delivery notification calls and messages and must honor an opt-out request within a reasonable time from the date such request is made, not to exceed six business days;", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["required_preparation_a"], "supported_patch_slots": ["required_preparation_a"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml?part=64"}]}`
- 复核说明：通知类别与停止时间移入case facts，泛化前八个行动；补齐传真与包裹退订节点的完整法定主语和期限原句。

### SWOR-R041

- 结论：`FIX`；问题类型：L1, L2, L3, L7。
- 保持：保留决策日、辖区、12个行动ID与类型、四个机场时段、分配结构、成本、目标和现有Gold Patch/IR。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "F1、F2、F3均由外国国家航空器执行，并分别持有覆盖所列机场及时段的外交许可；三项任务的其他飞行许可材料齐全。", "decision_date": "2026-08-04", "jurisdiction": "新加坡民航；樟宜机场与实里达机场", "regulated_subject": "为三项非定期飞行分配樟宜或实里达机场时段的航空运营人"}`
- C2：`{"boundary_facts": "F1是在导航设备维护后执行的雷达与NAVAID校验飞行；F2用于转送一名生命垂危的病人；F3由商业包机公司按国防供应合同运送军用备件，飞机不由军方所有或运营。C为星期二09:45的实里达机场时段。樟宜协调团队本轮不再受理新的SCR/GCR申请。", "decision_date": "2026-08-04", "jurisdiction": "新加坡民航；樟宜机场与实里达机场", "regulated_subject": "为三项非定期飞行分配樟宜或实里达机场时段的航空运营人"}`
- C1 不适用原因：CAAS AIP对外交许可飞行设置樟宜时刻与实里达训练时段的例外；C1三项飞行均具有该客观身份，现有三个禁用Patch不适用。
- 题内行动映射：F1至F3仍各选一个A至D时段；外部规则只决定具体任务—时段组合是否可用，不改变成本与分配结构。
- source 精确替换：
  - 旧：`F1是在导航设备维护后执行雷达与NAVAID校验；F2把一名生命垂危的病人从离岛转送到医院；F3由商业包机公司按国防供应合同运送军用备件，承运飞机并非军方自有或运营。四个单元分别为：A=樟宜机场09:45，B=樟宜机场12:30，C=实里达机场09:45，D=实里达机场11:00；C处在CAAS公布的星期二训练飞行时段内。樟宜机场的协调团队已结束本轮排班，不再处理新增的SCR/GCR时刻申请，A和B仍保留在本轮候选单元中。`
  - 新：`F1、F2、F3的飞行性质、运营方式和许可材料由任务档案给出。四个单元分别为：A=樟宜机场09:45，B=樟宜机场12:30，C=实里达机场09:45，D=实里达机场11:00。任务是否需要为A、B另行取得时刻由任务性质和已有许可材料决定。`
  - 旧：`方案须符合截至决策日有效的新加坡民航局AIP GEN 1.2。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Civil Aviation Authority of Singapore (CAAS)", "url": "https://aim-sg.caas.gov.sg/aim-content/uploads/aip/09-JUL-2026/AIP/2026-07-09-000000/html/eAIP/SG-GEN-1.2-en-GB.html"}], "notes": "已核对官方AIP 2.1、2.6、3.8.1与3.8.3；现有quote与三个Patch slot的范围一致。"}`
- 复核说明：将原list型boundary_facts统一为中文事实字符串；未发现需改Gold或IR的证据。

### SWOR-R042

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L7。
- 保持：保留决策日、辖区、15个行动ID与类型、三个站点、五类设备、匹配效益、唯一分配、临时批准集中度政策、目标和现有Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至E均为美国境内生产的RiverLink RL系列路由器；五个型号均未出现在FCC 2026年6月附件的具名型号清单中。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "为三个关键基础设施应急站部署路由器的美国公用事业运营商"}`
- C2：`{"boundary_facts": "A为Netgear Nighthawk RAX系列，B为Adtran Service Delivery Gateway，C为Arcadyan制造的Verizon CE1000A，D为美国境内生产的RiverLink RL-8，E为外国生产的Pioneer PX-5。E没有DoW或DHS Conditional Approval；A、B、C的批准期限分别按FCC 2026年6月附件所列日期记录。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "为三个关键基础设施应急站部署路由器的美国公用事业运营商"}`
- C1 不适用原因：FCC Covered List路由器分支及附件中的临时批准期限均依赖生产地、批准材料和具名型号；C1五台均为未列名的美国境内产品，现有四个Patch不适用。
- 题内行动映射：题内连续运行政策把项目结束前到期的批准设备限制为至多一台；外部证据只确定A至E的设备属性和可部署性。
- source 精确替换：
  - 旧：`候选为Netgear Nighthawk RAX系列、Adtran Service Delivery Gateway、Arcadyan制造的Verizon CE1000A、美国本土生产的RiverLink RL-8，以及在外国生产且未取得DoW或DHS专项批准的Pioneer PX-5。`
  - 新：`候选路由器记为A、B、C、D、E；其型号、生产地和批准材料记录在本次采购档案中。`
  - 旧：`部署须遵守决策日有效的美国FCC通信设备授权规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r042_a01": "向北区应急站部署路由器A", "swor_r042_a02": "向北区应急站部署路由器B", "swor_r042_a03": "向北区应急站部署路由器C", "swor_r042_a04": "向北区应急站部署路由器D", "swor_r042_a05": "向北区应急站部署路由器E", "swor_r042_a06": "向东区应急站部署路由器A", "swor_r042_a07": "向东区应急站部署路由器B", "swor_r042_a08": "向东区应急站部署路由器C", "swor_r042_a09": "向东区应急站部署路由器D", "swor_r042_a10": "向东区应急站部署路由器E", "swor_r042_a11": "向西区应急站部署路由器A", "swor_r042_a12": "向西区应急站部署路由器B", "swor_r042_a13": "向西区应急站部署路由器C", "swor_r042_a14": "向西区应急站部署路由器D", "swor_r042_a15": "向西区应急站部署路由器E"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Communications Commission", "url": "https://docs.fcc.gov/public/attachments/DA-26-585A1.pdf"}], "notes": "复核V1.4.4保存的Covered List范围、三组具名临时批准及到期日quote；未改Patch。"}`
- 复核说明：为消除C1/C2型号冲突，将公开行动meaning泛化为路由器A至E。

### SWOR-R043

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留决策日、辖区、7个行动ID与类型、五选三、五项贡献、两个作业单元成本、互斥关系、目标和现有Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "订单A至E使用的溶剂分别为丙酮、乙醇、异丙醇、正庚烷和乙酸乙酯；五项订单均不含四氯乙烯（CAS 127-18-4）。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "2028年7月起执行五类化工作业的美国非联邦特种化工厂"}`
- C2：`{"boundary_facts": "订单A以四氯乙烯作为制冷剂生产中间体，B使用四氯乙烯蒸气脱脂，C进行有限实验室分析，D使用四氯乙烯清洗带电设备，E调配含四氯乙烯的消费级制动清洁剂。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "2028年7月起执行五类化工作业的美国非联邦特种化工厂"}`
- C1 不适用原因：EPA PCE风险管理规则以四氯乙烯的物质身份和用途为前提；C1五项订单均使用明确的非PCE溶剂，现有五个PCE Patch不适用。
- 题内行动映射：北翼单元为A/B/D提供职业暴露控制能力，南翼单元为C提供实验分析控制能力，D可用任一单元；E没有题内替代执行单元。
- source 精确替换：
  - 旧：`美国特种化工订单选择。2026年8月4日，蓝岭材料公司的非联邦工厂规划在2028年7月1日开始一轮PCE作业，要从五个订单中恰好承接三个：以PCE为中间体生产制冷剂、PCE蒸气脱脂、PCE实验室分析、PCE带电电气设备清洗，以及含PCE消费级制动清洁剂调配，业务贡献依次为18、17、16、15、20点。`
  - 新：`美国特种化工订单选择。2026年8月4日，蓝岭材料公司的非联邦工厂规划在2028年7月1日开始一轮化工作业，要从订单A至E中恰好承接三个，业务贡献依次为18、17、16、15、20点；各订单所用物质和用途记录在订单及工艺档案中。`
  - 旧：`工厂可启用北翼密闭生产单元或南翼分析作业单元，启用成本分别为7点和5点；未承接订单时不能单独启用作业单元。`
  - 新：`工厂可启用北翼职业暴露控制单元或南翼实验分析控制单元，启用成本分别为7点和5点；北翼可服务订单A、B、D，南翼可服务订单C，订单D可使用任一单元；未承接订单时不能单独启用作业单元。`
  - 旧：`订单组合须遵守决策日有效的美国EPA关于PCE制造、加工和商业使用的规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r043_a01": "承接化工作业订单A", "swor_r043_a02": "承接化工作业订单B", "swor_r043_a03": "承接化工作业订单C", "swor_r043_a04": "承接化工作业订单D", "swor_r043_a05": "承接化工作业订单E"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency", "url": "https://www.epa.gov/assessing-and-managing-chemicals-under-tsca/risk-management-perchloroethylene-pce"}], "notes": "以EPA 2024 PCE最终规则fact sheet的处理禁令表格原文替换概括性E1，明确消费用途处理禁令及2026-09-09合规日；其余用途节点保持。", "official_evidence_node_overrides": [{"information_responsibility": "确认PCE消费用途处理禁令及其2026年9月9日合规日，从而支撑2028年消费级制动清洁剂订单禁用。", "node_id": "E1", "omission_effect": "无法确定2028年订单E的PCE消费用途处理是否已被禁止。", "publisher": "U.S. Environmental Protection Agency", "quote": "All persons are prohibited from processing PCE, including any PCE-containing products, except for industrial and commercial uses that will continue under the WCPP or other workplace controls and dry cleaning (see § 751.605(b)(2)).\nSeptember 9, 2026", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["bar_consumer_product"], "supported_patch_slots": ["bar_consumer_product"], "url": "https://www.epa.gov/system/files/documents/2024-12/pce-fact-sheet_english.pdf"}]}`
- 复核说明：只泛化会与C1物质身份冲突的五个订单meaning；单元行动ID和成本不变。

### SWOR-R044

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、俄亥俄辖区、5个行动ID与类型、季度结构、0至2取值、成本、透明度约束、工作量上限、目标和现有Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "企业不维护托管容量地图；Q1至Q4是其自愿发布的四次透明度更新选项。", "decision_date": "2026-08-02", "jurisdiction": "美国俄亥俄州", "regulated_subject": "在俄亥俄州销售零售电力、但不拥有配电系统的竞争性零售电力服务商"}`
- C2：`{"boundary_facts": "公司维护一张公开托管容量地图；Q1至Q4分别表示该地图在四个季度的公开更新次数。", "decision_date": "2026-08-02", "jurisdiction": "美国俄亥俄州", "regulated_subject": "在俄亥俄州运营配电系统的电力配送公用事业公司"}`
- C1 不适用原因：Ohio Revised Code的季度地图更新要求指向维护托管容量地图的配电公用事业主体；C1零售服务商不拥有配电系统也不维护该地图，四个季度下限Patch不适用。
- 题内行动映射：Q1至Q4表示季度公开透明度更新；C2事实将其桥接为托管容量地图更新，C1保持自愿透明度更新；S仅为企业内部年度摘要。
- source 精确替换：
  - 旧：`美国俄亥俄州河城电力配送公用事业公司`
  - 新：`美国俄亥俄州河城电力企业`
  - 旧：`第1至第4季度的托管容量地图更新次数Q1、Q2、Q3、Q4`
  - 新：`第1至第4季度的公开透明度更新次数Q1、Q2、Q3、Q4`
  - 旧：`每次地图更新成本3工日并贡献1个透明度点`
  - 新：`每次透明度更新成本3工日并贡献1个透明度点`
  - 旧：`团队全年最多承担5次地图更新`
  - 新：`团队全年最多承担5次透明度更新`
  - 旧：`公开计划还须按适用于该辖区、主体和业务的现行外部要求定案。`
  - 新：``
- output_schema meaning 修改：`{"swor_r044_a01": "第1季度公开透明度更新次数", "swor_r044_a02": "第2季度公开透明度更新次数", "swor_r044_a03": "第3季度公开透明度更新次数", "swor_r044_a04": "第4季度公开透明度更新次数"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Ohio Legislative Service Commission", "url": "https://codes.ohio.gov/ohio-revised-code/section-4928.83"}], "notes": "Ohio Revised Code完整原句同时明确主体为electric distribution utility、地图公开义务与至少季度更新频率；主体差异保留在case层。", "official_evidence_node_overrides": [{"information_responsibility": "确认主体为electric distribution utility，并确认托管容量地图须公开且至少每季度更新一次。", "node_id": "E1", "omission_effect": "无法确定C1/C2主体门或四个季度更新下限。", "publisher": "Ohio Legislative Service Commission", "quote": "Not later than May 31, 2026, every electric distribution utility in the state shall develop and publicly share distribution system hosting capacity maps. The utility shall ensure that the maps are available on the utility's web site and shall be updated at least once per quarter.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["quarter_1_update", "quarter_2_update", "quarter_3_update", "quarter_4_update"], "supported_patch_slots": ["quarter_1_update", "quarter_2_update", "quarter_3_update", "quarter_4_update"], "url": "https://codes.ohio.gov/ohio-revised-code/section-4928.83"}]}`
- 复核说明：共通source不再写死主体或地图对象，公开action改为中性透明度更新；C2 facts提供托管容量地图桥接，完整证据原句补齐配电公用事业主体门。

### SWOR-R045

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留日期、辖区、8个行动ID与类型、六选三、运行效益、两个共享监测中心、12点成本、容量、目标和现有Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B、D、F的满充注量分别为1600、1600、1700、1800磅，所用制冷剂GWP均为1；C为工业工艺制冷机组，满充注量1490磅、GWP 675；E为办公楼舒适制冷机组，满充注量1700磅、GWP 675。安装日期沿用题面项目记录。", "decision_date": "2026-08-04", "jurisdiction": "美国40 CFR Part 84辖区", "regulated_subject": "规划2027年商业与工业制冷机组网络的美国设施所有者"}`
- C2：`{"boundary_facts": "A为2026年2月安装的密闭商业冷藏机组，满充注量1600磅、GWP 1430；B为2026年3月安装的开放式商业冷藏机组，1600磅、GWP 1；C为2026年5月安装的工业工艺制冷机组，1490磅、GWP 675；D为2015年8月安装的工业工艺制冷机组，1700磅、GWP 675；E为2026年4月安装的舒适制冷机组，1700磅、GWP 675；F为2019年9月安装的工业工艺制冷机组，1800磅、GWP 675。", "decision_date": "2026-08-04", "jurisdiction": "美国40 CFR Part 84辖区", "regulated_subject": "规划2027年商业与工业制冷机组网络的美国设施所有者"}`
- C1 不适用原因：自动检漏条件同时依赖机组用途、满充注量与制冷剂阈值；C1每台候选至少缺少其中一个客观条件，A/F共享监测Patch不适用。
- 题内行动映射：直接式或间接式共享中心均可同时覆盖A至F，成本均为12点；外部事实只决定哪些入网机组必须由中心覆盖。
- source 精确替换：
  - 旧：`候选及运行效益为：A号密闭商业冷藏机组，2026年2月安装、满充注量1,600磅、制冷剂GWP 1,430，34点；B号开放式商业冷藏机组，2026年3月安装、1,600磅、GWP 1，30点；C号工业工艺制冷机组，2026年5月安装、1,490磅、GWP 675，29点；D号工业工艺制冷机组，2015年8月安装、1,700磅、GWP 675，28点；E号办公楼舒适制冷机组，2026年4月安装、1,700磅、GWP 675，27点；F号工业工艺制冷机组，2019年9月安装、1,800磅、GWP 675，32点。`
  - 新：`候选机组记为A至F，运行效益依次为34、30、29、28、27、32点；各机组的用途、安装日期、满充注量和制冷剂GWP记录在设备台账中。`
  - 旧：`设施网络须遵守决策日有效、作用于2027年运行的美国EPA制冷设备自动检漏规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r045_a01": "纳入2027年制冷设施网络的A号密闭商业冷藏机组：2026年2月安装，满充注量1,600磅，制冷剂GWP为1,430", "swor_r045_a02": "纳入2027年制冷设施网络的B号开放式商业冷藏机组：2026年3月安装，满充注量1,600磅，制冷剂GWP为1", "swor_r045_a03": "纳入2027年制冷设施网络的C号工业工艺制冷机组：2026年5月安装，满充注量1,490磅，制冷剂GWP为675", "swor_r045_a04": "纳入2027年制冷设施网络的D号工业工艺制冷机组：2015年8月安装，满充注量1,700磅，制冷剂GWP为675", "swor_r045_a05": "纳入2027年制冷设施网络的E号办公楼舒适制冷机组：2026年4月安装，满充注量1,700磅，制冷剂GWP为675", "swor_r045_a06": "纳入2027年制冷设施网络的F号工业工艺制冷机组：2019年9月安装，满充注量1,800磅，制冷剂GWP为675", "swor_r045_a07": "部署一套直接式自动检漏共享监测中心", "swor_r045_a08": "部署一套间接式自动检漏共享监测中心"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency", "url": "https://www.epa.gov/system/files/documents/2026-01/er-r-fact-sheet-ald-2026-01-13.pdf"}], "notes": "复核现存官方quote中的机组用途、1500磅、GWP/exchange-value和安装日期条件，以及共享ALD能力。"}`
- 复核说明：监测中心技术能力与成本留在题内；机组门槛属性全部移到case层；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R046

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、辖区、11个行动ID与类型、八选三、A-D/B-E/C-F配对、贡献、12点准备包、目标和现有Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A、B、C分别对应番茄、葡萄和甜菜原料；D、E、F分别把对应原料制成常温稳定番茄酱、葡萄酒和糖，并提供随货披露及2026年度客户书面保证；G为马铃薯项目；H的草莓全部供经营者家庭食用。", "decision_date": "2026-08-04", "jurisdiction": "美国FDA农产品安全规则辖区", "regulated_subject": "仅采购已收获原料并进行下游食品加工、不从事种植、采收、包装或持有业务的独立食品加工商"}`
- C2：`{"boundary_facts": "A、B、C在未选择对应D、E、F时分别把番茄、葡萄和甜菜作为生鲜农产品销售；D、E、F把全部对应产出制成常温稳定番茄酱、葡萄酒和糖，并提供随货披露及2026年度客户书面保证；G为马铃薯项目；H的草莓全部供经营者家庭食用。", "decision_date": "2026-08-04", "jurisdiction": "美国FDA农产品安全规则辖区", "regulated_subject": "在美国种植、采收、包装并持有题列农产品的农场经营网络"}`
- C1 不适用原因：21 CFR Part 112的农场生产活动及商业加工路径以农场/农场经营者身份为前提；C1主体只从事独立下游加工，A/B/C的三个组合Patch不适用。
- 题内行动映射：准备包提供完整农产品安全控制能力；D/E/F提供对应商业加工和文件能力。外部规则决定何种经营主体与产品组合需调用这些能力。
- source 精确替换：
  - 旧：`GreenDelta Growers`
  - 新：`GreenDelta食品供应网络`
  - 旧：`A、B或C若没有依法完整的处理豁免，须启用成本12点的完整农产品安全准备包。普通农场条件均满足，且不存在未述豁免。`
  - 新：`完整农产品安全准备包可分别为A、B、C提供种植、采收、包装和持有环节的安全控制能力，每个包成本12点；D、E、F可为对应中心提供题述商业加工、随货披露和年度书面保证能力。具体经营主体和产品用途记录在供应网络业务档案中。`
  - 旧：`网络须遵守决策日有效的美国FDA农产品安全适用范围规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Government Publishing Office, Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-21.xml?part=112"}], "notes": "复核V1.4.4九个证据节点对少生食清单、家庭自用、商业加工、披露和年度保证的支持，并补入covered activity的farm主体定义。", "official_evidence_node_overrides": [{"information_responsibility": "确认Part 112 covered activity以在farm上种植、收获、包装或持有covered produce为主体与活动边界。", "node_id": "E10", "omission_effect": "无法证明C1独立下游加工商不进入题列farm activity适用门。", "publisher": "U.S. Food and Drug Administration / eCFR", "quote": "Covered activity means growing, harvesting, packing, or holding covered produce on a farm.", "role": "definition", "source_node_id": "E10", "support_target_type": "applicability_gate", "support_targets": ["covered_activity_on_a_farm"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-112/subpart-A/section-112.3"}]}`
- 复核说明：未把法规适用结论写入source；保留现有三条Patch和求解结果。

### SWOR-R047

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留日期、辖区、10个行动ID与类型、十选三、金额上限、金额、收益、股权比例、无授权事实、目标和现有Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "决策日的OFAC名单记录列有Raven Holdings、Sable Ventures和Tern Industries。Raven与Sable各持Alder 24%；Raven持Birch 49%；Raven持Cedar 49%，Cedar持Dune 49%、Ember 49%；Raven与Tern分别持Fjord 29%和20%；Alder持Gale 50%；Sable持Harbor 30%；Raven与Sable分别持Iris 25%和24%；Juniper无上述直接或间接持股。", "decision_date": "2026-08-04", "jurisdiction": "美国OFAC制裁制度", "regulated_subject": "为自营账户买入公司债券的美国国民银行"}`
- C2：`{"boundary_facts": "决策日的OFAC名单记录列有Raven Holdings、Sable Ventures和Tern Industries。Raven与Sable各持Alder 25%；Raven持Birch 49%并控制董事会；Raven持Cedar 60%，Cedar持Dune 50%、Ember 49%；Raven与Tern分别持Fjord 30%和20%；Alder持Gale 50%；Sable持Harbor 30%并控制董事会；Raven与Sable分别持Iris 25%和24%；Juniper无上述直接或间接持股。", "decision_date": "2026-08-04", "jurisdiction": "美国OFAC制裁制度", "regulated_subject": "为自营账户买入公司债券的美国国民银行"}`
- C1 不适用原因：C1中三个名单主体对任一发行人的单独或合计直接、间接持股均低于50%；Alder自身未被50 Percent Rule阻断，其持有Gale 50%也不传播blocked身份，五个禁买Patch均不适用。
- 题内行动映射：每个公开行动仍表示买入一个固定债券批次；外部证据和股权图只决定该批次是否可买，不改变金额与收益。
- source 精确替换：
  - 旧：`美国Northbank`
  - 新：`Northbank银行`
  - 旧：`Alder Systems至Juniper Packaging十个批次`
  - 新：`Alder Systems、Birch Controls、Cedar Networks、Dune Analytics、Ember Medical、Fjord Logistics、Gale Software、Harbor Utilities、Iris Foods和Juniper Packaging十个批次`
  - 旧：`银行合规部门已确认Raven Holdings、Sable Ventures和Tern Industries在决策日均属于OFAC blocked persons。发行人股权关系如下：Raven与Sable分别持有Alder 25%；Raven持有Birch 49%并控制其董事会；Raven持有Cedar 60%，Cedar分别持有Dune 50%和Ember 49%；Raven与Tern分别持有Fjord 30%和20%；Alder持有Gale 50%；Sable持有Harbor 30%并控制其董事会；Raven与Sable分别持有Iris 25%和24%；Juniper不由上述主体直接或间接持股。除题面所列关系外不存在其他直接或间接持股，任何候选交易都没有OFAC许可证或其他授权。`
  - 新：`Raven Holdings、Sable Ventures和Tern Industries的名单记录，以及Alder至Juniper各发行人的直接和间接股权关系由交易尽调档案给出。任何候选交易都没有单独许可证或交易授权。`
  - 旧：`投资须遵守决策日有效的美国OFAC blocking sanctions规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r047_a01": "买入2800万美元Alder Systems固定债券批次", "swor_r047_a02": "买入2700万美元Birch Controls固定债券批次", "swor_r047_a03": "买入2600万美元Cedar Networks固定债券批次", "swor_r047_a04": "买入2500万美元Dune Analytics固定债券批次", "swor_r047_a05": "买入2400万美元Ember Medical固定债券批次", "swor_r047_a06": "买入2300万美元Fjord Logistics固定债券批次", "swor_r047_a07": "买入2200万美元Gale Software固定债券批次", "swor_r047_a08": "买入2100万美元Harbor Utilities固定债券批次", "swor_r047_a09": "买入2000万美元Iris Foods固定债券批次", "swor_r047_a10": "买入1900万美元Juniper Packaging固定债券批次"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of the Treasury, Office of Foreign Assets Control", "url": "https://ofac.treasury.gov/media/6186/download?inline"}, {"publisher": "U.S. Department of the Treasury, Office of Foreign Assets Control", "url": "https://ofac.treasury.gov/faqs/585"}], "notes": "复核现存官方quote对直接/间接、单独/合计50%及低于50%仅控制不自动blocked的边界。"}`
- 复核说明：名单命中仍是case事实输入；C1/C2统一为美国国民银行，仅以原始持股比例形成低于50%与达到50%的差异，避免从未指定制裁项目推断域外适用性；将10个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R048

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、辖区、12个行动ID与类型、资本和盈余、十二选五、证券类别、发行人、面值、收益、目标和现有Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A/B为同一Alpha义务人的Type II/III证券；C/D为同一Theta发行人的Type V证券；E至H为四个不同义务人的可销售非投资级债务证券，银行档案分别记录了基于可靠估计的偿付判断；I为Type I，J/K为不同发行人的Type IV，L为另一义务人的Type III。", "decision_date": "2026-08-04", "jurisdiction": "美国OCC银行投资证券制度", "regulated_subject": "资本和盈余为1亿美元的美国州立非会员银行；该行不是国民银行"}`
- C2：`{"boundary_facts": "A/B为同一Alpha义务人的Type II/III证券；C/D为同一Theta发行人的Type V证券；E至H为四个不同义务人的可销售非投资级债务证券，银行档案分别记录了基于可靠估计的偿付判断；I为Type I，J/K为不同发行人的Type IV，L为另一义务人的Type III。", "decision_date": "2026-08-04", "jurisdiction": "美国OCC银行投资证券制度", "regulated_subject": "资本和盈余为1亿美元、为自营账户选择证券包的美国国民银行"}`
- C1 不适用原因：12 CFR Part 1的Type II/III、Type V和履约估计证券限额适用于国民银行；C1是州立非会员银行，三个OCC组合限额Patch不适用。
- 题内行动映射：每个行动对应一个不可拆分证券包；外部限额按题内面值、义务人/发行人和资本盈余映射到组合约束。
- source 精确替换：
  - 旧：`美国国民银行投资证券包组合。`
  - 新：`美国银行投资证券包组合。`
  - 旧：`Meridian National Bank`
  - 新：`Meridian Bank`
  - 旧：`题面给出的法律类别、发行人或义务人归属、面值、可销售性和履约估计结论均已核实，银行没有相关既有持仓或未履行买卖承诺。`
  - 新：`各证券发行文件载明题述类别、发行人或义务人和面值；E至H的交易档案载明可销售性及银行采用的履约估计。银行没有相关既有持仓或未履行买卖承诺。`
  - 旧：`投资须遵守决策日有效的美国OCC国民银行投资证券限额。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r048_a01": "采用A包：Alpha义务人Type II证券，面值600万美元", "swor_r048_a02": "采用B包：Alpha义务人Type III证券，面值500万美元", "swor_r048_a03": "采用C包：Theta发行人Type V证券，面值1600万美元", "swor_r048_a04": "采用D包：Theta发行人另一Type V证券，面值1200万美元", "swor_r048_a05": "采用E包：Kappa义务人的可销售履约估计型债务证券，面值300万美元", "swor_r048_a06": "采用F包：Lambda义务人的可销售履约估计型债务证券，面值300万美元", "swor_r048_a07": "采用G包：Mu义务人的可销售履约估计型债务证券，面值200万美元", "swor_r048_a08": "采用H包：Nu义务人的可销售履约估计型债务证券，面值200万美元", "swor_r048_a09": "采用I包：美国政府Type I证券，面值900万美元", "swor_r048_a10": "采用J包：Omicron发行人Type IV证券，面值800万美元", "swor_r048_a11": "采用K包：Pi发行人Type IV证券，面值700万美元", "swor_r048_a12": "采用L包：Gamma义务人Type III证券，面值600万美元"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Electronic Code of Federal Regulations / Office of the Comptroller of the Currency", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-12.xml"}], "notes": "复核现存quote中的5%、25%与10%限额及national bank主体表述；未改系数。"}`
- 复核说明：只把银行章程身份移到case层，证券包结构保持；将12个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R049

- 结论：`FIX`；问题类型：L1, L2, L3, L7。
- 保持：保留日期、辖区、9个行动ID与类型、六选二、设备状态、服务贡献、三个评估时段、15点成本、目标和现有Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A为新安装设备，C在原址拆卸后重装，D安装了软件升级；B、E、F未经历安装、拆装、主要部件维修或软件变更。所列评估时段均由医学物理师执行并可在设备投入计划用途前纠正问题。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "只对成像设备进行台架研究、不为人体患者提供乳腺摄影检查的非临床实验室"}`
- C2：`{"boundary_facts": "A为新安装设备，C在原址拆卸后重装，D安装了软件升级；B、E、F未经历安装、拆装、主要部件维修或软件变更。所列评估时段均由医学物理师执行并可在患者使用前纠正问题。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "把乳腺摄影设备和影像处理器恢复用于患者检查的美国乳腺摄影设施"}`
- C1 不适用原因：MQSA设备评价要求面向执行人体乳腺摄影检查的设施；C1仅作非临床台架研究，A/C/D的三个评价时段Patch不适用。
- 题内行动映射：A/C/D各有一个专属评估时段，时段能完成评估和纠正且成本已计入；外部规则只决定恢复项目是否必须搭配对应时段。
- source 精确替换：
  - 旧：`美国乳腺摄影设备恢复排程。2026年8月4日，银湾医学影像中心只能优先完成六个恢复项目中的两个并随后用于患者检查。`
  - 新：`美国影像设备恢复排程。2026年8月4日，银湾影像中心只能优先完成六个恢复项目中的两个；完成后的设备用途记录在项目档案中。`
  - 旧：`患者服务净贡献`
  - 新：`设备恢复净贡献`
  - 旧：`恢复安排必须遵守决策日有效的美国FDA乳腺摄影设备评估要求。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration", "url": "https://www.fda.gov/radiation-emitting-products/regulations-mqsa/mqsa-alternative-standard-6-conducting-mammography-equipment-evaluation-after-software-upgrade-under"}], "notes": "复核现存FDA quote对安装、拆装、主要部件/软件变更、物理师执行和患者使用前纠正的支持。"}`
- 复核说明：设备改变事实保持不变，仅移动设施用途轴。

### SWOR-R050

- 结论：`FIX`；问题类型：L1, L2, L3, L7。
- 保持：保留日期、密歇根辖区、6个行动ID与类型、六选一、机构名称、成本、计划开始日、目标和现有Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "该患者的居家护理计划于2026年8月7日建立，服务从8月10日开始；六家候选的本地服务能力、许可、排班和服务区域材料齐全。", "decision_date": "2026-08-04", "jurisdiction": "美国密歇根州Medicare居家护理项目", "regulated_subject": "为密歇根州一名Medicare参保人选择居家护理机构的计划协调员"}`
- C2：`{"boundary_facts": "该患者的居家护理计划于2026年8月8日建立，服务从8月10日开始；六家候选的本地服务能力、许可、排班和服务区域材料齐全。", "decision_date": "2026-08-04", "jurisdiction": "美国密歇根州Medicare居家护理项目", "regulated_subject": "为密歇根州一名Medicare参保人选择居家护理机构的计划协调员"}`
- C1 不适用原因：CMS终止通知把不付款边界设为治疗计划在2026年8月8日或之后建立；C1计划在8月7日建立，QCN禁用Patch不适用。
- 题内行动映射：每个行动选择一家执行机构；本地预审只说明服务可执行性，外部CMS状态决定QCN是否可用于该计划。
- source 精确替换：
  - 旧：`密歇根州Medicare居家护理机构选择。2026年8月4日，湖湾健康计划要为一名Medicare参保人确定2026年8月10日建立并开始执行的新居家护理计划。`
  - 新：`密歇根州Medicare居家护理机构选择。2026年8月4日，湖湾健康计划要为一名Medicare参保人选择执行机构，护理服务从2026年8月10日开始；计划建立日期记录在护理计划台账中。`
  - 旧：`经过服务能力、所在地许可、排班容量和服务区域的本地预审，六家机构均可承接该患者：`
  - 新：`经过服务能力、所在地许可、排班容量和服务区域的本地预审，六家机构均具备提供题列居家护理服务的本地条件：`
  - 旧：`机构选择还须遵守决策日已经公布、对计划开始日有效的美国CMS Medicare机构参与状态与付款规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Centers for Medicare & Medicaid Services", "url": "https://www.cms.gov/files/document/michigan-qcn-home-care-7-27-2026-pdf.pdf"}], "notes": "复核现存官方通知quote中的终止日及“established on or after August 8, 2026”边界。"}`
- 复核说明：把建立日期与开始服务日期拆开，避免原source把二者都写成8月10日。

### SWOR-R051

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留日期、美国联邦辖区、六个PAG批次的收益与化学身份、恰选两个、逐批审查行动及6点成本、互斥关系、目标、现有Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "六个候选批次仅在全封闭系统内分装，过程中不产生粉尘、雾或气溶胶；各批均以溶液形态装于5千克以下密封容器进口，制造时长保持在既有EPA订单记载期限内。A为heteroonium, tri(substitutedaromatichydrocarbon)-, nitrate (1:1)，B为sulfonium, triphenyl-, salt with heterosubstituteddifluorosubstitutedalkyl substitutedalkyl trihalosubstitutedcarbomonocycle carboxylate (1:1)；C至F的取代基、反离子、环卤化或锍结构与二者不同。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦TSCA化学品管理辖区", "regulated_subject": "采购两个光刻胶用光酸发生剂批次并在亚利桑那州加工的半导体材料制造商"}`
- C2：`{"boundary_facts": "六个候选批次都在同类非封闭设备中分装，过程产生气溶胶，且此前未就该分装流程完成EPA审查。A为heteroonium, tri(substitutedaromatichydrocarbon)-, nitrate (1:1)，B为sulfonium, triphenyl-, salt with heterosubstituteddifluorosubstitutedalkyl substitutedalkyl trihalosubstitutedcarbomonocycle carboxylate (1:1)；C至F的取代基、反离子、环卤化或锍结构与二者不同。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦TSCA化学品管理辖区", "regulated_subject": "采购两个光刻胶用光酸发生剂批次并在亚利桑那州加工的半导体材料制造商"}`
- C1 不适用原因：§§721.12210与721.12216把对应物质在非封闭流程中产生粉尘、雾或气溶胶的加工列为显著新用途；C1采用不产生这些形态的全封闭加工，review_a_if_selected与review_b_if_selected均不进入模型。
- 题内行动映射：每个偶数action_id为对应采购批次启动并完成一次外部审查流程，成本6点；流程等待书面处理结论并具备在计划加工前形成放行记录的业务能力。
- source 精确替换：
  - 旧：`六个批次都将在同一类非封闭设备中分装，过程都会产生气溶胶；六个批次此前都没有完成覆盖本次用途的SNUN审查。`
  - 新：`六个批次的分装设备、颗粒物释放状态及既有审查记录由本次生产档案给出。`
  - 旧：`工厂可以为每个入选批次分别提交一次SNUN并等待EPA审查完成，每次流程成本6点，未采购的批次不能启动对应流程。`
  - 新：`工厂可以为每个入选批次分别启动一次外部审查并等待书面处理结论；该流程具备在计划加工前完成审查并形成放行记录的能力，每次成本6点，未采购的批次不能启动对应流程。`
  - 旧：`采购与处理须遵守决策日有效的美国TSCA显著新用途规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r051_a02": "为PAG-A批次启动并完成外部审查流程", "swor_r051_a04": "为PAG-B批次启动并完成外部审查流程", "swor_r051_a06": "为PAG-C批次启动并完成外部审查流程", "swor_r051_a08": "为PAG-D批次启动并完成外部审查流程", "swor_r051_a10": "为PAG-E批次启动并完成外部审查流程", "swor_r051_a12": "为PAG-F批次启动并完成外部审查流程"}`
- IR 目标 meaning 修改：`"两个光刻材料批次扣除外部审查流程成本后的净供应收益"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"citation": "91 FR 31962", "effective_date": "2026-07-28", "publication_date": "2026-05-29", "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}], "notes": "已用GovInfo正式刊载的最终规则替换V1.4.4的public-inspection draft；规则于2026-05-29发布、2026-07-28生效，Gold不变。", "official_evidence_override": [{"information_responsibility": "识别§721.12210覆盖的第一项generic identity。", "node_id": "E1", "omission_effect": null, "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "quote": "§ 721.12210 Heteroonium, tri(substitutedaromatichydrocarbon)-, nitrate (1:1) (generic).", "role": "classification", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["review_a_if_selected"], "supported_patch_slots": ["review_a_if_selected"], "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}, {"information_responsibility": "支持§721.12210对非封闭流程产生粉尘、雾或气溶胶的加工条件。", "node_id": "E2", "omission_effect": null, "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "quote": "It is a significant new use to process the substance in any way that generates dust, mist, or aerosol in a non-enclosed process.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["review_a_if_selected"], "supported_patch_slots": ["review_a_if_selected"], "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}, {"information_responsibility": "识别§721.12216覆盖的第二项generic identity。", "node_id": "E3", "omission_effect": null, "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "quote": "§ 721.12216 Sulfonium, triphenyl-, salt with heterosubstituteddifluorosubstitutedalkyl substitutedalkyltrihalosubstituted carbomonocycle carboxylate (1:1) (generic).", "role": "classification", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["review_b_if_selected"], "supported_patch_slots": ["review_b_if_selected"], "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}, {"information_responsibility": "支持§721.12216对非封闭流程产生粉尘、雾或气溶胶的加工条件。", "node_id": "E4", "omission_effect": null, "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "quote": "It is a significant new use to process the substance in any way that generates dust, mist, or aerosol in a non-enclosed process.", "role": "operative_rule", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["review_b_if_selected"], "supported_patch_slots": ["review_b_if_selected"], "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}, {"information_responsibility": "支持显著新用途在EPA完成审查、作出适当决定并采取相应行动前不得开始。", "node_id": "E5", "omission_effect": "缺少E5时，题内外部审查行动是否必须等到书面处理结论无法确定。", "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "quote": "The manufacture or processing for the significant new use may not commence until EPA has conducted a review of the required notification; made an appropriate determination regarding that notification; and taken such actions as required by that determination.", "role": "review_completion", "source_node_id": "E5", "support_target_type": "patch_slot", "support_targets": ["review_a_if_selected", "review_b_if_selected"], "supported_patch_slots": ["review_a_if_selected", "review_b_if_selected"], "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}, {"information_responsibility": "支持最终规则于2026年7月28日生效。", "node_id": "E6", "omission_effect": "缺少E6时，2026-08-04是否已进入最终规则效力期无法确定。", "publisher": "U.S. Environmental Protection Agency / Federal Register / GovInfo", "quote": "This rule is effective on July 28, 2026.", "role": "effective_date", "source_node_id": "E6", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.govinfo.gov/content/pkg/FR-2026-05-29/pdf/2026-10712.pdf"}]}`
- 复核说明：把共同source写死的加工状态移到case层，将候选流程泛化为可执行的外部审查服务，并补齐最终规则生效日与等待EPA处理结论的官方证据；不改变两个Patch槽或Gold。

### SWOR-R052

- 结论：`FIX`；问题类型：L2, L7。
- 保持：保留日期、美国医院库存业务、六个候选的剂量结构与价值顺序、恰好释放两个、逐批退货成本1点、互斥关系、目标、Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A为1 g、NDC 81298-8112-1、批号C23019V2；B为1 g、同一NDC、C24015V2；C为1 g、同一NDC、C23019V7；D为1 g、同一NDC、C24015V7；E为2 g、NDC 81298-8114-1、V24010V7；F为2 g、同一NDC、V24011V1。六批的储存与放行状态相同。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "持有六个Cyclophosphamide注射剂候选批次的凤凰城医院药品配送中心"}`
- C2：`{"boundary_facts": "A为1 g、NDC 81298-8112-1、批号C23019V1；B为1 g、同一NDC、C24015V1；C为1 g、同一NDC、C23019V7；D为1 g、同一NDC、C24015V7；E为2 g、NDC 81298-8114-1、V24010V7；F为2 g、同一NDC、V24011V1。六批的储存与放行状态相同。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "持有六个Cyclophosphamide注射剂候选批次的凤凰城医院药品配送中心"}`
- C1 不适用原因：FDA公告按NDC与批号的联合精确匹配识别目标库存；C1的六个联合标识均未命中公告中的召回组合，return_a_after_recall与return_b_after_recall均不进入模型。
- 题内行动映射：前六个行动分别释放A至F，后六个行动分别把同一批次送入本地退货流程；每批释放与退货互斥，退货成本1点。
- source 精确替换：
  - 旧：`候选依次为：1 g、NDC 81298-8112-1、C23019V1，释放价值12点；1 g、同一NDC、C24015V1，11点；1 g、同一NDC、C23019V7，10点；1 g、同一NDC、C24015V7，9点；2 g、NDC 81298-8114-1、V24010V7，8点；2 g、同一NDC、V24011V1，7点。`
  - 新：`六个候选分别标记为批次A至F，释放价值依次为12、11、10、9、8、7点；各批次的规格、NDC和批号记录在本次库存处置清单中。`
  - 旧：`库存处置须遵守决策日有效的FDA药品召回要求。`
  - 新：``
- output_schema meaning 修改：`{"swor_r052_a01": "将候选批次A释放给医院订单", "swor_r052_a02": "将候选批次B释放给医院订单", "swor_r052_a03": "将候选批次C释放给医院订单", "swor_r052_a04": "将候选批次D释放给医院订单", "swor_r052_a05": "将候选批次E释放给医院订单", "swor_r052_a06": "将候选批次F释放给医院订单", "swor_r052_a07": "把候选批次A转入退货流程", "swor_r052_a08": "把候选批次B转入退货流程", "swor_r052_a09": "把候选批次C转入退货流程", "swor_r052_a10": "把候选批次D转入退货流程", "swor_r052_a11": "把候选批次E转入退货流程", "swor_r052_a12": "把候选批次F转入退货流程"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration", "url": "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/sunny-pharmtech-inc-issues-voluntary-nationwide-recall-cyclophosphamide-injection-usp-user-level-due"}], "notes": "复核V1.4.4保存的FDA发布者、URL和quote；公告列出C23019V1、C24015V1及V24010V1并说明退回、核对和销毁安排。"}`
- 复核说明：把会随case变化的NDC与批号从共通source及action meaning移出；只改变C1的A、B批号。

### SWOR-R053

- 结论：`FIX`；问题类型：L2, L7。
- 保持：保留新加坡辖区、六类VPC订单及价值、有效停车场许可与材料、恰选两份、目标、三个既有Patch与Gold。
- 主差异轴：`decision_date`。
- C1：`{"boundary_facts": "A、B、C分别为集装箱拖车新车注册、低架拖车过户和平板拖车路税续期订单；D、E、F分别涉及刚性重型货车、牵引车和厢式货车。所有停车位、车辆与客户材料完整。", "decision_date": "2026-02-05", "jurisdiction": "新加坡", "regulated_subject": "持有重型车辆停车场许可并选择两份VPC签发订单的本地运营公司"}`
- C2：`{"boundary_facts": "A、B、C分别为集装箱拖车新车注册、低架拖车过户和平板拖车路税续期订单；D、E、F分别涉及刚性重型货车、牵引车和厢式货车。所有停车位、车辆与客户材料完整。", "decision_date": "2026-08-04", "jurisdiction": "新加坡", "regulated_subject": "持有重型车辆停车场许可并选择两份VPC签发订单的本地运营公司"}`
- C1 不适用原因：LTA试行暂停期自2026-02-06开始；C1决策日在开始日前一日，针对A/B/C的VPC禁用Patch尚未进入模型。
- 题内行动映射：六个行动各承接一份签发订单；本地许可与材料保证签发流程可执行，外部日期边界只决定拖车三项是否保留。
- source 精确替换：
  - 旧：`新加坡重型车辆停车证服务订单选择。2026年8月4日，星港重型车辆停车场运营公司本日只能处理六份候选车辆停车证（VPC）签发订单中的两份。`
  - 新：`新加坡重型车辆停车证服务订单选择。星港重型车辆停车场运营公司本次只能处理六份候选车辆停车证（VPC）签发订单中的两份。`
  - 旧：`VPC业务须遵守决策日有效的新加坡陆路交通管理规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`"两份VPC签发订单的总服务价值"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Singapore Land Transport Authority", "url": "https://onemotoring.lta.gov.sg/content/dam/onemotoring/pdf/Circulars%20to%20ESAs/2026/VRL_03_2026.pdf"}], "notes": "直接复核LTA正式通告PDF：暂停期为2026-02-06至2028-02-05，涵盖拖车新车注册、车辆过户、路税续期，且期间停车场运营方不能签发拖车VPC。"}`
- 复核说明：将会变化的决策日移到case层，并把C1设为官方暂停期开始日前一日，避免使用证据访问日之后的未来法律状态；车辆类型、交易类型、数值与Gold不变。

### SWOR-R054

- 结论：`FIX`；问题类型：L2, L7。
- 保持：保留英国辖区、六批批准类别与价值、生产三个、共享eCoC单元45点、纸质交付条件、目标、现有Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至F的完工日期依次为2026年11月28日、11月27日、11月26日、11月25日、11月24日和11月20日。D为GB国家小批量M类，E为GB无限系列L类，B为UKNI欧盟小批量N类。", "decision_date": "2026-08-04", "jurisdiction": "英国GB与UKNI车辆型式批准体系", "regulated_subject": "从六个已获对应型式批准的车辆批次中排产三个的英国制造商"}`
- C2：`{"boundary_facts": "A至F的完工日期依次为2026年12月2日、12月3日、11月30日、12月4日、12月5日和11月20日。D为GB国家小批量M类，E为GB无限系列L类，B为UKNI欧盟小批量N类。", "decision_date": "2026-08-04", "jurisdiction": "英国GB与UKNI车辆型式批准体系", "regulated_subject": "从六个已获对应型式批准的车辆批次中排产三个的英国制造商"}`
- C1 不适用原因：VCA把相关M/N/O车辆的强制eCoC起点设为2026-11-29，并分别保留国家小批量和L类分支；C1六批均在11月28日或之前完工，共享单元的三个Patch均不进入模型。
- 题内行动映射：第七个行动启用一套可同时完成全部入选批次数据准备与提交的共享单元，固定消耗45点；纸质合格证交付能力另行具备。
- source 精确替换：
  - 旧：`A是2026年12月2日完工的GB无限系列M类车辆，生产价值75点；B是12月3日完工的UKNI欧盟小批量N类车辆，72点；C是11月30日完工的GB中等批量O类车辆，70点。D是12月4日完工的GB国家小批量M类车辆，68点；E是12月5日完工的GB无限系列L类车辆，65点；F是11月20日完工的GB无限系列N类车辆，63点。`
  - 新：`A是GB无限系列M类车辆，生产价值75点；B是UKNI欧盟小批量N类车辆，72点；C是GB中等批量O类车辆，70点；D是GB国家小批量M类车辆，68点；E是GB无限系列L类车辆，65点；F是GB无限系列N类车辆，63点。各批次完工日期记录在本次排产清单中。`
  - 旧：`生产计划须遵守决策日已公布、适用于各批次制造日期与批准类别的英国eCoC规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r054_a01": "生产GB无限系列M类车辆批次A", "swor_r054_a02": "生产UKNI欧盟小批量N类车辆批次B", "swor_r054_a03": "生产GB中等批量O类车辆批次C", "swor_r054_a04": "生产GB国家小批量M类车辆批次D", "swor_r054_a05": "生产GB无限系列L类车辆批次E", "swor_r054_a06": "生产GB无限系列N类车辆批次F"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Vehicle Certification Agency", "url": "https://www.vehicle-certification-agency.gov.uk/electronic-certificates-of-conformity-ecocs/"}], "notes": "复核V1.4.4保存的VCA quote，覆盖2026-11-29起点、GB/UKNI相关批准类别、国家小批量与L类说明，以及此前制造车辆。"}`
- 复核说明：把六个制造日期从共通source和action meaning移至case层；批准类别与成本不变。

### SWOR-R055

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、美国州际货运场景、四个里程与贡献、四种检查服务与成本、三小时事实、三组选择结构、目标、三个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至D四项候选均使用铅封货厢，承运指令要求司机不得开封，且现有装载方式使司机无法查看货物。四项里程与驾驶时间保持题列数值，固定装置及装载记录完整。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦机动车承运安全辖区", "regulated_subject": "选择一项州际货运任务及一个固定检查服务的财产承运人"}`
- C2：`{"boundary_facts": "A、B、D为可由司机进入货厢查看的普通未封闭货物；C使用铅封货厢，承运指令要求司机不得开封，且现有装载方式使司机无法查看货物。四项里程与驾驶时间保持题列数值。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦机动车承运安全辖区", "regulated_subject": "选择一项州际货运任务及一个固定检查服务的财产承运人"}`
- C1 不适用原因：49 CFR 392.9(b)排除司机被命令不得开封或因装载方式无法检查货物的情形；C1四项任务均满足该边界，三个途中检查Patch均不进入模型。
- 题内行动映射：行动1至4按题面首次出现顺序选择任务A至D，行动5至8依次选择不检查、50英里内一次、再加一个150英里节点、再加两个150英里节点；成本已本地化。
- source 精确替换：
  - 旧：`未密封普通货物40英里、未密封普通货物180英里、司机奉命不得开启且无法检查的密封180英里、未密封普通货物320英里任务，贡献分别为80、112、105、135点。`
  - 新：`四项任务A至D的里程分别为40、180、180和320英里，贡献分别为80、112、105、135点；各项装载封闭状态及司机能否检查货物记录在本次派车单中。`
  - 旧：`各任务驾驶时间不会早于里程节点触发三小时复检，其他装载和固定条件合规。`
  - 新：`各任务在到达所列里程节点前的驾驶时间均少于3小时；各车现有固定装置及装载记录完整。`
  - 旧：`方案须遵守决策日有效的美国联邦货物检查规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r055_a01": "未密封普通货物40英里任务", "swor_r055_a02": "未密封普通货物180英里任务", "swor_r055_a03": "司机无法检查货物的密封180英里任务", "swor_r055_a04": "未密封普通货物320英里任务", "swor_r055_a05": "不安排途中货物固定检查", "swor_r055_a06": "在前50英里内安排一次检查", "swor_r055_a07": "在前50英里内及随后150英里节点安排检查", "swor_r055_a08": "在前50英里内及两个后续150英里节点安排检查"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Motor Carrier Safety Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}, {"publisher": "Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-392/subpart-A/section-392.9"}], "notes": "复核V1.4.4保存的50英里、3小时/150英里复查quote及当前§392.9(b)的密封或无法检查边界。"}`
- 复核说明：把四项货物可检查性移到case层，并用客观装载记录替换“合规”结论；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R056

- 结论：`FIX`；问题类型：L2, L5, L7。
- 保持：保留日期、Blue Ridge Parkway辖区、六条路线收益、恰选两条、不绕行、车辆司机许可、目标、两个排除Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至F的精确里程闭区间依次为62.0—62.5、286.0—287.0、62.8—63.4、276.6—280.0、66.3—76.4和280.9—285.5；路线仅经过各自闭区间内的里程点。", "decision_date": "2026-08-04", "jurisdiction": "美国Blue Ridge Parkway", "regulated_subject": "从六条同日公园道路接驳路线中选择两条的持证运营商"}`
- C2：`{"boundary_facts": "A至F的精确里程闭区间依次为63.4—64.0、274.2—276.6、62.8—63.4、276.6—280.0、66.3—76.4和280.9—285.5；路线仅经过各自闭区间内的里程点。", "decision_date": "2026-08-04", "jurisdiction": "美国Blue Ridge Parkway", "regulated_subject": "从六条同日公园道路接驳路线中选择两条的持证运营商"}`
- C1 不适用原因：NPS两份定期新闻稿表明2026-08-04时MP 63.5—63.9及Deep Gap绕行段MP 269.8—276.5处于全封闭施工期；C1六个路线闭区间均不与其相交，exclude_a与exclude_b均不进入模型。
- 题内行动映射：六个行动各执行对应路线完整闭区间，不允许改成绕行；调度单中的车辆登记、司机排班和运营许可证文件使路线具备本地执行能力，行动收益保持题列数值。
- source 精确替换：
  - 旧：`2026年8月4日，蓝岭接驳公司要从六条当日路线中执行两条：里程63.4至64.0，收益12点；里程274.2至276.6，收益11点；里程62.8至63.4，收益10点；里程276.6至280.0，收益9点；里程66.3至76.4，收益8点；里程280.9至285.5，收益7点。`
  - 新：`2026年8月4日，蓝岭接驳公司要从六条当日路线中执行两条。六条路线标记A至F，收益依次为12、11、10、9、8、7点；各路线的精确里程闭区间记录在本次调度单中。`
  - 旧：`车辆、司机和许可条件均已满足，不允许把封闭区间改为绕行路线。`
  - 新：`调度单附车辆登记、司机排班表和运营许可证副本；路线须完整经过所列闭区间，不能改为绕行路线。`
  - 旧：`唯一目标是最大化两条可执行路线的总服务收益。`
  - 新：`唯一目标是最大化两条路线的总服务收益。`
  - 旧：`运营须遵守当日美国国家公园管理局发布的Blue Ridge Parkway道路状态。`
  - 新：``
- output_schema meaning 修改：`{"swor_r056_a01": "执行接驳路线A", "swor_r056_a02": "执行接驳路线B", "swor_r056_a03": "执行接驳路线C", "swor_r056_a04": "执行接驳路线D", "swor_r056_a05": "执行接驳路线E", "swor_r056_a06": "执行接驳路线F"}`
- IR 目标 meaning 修改：`"两条公园接驳路线的总服务收益"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publication_date": "2025-09-02", "publisher": "U.S. National Park Service", "url": "https://www.nps.gov/blri/learn/news/critical-repairs-to-james-river-bridge-begin-on-the-blue-ridge-parkway.htm"}, {"publication_date": "2026-07-24", "publisher": "U.S. National Park Service", "url": "https://www.nps.gov/blri/learn/news/critical-repairs-to-deep-gap-bridge-underway-on-the-blue-ridge-parkway.htm"}], "notes": "改用两条带发布日期的NPS官方新闻稿：James River公告给出MP 63.5—63.9约自2025-09-09关闭至2026年秋；Deep Gap公告给出2026-07-27起MP 269.8—276.5全封闭绕行至9月下旬。2026-08-04同时落在两个公告时段内，Gold不变。", "official_evidence_override": [{"information_responsibility": "支持James River Bridge施工期与MP 63.5—63.9关闭区间。", "node_id": "E1", "omission_effect": null, "publisher": "U.S. National Park Service", "quote": "JAMES RIVER, VA - A section of the Blue Ridge Parkway from milepost 63.5 to 63.9 will close on or around September 9, for a significant rehabilitation of the multi-level James River Bridge at milepost 63.7. Planned repairs include bridge deck rehabilitation, new asphalt overlay on the bridge, bridge bearing replacement, as well as parking area repairs and rehabilitation. The work is expected to be complete by Fall of 2026.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["exclude_a"], "supported_patch_slots": ["exclude_a"], "url": "https://www.nps.gov/blri/learn/news/critical-repairs-to-james-river-bridge-begin-on-the-blue-ridge-parkway.htm"}, {"information_responsibility": "支持Deep Gap Bridge全封闭绕行的日期与MP 269.8—276.5区间。", "node_id": "E2", "omission_effect": null, "publisher": "U.S. National Park Service", "quote": "BOONE, N.C. — On July 27, the Blue Ridge Parkway will begin significant rehabilitation of the Deep Gap Bridge over U.S. Highway 421 to improve a section of the Parkway at milepost 276.4. The project is part of the National Park Service’s larger effort to improve visitor safety, protect access to popular destinations, and help preserve historic park infrastructure. During construction, visitors can expect a full road closure with signed detour on the Blue Ridge Parkway and single lane closures on U.S. Highway 421 in the work zone below the bridge. The detour runs north to south, beginning at milepost 269.8 at the intersection with Phillips Gap Road, continuing to U.S. Route 221, and reentering the park at milepost 276.5 off of U.S. Highway 421. The full road closure is expected to be in place until late September, followed by single-lane closures until the target completion of this project in late spring 2027.", "role": "operative_rule_and_applicability", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["exclude_b"], "supported_patch_slots": ["exclude_b"], "url": "https://www.nps.gov/blri/learn/news/critical-repairs-to-deep-gap-bridge-underway-on-the-blue-ridge-parkway.htm"}]}`
- 复核说明：路线区间必须同时从共通source和action meaning移到case层；以客观调度文件替换合法性结论，正式证据使用两条定期NPS新闻稿的连续原文，不再依赖实时状态页。

### SWOR-R057

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、四个值守计划及睡眠事实、三个人员支持包、五个计薪包、所有成本与兼容约束、目标、11个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "服务商自行选择在候选时段留在客户设施，不在该场所长期居住。四个候选依次为：23小时值守、实际睡眠6小时；24小时值守、双方有书面睡眠时段排除协议、排定8小时且报警后实际睡眠6小时；26小时值守、同类书面协议、排定8小时且报警后实际睡眠4小时；24小时远端值守、双方没有明示或默示睡眠时段排除协议且实际睡眠8小时。四处均有安静、独立且适合睡眠的房间。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦工资工时辖区", "regulated_subject": "以独立企业名义按项目开票、自备作业设备、独立安排人员并可同时服务其他客户的夜间设施操作服务商"}`
- C2：`{"boundary_facts": "公司要求该操作员按候选计划留在值守设施，不在雇主场所长期居住。四个候选依次为：23小时值守、实际睡眠6小时；24小时值守、双方有书面睡眠时段排除协议、排定8小时且报警后实际睡眠6小时；26小时值守、同类书面协议、排定8小时且报警后实际睡眠4小时；24小时远端值守、双方没有明示或默示睡眠时段排除协议且实际睡眠8小时。四处均有安静、独立且适合睡眠的房间。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦工资工时辖区", "regulated_subject": "由松港公司雇用、按小时计薪、执行设施操作而不承担管理或专业决策职责的操作员"}`
- C1 不适用原因：29 CFR part 785的题列睡眠时间规则用于计算employee的工作小时；C1主体按已给客观关系要素为独立服务商，11个sleep/pay组合Patch均不进入模型。
- 题内行动映射：行动1至4选择一个值守计划，5至7选择一个人员支持包，8至12选择一个工时结算包；结算行动直接确定题内成本和小时档，不额外改写101之外的模型结构。
- source 精确替换：
  - 旧：`美国远程公用设施连续值守排班。2026年8月4日，松港公用事业公司为一名受联邦工时规定保护、必须留在值守设施内的非豁免操作员选择值守计划、人员支持和计薪包。`
  - 新：`美国远程公用设施连续值守排班。松港公用事业公司为一名在值守期间留在设施内的夜间操作人员选择值守计划、人员支持和工时结算包。`
  - 旧：`雇主与员工有书面睡眠排除协议`
  - 新：`值守安排双方有书面睡眠时段排除协议`
  - 旧：`操作员不长期居住在雇主场所。`
  - 新：`操作人员不长期居住在值守场所。`
  - 旧：`计薪包可选按16、18、22、24或26个工时计薪，耗用依次为0、2、6、8、10点。`
  - 新：`工时结算包可选按16、18、22、24或26个工时结算，耗用依次为0、2、6、8、10点。`
  - 旧：`以计划贡献减去人员和计薪耗用后的值守净效用最大为唯一目标。`
  - 新：`以计划贡献减去人员支持与工时结算包耗用后的值守净效用最大为唯一目标。`
  - 旧：`排班须遵守决策日有效的美国联邦在岗睡眠时间认定规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r057_a08": "按16个工时结算", "swor_r057_a09": "按18个工时结算", "swor_r057_a10": "按22个工时结算", "swor_r057_a11": "按24个工时结算", "swor_r057_a12": "按26个工时结算"}`
- IR 目标 meaning 修改：`"值守计划贡献减去人员支持与工时结算包耗用后的净效用"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Wage and Hour Division, U.S. Department of Labor / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml?part=785"}], "notes": "复核V1.4.4保存的少于24小时、24小时以上协议、无协议及少于5小时实际睡眠四组官方quote。"}`
- 复核说明：把用工身份从共通source移至case层，并把题内候选行动中带法律含义的“计薪”改为中性工时结算包；保留复杂Patch与全部本地排班语义。

### SWOR-R058

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留2024-07-15、A既有运营与及时通知、B/C新增时点、每线一人或两人、乘务及三类后续动作成本、兼容约束、目标、9个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "三条服务均为旅游、观光、历史或游览列车，所在线路专用于此类列车。A自2023年1月持续同范围运营并在2024年6月24日前提交书面通知，B与C为计划新增服务。", "decision_date": "2024-07-15", "jurisdiction": "美国FRA铁路运营辖区", "regulated_subject": "运营三条旅游、观光、历史或游览列车服务的铁路运营方"}`
- C2：`{"boundary_facts": "三条服务均在美国一般铁路系统线路上运输货物。A自2023年1月持续同范围运营并在2024年6月24日前提交书面通知，B与C分别计划于2026年10月和11月首次开行。", "decision_date": "2024-07-15", "jurisdiction": "美国FRA铁路运营辖区", "regulated_subject": "在美国一般铁路系统上运营三条货运列车服务的Class I铁路公司"}`
- C1 不适用原因：FRA最终规则排除既不在一般铁路系统运行、也不与其连接的旅游、观光、历史或游览运营；C1三线均处于该边界，continuation、special approval和annual report Patch均不进入模型。
- 题内行动映射：每条线路均有一人、两人、既有运营延续申请、新增运营特别批准和首个年度安全报告五类候选行动；后续动作只能与同线单人方案组合。
- source 精确替换：
  - 旧：`美国铁路乘务排班与准入计划。2024年7月15日，一家Class I铁路公司要为三条均已完成低风险分析、在美国一般铁路系统上运行且不属于调车服务的货运列车服务选择乘务人数及必要的准入后续动作。A线自2023年1月以来连续按同一范围运行，且公司已在2024年6月24日前向FRA提交继续该既有单人运营所需的书面通知；B线计划于2026年10月首次开行，C线计划于2026年11月首次开行，B和C此前从未运营。`
  - 新：`美国铁路乘务排班与准入计划。2024年7月15日，一家铁路运营方要为三条候选服务选择乘务人数及必要的准入后续动作。A线自2023年1月以来连续按同一范围运行，运营方已在2024年6月24日前提交一份说明A线继续单人运营安排的书面通知；B线计划于2026年10月首次开行，C线计划于2026年11月首次开行，B和C此前从未运营。服务种类、与美国一般铁路系统的连接状态及运营方分类记录在本次运行档案中。`
  - 旧：`三线均不适用调车、旅游、helper、遥控作业或Class II/III铁路条件性例外。`
  - 新：``
  - 旧：`方案须遵守决策日有效的美国FRA列车乘务人数规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r058_a01": "A线采用一名乘务员", "swor_r058_a02": "A线采用两名乘务员", "swor_r058_a03": "为A线提交既有运营延续申请", "swor_r058_a04": "为A线取得新增运营特别批准", "swor_r058_a05": "为A线提交首个年度安全报告", "swor_r058_a06": "B线采用一名乘务员", "swor_r058_a07": "B线采用两名乘务员", "swor_r058_a08": "为B线提交既有运营延续申请", "swor_r058_a09": "为B线取得新增运营特别批准", "swor_r058_a10": "为B线提交首个年度安全报告", "swor_r058_a11": "C线采用一名乘务员", "swor_r058_a12": "C线采用两名乘务员", "swor_r058_a13": "为C线提交既有运营延续申请", "swor_r058_a14": "为C线取得新增运营特别批准", "swor_r058_a15": "为C线提交首个年度安全报告"}`
- IR 目标 meaning 修改：`"三条线路乘务与后续动作总成本"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Federal Railroad Administration / GovInfo", "url": "https://www.govinfo.gov/content/pkg/FR-2024-04-09/pdf/2024-06625.pdf"}], "notes": "复核V1.4.4保存的FRA最终规则发布者、URL及既有运营延续、新增运营特别批准、首个年度报告与生效日期quote；新增连续原文节点核对专用旅游列车线路的定义与排除边界。", "official_evidence_node_overrides": [{"information_responsibility": "界定不属于一般铁路运输系统的旅游列车运营所需的专用线路事实。", "node_id": "E5", "omission_effect": "缺少E5时，无法由C1的服务种类与专用线路事实判定其是否落入旅游列车边界。", "publisher": "U.S. Federal Railroad Administration / GovInfo", "quote": "Tourist train operation that is not part of the general railroad system of transportation means a tourist, scenic, historic, or excursion train operation conducted only on track used exclusively for that purpose (i.e., there is no freight, intercity passenger, or commuter passenger railroad operation on the track).", "role": "classification", "source_node_id": "E5", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.govinfo.gov/content/pkg/FR-2024-04-09/pdf/2024-06625.pdf"}, {"information_responsibility": "支持专用旅游列车线路上的一人乘务运营不适用本分部要求。", "node_id": "E6", "omission_effect": "缺少E6时，C1是否排除全部延续、特别批准和年度报告Patch无法确定。", "publisher": "U.S. Federal Railroad Administration / GovInfo", "quote": "The requirements in this subpart are not applicable to the following passenger and tourist train operations that are operated with a one-person train crew: (a) The train is a tourist train operation that is not part of the general railroad system of transportation;", "role": "applicability_gate", "source_node_id": "E6", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.govinfo.gov/content/pkg/FR-2024-04-09/pdf/2024-06625.pdf"}]}`
- 复核说明：把铁路类别、服务性质和线路用途从共通source移至case层，以专用于旅游列车的正面属性重构C1；泛化全部行动meaning并补足旅游列车定义和排除边界证据，不改9个Patch或Gold；删除题面中的顺序映射元说明。

### SWOR-R059

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、新加坡持证本地企业、两个SER名额、六个型号价值、SDoC与EU-TEC材料、其他路径无容量、目标、三个排除Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A为5G蜂窝移动终端，B为GMPCS终端，C为电缆调制解调器，D为LTE蜂窝移动终端，E为ADSL调制解调器，F为同轴电缆家庭联网设备。六项均附供应商符合性声明和有效EU型式检验证书。", "decision_date": "2026-08-04", "jurisdiction": "新加坡", "regulated_subject": "持有电信经销商执照并拥有两个当前申报名额的新加坡本地设备供应商"}`
- C2：`{"boundary_facts": "A为5G蜂窝移动终端，B为GMPCS终端，C为电缆调制解调器，D为工业UWB资产标签，E为企业PABX设备，F为陆地移动无线电设备。六项均附供应商符合性声明和有效EU型式检验证书。", "decision_date": "2026-08-04", "jurisdiction": "新加坡", "regulated_subject": "持有电信经销商执照并拥有两个当前申报名额的新加坡本地设备供应商"}`
- C1 不适用原因：IMDA页面列明SER设备类别；C1六项均落在所列移动终端、GMPCS或宽带接入设备类别，针对D/E/F超出清单的排除Patch均不进入模型。
- 题内行动映射：六个行动各占用一个SER申报名额并提交对应型号材料；当前只能选择两个，其他注册方式在上市期限前没有本地处理能力。
- source 精确替换：
  - 旧：`A是5G蜂窝移动终端，上市价值68点；B是全球移动个人通信卫星（GMPCS）终端，价值63点；C是有线电视网络使用的电缆调制解调器，价值59点；D是工业超宽带（UWB）资产标签，价值74点；E是企业内部使用的程控用户交换机（PABX），价值71点；F是陆地移动无线电设备，价值66点。`
  - 新：`候选型号标记A至F，上市价值依次为68、63、59、74、71、66点；各型号的设备类别及无线或有线功能记录在本次申报清单中。`
  - 旧：`六个型号均不是禁用或免注册设备，并已备齐符合相应IMDA技术规范的供应商符合性声明和有效EU型式检验证书。`
  - 新：`六个型号均已备齐供应商符合性声明和有效EU型式检验证书，其产品资料包含申报表所需技术参数。`
  - 旧：`申报方案须遵守决策日有效的新加坡电信设备注册规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r059_a01": "通过SER申报候选型号A", "swor_r059_a02": "通过SER申报候选型号B", "swor_r059_a03": "通过SER申报候选型号C", "swor_r059_a04": "通过SER申报候选型号D", "swor_r059_a05": "通过SER申报候选型号E", "swor_r059_a06": "通过SER申报候选型号F"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Singapore Infocomm Media Development Authority, IRIS", "url": "https://iris.imda.gov.sg/application/simplified-equipment-registration-%28ser%29"}], "notes": "复核V1.4.4保存的IRIS quote，覆盖SDoC、EU-TEC材料以及5G、GMPCS、ADSL、电缆调制解调器和同轴电缆家庭联网类别。"}`
- 复核说明：设备类别从共通source和action meaning移至case层；数值和文档能力保持不变。

### SWOR-R060

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、四种来话负载及贡献、四个能力包及成本、无网络故障、完整月度样本、两组应答时间、选择结构、两个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "不存在网络故障；每100通计数构成完整月度样本；传统文本中继型来话中题列快速来话均被立即接通，没有排队或保持。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦电信服务辖区", "regulated_subject": "仅为本集团员工提供内部无障碍来话协助、不向公众或州际用户提供TRS或VRS的企业呼叫中心"}`
- C2：`{"boundary_facts": "不存在网络故障；每100通计数构成完整月度样本；传统TRS题列快速来话均被立即接通，没有排队或保持。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦电信服务辖区", "regulated_subject": "向州际用户提供传统TRS与VRS并持有FCC认证的服务提供商"}`
- C1 不适用原因：47 CFR 64.604的题列应答比例约束TRS/VRS提供者；C1仅运营内部企业无障碍中心，不提供该规则覆盖的州际relay service，voice70与vrs76容量Patch均不进入模型。
- 题内行动映射：行动1至4按首次出现顺序选择四个负载方案，行动5至8依次选择无增配、传统专项、视频专项和跨业务包；题内明确每个包可达到的客观比例与成本。
- source 精确替换：
  - 旧：`美国电信中继服务应答能力配置。2026年8月5日，云桥TRS提供商须从四种月度来话方案中选择一种，并从四个应答能力包中选择一个。`
  - 新：`美国来话应答能力配置。云桥呼叫中心要从四种月度来话方案中选择一种，并从四个应答能力包中选择一个。`
  - 旧：`四种方案均表示未增加能力时的基准预测：传统TRS每100通中70通或88通可在10秒内立即接通，贡献150点或142点；VRS每100通中76通或84通可在120秒内接通，贡献168点或158点。`
  - 新：`四种方案均表示未增加能力时的基准预测：传统文本中继型来话每100通中70通或88通可在10秒内立即接通，贡献150点或142点；视频中继型来话每100通中76通或84通可在120秒内接通，贡献168点或158点。`
  - 旧：`本地工程评估确认，传统专项包只能把所选传统TRS基准方案补足到适用的联邦最低水平，VRS专项包只能把所选VRS基准方案补足到适用的联邦最低水平，跨业务包可以补足任一类方案；不增加能力时基准比例不变，各能力包不改变来话方案贡献。`
  - 新：`本地工程评估确认，传统专项包可把所选传统文本中继型方案的10秒内立即接通比例提高到85%，视频专项包可把所选视频中继型方案的120秒内接通比例提高到80%，跨业务包可对任一类方案达到相同数值；不增加能力时基准比例不变，各能力包不改变来话方案贡献。`
  - 旧：`配置须遵守决策日有效的美国联邦TRS应答规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r060_a01": "未增加能力时，传统TRS每100通中70通在10秒内立即接通的基准方案", "swor_r060_a02": "未增加能力时，传统TRS每100通中88通在10秒内立即接通的基准方案", "swor_r060_a03": "未增加能力时，VRS每100通中76通在120秒内接通的基准方案", "swor_r060_a04": "未增加能力时，VRS每100通中84通在120秒内接通的基准方案", "swor_r060_a05": "不增加应答能力", "swor_r060_a06": "配置传统TRS专项应答能力包", "swor_r060_a07": "配置VRS专项应答能力包", "swor_r060_a08": "配置跨业务完整应答能力包"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-64/subpart-F/section-64.604"}], "notes": "复核V1.4.4保存的FCC/eCFR quote：传统TRS为10秒内85%且立即接通，VRS为月度120秒内80%。"}`
- 复核说明：主体类型移到case层，并把“补足联邦最低水平”改成客观85%/80%能力映射；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R061

- 结论：`FIX`；问题类型：L2, L7。
- 保持：保留日期、波士顿酒店、四个Nottaway型号、两名技师收益矩阵、各分配一个不同任务、逐任务更换成本8点、目标、四个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至D四盏灯的顶部分配器盖外侧各有一枚清晰可见的螺钉；型号依次为9000-1128、9000-1129、9000-1253和9000-1130。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "为两名技师分配两盏未安装Nottaway吊灯任务的波士顿酒店工程部"}`
- C2：`{"boundary_facts": "A至D四盏灯的顶部分配器盖外侧均看不到螺钉；型号依次为9000-1128、9000-1129、9000-1253和9000-1130。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "为两名技师分配两盏未安装Nottaway吊灯任务的波士顿酒店工程部"}`
- C1 不适用原因：CPSC公告以题列型号与顶部分配器盖外侧无可见螺钉共同识别目标产品；C1四盏均有清晰可见螺钉，四个召回更换Patch均不进入模型。
- 题内行动映射：行动1至4把A至D分给北区技师，5至8把A至D分给南区技师，9至12为对应任务启用厂家处置与状态确认服务；服务仅能随已分配任务、会在需要时完成补救并形成确认记录，每次成本8点。
- source 精确替换：
  - 旧：`四盏灯均为Currey & Company Nottaway系列，顶部分配器盖外侧均看不到螺钉，且尚未安装。`
  - 新：`四盏灯均为Currey & Company Nottaway系列且尚未安装；每盏灯顶部分配器盖外侧的螺钉可见情况记录在到货检验表中。`
  - 旧：`工程部可以为已分配任务先办理厂家召回更换，每次成本8点；未分配任务不能办理更换。`
  - 新：`工程部可以为已分配任务启用厂家处置与状态确认服务；该服务在需要时完成厂家补救并形成确认记录，每次成本8点；未分配任务不能启用。`
  - 旧：`唯一目标是最大化两名技师的任务收益减去必要更换成本后的净收益。`
  - 新：`唯一目标是最大化两名技师的任务收益减去处置服务成本后的净收益。`
  - 旧：`安装安排须遵守决策日有效的CPSC产品召回要求。`
  - 新：``
- output_schema meaning 修改：`{"swor_r061_a09": "为任务A启用厂家处置与状态确认服务", "swor_r061_a10": "为任务B启用厂家处置与状态确认服务", "swor_r061_a11": "为任务C启用厂家处置与状态确认服务", "swor_r061_a12": "为任务D启用厂家处置与状态确认服务"}`
- IR 目标 meaning 修改：`"两名技师的任务收益减去厂家处置服务成本后的净收益"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Consumer Product Safety Commission", "url": "https://www.cpsc.gov/Recalls/2026/Currey-Company-Recalls-Nottaway-Chandeliers-Due-to-Risk-of-Serious-Injury-or-Death-from-Electrocution-Hazard"}], "notes": "复核V1.4.4保存的CPSC发布者、URL和quote，覆盖四个型号及顶部分配器盖外侧无可见螺钉的识别特征。"}`
- 复核说明：把螺钉可见状态从共通source移至case层，并把厂家行动泛化为两类case均可执行的处置与状态确认服务；型号、Patch与分配结构不变。

### SWOR-R062

- 结论：`FIX`；问题类型：L2。
- 保持：保留日期、芝加哥酒店、A/C为N1844-776、B为N1847-776、D为N1848-776、房间收益矩阵、原包装与内部要求、二选分配结构、两个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至D均为Minka Bardon N1844-776；四盏均保持原包装，电气容量、风格和施工工期记录与宴会厅和大堂的施工单一致。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "从四盏未安装Bardon库存灯具中为两个房间各分配一盏的芝加哥酒店"}`
- C2：`{"boundary_facts": "B与D分别是最初购入且没有厂家处置完成记录的N1847-776和N1848-776单元；A与C均为N1844-776。四盏均保持原包装，电气容量、风格和施工工期记录与宴会厅和大堂的施工单一致。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "从四盏未安装Bardon库存灯具中为两个房间各分配一盏的芝加哥酒店"}`
- C1 不适用原因：CPSC公告列明N1847-776与N1848-776等目标型号；C1四盏均为未列入该公告的N1844-776，两个禁用Patch均不进入模型。
- 题内行动映射：行动1至4把A至D分给宴会厅，5至8把A至D分给大堂；同一库存单元不能重复使用，收益矩阵保持题列数值。
- source 精确替换：
  - 旧：`库存A和C均为Minka Bardon N1844-776，库存B为N1847-776，库存D为N1848-776。`
  - 新：`库存A至D的具体型号记载在到货台账中。`
  - 旧：`安装安排须遵守决策日有效的CPSC产品召回要求。`
  - 新：``
- output_schema meaning 修改：`{"swor_r062_a01": "把库存A分配给宴会厅", "swor_r062_a02": "把库存B分配给宴会厅", "swor_r062_a03": "把库存C分配给宴会厅", "swor_r062_a04": "把库存D分配给宴会厅", "swor_r062_a05": "把库存A分配给大堂", "swor_r062_a06": "把库存B分配给大堂", "swor_r062_a07": "把库存C分配给大堂", "swor_r062_a08": "把库存D分配给大堂"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Consumer Product Safety Commission", "url": "https://www.cpsc.gov/Recalls/2026/Minka-Lighting-Group-Recalls-Bardon-Series-Pendant-Light-Fixtures-Due-to-Risk-of-Serious-Injury-or-Death-from-an-Impact-Hazard"}], "notes": "复核V1.4.4保存的CPSC公告quote，公告列明N1847-776、N1848-776等召回型号，补救方式为退款而非更换；因此C1改用四盏N1844-776的客观型号事实，不虚构更换单元。"}`
- 复核说明：把四盏具体型号从共通source及action meaning移到case层；C1以四盏N1844-776保留现有Gold，并纠正原草稿误写的厂家更换补救。

### SWOR-R063

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、四个设施贡献90/104/111/82点、三个报告包与成本、三个监测包与成本、三组选一、目标、现有Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至D的源清单均只记录固定燃烧锅炉；总额定热输入依次为24、25、26、29 mmBtu/小时，年度排放依次为18,000、20,000、23,000、24,000吨CO2e。四座均由集团自营，不供应或进口燃料或温室气体。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦温室气体报告项目辖区", "regulated_subject": "从四座自有工业设施中选择下一年度运营对象的美国设施所有人"}`
- C2：`{"boundary_facts": "A运营己二酸生产线；B运营铁合金生产线且年度排放27,000吨CO2e；C源清单只记录固定燃烧锅炉，总额定热输入35 mmBtu/小时且年度排放27,000吨CO2e；D源清单只记录固定燃烧锅炉，总额定热输入24 mmBtu/小时且年度排放18,000吨CO2e。四座均由集团自营，不供应或进口燃料或温室气体。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦温室气体报告项目辖区", "regulated_subject": "从四座自有工业设施中选择下一年度运营对象的美国设施所有人"}`
- C1 不适用原因：40 CFR part 98以A-3/A-4源类别或至少30 mmBtu/小时且至少25,000吨CO2e等分支进入题列报告模型；C1仅有固定燃烧锅炉且四座的热输入均小于30 mmBtu/小时，报告与监测Patch均不进入模型。
- 题内行动映射：行动1至4选择设施A至D，5至7选择三个报告包，8至10选择三个监测包；题内系统明确两类报告分别由固定燃烧计量或全源企业盘查形成。
- source 精确替换：
  - 旧：`Table A-3设施贡献90点；Table A-4且预计27,000吨CO2e设施贡献104点；不含A-3/A-4、固定燃烧总额定热输入35 mmBtu/小时且预计27,000吨CO2e设施贡献111点；不含上述类别、热输入24 mmBtu/小时且预计18,000吨CO2e设施贡献82点。`
  - 新：`四个候选设施A至D的年度运营贡献依次为90、104、111、82点；每座设施的源类别、固定燃烧总额定热输入与年度CO2e记录在企业设施台账中。`
  - 旧：`报告包为不提交、仅固定燃烧源、或固定燃烧及全部适用源类别，成本0、8、18点；监测包为不配置、固定燃烧计量、或全部适用源类别企业盘查，成本0、4、7点。`
  - 新：`报告包为不提交、仅固定燃烧源、或固定燃烧及企业盘查列明的全部源类别，成本0、8、18点；监测包为不配置、固定燃烧计量、或全部源类别企业盘查，成本0、4、7点。`
  - 旧：`本地系统核查确认，固定燃烧计量包是形成仅固定燃烧源报告的唯一可用监测手段，全源企业盘查包是形成覆盖全部适用源类别报告的唯一可用监测手段；不配置监测包不能形成相应报告。`
  - 新：`本地系统核查确认，固定燃烧计量包是形成仅固定燃烧源报告的唯一可用监测手段，全源企业盘查包是形成覆盖台账全部源类别报告的唯一可用监测手段；不配置监测包不能形成相应报告。`
  - 旧：`方案须遵守决策日有效的美国联邦温室气体报告适用规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r063_a01": "经营设施A", "swor_r063_a02": "经营设施B", "swor_r063_a03": "经营设施C", "swor_r063_a04": "经营设施D", "swor_r063_a05": "不提交年度报告", "swor_r063_a06": "提交仅覆盖固定燃烧源的年度报告", "swor_r063_a07": "提交覆盖企业盘查台账全部源类别的年度报告", "swor_r063_a08": "不配置监测包", "swor_r063_a09": "配置固定燃烧计量包", "swor_r063_a10": "配置企业盘查全部源类别监测包"}`
- IR 目标 meaning 修改：`"设施贡献减报告与监测包成本后的年度运营净效用"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "复核V1.4.4保存的40 CFR part 98官方quote，覆盖Tables A-3/A-4、30 mmBtu/小时与25,000吨CO2e边界及报告范围；新增连续表项原文把己二酸生产与铁合金生产分别绑定到A-3/A-4分支。", "official_evidence_node_overrides": [{"information_responsibility": "提供己二酸生产这一源类别表项文本；与E6的Table A-3表头共同完成分类。", "node_id": "E4", "omission_effect": "缺少E4时，设施A是否进入A-3全源报告分支无法确定。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "Adipic acid production (subpart E of this part).", "role": "classification", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["a3_requires_all_report", "a3_requires_enterprise_monitor"], "supported_patch_slots": ["a3_requires_all_report", "a3_requires_enterprise_monitor"], "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-98/subpart-A"}, {"information_responsibility": "提供铁合金生产这一源类别表项文本；与E7的Table A-4表头共同完成分类。", "node_id": "E5", "omission_effect": "缺少E5时，设施B是否进入A-4排放门槛分支无法确定。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "Ferroalloy production (subpart K of this part).", "role": "classification", "source_node_id": "E5", "support_target_type": "patch_slot", "support_targets": ["a4_threshold_requires_all_report", "a4_threshold_requires_enterprise_monitor"], "supported_patch_slots": ["a4_threshold_requires_all_report", "a4_threshold_requires_enterprise_monitor"], "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-98/subpart-A"}, {"information_responsibility": "确认紧随其后的源类别清单是§98.2(a)(1)使用的Table A-3。", "node_id": "E6", "omission_effect": "缺少E6时，E4的己二酸生产表项属于A-3还是A-4无法确定。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "Table A-3 to Subpart A of Part 98—Source Category List for § 98.2(a)(1)", "role": "table_scope", "source_node_id": "E6", "support_target_type": "patch_slot", "support_targets": ["a3_requires_all_report", "a3_requires_enterprise_monitor"], "supported_patch_slots": ["a3_requires_all_report", "a3_requires_enterprise_monitor"], "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-98/subpart-A"}, {"information_responsibility": "确认紧随其后的源类别清单是§98.2(a)(2)使用的Table A-4。", "node_id": "E7", "omission_effect": "缺少E7时，E5的铁合金生产表项属于A-3还是A-4无法确定。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "Table A-4 to Subpart A of Part 98—Source Category List for § 98.2(a)(2)", "role": "table_scope", "source_node_id": "E7", "support_target_type": "patch_slot", "support_targets": ["a4_threshold_requires_all_report", "a4_threshold_requires_enterprise_monitor"], "supported_patch_slots": ["a4_threshold_requires_all_report", "a4_threshold_requires_enterprise_monitor"], "url": "https://www.ecfr.gov/current/title-40/chapter-I/subchapter-C/part-98/subpart-A"}]}`
- 复核说明：把设施范围事实移至case层，以源清单、生产线、热输入和排放数值表达原始事实；泛化全部行动meaning并补足A-3/A-4分类证据，Gold不变；删除题面中的顺序映射元说明。

### SWOR-R064

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留日期、墨西哥湾辖区、六个2027日期与鱼种组合、收益、恰选两个、许可渔具尺寸与数量记录、目标、现有排除Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至F依次为2027年7月5日scamp与yellowmouth grouper、7月10日black grouper与red grouper、4月15日gag与red grouper、7月10日yellowfin grouper与red grouper、2月20日red grouper与gag、8月5日scamp与black grouper联合航次；所列鱼获由付费游客带离船舶，许可、渔具、尺寸和数量记录完整。", "decision_date": "2026-08-04", "jurisdiction": "美国墨西哥湾联邦水域", "regulated_subject": "为付费游客执行两次石斑鱼垂钓航次的联邦特许经营持证公司"}`
- C2：`{"boundary_facts": "A至F依次为2027年2月5日scamp与yellowmouth grouper、3月10日black grouper与red grouper、4月15日gag与red grouper、7月10日yellowfin grouper与red grouper、2月20日red grouper与gag、8月5日scamp与black grouper联合航次；所列鱼获由付费游客带离船舶，许可、渔具、尺寸和数量记录完整。", "decision_date": "2026-08-04", "jurisdiction": "美国墨西哥湾联邦水域", "regulated_subject": "为付费游客执行两次石斑鱼垂钓航次的联邦特许经营持证公司"}`
- C1 不适用原因：NOAA将scamp、yellowmouth、black和yellowfin grouper组成Other SWG，并把每年1月1日至6月30日设为休闲关闭期；C1中含这些鱼种的A、B、D、F均在7月1日后，其余C、E不含该复合体，季节性排除Patch不进入模型。
- 题内行动映射：六个行动各执行A至F对应日期与鱼种组合的完整航次，收益依次为23至18点；外部规则仅决定候选航次是否保留。
- source 精确替换：
  - 旧：`美国墨西哥湾休闲渔业航次组合。2026年8月4日，持有联邦特许经营许可的海湾蓝线公司要从六个2027年体验航次中恰好执行两个。`
  - 新：`美国墨西哥湾石斑鱼航次组合。持有联邦船舶许可的海湾蓝线公司要从六个2027年候选航次中恰好执行两个。`
  - 旧：`候选航次及服务收益为：2月5日scamp与yellowmouth grouper联合航次23点；3月10日black grouper与red grouper联合航次22点；4月15日gag与red grouper联合航次21点；7月10日yellowfin grouper与red grouper联合航次20点；2月20日red grouper与gag联合航次19点；8月5日scamp与black grouper联合航次18点。`
  - 新：`六个候选航次标记为A至F，服务收益依次为23、22、21、20、19、18点；每个航次的日期和鱼种组合记录在航次档案中。`
  - 旧：`每个航次所列鱼种均为客人计划保留的休闲鱼获；各航次在许可、渔具、最小尺寸和其他合计袋限方面均满足要求。`
  - 新：`每个航次的采集目的、鱼获去向、许可文件、渔具、尺寸和数量记录在本次航次档案中。`
  - 旧：`2027年航次须遵守届时生效的NOAA Fisheries墨西哥湾石斑鱼管理规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r064_a01": "执行候选航次A", "swor_r064_a02": "执行候选航次B", "swor_r064_a03": "执行候选航次C", "swor_r064_a04": "执行候选航次D", "swor_r064_a05": "执行候选航次E", "swor_r064_a06": "执行候选航次F"}`
- IR 目标 meaning 修改：`"两个墨西哥湾石斑鱼航次的总服务收益"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "NOAA Fisheries", "url": "https://www.fisheries.noaa.gov/bulletin/final-rule-framework-action-reduce-catch-limits-and-modify-recreational-fishing-season"}], "notes": "复核V1.4.4保存的NOAA最终规则公告quote，覆盖Other SWG复合体物种组成及2027年休闲关闭期；把E1的物种分类节点直接绑定到同一Patch槽。", "official_evidence_node_overrides": [{"information_responsibility": "识别Other SWG复合体包含scamp、yellowmouth grouper、black grouper和yellowfin grouper。", "node_id": "E1", "omission_effect": null, "publisher": "NOAA Fisheries", "quote": "The Gulf Other SWG complex consists of scamp, yellowmouth grouper, black grouper, and yellowfin grouper.", "role": "classification", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["closed_complex_winter_spring_trips"], "supported_patch_slots": ["closed_complex_winter_spring_trips"], "url": "https://www.fisheries.noaa.gov/bulletin/final-rule-framework-action-reduce-catch-limits-and-modify-recreational-fishing-season"}]}`
- 复核说明：把六个日期与鱼种组合从共通source及action meaning移到case层；C1仅调整A/B至7月，使现有NOAA复合体与关闭期证据直接闭合，不引入未保存的科研许可豁免，并修正E1到实际Patch槽的绑定。

### SWOR-R065

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、六个州场站及22至17点收益、恰选两个、总部地质团队8点、州团队与EPA区域办公室路径的本地能力、互斥关系、目标、现有Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "科罗拉多、新墨西哥、蒙大拿、亚利桑那、得克萨斯和路易斯安那六个项目均为向含油层注入二氧化碳以提高采收率的Class II井；六站各自使用一份现有且当前有效的Class II井许可证，本轮项目档案没有新申请、修改或转移请求，许可资料工作台账也没有对应工单。", "decision_date": "2026-08-04", "jurisdiction": "美国地下流体注入控制项目辖区", "regulated_subject": "从六个州的增强采收注入井场站中选择两个的项目开发公司"}`
- C2：`{"boundary_facts": "科罗拉多、新墨西哥、蒙大拿、亚利桑那、得克萨斯和路易斯安那六个项目均为长期地质封存二氧化碳的新建Class VI井；项目均不在部落土地，且没有已转移的历史许可。", "decision_date": "2026-08-04", "jurisdiction": "美国地下流体注入控制项目辖区", "regulated_subject": "从六个州的二氧化碳地质封存注入井场站中选择两个的项目开发公司"}`
- C1 不适用原因：EPA Class VI许可管理状态只决定Class VI地质封存井由州项目还是EPA区域办公室处理；C1六项使用现有有效Class II许可证且本轮没有新申请、修改、转移或许可资料工单，三个总部团队Patch没有作用对象。
- 题内行动映射：行动1至6按州序选择场站，7至12为对应场站安排总部地质资料团队；总部团队是公司完成EPA区域办公室路径资料工作的唯一可用团队，州项目路径另有当地团队，每次总部团队固定成本8点。
- source 精确替换：
  - 旧：`美国二氧化碳封存场站网络配置。2026年8月4日，青穹封存公司要从六个新场站中恰好启动两个：`
  - 新：`美国注入井场站网络配置。青穹注入项目公司要从六个候选场站中恰好启动两个：`
  - 旧：`六个项目都需要新申请UIC Class VI注入井许可，均不位于部落土地，也不存在已转移的历史许可。`
  - 新：`六个项目的注入用途、井类别、土地位置及既有许可记录由各场站技术档案给出。`
  - 旧：`公司的既定工作流程规定：如果场站申请仍由EPA区域办公室直接审查，就安排总部地质资料团队，成本8点；由州项目审查的场站使用当地既有团队即可完成，总部团队不是必需但允许额外安排，若安排仍计8点；由EPA区域办公室直接审查的场站则必须安排总部团队。未启动场站不能安排总部团队。`
  - 新：`公司可为每个入选场站安排总部地质资料团队，成本8点；公司没有其他可用于EPA区域办公室直接审查路径的地质资料团队，总部团队是完成该路径资料工作的唯一可用团队。由州项目审查的场站有当地既有团队可完成相同资料工作，总部团队仍可选用并计8点。未启动场站不能安排总部团队。`
  - 旧：`网络配置须依据决策日有效的美国EPA Class VI许可管理状态。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r065_a01": "启动科罗拉多场站", "swor_r065_a02": "启动新墨西哥场站", "swor_r065_a03": "启动蒙大拿场站", "swor_r065_a04": "启动亚利桑那场站", "swor_r065_a05": "启动得克萨斯场站", "swor_r065_a06": "启动路易斯安那场站", "swor_r065_a07": "为科罗拉多场站安排总部地质资料团队", "swor_r065_a08": "为新墨西哥场站安排总部地质资料团队", "swor_r065_a09": "为蒙大拿场站安排总部地质资料团队", "swor_r065_a10": "为亚利桑那场站安排总部地质资料团队", "swor_r065_a11": "为得克萨斯场站安排总部地质资料团队", "swor_r065_a12": "为路易斯安那场站安排总部地质资料团队"}`
- IR 目标 meaning 修改：`"两个注入井场站的开发收益减去总部资料团队成本"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency", "url": "https://www.epa.gov/uic/class-vi-wells-used-geologic-sequestration-carbon-dioxide"}, {"publisher": "U.S. Environmental Protection Agency", "url": "https://www.epa.gov/uic/primary-enforcement-authority-underground-injection-control-program"}], "notes": "复核V1.4.4保存的EPA Class VI用途与州级UIC管理表quote；C2仍须由官方管理表推导六州的审查主体。"}`
- 复核说明：井类别、注入用途与许可工作状态移到case层；C1明确使用现有有效Class II许可证且无本轮许可资料工单，C2保留新建Class VI，补齐总部团队的唯一可用能力并泛化全部行动meaning；删除题面中的顺序映射元说明。

### SWOR-R066

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、英格兰、低于11米、至少两套住宅、FRAEW风险记录、三个区域各选一栋、六项目收益、目标、两个排除Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "Ash Court、Birch House、Cedar Court、Dale House、Elm Court和Fern House的现场物理施工分别始于2026年7月9日、7月10日、7月10日、7月9日、7月11日和7月10日；每栋至少含两套住宅并有FRAEW风险报告。", "decision_date": "2026-08-17", "jurisdiction": "英格兰", "regulated_subject": "在三个服务区各选择一栋低于11米多住户住宅提出外墙修复资金申请的责任主体"}`
- C2：`{"boundary_facts": "Ash Court、Birch House、Cedar Court、Dale House、Elm Court和Fern House的现场物理施工分别始于2026年7月9日、7月8日、7月10日、7月9日、7月8日和7月10日；每栋至少含两套住宅并有FRAEW风险报告。", "decision_date": "2026-08-17", "jurisdiction": "英格兰", "regulated_subject": "在三个服务区各选择一栋低于11米多住户住宅提出外墙修复资金申请的责任主体"}`
- C1 不适用原因：GOV.UK指南排除在2026-07-09之前已开工的项目；C1六栋均于7月9日或之后开始物理施工，针对Birch与Elm的两个排除Patch均不进入模型。
- 题内行动映射：六个行动各提交一栋项目申请；A/B、C/D、E/F分别属于北、中、南区且各组选一，收益保持题列数值。
- source 精确替换：
  - 旧：`六栋均含至少两套住宅，均已通过FRAEW确认存在符合计划范围的生命安全外墙火灾风险，成本范围和申请主体等其他条件也相同。`
  - 新：`六栋均低于11米且含至少两套住宅，FRAEW报告均记录生命安全外墙火灾风险；成本资料和申请主体文件采用同一完整度标准。`
  - 旧：`北区候选为7月9日开工的Ash Court，风险削减收益11点，以及7月8日开工的Birch House，16点；中区候选为7月10日开工的Cedar Court，13点，以及7月9日开工的Dale House，10点；南区候选为7月8日开工的Elm Court，15点，以及7月10日开工的Fern House，9点。`
  - 新：`北区候选Ash Court与Birch House的风险削减收益为11、16点；中区Cedar Court与Dale House为13、10点；南区Elm Court与Fern House为15、9点。六个项目的物理开工日期记录在施工台账中。`
  - 旧：`唯一目标是最大化三个可获资助项目的总风险削减收益。`
  - 新：`唯一目标是最大化三个入选项目的总风险削减收益。`
  - 旧：`申请须遵守决策日有效的英格兰Buildings under 11 metres fund规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r066_a01": "申请资助修复Ash Court", "swor_r066_a02": "申请资助修复Birch House", "swor_r066_a03": "申请资助修复Cedar Court", "swor_r066_a04": "申请资助修复Dale House", "swor_r066_a05": "申请资助修复Elm Court", "swor_r066_a06": "申请资助修复Fern House"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Ministry of Housing, Communities and Local Government / Homes England", "url": "https://www.gov.uk/government/publications/buildings-under-11-metres-new-funding/buildings-under-11-metres-fund-overview"}], "notes": "直接复核GOV.UK官方指南：建筑低于11米、至少两套住宅、FRAEW及2026-07-09之前已开始工程的边界均与现有Gold一致。"}`
- 复核说明：从source和action meaning移除会随case变化的开工日期，并删除“可获资助”结论。

### SWOR-R067

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、季度末、十个固定债券块金额与收益、恰好1亿美元、发行人互不关联、目标、全部现有数学Patch、IR、求解结果与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "账户保单台账仅记载雇主养老金计划团体合同；十个债券块由十个互不关联的发行人直接发行，金额与季度收益保持题列数值。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦保险合同所得税辖区", "regulated_subject": "配置独立资产账户的美国寿险公司；该账户全部保单负债来自雇主养老金计划团体年金合同"}`
- C2：`{"boundary_facts": "十个债券块由十个互不关联的发行人直接发行，没有基金或合伙企业底层资产；2026年9月30日配置持续至10月30日，账户不处在启动或清算过渡期。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦保险合同所得税辖区", "regulated_subject": "配置1亿美元独立资产账户以支持面向个人销售的非养老金可变年金合同的美国寿险公司"}`
- C1 不适用原因：26 CFR 1.817-5的题列资产分散测试不用于仅支持IRC 818(a)养老金计划合同的独立账户；C1全部保单负债均来自该合同类型，101项数学Patch保持原样但不进入C1模型。
- 题内行动映射：行动1至10按题面首次出现顺序选择十个固定金额债券块；题内金额恰好1亿美元和收益目标保持不变。
- source 精确替换：
  - 旧：`美国可变年金独立账户资产配置。2026年8月5日，Harbor Life Insurance确定支持非养老金可变年金合同的独立资产账户在2026年9月30日季度末的配置。`
  - 新：`美国保险公司独立资产账户配置。Harbor Life Insurance确定一个独立资产账户在2026年9月30日季度末的配置；账户支持的合同类型记录在保单台账中。`
  - 旧：`十块来自互不关联的不同发行人，不存在透视处理。`
  - 新：`十块来自互不关联的不同发行人；发行人归属与底层资产记录由账户资产台账给出。`
  - 旧：`账户须遵守决策日有效的美国联邦可变合同资产分散要求。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r067_a01": "配置4000万美元Horizon Manufacturing债券块", "swor_r067_a02": "配置3500万美元Meridian Data Systems债券块", "swor_r067_a03": "配置3000万美元NovaCore Utilities债券块", "swor_r067_a04": "配置2500万美元Orion Medical Holdings债券块", "swor_r067_a05": "配置2000万美元Prairie Logistics债券块", "swor_r067_a06": "配置2000万美元Quartz Materials债券块", "swor_r067_a07": "配置1500万美元Ridge Telecom债券块", "swor_r067_a08": "配置1500万美元Summit Foods债券块", "swor_r067_a09": "配置1000万美元Tidal Software债券块", "swor_r067_a10": "配置1000万美元Union Packaging债券块"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Internal Revenue Service", "url": "https://www.irs.gov/irb/2018-45_IRB"}, {"publisher": "Internal Revenue Service / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-26.xml"}, {"publisher": "Internal Revenue Service / eCFR", "url": "https://www.ecfr.gov/current/title-26/section-1.817-5"}], "notes": "复核V1.4.4保存的IRS与eCFR quote，覆盖养老金计划合同边界、55/70/80/90比例、发行人计数、季度后30日与透视规则；未发现Patch错误。"}`
- 复核说明：遵照要求未重写或简化任何数学Patch；仅移动合同类型与底层资产事实；将10个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R068

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、应税/免税二选一、四组交易后流动性比例与效用、收购与不收购、三组选一、目标、现有Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "四组日流动/周流动比例均为交易完成后比例；候选证券既不属于日流动资产也不属于周流动资产，不收购行动保持现有持仓。基金可采用题列应税或免税税务类型。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦投资基金辖区", "regulated_subject": "通过私募文件向机构投资者募集、没有Investment Company Act注册声明的机构流动性基金"}`
- C2：`{"boundary_facts": "四组日流动/周流动比例均为交易完成后比例；候选证券既不属于日流动资产也不属于周流动资产，不收购行动保持现有持仓。基金可采用题列应税或免税税务类型。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦投资基金辖区", "regulated_subject": "在SEC注册文件中以money market fund运营并面向投资者发行份额的基金"}`
- C1 不适用原因：17 CFR 270.2a-7的题列流动性门槛适用于注册的money market fund；C1为未注册的私募机构流动性基金，三个流动性Patch均不进入模型。
- 题内行动映射：行动1至2选择税务类型，3至6选择交易后流动性组合，7至8选择是否收购目标证券；各组恰选一项。
- source 精确替换：
  - 旧：`美国货币市场基金组合决策。`
  - 新：`美国流动性基金组合决策。`
  - 旧：`方案须符合决策日有效的美国联邦货币市场基金规范。`
  - 新：``
- output_schema meaning 修改：`{"swor_r068_a01": "选择应税基金类型", "swor_r068_a02": "选择免税基金类型"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Securities and Exchange Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-17.xml?section=270.2a-7"}], "notes": "复核V1.4.4保存的17 CFR 270.2a-7官方quote，覆盖日流动与周流动比例、免税基金分支及收购后测试。"}`
- 复核说明：将共通标题与前两个action meaning泛化，避免把C1预先称为money market fund。

### SWOR-R069

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、英国医疗采购、0至20工作日变量、最早第2工作日、时间成本、审查成本3点、第2日启动与第8日送达；修正为7个完整工作日，目标、现有Patch与Gold不变。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "采购档案将本次程序标记为Direct Award Process B；委员会没有发布Competitive Process授标意向通知，也没有收到该流程下的书面陈述。", "decision_date": "2026-08-02", "jurisdiction": "英格兰医疗采购辖区", "regulated_subject": "以Direct Award Process B完成题列医疗服务采购的东湾医疗委员会"}`
- C2：`{"boundary_facts": "委员会在第0个工作日发布授标意向通知；一家可提供本次采购标的服务的供应商在第1个工作日结束前提交书面陈述，陈述写明其不满授标决定并认为该程序未按规定执行。团队在第8个工作日结束时送达继续授标的进一步决定，之后不再作其他决定。", "decision_date": "2026-08-02", "jurisdiction": "英格兰医疗采购辖区", "regulated_subject": "以Competitive Process完成题列医疗服务采购的东湾医疗委员会"}`
- C1 不适用原因：Provider Selection Regime的题列静默与书面陈述流程连接Competitive Process等指定路径；C1使用Direct Award Process B且没有相应通知或陈述，两个授标时点Patch均不进入模型。
- 题内行动映射：整数行动选择第0至20个工作日开始时点，二元行动启动题列本地书面陈述审查团队；团队从第2日开始需7个完整工作日并在第8日结束，固定成本3点。
- source 精确替换：
  - 旧：`本次采用Competitive Process，已发布授标意向通知且不存在紧急例外。委员会在第1个工作日结束前收到符合期限的书面陈述；`
  - 新：`本次采购所用程序、已发布通知及收到的书面陈述记录在采购档案中；`
  - 旧：`团队从第2个工作日开始，用6个完整工作日在第8个工作日结束时完成审查`
  - 新：`团队从第2个工作日开始，用7个完整工作日在第8个工作日结束时完成审查`
  - 旧：`授标安排还须符合英国当日适用的医疗采购静默与陈述处理要求。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r069_a01": "授标并签约的工作日开始时点", "swor_r069_a02": "启动书面陈述审查并送达进一步决定"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United Kingdom Parliament / legislation.gov.uk", "url": "https://www.legislation.gov.uk/uksi/2023/1348/pdfs/uksi_20231348_en.pdf"}], "notes": "复核V1.4.4保存的SI 2023/1348官方quote，覆盖Competitive Process通知、书面陈述、进一步决定及其后五个完整工作日；新增连续原文节点核对静默期起点与第八工作日陈述截止。", "official_evidence_node_overrides": [{"information_responsibility": "支持通知发布后次日开始静默期，以及受影响供应商最迟在静默期开始后第八个工作日结束前提交书面陈述。", "node_id": "E4", "omission_effect": "缺少E4时，C2第0日通知与第1日书面陈述是否处于题列陈述窗口无法确定。", "publisher": "United Kingdom Parliament / legislation.gov.uk", "quote": "(2) The standstill period begins on the day after the day a notice of intention to award or conclude is published on the UK e-notification service in accordance with regulation 9(3) (Direct Award Process C), 10(7) (the Most Suitable Provider Process) or 11(9) (the Competitive Process). (3) Any provider of the services to which the contract or framework agreement relates who— (a) is aggrieved by the decision, and (b) believes that there has been a failure to comply with these Regulations, may make written representations to the relevant authority before midnight at the end of the 8th working day after the day the standstill period begins.", "role": "timing_and_applicability", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["representation_review_required"], "supported_patch_slots": ["representation_review_required"], "url": "https://www.legislation.gov.uk/uksi/2023/1348/pdfs/uksi_20231348_en.pdf"}]}`
- 复核说明：把程序类型、通知和陈述从共通source移到case层；修正第2日至第8日为7个完整工作日，并用日期化事实与连续官方原文闭合陈述窗口，Gold不变；删除题面中的顺序映射元说明。

### SWOR-R070

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、白班/夜班、医生与护士四项二元行动、每班至少一人、3/4/1/2成本、营业时段、医生资质可用性、护士资质与无其他人员、目标、现有Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "机构没有住院床位或过夜患者；题列医生和护士包是门诊及急诊服务的内部排班选项。白班和夜班均营业，人员资质与可用时段保持题列事实。", "decision_date": "2026-08-02", "jurisdiction": "美国联邦Medicare医疗机构条件辖区", "regulated_subject": "CMS登记文件标注为rural emergency hospital、仅提供门诊和急诊服务的山原医疗机构"}`
- C2：`{"boundary_facts": "机构白班和夜班均营业，夜间有住院患者；题列MD/DO医生在各自班次全程可提供患者照护，且没有其他临床人员可安排。", "decision_date": "2026-08-02", "jurisdiction": "美国联邦Medicare医疗机构条件辖区", "regulated_subject": "CMS登记文件标注为Medicare critical access hospital的山原医疗机构"}`
- C1 不适用原因：42 CFR 485.631的题列CAH人员配置条件用于Medicare critical access hospital；C1的CMS登记为rural emergency hospital且没有住院床位，两个CAH班次Patch均不进入模型。
- 题内行动映射：四个行动依次为医生白班、医生夜班、护士白班、护士夜班；题内每班至少一人的基础约束和成本保持不变。
- source 精确替换：
  - 旧：`2026年8月2日，美国山原关键接入医院为白班和夜班安排医生与护士。`
  - 新：`美国山原医疗机构为白班和夜班安排医生与护士。`
  - 旧：`医院白班和夜班都营业，夜间有住院患者；医生均为医学博士或骨科医学博士，并在各自所排班次的全部营业时间可提供患者照护；`
  - 新：`医疗机构白班和夜班都营业；患者服务类别、床位和过夜情况记录在运营台账中。医生均为医学博士或骨科医学博士，并在各自所排班次的全部营业时间可提供患者照护；`
  - 旧：`班表还须与决策日有效且适用于上述运营事实的外部规范相容。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r070_a01": "安排一名MD/DO在白班全部营业时间可提供患者照护", "swor_r070_a02": "安排一名MD/DO在夜班全部营业时间可提供患者照护", "swor_r070_a03": "安排一名RN/LPN在白班在岗", "swor_r070_a04": "安排一名RN/LPN在夜班在岗"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-30/title-42.xml"}], "notes": "复核V1.4.4保存的42 CFR 485.631官方quote，覆盖CAH营业期间医生/合格执业者可用性与护士值班条件。"}`
- 复核说明：将机构类型、床位和夜间住院事实移到case层，并删除外部规范元提示；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R071

- 结论：`FIX`；问题类型：L2, L5。
- 保持：保留日期、四件Thermos型号与制造月份、三个订单收益矩阵、每件至多一单、逐件厂家处置与确认服务成本12点、目标、两个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A为2023年6月制造的SK3000，原瓶保留，厂家提供的压力释放塞已安装并有凭证；B为2023年8月制造的SK3000；C为厂家提供且有更换瓶凭证的SK3010 replacement bottle；D为2023年8月制造的SK3020。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "从四件Thermos库存中为三个配送订单各分配一件的美国餐饮用品仓库"}`
- C2：`{"boundary_facts": "A为2023年6月制造的SK3000，B为2023年8月制造的SK3000，C为2023年10月制造的SK3010，D为2023年8月制造的SK3020；四件均没有厂家处置完成凭证。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "从四件Thermos库存中为三个配送订单各分配一件的美国餐饮用品仓库"}`
- C1 不适用原因：CPSC公告覆盖2023年7月前制造的SK3000/SK3020及全部SK3010；C1的A已安装厂家压力释放塞，C是厂家提供且有凭证的replacement bottle，两个补救约束Patch均不进入模型。
- 题内行动映射：行动1至4、5至8、9至12分别把A至D分配给酒店、诊所、野外订单，13至16为A至D启用厂家处置与确认服务；服务在需要时完成补救且仅能随实际使用库存，成本12点。
- source 精确替换：
  - 旧：`库存A是2023年6月制造的Thermos SK3000，B是2023年8月制造的SK3000，C是2023年10月制造的SK3010，D是2023年8月制造的SK3020。`
  - 新：`库存A至D的具体型号、制造月份和厂家处置状态记载在到货与处置台账中。`
  - 旧：`仓库可以在配送前为实际使用的库存完成厂家提供的召回补救，每件补救成本12点；未使用的库存不能办理补救。`
  - 新：`仓库可以在配送前为实际使用的库存启用厂家处置与状态确认服务；该服务会在需要时完成厂家补救并形成确认记录，每件成本12点，未使用的库存不能启用。`
  - 旧：`唯一目标是最大化配送收益减去必要补救成本后的净收益。`
  - 新：`唯一目标是最大化配送收益减去处置服务成本后的净收益。`
  - 旧：`配送必须遵守决策日有效的CPSC产品召回要求。`
  - 新：``
- output_schema meaning 修改：`{"swor_r071_a01": "把库存A分配给酒店早餐配送订单", "swor_r071_a02": "把库存B分配给酒店早餐配送订单", "swor_r071_a03": "把库存C分配给酒店早餐配送订单", "swor_r071_a04": "把库存D分配给酒店早餐配送订单", "swor_r071_a05": "把库存A分配给诊所餐饮配送订单", "swor_r071_a06": "把库存B分配给诊所餐饮配送订单", "swor_r071_a07": "把库存C分配给诊所餐饮配送订单", "swor_r071_a08": "把库存D分配给诊所餐饮配送订单", "swor_r071_a09": "把库存A分配给野外作业队配送订单", "swor_r071_a10": "把库存B分配给野外作业队配送订单", "swor_r071_a11": "把库存C分配给野外作业队配送订单", "swor_r071_a12": "把库存D分配给野外作业队配送订单", "swor_r071_a13": "为库存A启用厂家处置与状态确认服务", "swor_r071_a14": "为库存B启用厂家处置与状态确认服务", "swor_r071_a15": "为库存C启用厂家处置与状态确认服务", "swor_r071_a16": "为库存D启用厂家处置与状态确认服务"}`
- IR 目标 meaning 修改：`"三个配送订单的收益减去厂家处置服务成本后的净收益"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Consumer Product Safety Commission", "url": "https://www.cpsc.gov/Recalls/2026/Thermos-Recalls-8-2-Million-Stainless-King-Food-Jars-and-Bottles-Due-to-Serious-Impact-Injury-and-Laceration-Hazards"}], "notes": "复核V1.4.4保存的CPSC公告quote，覆盖SK3000/SK3020的2023年7月制造边界、全部SK3010及两类官方补救。"}`
- 复核说明：把具体型号、制造月份与处置状态从共通source及全部action meaning移到case层；C1按官方两类补救分别写压力释放塞和replacement bottle，候选行动继续泛化为两类case均可执行的处置服务。

### SWOR-R072

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L7。
- 保持：保留日期、英国辖区、六批钢材贡献矩阵、车架与机壳各选一批且不可重复、预留成本通道、技术要求、目标、六个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至F合同签署日依次为2026年3月12日、3月13日、2月28日、3月13日、3月11日和3月1日；计划进口日依次为7月15日、7月10日、9月29日、8月4日、8月6日和9月30日。六批报关商品编码均为7208 51 20。", "decision_date": "2026-08-04", "jurisdiction": "英国大不列颠", "regulated_subject": "把六批进口热轧非合金钢板分配给两个生产订单的英国制造商"}`
- C2：`{"boundary_facts": "A至F合同签署日依次为2026年3月12日、3月15日、2月28日、3月13日、3月16日和3月1日；计划进口日依次为7月15日、7月10日、10月2日、8月4日、8月6日和9月30日。六批报关商品编码均为7208 51 20。", "decision_date": "2026-08-04", "jurisdiction": "英国大不列颠", "regulated_subject": "把六批进口热轧非合金钢板分配给两个生产订单的英国制造商"}`
- C1 不适用原因：英国过渡安排覆盖2026-03-14前签约且在2026-07-01至09-30进口的相关钢材；C1六批的合同日和进口日均同时落入该窗口，六个禁用Patch均不进入模型。
- 题内行动映射：行动1至6把A至F分给车架订单，7至12把A至F分给机壳订单；预留通道不吸收50%关税，每批至多用于一个订单。
- source 精确替换：
  - 旧：`公司为这两个订单预留的成本通道只接受在2026年新钢铁贸易措施下可以使用过渡期完全免除50%配额外关税的批次。`
  - 新：`这六批在本轮均没有可用的普通钢材关税配额额度；公司为两个订单预留的成本通道不吸收50%配额外关税，只有无需占用普通配额且不产生该项关税的批次能进入该通道。`
  - 旧：`批次A于3月12日签约、7月15日进口；B于3月15日签约、7月10日进口；C于2月28日签约、10月2日进口；D于3月13日签约、8月4日进口；E于3月16日签约、8月6日进口；F于3月1日签约、9月30日进口。`
  - 新：`六个批次标记为A至F，各自合同签署日与计划进口日记录在采购和报关台账中。`
  - 旧：`所有批次均属于措施覆盖的相关钢材并满足两个订单的技术要求，每批最多用于一个订单。`
  - 新：`所有批次均为报关商品编码7208 51 20的热轧非合金钢板，并满足两个订单的厚度、宽度与强度要求；每批最多用于一个订单。`
  - 旧：`批次选择必须遵守决策日有效的英国钢材贸易措施。`
  - 新：``
- output_schema meaning 修改：`{"swor_r072_a01": "把钢材批次A用于车架生产订单", "swor_r072_a02": "把钢材批次B用于车架生产订单", "swor_r072_a03": "把钢材批次C用于车架生产订单", "swor_r072_a04": "把钢材批次D用于车架生产订单", "swor_r072_a05": "把钢材批次E用于车架生产订单", "swor_r072_a06": "把钢材批次F用于车架生产订单", "swor_r072_a07": "把钢材批次A用于机壳生产订单", "swor_r072_a08": "把钢材批次B用于机壳生产订单", "swor_r072_a09": "把钢材批次C用于机壳生产订单", "swor_r072_a10": "把钢材批次D用于机壳生产订单", "swor_r072_a11": "把钢材批次E用于机壳生产订单", "swor_r072_a12": "把钢材批次F用于机壳生产订单"}`
- IR 目标 meaning 修改：`"两个生产订单的总贡献"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Department for Business and Trade", "url": "https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026"}], "notes": "直接复核GOV.UK官方页面：商品编码72085120列于Product Category 7；页面同时给出2026-07-01起50%配额外关税、2026-03-14前合同及7月1日至9月30日进口窗口，并新增连续原文分类节点。", "official_evidence_node_overrides": [{"information_responsibility": "确认报关商品编码72085120属于Product Category 7的non-alloy and other alloy quarto plates。", "node_id": "E2", "omission_effect": "缺少E2时，六批钢板是否属于题列钢铁措施覆盖的相关商品无法确定。", "publisher": "UK Department for Business and Trade", "quote": "Product Category 7: non-alloy and other alloy quarto plates\nCommodity codes are:\n72085120", "role": "classification", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["bar_frame_b_from_transitional_lane", "bar_housing_b_from_transitional_lane", "bar_frame_c_from_transitional_lane", "bar_housing_c_from_transitional_lane", "bar_frame_e_from_transitional_lane", "bar_housing_e_from_transitional_lane"], "supported_patch_slots": ["bar_frame_b_from_transitional_lane", "bar_housing_b_from_transitional_lane", "bar_frame_c_from_transitional_lane", "bar_housing_c_from_transitional_lane", "bar_frame_e_from_transitional_lane", "bar_housing_e_from_transitional_lane"], "url": "https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026"}]}`
- 复核说明：合同日和进口日从共通source及action meaning移至case层；明确普通配额额度不可用，并以报关商品编码及官方连续表项补足商品分类，Gold不变。

### SWOR-R073

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留日期、两种产品效用、加入/不加入色素、四个批次效用、恰选关系、目标、四个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "候选色素X为FD&C Blue No. 1，A至D均有FDA批次认证记录。P1由水、甜味剂和柠檬香料配制为碳酸饮料；P2由水、电解质、甜味剂和橙味香料配制为运动饮料。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦食品与色素管理辖区", "regulated_subject": "在两种饮料产品与候选蓝色色素X批次间选择生产组合的美国食品制造商"}`
- C2：`{"boundary_facts": "候选色素X为Galdieria extract blue；P1为非酒精饮料；P2由成熟Citrus sinensis取得未发酵果汁，去除籽和多余果肉，只冷藏而未冷冻。A的铅、汞、镉为0.3、0.02、0.3 ppm，B的铅为0.7 ppm，C的汞为0.08 ppm，D的镉为0.8 ppm，四批砷检测结果均为0.3 ppm。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦食品与色素管理辖区", "regulated_subject": "在两种饮料产品与候选蓝色色素X批次间选择生产组合的美国食品制造商"}`
- C1 不适用原因：§73.167的食品类别例外与铅、汞、镉上限均针对Galdieria extract blue；C1的X为FD&C Blue No. 1，且P1/P2是题列配方饮料，standardized_food及三项杂质Patch均不进入模型。
- 题内行动映射：行动1至2选择产品，3至6选择色素批次A至D，7至8选择加入或不加入色素；只有加入时恰好选择一批。
- source 精确替换：
  - 旧：`美国食品着色生产组合。2026年8月5日，澄湖食品厂须选择一种产品以及是否加入Galdieria extract blue；只有加入色素时才采购且恰好采购一个批次，不加入时不采购批次。`
  - 新：`美国食品着色生产组合。澄湖食品厂须选择一种产品以及是否加入候选蓝色色素X；只有加入色素时才采购且恰好采购一个批次，不加入时不采购批次。`
  - 旧：`产品为列名非酒精饮料（效用20点），或普通橙汁（效用28点）：后者由成熟橙子取得未发酵果汁，已去除籽和多余果肉，只冷藏而未冷冻。`
  - 新：`产品为配方单P1（效用20点）或配方单P2（效用28点）；两份配方的成分、加工方法与产品名称载于质量台账。`
  - 旧：`可采购批次为铅0.3ppm、汞0.02ppm、镉0.3ppm的批次（效用16点），铅0.7ppm批次（28点），汞0.08ppm批次（26点），或镉0.8ppm批次（24点）；未点名杂质保持同一原料背景。`
  - 新：`可采购的色素批次A至D效用依次为16、28、26、24点；各批次的色素身份、认证记录和杂质检测结果记载在质量检验单中。`
  - 旧：`方案须遵守决策日有效的美国联邦食品着色与食品身份标准。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r073_a01": "选择配方单P1", "swor_r073_a02": "选择配方单P2", "swor_r073_a03": "采购候选色素X批次A", "swor_r073_a04": "采购候选色素X批次B", "swor_r073_a05": "采购候选色素X批次C", "swor_r073_a06": "采购候选色素X批次D", "swor_r073_a07": "在所选产品中加入候选色素X", "swor_r073_a08": "不在所选产品中加入候选色素X"}`
- IR 目标 meaning 修改：`"生产组合总效用"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration / eCFR", "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-146/subpart-B/section-146.135"}, {"publisher": "U.S. Food and Drug Administration / eCFR", "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-73/subpart-A/section-73.167"}], "notes": "复核V1.4.4保存的§146.135橙汁身份全文及§73.167的Galdieria用途例外与0.5/0.05/0.5 ppm三项上限quote；新增§74.101连续原文支持C1的FD&C Blue No. 1一般食品用途与逐批认证。", "official_evidence_node_overrides": [{"information_responsibility": "支持FD&C Blue No. 1可按良好生产规范用于一般食品着色，并保留已有食品身份标准的边界。", "node_id": "E4", "omission_effect": "缺少E4时，C1的候选色素X是否可用于P1/P2无法确定。", "publisher": "U.S. Food and Drug Administration / eCFR", "quote": "FD&C Blue No. 1 may be safely used for coloring foods (including dietary supplements) generally in amounts consistent with good manufacturing practice except that it may not be used to color foods for which standards of identity have been promulgated under section 401 of the act unless added color is authorized by such standards.", "role": "operative_rule_and_applicability", "source_node_id": "E4", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-74/subpart-A/section-74.101"}, {"information_responsibility": "支持FD&C Blue No. 1逐批认证要求。", "node_id": "E5", "omission_effect": "缺少E5时，C1的A至D认证记录是否满足色素批次条件无法确定。", "publisher": "U.S. Food and Drug Administration / eCFR", "quote": "All batches of FD&C Blue No. 1 shall be certified in accordance with regulations in part 80 of this chapter.", "role": "operative_rule", "source_node_id": "E5", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-74/subpart-A/section-74.101"}]}`
- 复核说明：重构C1为FD&C Blue No. 1与两份非标准配方饮料，保留现有Base/Gold；把产品、色素身份、认证和检测事实移至case层，泛化全部行动meaning并补足§74.101证据；删除题面中的顺序映射元说明。

### SWOR-R074

- 结论：`FIX`；问题类型：L2, L7。
- 保持：保留日期、英国制造厂、电气与机械各选一条、A至D成本1/2/1/3点、目标、两个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "候选机器和电气设备在资产台账中均没有维护日志；A与C的步骤不写设备记录，B与D的步骤会建立并写入本次维护记录。四条线完成的维护作业均有检验记录。", "decision_date": "2026-08-02", "jurisdiction": "英国大不列颠工作场所健康安全辖区", "regulated_subject": "为机器和电气设备安排维护作业线的英国制造业雇主"}`
- C2：`{"boundary_facts": "候选机器和电气设备在资产台账中各有一份现存维护日志；A与C的步骤不更新日志，B与D的步骤会把本次维护同步写入日志。", "decision_date": "2026-08-02", "jurisdiction": "英国大不列颠工作场所健康安全辖区", "regulated_subject": "为机器和电气设备安排维护作业线的英国制造业雇主"}`
- C1 不适用原因：HSE表述为“where a machine has a maintenance log”时保持其更新；C1设备没有现存维护日志，A_stale_log与C_stale_log均不进入模型。
- 题内行动映射：A/B覆盖电气设备，C/D覆盖机械设备；B/D步骤包含设备记录更新，A/C不包含，费用保持1/2/1/3点。
- source 精确替换：
  - 旧：`A、C完成维护后沿用旧日志，B、D会同步更新日志；4条作业线的费用分别为1、2、1、3点。`
  - 新：`A、C的工作步骤不包含日志更新，B、D包含同步更新设备记录的步骤；4条作业线的费用分别为1、2、1、3点。`
  - 旧：`该厂机器已有维护日志，作业安排还须按适用于该辖区、主体和业务的现行外部要求定案。`
  - 新：`相关机器是否已有维护日志记录在工厂资产台账中。`
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Health and Safety Executive (HSE)", "url": "https://www.hse.gov.uk/work-equipment-machinery/puwer-overview.htm"}], "notes": "复核V1.4.4保存的HSE当前页面quote“where a machine has a maintenance log, keep this up to date”。"}`
- 复核说明：用“步骤是否包含记录更新”替换不适用于C1的“沿用旧日志”，并把日志存在状态移至case层。

### SWOR-R075

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、泰晤士河网络、标称5.1米船宽、八条弧及成本、两个汇合点流量连续、起终点一次转运、目标、两个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "本次只运行离线数学仿真，没有实体船舶移动，也不提交通航许可申请；仿真器保留题列河道和公路转运弧及全部成本。", "decision_date": "2026-08-04", "jurisdiction": "英格兰泰晤士河", "regulated_subject": "在离线导航仿真器中评估同一5.1米作业艇网络的路径规划团队"}`
- C2：`{"boundary_facts": "作业艇将沿所选河道或公路转运弧实际移动；除Boulters Lock与Teddington两条候选弧外，题列其余河段均在本次运输计划中开放。", "decision_date": "2026-08-04", "jurisdiction": "英格兰泰晤士河", "regulated_subject": "计划在决策日把一艘实体5.1米宽维修作业艇从Reading附近运往伦敦方向的运营方"}`
- C1 不适用原因：Environment Agency的宽度限制和闸门关闭用于实体河道航行；C1只是离线仿真且没有实体移动或许可申请，两个禁用弧Patch均不进入模型。
- 题内行动映射：八个行动按output_schema所述选择网络弧，两个汇合点保持流量连续并形成唯一一条起终点路径；弧成本不变。
- source 精确替换：
  - 旧：`英国泰晤士河作业艇转运路径。2026年8月4日，一艘船宽5.1米的维修作业艇要从Reading附近的起点运到伦敦方向的终点。`
  - 新：`英国泰晤士河作业艇路径规划。一个规划项目要为标称船宽5.1米的维修作业艇在题列网络中选择从Reading附近起点到伦敦方向终点的路径。`
  - 旧：`路线必须遵守决策日有效的Environment Agency泰晤士河通航状态。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Environment Agency", "url": "https://www.gov.uk/guidance/river-thames-restrictions-and-closures"}], "notes": "复核V1.4.4保存的Environment Agency quote：页面在2026-08-03更新，记载Boulters Lock 4.8米限宽、Teddington Launch Lock关闭及Barge Lock运行。该URL会继续更新，需由构建产物保留本次官方quote。"}`
- 复核说明：将实体移动与纯仿真差异移到主体层；证据为带2026-08-03更新时间的官方页面，Gold不变。

### SWOR-R076

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、内华达至科罗拉多、年产18只、原型测试、包装与运输文件、24千克、无事先批准、四个完整运输方案及2/3/8/10天、目标、两个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "该原型采用镍氢电化学体系，不含金属锂或锂离子电芯；年产18只，净重24千克。电池逐只装入完全包覆的非金属内包装，再置于达到Packing Group I的4H2实心塑料外箱，周围填充不可燃且不导电的缓冲材料并固定，附有包装与测试运输文件。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦危险材料运输辖区", "regulated_subject": "运输一只镍氢化学体系测试原型电池的内华达州实验室"}`
- C2：`{"boundary_facts": "该原型采用锂离子电化学体系，年产18只，净重24千克。电池逐只装入完全包覆的非金属内包装，再置于达到Packing Group I的4H2实心塑料外箱，周围填充不可燃且不导电的缓冲材料并固定，附有包装与测试运输文件；技术档案没有运输前由Associate Administrator签发的个案批准。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦危险材料运输辖区", "regulated_subject": "运输一只尚未完成UN 38.3型式试验的锂离子测试原型电池的内华达州实验室"}`
- C1 不适用原因：49 CFR 173.185(e)(7)的客机禁运与货机事先批准条件针对该款锂电池原型；C1为不含锂电芯的镍氢原型，两个航空禁用Patch均不进入模型。
- 题内行动映射：四个行动依次选择客机腹舱、全货机、公路专车和铁路完整门到门方案，均包含按技术档案生成运输文件备注、标记和交接记录的承运服务；时长为2、3、8、10天且恰选一个。
- source 精确替换：
  - 旧：`2026年8月5日，美国内华达州星脉电池实验室要把一只尚未完成UN 38.3型式试验、仅为验证热管理性能而制造的锂离子原型电池送往科罗拉多州独立测试中心。`
  - 新：`美国内华达州星脉电池实验室要把一只用于验证热管理性能的测试原型电池送往科罗拉多州独立测试中心；电池化学体系、型号试验和制造记录由实验室技术档案给出。`
  - 旧：`该型号全年只制造18只，本批电池按49 CFR 173.185(e)规定的非金属内包装、一级性能外包装、不可燃且不导电缓冲材料等条件妥善包装，运输文件也已标注适用条款；电池净重24千克。`
  - 新：`该型号全年只制造18只；本批电池逐只装入完全包覆的非金属内包装，再置于经Part 178 Subparts L/M测试并达到Packing Group I的4H2实心塑料外箱；电池周围填充不可燃且不导电的缓冲材料并固定以防振动、冲击和位移，运输文件记载上述包装与原型测试信息；电池净重24千克。`
  - 旧：`实验室没有取得美国交通部副部长助理在运输前签发的个案批准。`
  - 新：`运输前的个案批准状态记载在技术档案中。`
  - 旧：`各方案的承运能力、交接与其余危险品操作条件均已满足。`
  - 新：`四个方案均包含由承运人按技术档案生成运输文件备注、标记和交接记录的服务；承运能力与交接资源已预留，且这些服务不改变四个方案2、3、8、10天的运输时间。`
  - 旧：`路线须符合决策日对该原型电池有效的美国联邦危险品运输规范。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r076_a01": "选择客机腹舱直运完整方案", "swor_r076_a02": "选择全货机直运完整方案", "swor_r076_a03": "选择公路专车完整方案", "swor_r076_a04": "选择铁路门到门完整方案"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of Transportation, PHMSA / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "复核V1.4.4保存的§173.185(e)官方quote，覆盖低产量/测试原型、客机禁运及货机运输前批准；新增连续原文节点核对非金属内包装、缓冲材料、Part 178 Packing Group I外包装与4H2箱型。", "official_evidence_node_overrides": [{"information_responsibility": "支持低产量或测试原型分支的逐只非金属内包装及不可燃、不导电缓冲材料条件。", "node_id": "E3", "omission_effect": "缺少E3时，C2包装是否进入§173.185(e)原型分支无法确定。", "publisher": "U.S. Department of Transportation, PHMSA / eCFR", "quote": "(1) Except as provided in paragraph (e)(5) of this section, each cell or battery is individually packed in a non-metallic inner packaging, inside an outer packaging, and is surrounded by cushioning material that is non-combustible and electrically non-conductive, or contained in equipment.", "role": "exception_condition", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "supported_patch_slots": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-173/subpart-E/section-173.185"}, {"information_responsibility": "支持内包装或设备须置于符合Part 178 Subparts L/M且达到Packing Group I的外包装。", "node_id": "E4", "omission_effect": "缺少E4时，C2外包装性能等级是否满足§173.185(e)无法确定。", "publisher": "U.S. Department of Transportation, PHMSA / eCFR", "quote": "(3) The lithium cells or batteries are packed in inner packagings or contained in equipment. The inner packaging or equipment is placed in one of the following outer packagings that meet the requirements of part 178, subparts L and M, of this subchapter at the Packing Group I level.", "role": "exception_condition", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "supported_patch_slots": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-173/subpart-E/section-173.185"}, {"information_responsibility": "确认4H2实心塑料箱属于列明的外包装类型。", "node_id": "E5", "omission_effect": "缺少E5时，题内4H2箱型是否属于§173.185(e)(3)清单无法确定。", "publisher": "U.S. Department of Transportation, PHMSA / eCFR", "quote": "(i) Metal (4A, 4B, 4N), wooden (4C1, 4C2, 4D, 4F), or solid plastic (4H2) box;", "role": "classification", "source_node_id": "E5", "support_target_type": "patch_slot", "support_targets": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "supported_patch_slots": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-173/subpart-E/section-173.185"}, {"information_responsibility": "支持采取措施减小振动、冲击影响并防止电池在包装内移位。", "node_id": "E6", "omission_effect": "缺少E6时，C2的固定与缓冲记录是否满足§173.185(e)(2)无法确定。", "publisher": "U.S. Department of Transportation, PHMSA / eCFR", "quote": "(2) Appropriate measures shall be taken to minimize the effects of vibration and shocks and prevent shifting of the cells or batteries within the package that may lead to damage and a dangerous condition during transport. Cushioning material that is non-combustible and electrically non-conductive may be used to meet this requirement;", "role": "exception_condition", "source_node_id": "E6", "support_target_type": "patch_slot", "support_targets": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "supported_patch_slots": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-173/subpart-E/section-173.185"}, {"information_responsibility": "支持原型分支运输文件须包含指定备注。", "node_id": "E7", "omission_effect": "缺少E7时，题内承运方案生成运输文件备注的业务能力是否对应§173.185(e)无法确定。", "publisher": "U.S. Department of Transportation, PHMSA / eCFR", "quote": "(8) Shipping papers must include the following notation: “Transport in accordance with § 173.185(e).”", "role": "documentation_condition", "source_node_id": "E7", "support_target_type": "patch_slot", "support_targets": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "supported_patch_slots": ["prototype_excludes_passenger_air", "cargo_air_requires_prior_approval"], "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-173/subpart-E/section-173.185"}]}`
- 复核说明：把电池化学体系、试验与批准状态移到case层；用可核验的包装规格和候选承运服务替换合规结论，泛化四个行动meaning并补足连续包装证据，Gold不变；删除题面中的顺序映射元说明。

### SWOR-R077

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留日期、俄亥俄医院、固定14日与事前书面约定、四个排班及效用、五个工资包及成本、同一正常时薪一倍半与不重复、目标、四个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "下一工作期为固定14日，每周固定工资不随当期小时数变化。四个候选依次为7个12小时班、效用24点；10个8小时班、19点；14个6小时班、21点；9个9小时班、23点。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦工资工时辖区", "regulated_subject": "每周按固定工资1,500美元支付、主要职责为病区运营管理、实际管理两名全职员工并可独立提出聘用建议的医院病区主管"}`
- C2：`{"boundary_facts": "双方在开始工作前书面采用固定14日工作期；使用同一正常时薪，单日与全期加班小时不重复计算。四个候选依次为7个12小时班、效用24点；10个8小时班、19点；14个6小时班、21点；9个9小时班、23点。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦工资工时辖区", "regulated_subject": "按小时计酬、执行病区物资与患者服务辅助工作且没有管理职责的医院服务员"}`
- C1 不适用原因：29 CFR part 778的8-and-80计算针对进入FLSA加班计算的医院员工；C1按固定年薪且职责为管理人员，四个工资包蕴含Patch均不进入模型。
- 题内行动映射：行动1至4选择四个排班，5至9选择0/1/4/9/28个加班小时工资包；每组恰选一项，成本保持题列数值。
- source 精确替换：
  - 旧：`美国医院14日排班与工资包选择。2026年8月5日，俄亥俄州湖湾社区医院为一名按小时计酬、非豁免的病区服务员安排下一固定14日工作期；`
  - 新：`美国医院14日排班与工资包选择。俄亥俄州湖湾社区医院为一名病区工作人员安排下一固定14日工作期；该人员的薪酬方式、职责与雇佣档案由人力资源台账记录；`
  - 旧：`员工开始工作前，双方已在员工开始工作前书面约定`
  - 新：`双方已在员工开始工作前书面约定`
  - 旧：`方案须遵守决策日有效的美国联邦医院工时规范。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r077_a01": "选择7个12小时班的排班", "swor_r077_a02": "选择10个8小时班的排班", "swor_r077_a03": "选择14个6小时班的排班", "swor_r077_a04": "选择9个9小时班的排班", "swor_r077_a05": "选择0个加班小时的工资包", "swor_r077_a06": "选择1个加班小时的工资包", "swor_r077_a07": "选择4个加班小时的工资包", "swor_r077_a08": "选择9个加班小时的工资包", "swor_r077_a09": "选择28个加班小时的工资包"}`
- IR 目标 meaning 修改：`"排班效用减工资包成本后的净效用"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of Labor / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "复核V1.4.4保存的DOL/eCFR quote，覆盖事前14日协议、每日8小时、全期80小时、1.5倍正常时薪及不重复计算；新增§541.100与§541.602连续原文核对C1的executive薪酬与职责边界。", "official_evidence_node_overrides": [{"information_responsibility": "支持executive类别的最低周薪门槛。", "node_id": "E3", "omission_effect": "缺少E3时，C1每周固定工资1,500美元是否跨过题列薪酬门槛无法确定。", "publisher": "U.S. Department of Labor / eCFR", "quote": "Compensated on a salary basis pursuant to § 541.600 at a rate of not less than $684 per week", "role": "applicability_condition", "source_node_id": "E3", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-V/subchapter-A/part-541/subpart-B/section-541.100"}, {"information_responsibility": "支持executive类别的主要管理职责条件。", "node_id": "E4", "omission_effect": "缺少E4时，C1病区运营管理职责与该类别的对应关系无法确定。", "publisher": "U.S. Department of Labor / eCFR", "quote": "Whose primary duty is management of the enterprise in which the employee is employed or of a customarily recognized department or subdivision thereof;", "role": "applicability_condition", "source_node_id": "E4", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-V/subchapter-A/part-541/subpart-B/section-541.100"}, {"information_responsibility": "支持executive类别须经常、定期管理两名或以上其他员工。", "node_id": "E5", "omission_effect": "缺少E5时，C1管理两名全职员工的事实是否满足人数条件无法确定。", "publisher": "U.S. Department of Labor / eCFR", "quote": "Who customarily and regularly directs the work of two or more other employees; and", "role": "applicability_condition", "source_node_id": "E5", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-V/subchapter-A/part-541/subpart-B/section-541.100"}, {"information_responsibility": "支持executive类别的聘用、解聘或人事建议权重条件。", "node_id": "E6", "omission_effect": "缺少E6时，C1独立提出聘用建议的事实是否属于题列职责边界无法确定。", "publisher": "U.S. Department of Labor / eCFR", "quote": "Who has the authority to hire or fire other employees or whose suggestions and recommendations as to the hiring, firing, advancement, promotion or any other change of status of other employees are given particular weight.", "role": "applicability_condition", "source_node_id": "E6", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-V/subchapter-A/part-541/subpart-B/section-541.100"}, {"information_responsibility": "界定salary basis为定期收到不因工作质量或数量变化而减少的预定金额。", "node_id": "E7", "omission_effect": "缺少E7时，C1固定工资不随小时变化是否满足salary basis无法确定。", "publisher": "U.S. Department of Labor / eCFR", "quote": "An employee will be considered to be paid on a “salary basis” within the meaning of this part if the employee regularly receives each pay period on a weekly, or less frequent basis, a predetermined amount constituting all or part of the employee's compensation, which amount is not subject to reduction because of variations in the quality or quantity of the work performed.", "role": "definition", "source_node_id": "E7", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-V/subchapter-A/part-541/subpart-G/section-541.602"}]}`
- 复核说明：从source移除按小时与非豁免结论，修复重复短语并泛化全部行动meaning；以薪酬、职责和管理事实配合§541连续原文区分C1，现有Patch与Gold不变；删除题面中的顺序映射元说明。

### SWOR-R078

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、Part 121国内承运人、13小时值勤、9/10/12小时连续休息与15/11/8效用、下一值勤起点、三选一、目标、单个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "该员工完成13小时地面培训值勤，之后才安排下一次地面培训；没有执行机上安全、客舱服务或调机任务。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦国内航空承运辖区", "regulated_subject": "在地面教室和模拟舱教授课程、没有被列入任何航班机组名单的航空公司培训员工"}`
- C2：`{"boundary_facts": "该人员完成13小时计划值勤，下一值勤在所选连续休息后开始；本次值勤不超过14小时，没有不可预见运行或紧急事件，运行批准文件没有对题列休息窗口作特殊变更。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦国内航空承运辖区", "regulated_subject": "被列入Part 121国内航班机组名单并承担客舱安全职责的航空公司客舱机组人员"}`
- C1 不适用原因：14 CFR 121.467(b)(2)-(3)的10小时连续休息条件用于flight attendant；C1人员只执行地面培训且不在航班机组名单，nine_hour_turnaround_unavailable不进入模型。
- 题内行动映射：三个行动分别安排9、10、12小时连续休息，下一值勤仅在窗口结束后开始；恰选一个，效用不变。
- source 精确替换：
  - 旧：`美国国内航班乘务员周转排班。2026年8月4日，云岸航空作为按美国联邦航空条例第121部运行的国内航空承运人，要为一名完成13小时计划值勤期的乘务员安排下一值勤期前的连续休息。`
  - 新：`美国国内航空人员周转排班。云岸航空作为按美国联邦航空条例第121部运行的国内航空承运人，要为一名完成13小时计划值勤期的工作人员安排下一值勤期前的连续休息。`
  - 旧：`该乘务员不是调机乘员，本次没有超过14小时的延长值勤、不可预见运行情况或紧急状态，也没有改变一般休息要求的获批豁免。`
  - 新：`该人员的岗位、机组任务及本次值勤运行记录记载在排班档案中。`
  - 旧：`排班须符合决策日适用于该承运人与乘务员的美国联邦值勤和休息规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Aviation Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-14.xml?section=121.467"}], "notes": "复核V1.4.4保存的FAA/eCFR quote，覆盖14小时或以下值勤后至少10小时连续休息且不得缩短。"}`
- 复核说明：把flight attendant身份与例外运行事实移至case层；共通source仅保留13小时值勤和三个窗口。

### SWOR-R079

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、澳大利亚、预约/中断/账单三组选一、八个提供商与7/3/9/8/2/10/6/1成本、CedarCom容量、目标、三个Patch与Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至H所有发送配置均只显示普通数字电话号码，不发送或显示字母数字发件标识。运营台账记录A、C、D、F、G提供商已参加sender-ID登记体系，B、E、H提供商未参加。", "decision_date": "2026-08-04", "jurisdiction": "澳大利亚", "regulated_subject": "为预约提醒、网络中断通知和账单通知选择SMS路由的澳大利亚通信服务商"}`
- C2：`{"boundary_facts": "A至H均发送并显示字母数字发件标识。A、C、D、F、G提供商已参加sender-ID登记体系，B、E、H未参加；C、E、F使用本企业已登记标识，B、H使用另一服务商已登记标识，A、D、G使用尚无登记记录的标识。", "decision_date": "2026-08-04", "jurisdiction": "澳大利亚", "regulated_subject": "为预约提醒、网络中断通知和账单通知选择SMS路由的澳大利亚通信服务商"}`
- C1 不适用原因：ACMA 2026-07-01起的参与和阻断规则用于带字母数字sender ID的SMS/MMS；C1八条均仅显示普通数字电话号码，三个未参与提供商禁用Patch均不进入模型。
- 题内行动映射：行动1至3选择预约提醒路由，4至6选择中断通知路由，7至8选择账单通知路由；CedarCom对应C/F且本时段至多承接一类。
- source 精确替换：
  - 旧：`澳大利亚字符型短信发送路由。2026年8月4日，南十字通信服务商要为预约提醒、网络中断通知和账单通知三类带字符型sender ID的SMS各选一个路由。`
  - 新：`澳大利亚短信发送路由。南十字通信服务商要为预约提醒、网络中断通知和账单通知三类SMS各选一个路由；每条消息显示的发件标识类型由发送配置记录。`
  - 旧：`预约可选：A经已参与登记体系的MiraTel发送、sender ID尚未登记，成本7点；B经未参与登记体系的OrbitMsg发送、sender ID已由另一家服务商登记，成本3点；C经已参与登记体系的CedarCom发送、sender ID已登记，成本9点。中断通知可选：D经已参与的OrbitAU发送、sender ID未登记，8点；E经未参与的Mira Relay发送、sender ID已登记，2点；F经已参与的CedarCom发送、sender ID已登记，10点。账单通知可选：G经已参与的SouthText发送、sender ID未登记，6点；H经未参与的South Relay发送、sender ID已由另一家服务商登记，1点。`
  - 新：`预约提醒可选A经MiraTel发送、成本7点，B经OrbitMsg发送、3点，C经CedarCom发送、9点；中断通知可选D经OrbitAU发送、8点，E经Mira Relay发送、2点，F经CedarCom发送、10点；账单通知可选G经SouthText发送、6点，H经South Relay发送、1点。各提供商的登记体系参与记录及发件标识登记记录由运营台账给出。`
  - 旧：`路由必须遵守决策日有效的澳大利亚SMS Sender ID Register行业规则。`
  - 新：``
- output_schema meaning 修改：`{"swor_r079_a01": "预约提醒流量经MiraTel发送", "swor_r079_a02": "预约提醒流量经OrbitMsg发送", "swor_r079_a03": "预约提醒流量经CedarCom发送", "swor_r079_a04": "网络中断通知经OrbitAU发送", "swor_r079_a05": "网络中断通知经Mira Relay发送", "swor_r079_a06": "网络中断通知经CedarCom发送", "swor_r079_a07": "账单通知经SouthText发送", "swor_r079_a08": "账单通知经South Relay发送"}`
- IR 目标 meaning 修改：`"三类SMS消息流量的总发送成本"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Australian Communications and Media Authority", "url": "https://www.acma.gov.au/industry-rules-sms-sender-id-register"}], "notes": "复核V1.4.4保存的ACMA quote，覆盖2026-07-01、提供商参与状态、未参与时阻断及已参与但标识未登记时加盖Unverified。"}`
- 复核说明：把发件标识类型、提供商参与状态和标识登记状态从共通source及action meaning移至case层，并覆盖Base/Patched IR中原先绑定C2状态的目标meaning。

### SWOR-R080

- 结论：`FIX`；问题类型：L1, L2, L7。
- 保持：保留日期、学校校内宽带业务、七个服务包与成本、三类需求覆盖、最多三个包、设备用于教学网、目标、三个Patch与Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "学校本轮不提交或使用E-Rate资金请求；交换机、路由器和接入点均部署于校内教学宽带网络，采购须覆盖交换机生命周期、防火墙、配置或软件支持三类需求，且最多选择三个服务包。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦学校宽带项目辖区", "regulated_subject": "完全使用学区自有资金采购七类校内宽带服务包的K-12学校"}`
- C2：`{"boundary_facts": "本轮表单只申报Internal Connections，不申报Basic Maintenance of Internal Connections，也不参加Cybersecurity Pilot；交换机、路由器和接入点均部署于校内教学宽带网络。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦学校宽带项目辖区", "regulated_subject": "为Funding Year 2026提交Category Two Internal Connections资金请求的K-12学校"}`
- C1 不适用原因：FY2026 E-Rate Eligible Services List的题列类别和资格Patch用于E-Rate资金请求；C1完全自筹且不提交或使用资金请求，B/C/G三个禁用Patch均不进入模型。
- 题内行动映射：A/B/G覆盖交换机生命周期，C/D覆盖防火墙，B/E/F覆盖配置或软件支持；最多选三个包且三类需求均至少覆盖一次，成本不变。
- source 精确替换：
  - 旧：`美国学校FY2026校内宽带服务包选择。2026年8月4日，具备E-Rate申请资格的河谷学区中学要为Funding Year 2026提交一份只包含Category Two Internal Connections、且不参加Cybersecurity Pilot的申请。`
  - 新：`美国学校校内宽带服务包选择。河谷学区中学要从候选服务包中完成一次校内宽带采购；本轮资金来源、申报类别与项目文件记录在采购台账中。`
  - 旧：`候选为：A，远程交换机安全补丁和软件技术支持，随交换机申报，成本8点；B，工程师到校现场完成交换机配置变更，3点；C，独立的下一代高级防火墙入侵检测服务，2点；D，独立的基础防火墙服务与组件，9点；E，远程路由器配置变更，随路由器申报，7点；F，远程无线接入点软件技术支持，随接入点申报，10点；G，交换机物理维修并按实际工时计费，4点。`
  - 新：`候选为：A，远程交换机安全补丁和软件技术支持，与交换机一并采购，成本8点；B，工程师到校现场完成交换机配置变更，3点；C，独立的下一代高级防火墙入侵检测服务，2点；D，独立的基础防火墙服务与组件，9点；E，远程路由器配置变更，与路由器一并采购，7点；F，远程无线接入点软件技术支持，与接入点一并采购，10点；G，交换机物理维修并按实际工时计费，4点。`
  - 旧：`所有关联设备均用于校内教学宽带且本身具备E-Rate资格。`
  - 新：`所有关联交换机、路由器和无线接入点均部署于校内教学宽带网络，资产台账记录设备型号及对应服务合同。`
  - 旧：`唯一目标是最小化申请成本。`
  - 新：`唯一目标是最小化采购成本。`
  - 旧：`服务包必须符合决策日已经发布的FCC FY2026 E-Rate Eligible Services List。`
  - 新：``
- output_schema meaning 修改：`{"swor_r080_a01": "远程交换机安全补丁和软件技术支持，与所支持交换机一并采购", "swor_r080_a05": "远程路由器配置变更，与所支持路由器一并采购", "swor_r080_a06": "远程无线接入点软件技术支持，与所支持接入点一并采购"}`
- IR 目标 meaning 修改：`"校内宽带服务包的采购成本"`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Communications Commission, Wireline Competition Bureau", "url": "https://www.usac.org/wp-content/uploads/e-rate/documents/resources/DA-25-1069A1.pdf"}], "notes": "复核V1.4.4保存的FCC FY2026最终清单quote，覆盖远程软件/配置随设备列入IC、现场配置与物理维修属于BMIC实际工作，以及高级/基础防火墙区分。"}`
- 复核说明：将资金来源与申请类型移到case层，把共通source及A/E/F action meaning中的“申报”改为中性采购表述，并同步Base/Patched IR目标meaning为采购成本。

### SWOR-R081

- 结论：`FIX`；问题类型：L1, L2, L5, L6, L7。
- 保持：保留两市各二选一、共享门户支持、全部成本、最小化目标、action ID 与现有 Gold 数学结构。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "本报告周期内，环境署没有向任一议会发出信息需求函，也没有指定资料类别、格式或通知方式；两市仅把发送动作作为内部工作流选项。", "decision_date": "2026-08-02", "jurisdiction": "爱尔兰科克市与都柏林市的地方废物资料处理场景", "regulated_subject": "科克市议会和都柏林市议会安排本期资料发送或延期处理"}`
- C2：`{"boundary_facts": "环境署已分别向两市发出年度资料函，并逐项指定资料类别和电子格式；底层记录齐备，题列发送动作就是两市向环境署提交资料。", "decision_date": "2026-08-02", "jurisdiction": "爱尔兰科克市与都柏林市的地方废物资料处理场景", "regulated_subject": "科克市议会和都柏林市议会处理环境署年度资料函"}`
- C1 不适用原因：Regulation 45(7) 的提交规则以环境署指定信息或通知为前提；C1 没有该项机构行为，因此 Base IR 保持不变。
- 题内行动映射：a01/a03 是两市本期发送，a02/a04 是延期队列，a05 是任一发送动作启用的共享门户支持；映射与 IR 变量 submit_cork、submit_dublin、defer_*、portal_support 一致。
- source 精确替换：
  - 旧：`环境署已分别向两个议会发出本年度数据需求函，列明所需资料类别和电子格式；两个议会的底层记录均已完成，除处理时点外不存在其他资料缺口。`
  - 新：`两个议会的底层记录均已完成，除处理时点外不存在其他资料缺口。`
  - 旧：`最终处理方案须遵守决策日有效的爱尔兰地方废物信息管理规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "千欧元", "value": 2.0}, {"unit": "欧元", "value": 2000.0}], "canonical_unit": "千欧元", "canonical_value": 2.0}, "old": {"accepted_equivalents": [{"unit": "千欧元", "value": 2.0}, {"unit": "欧元", "value": 2.0}], "canonical_unit": "千欧元", "canonical_value": 2.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Government of Ireland / Irish Statute Book", "url": "https://www.irishstatutebook.ie/eli/2020/si/323/made/en/print"}], "notes": "已于2026-08-26以Irish Statute Book打印页完整复核Regulation 6与7，并用official_evidence_override替换V1.4.4从单词中部开始的quote；Gold不变。", "official_evidence_override": [{"information_responsibility": "确认报告格式由Commission建立，且地方当局和Dublin City Council按Agency指定的书面或电子通知方式提供信息。", "node_id": "E1", "omission_effect": "缺少E1时，无法把科克与都柏林两项本期资料发送动作分别绑定到两个提交约束。", "publisher": "Government of Ireland / Irish Statute Book", "quote": "(6) Data and information reported under this Regulation shall be in compliance with the requirements of Article 37 of the Waste Directive and shall be reported in formats for reporting established by the Commission in accordance with paragraph 7 of this Article. (7) Local authorities and Dublin City Council shall provide such information to the Agency in writing, or other form of notification, including electronic means, as may be specified by the Agency for the purposes of compliance with this Regulation.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["cork_submission_required", "dublin_submission_required"], "supported_patch_slots": ["cork_submission_required", "dublin_submission_required"], "url": "https://www.irishstatutebook.ie/eli/2020/si/323/made/en/print"}]}`
- 复核说明：将是否存在环境署资料函移到case层，并以完整官方原文覆盖截断证据；两个提交约束及模型不变；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R082

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留五单、两个报关组容量、贡献值、单个季度名额、action ID、modify_constraint Patch 与既有 Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "Arden至Ember五份合同分别签于2026年3月14、15、16、17和18日；五单均在2026年7月1日至9月30日完成进口或保税仓放行，产品规格相同且没有其他原产地或加工路径。", "decision_date": "2026-08-04", "jurisdiction": "英国海关辖区", "regulated_subject": "Northmere Metals 的五个钢材订单及两个报关组"}`
- C2：`{"boundary_facts": "Arden、Beck、Cobalt、Dunlin、Ember合同分别签于2026年3月13、14、12、11和10日；对应进口或放行日为7月1、8月25、9月30、7月20和10月1日，Dunlin于6月30日进入英国保税仓；五单均为题列钢材，且没有乌克兰原产、再出口或自由港加工事实。", "decision_date": "2026-08-04", "jurisdiction": "英国海关辖区", "regulated_subject": "Northmere Metals 的五个钢材订单及两个报关组"}`
- C1 不适用原因：C1 的所有合同均未早于 2026 年 3 月 14 日，因而预先合同时间窗没有改变季度名额系数，Base IR 保持不变。
- 题内行动映射：十个 action 是五单到北/南报关组的二元分配；quarter_one_quota_slot 只改这些分配变量的系数，不新增公开 action。
- source 精确替换：
  - 旧：`Arden卷材订单依据2026年3月13日签订的合同订购，计划于7月1日进口；Beck板材订单依据3月14日签订的合同订购，计划于8月25日进口；Cobalt型材订单依据3月12日签订的合同订购，计划于9月30日进口；Dunlin线材订单依据3月11日签订的合同订购，已于6月30日进入英国保税仓，计划于7月20日放行进入英国市场；Ember钢管订单依据3月10日签订的合同订购，计划于10月1日进口。`
  - 新：`五个订单分别为Arden卷材、Beck板材、Cobalt型材、Dunlin线材和Ember钢管；公司的订单台账逐单记录合同签订日，以及进口日或保税仓放行日。`
  - 旧：`五个订单均有可核验的书面合同、发票和付款证明，均属于英国新钢铁贸易措施涵盖的产品线，且不存在乌克兰原产、再出口、自由港加工或其他优惠原产地安排。`
  - 新：`五个订单均有可核验的书面合同、发票和付款证明；产品规格、原产地、加工方式和转运路径均记载在订单台账中。`
  - 旧：`公司会对满足条件的订单使用可用的过渡安排；其他获选订单需要占用季度配额申请名额，而本批最多可使用一个这样的名额。`
  - 新：`公司的季度配额流程最多为本批启用一个申请名额；在订单台账中归入过渡路径的订单不占用该名额。`
  - 旧：`订单选择与分配须遵守决策日有效的英国政府关于2026年7月1日起钢铁贸易措施的实施通知。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "UK Department for Business and Trade", "url": "https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/implementation-notifications-on-the-transitional-exemption-quota-administration-and-the-ukraine-exclusion"}], "notes": "已复核保存的实施通知 publisher、URL、合同截止日、季度窗口、保税仓放行和 Q1 不计数 quote；未发现 Gold 边界错误。"}`
- 复核说明：R082 保留 modify_constraint；合同日和进口/放行日全部移到 case facts，source 只保留订单骨架和本地配额流程。

### SWOR-R083

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留九项目、三事件分组、四选一结构、价值、20点 petition 成本、action ID、add_variable/modify_objective Gold。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "P1、P2和U均是正常运营之外的独立活动，持续时间分别为30、45和20日；企业全年类别记录为LQG，三个项目组之间没有许可证、同意书或共享资源约束。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦危险废物产生者制度", "regulated_subject": "2026年全年登记为large quantity generator的Canyon Ridge Coatings"}`
- C2：`{"boundary_facts": "P1和P2为计划事件，U为非计划事件，持续时间分别为30、45和20日且彼此独立；企业已为年度第一项事件准备常规登记流程，并可为与第一项类型相反的第二项事件提交一份petition，内部成本20点。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦危险废物产生者制度", "regulated_subject": "2026年登记为small quantity generator的Canyon Ridge Coatings"}`
- C1 不适用原因：Part 262 的 episodic-event 替代路径面向 VSQG 与 SQG；C1 的 LQG 主体类别不进入该路径，因而不加入事件计数、petition 和目标成本 Patch。
- 题内行动映射：九个公开 action 仅对应九个项目；event_p1_active、event_u_active、event_p2_active 与 second_event_petition 是由项目选择派生的私有内部变量，petition 成本通过 modify_objective 计入。
- source 精确替换：
  - 旧：`Canyon Ridge Coatings作为small quantity generator，要`
  - 新：`Canyon Ridge Coatings要`
  - 旧：`每个事件均属于正常运营以外且使当月暂时超过原generator category的活动，持续不超过60日，并已满足通知、标签、manifest和期限等其他要求。`
  - 新：`三个事件的发生方式、持续时间和企业类别均记载在运营台账中；通知、标签、manifest和期限等作业资料已齐备。`
  - 旧：`若组合依法需要第二事件petition，公司可以办理，内部管理成本为20点。`
  - 新：`公司可以办理一份第二事件petition，办理时产生20点内部管理成本；该项只作为事件组合的内部支持变量。`
  - 旧：`组合须遵守决策日有效的美国联邦RCRA episodic generation规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States Environmental Protection Agency / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml?part=262"}], "notes": "已复核 V1.4.4 保存的年度事件数、第二事件 petition、计划/非计划相反类型与60日条文 quote；Gold 保持。"}`
- 复核说明：特别复核 R083 的四个 add_variable 和 modify_objective；不把内部变量伪装成公开候选行动。

### SWOR-R084

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留六项目、两个资源包、二选项目、贡献与成本、顺序 action 映射及 Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A至F的每个容器均已排空、清洗和吹扫，接收检测为无危险残余物；中心把它们作为普通空金属容器处理。", "decision_date": "2026-08-04", "jurisdiction": "美国境内的气雾容器回收场景", "regulated_subject": "绿环材料中心对已验收气雾容器进行分类与回收"}`
- C2：`{"boundary_facts": "A和C执行穿刺排空并回收空罐；C和D在接收时有泄漏，C立即穿刺，D保持完整；B、E、F完整且不泄漏。穿刺单元设在坚实平整通风区，配有书面程序、培训、溢漏程序和清理包；密闭外包装带吸附材料。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦通用废物气雾罐制度", "regulated_subject": "当日峰值持有量为4,800千克的绿环材料中心处理题列废气雾罐"}`
- C1 不适用原因：C1 的容器已为空且没有危险废物残余，不属于 40 CFR 273.13(e) 所述废气雾罐管理对象，因此泄漏、外包装和穿刺约束不进入模型。
- 题内行动映射：a01-a06 按 source 首次出现顺序对应 A-F，a07 为完整穿刺单元，a08 为密闭吸附外包装；资源动作直接承担题内作业能力与成本。
- source 精确替换：
  - 旧：`绿环材料中心是40 CFR第273部下的小数量通用废物处理者，当日累计持有量始终低于5,000千克，要`
  - 新：`绿环材料中心当日累计持有量始终低于5,000千克，要`
  - 旧：`A把完整的废涂料气雾罐穿刺排空并回收空金属罐，贡献95点；B把完整且不泄漏的废涂料气雾罐原样送往下游通用废物处理者，贡献81点；C把已经出现泄漏的废润滑剂气雾罐立即穿刺排空并回收空罐，贡献92点；D把泄漏的废清洁剂气雾罐保持完整等待外运，贡献90点；E转运完整且不泄漏的废食品脱模剂气雾罐，贡献79点；F只对完整且不泄漏的废胶黏剂气雾罐分类，不破坏罐体，贡献78点。`
  - 新：`A至F依次为穿刺排空并回收A、原样转运B、立即穿刺并回收C、完整暂存D、原样转运E和仅分类F六个项目，贡献依次为95、81、92、90、79和78点；各罐的内容物、泄漏状态和验收类别由当日接收记录确定。`
  - 旧：`处理方案必须遵守决策日有效的美国联邦通用废物气雾罐规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r084_a01": "执行完整废涂料气雾罐穿刺排空回收项目A", "swor_r084_a02": "执行完整且不泄漏的废涂料气雾罐下游转运项目B", "swor_r084_a03": "执行泄漏废润滑剂气雾罐立即穿刺排空项目C", "swor_r084_a04": "执行泄漏废清洁剂气雾罐保持完整并等待外运项目D", "swor_r084_a05": "执行完整且不泄漏的废食品脱模剂气雾罐转运项目E", "swor_r084_a06": "执行完整且不泄漏的废胶黏剂气雾罐不破罐分类项目F", "swor_r084_a07": "启用一套共享的完整合规穿刺排空单元", "swor_r084_a08": "启用一套独立密闭且带吸附材料的泄漏罐外包装"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "已复核泄漏罐的密闭/吸附外包装或立即穿刺分支及穿刺设备条件 quote；Gold 不变。"}`
- 复核说明：将容器内容、泄漏和管理类别移到 case facts；source 仅保留共通作业和资源能力；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R085

- 结论：`FIX`；问题类型：L2, L3, L5, L7。
- 保持：保留四设施、三路线包、三门包、全部贡献成本、三组选一与 Gold。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "四个候选设施均位于安大略省，雇佣关系和运营主体均在加拿大；小办公室可由一条路线安全撤离，大型配送层需要三条路线，题列设施均不是精神、监狱或矫正机构。", "decision_date": "2026-08-05", "jurisdiction": "加拿大安大略省的工作场所", "regulated_subject": "北湾配送公司选择设施、永久出口路线和出口门配置"}`
- C2：`{"boundary_facts": "小办公室、标准仓库、大型配送层和高危险作业室分别有12、80、320和60人；工程分析记录所需路线数分别为1、2、3和2，高危险作业室材料可能极速燃烧；三个门包分别为内开免钥匙、外开免钥匙和外开需钥匙。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦一般工业工作场所", "regulated_subject": "北湾配送公司选择美国境内设施、永久出口路线和出口门配置"}`
- C1 不适用原因：29 CFR Part 1910 的出口路线规则不延伸到 C1 中完全位于安大略省且没有美国雇佣联系的工作场所，故 Base IR 保持。
- 题内行动映射：a01-a04 是设施，a05-a07 是路线包，a08-a10 是门包；公开顺序与 IR 三组变量完全一致。
- source 精确替换：
  - 旧：`美国运营设施与疏散网络选择。`
  - 新：`运营设施与疏散网络选择。`
  - 旧：`设计须遵守决策日有效的美国联邦工作场所出口路线规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r085_a01": "租用12人小型办公室；工程疏散分析确认一条路线即可安全撤离全部人员", "swor_r085_a02": "租用80人标准仓库；一条路线不足而两条路线可安全撤离", "swor_r085_a03": "租用320人大型配送层；两条路线不足而三条路线可安全撤离", "swor_r085_a04": "租用60人高危险作业室；两条路线可安全撤离且室内材料可能极速燃烧", "swor_r085_a05": "建设一条永久出口路线", "swor_r085_a06": "建设两条尽可能相互远离的永久出口路线", "swor_r085_a07": "建设三条尽可能相互远离的永久出口路线", "swor_r085_a08": "安装从内部无需钥匙开启的侧铰内开门", "swor_r085_a09": "安装从内部无需钥匙开启的侧铰外开门", "swor_r085_a10": "安装从内部需要钥匙开启的侧铰外开门"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "已复核一条/至少两条/多于两条路线、门从内部开启和向疏散方向开启的保存 quote。"}`
- 复核说明：只移除共通 source 的美国地域标签和法规提示，设施与疏散数值保持原样；将10个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R086

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留四个时序包、五年复核发现、技术效果、净效用、单选结构和 Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "地上固定油罐合计1300美制加仑，完全埋地罐为0加仑；场址坡面和排水沟全部汇入没有外排口的场内衬里集液池。", "decision_date": "2026-08-05", "jurisdiction": "美国境内非运输储油设施", "regulated_subject": "设施开展内部泄漏控制计划复核"}`
- C2：`{"boundary_facts": "地上固定油罐合计2400美制加仑，完全埋地罐为0加仑；场址坡面与连续排水沟连接至毗邻的美国可航水域岸线；第五年现场复核确认一项已实地验证、可显著降低排放概率的控制技术。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦油污染预防制度", "regulated_subject": "运行SPCC Plan的非运输储油设施"}`
- C1 不适用原因：C1 同时位于 Part 112 的容量和排放路径范围之外，五年 SPCC 复核、六个月修订与六个月实施链条不进入模型。
- 题内行动映射：四个公开 action 分别对应四个完整 review/amend/implement 时序包，不存在独立隐含行动。
- source 精确替换：
  - 旧：`美国储油设施SPCC时间方案。`
  - 新：`储油设施计划时间方案。`
  - 旧：`一座受SPCC规则约束的非运输储油设施`
  - 新：`一座非运输储油设施`
  - 旧：`方案须符合决策日有效的美国联邦SPCC计划规则。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r086_a01": "采用5年复核、6个月修订、再6个月实施方案", "swor_r086_a02": "采用5年复核、9个月后修订方案", "swor_r086_a03": "采用7年首次复核方案", "swor_r086_a04": "采用5年复核、6个月修订、9个月后实施方案"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "补入§112.1的排放路径适用范围与1,320/42,000加仑例外，并保留五年复核、六个月修订和六个月实施的完整官方原文；证据同时闭合C1 RETAIN与C2三条Patch。", "official_evidence_override": [{"information_responsibility": "§112.1把可能向美国可航水域或毗连岸线有害排油的非运输相关储油设施纳入Part 112。", "node_id": "E1", "omission_effect": "缺少E1时，无法由C2的非运输储油设施和外排路径确认Part 112适用，也无法解释C1封闭集液池为何不满足该路径门槛。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "This part applies to any owner or operator of a non-transportation-related onshore or offshore facility engaged in drilling, producing, gathering, storing, processing, refining, transferring, distributing, using, or consuming oil and oil products, which due to its location, could reasonably be expected to discharge oil in quantities that may be harmful into or upon the navigable waters of the United States or adjoining shorelines.", "role": "jurisdiction", "source_node_id": "E1", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}, {"information_responsibility": "§112.1明确排除地上总储油容量不超过1,320加仑且完全埋地容量不超过42,000加仑的设施。", "node_id": "E2", "omission_effect": "缺少E2时，无法由C1的1,300加仑地上容量和0加仑埋地容量确认容量例外。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "This part does not apply to any facility with an aggregate aboveground oil storage capacity of 1,320 U.S. gallons or less and a completely buried storage capacity of 42,000 U.S. gallons or less.", "role": "exception", "source_node_id": "E2", "support_target_type": "exception_boundary", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}, {"information_responsibility": "受Part 112约束的设施至少每五年复核和评价一次SPCC Plan。", "node_id": "E3", "omission_effect": "缺少E3时，无法确定第五年后的首次复核方案不可用。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "The owner or operator of a facility subject to this part must review and evaluate the SPCC Plan at least once every five years from the date the facility becomes subject to this part.", "role": "operative_rule", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["exclude_late_review"], "supported_patch_slots": ["exclude_late_review"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}, {"information_responsibility": "若五年复核发现已现场验证且显著降低排放可能性的技术，须在复核后六个月内修订SPCC Plan。", "node_id": "E4", "omission_effect": "缺少E4时，无法排除复核九个月后才修订的方案。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "As a result of this review and evaluation, the owner or operator must amend the SPCC Plan within six months of the review to include more effective prevention and control technology if the technology has been field-proven at the time of the review and will significantly reduce the likelihood of a discharge.", "role": "operative_rule", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["exclude_late_amendment"], "supported_patch_slots": ["exclude_late_amendment"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}, {"information_responsibility": "任何SPCC Plan修订须尽快实施且不得晚于修订完成后六个月。", "node_id": "E5", "omission_effect": "缺少E5时，无法排除修订九个月后才实施的方案。", "publisher": "U.S. Environmental Protection Agency / eCFR", "quote": "The owner or operator must implement any amendment as soon as possible, but not later than six months following preparation of any amendment.", "role": "operative_rule", "source_node_id": "E5", "support_target_type": "patch_slot", "support_targets": ["exclude_late_implementation"], "supported_patch_slots": ["exclude_late_implementation"], "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}]}`
- 复核说明：删除 source 中“受SPCC规则约束”的结论，容量和场址事实改由两个 case 分别给出；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R087

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留十一头寸、四选、平台上限、收益、action ID、交易日与 Gold。
- 主差异轴：`decision_date`。
- C1：`{"boundary_facts": "Alzette Components以自身名义并为自身账户直接执行题列银行、支付平台、国库券和现金头寸；所有开户、交易和清算路径均与action标签所示对手方一致，不存在第三方代理、许可证、授权、撤资或其他豁免事实。", "decision_date": "2026-07-25", "jurisdiction": "卢森堡，欧盟", "regulated_subject": "在卢森堡注册的Alzette Components配置四个短期头寸"}`
- C2：`{"boundary_facts": "Alzette Components以自身名义并为自身账户直接执行题列银行、支付平台、国库券和现金头寸；所有开户、交易和清算路径均与action标签所示对手方一致，不存在第三方代理、许可证、授权、撤资或其他豁免事实。", "decision_date": "2026-08-20", "jurisdiction": "卢森堡，欧盟", "regulated_subject": "在卢森堡注册的Alzette Components配置四个短期头寸"}`
- C1 不适用原因：C1决策日2026年7月25日晚于文书7月24日生效日，Yelo Bank已被删除；其余题列点名实体的8月13日或23日生效日均未到，因此不加入四条交易排除约束。
- 题内行动映射：十一 action 逐一对应十一头寸；数字资产/支付平台上限只作用于 PilotFinance、Rapira、Aifory 三个题内头寸。
- source 精确替换：
  - 旧：`注册在卢森堡的Alzette Components`
  - 新：`Alzette Components`
  - 旧：`2026年8月20日，Alzette Components财务团队`
  - 新：`Alzette Components财务团队`
  - 旧：`团队已经完成信用、流动性、税务和交易对手集中度审查；除欧盟对俄限制措施的当期交易资格外，其他准入条件均已满足。`
  - 新：`团队已经完成信用、流动性、税务和交易对手集中度审查；各头寸的开户主体、交易地点和清算路径均由交易档案固定。`
  - 旧：`资金配置须遵守交易日有效并适用于卢森堡企业的欧盟对俄限制措施。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Council of the European Union / EUR-Lex", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02014R0833-20260717"}, {"publisher": "Council of the European Union / EUR-Lex", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A32026R1848"}], "notes": "改为同一卢森堡主体、只变决策日的pair；Article 13闭合主体范围，Article 2确认文书于2026-07-24生效，Annex条目标注使C1的7月25日与C2的8月20日分支可直接判断。", "official_evidence_override": [{"information_responsibility": "Article 13界定Regulation 833/2014的属地、船旗、国籍、成员国设立主体及在欧盟全部或部分开展业务的适用范围。", "node_id": "E1", "omission_effect": "缺少E1时，不能确认两案同一卢森堡设立主体均落入法规主体范围，日期比较没有适用基础。", "publisher": "Council of the European Union / EUR-Lex", "quote": "This Regulation shall apply: (a) within the territory of the Union; (b) on board any aircraft or any vessel under the jurisdiction of a Member State; (c) to any person inside or outside the territory of the Union who is a national of a Member State; (d) to any legal person, entity or body, inside or outside the territory of the Union, which is incorporated or constituted under the law of a Member State; (e) to any legal person, entity or body in respect of any business done in whole or in part within the Union.", "role": "jurisdiction", "source_node_id": "E1", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02014R0833-20260717"}, {"information_responsibility": "Article 5ac禁止与Annex XLIV所列俄罗斯境外主体直接或间接交易。", "node_id": "E2", "omission_effect": "缺少E2时，Annex XLIV仅证明Eco-Islamic被列名，不能推出其短期存款行动在C2不可执行。", "publisher": "Council of the European Union / EUR-Lex", "quote": "It shall be prohibited to engage, directly or indirectly, in any transaction with a legal person, entity or body established outside Russia as listed in Annex XLIV.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["transaction_unavailable_eco_islamic"], "supported_patch_slots": ["transaction_unavailable_eco_islamic"], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02014R0833-20260717"}, {"information_responsibility": "Article 5ad禁止与Annex XLV Part A所列欧盟境外信用、金融、加密资产或支付服务主体直接或间接交易。", "node_id": "E3", "omission_effect": "缺少E3时，Annex XLV的列名与日期不能推出Chinggis、Sberbank India和PilotFinance三项行动不可执行。", "publisher": "Council of the European Union / EUR-Lex", "quote": "It shall be prohibited to directly or indirectly engage in any transaction with a legal person, entity or body established outside of the Union that: (a) is a credit or financial institution or an entity providing crypto-asset services or payment services that provides such services to legal persons, entities and bodies listed in this Regulation or Regulation (EU) No 269/2014 or is otherwise significantly frustrating the purpose of the prohibitions in those Regulations, as listed in Part A of Annex XLV to this Regulation;", "role": "operative_rule", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["transaction_unavailable_chinggis", "transaction_unavailable_sberbank_india", "transaction_unavailable_pilotfinance"], "supported_patch_slots": ["transaction_unavailable_chinggis", "transaction_unavailable_sberbank_india", "transaction_unavailable_pilotfinance"], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02014R0833-20260717"}, {"information_responsibility": "Regulation 2026/1848规定文书自其在Official Journal公布次日起生效；文书日期为2026年7月23日，故7月24日生效。", "node_id": "E4", "omission_effect": "缺少E4时，无法确认C1的7月25日已经发生Yelo删除，同时又早于各新条目自定的8月13日或23日。", "publisher": "Council of the European Union / EUR-Lex", "quote": "This Regulation shall enter into force on the day following that of its publication in the Official Journal of the European Union.", "role": "effective_date", "source_node_id": "E4", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A32026R1848"}, {"information_responsibility": "Regulation 2026/1848 Annex VII删除Yelo Bank并自2026年8月13日起把CJSC Eco-Islamic Bank加入Annex XLIV。", "node_id": "E5", "omission_effect": "缺少E5时，无法确认7月25日和8月20日Yelo Bank均已删除，并区分Eco-Islamic在两日期的生效状态。", "publisher": "Council of the European Union / EUR-Lex", "quote": "ANNEX VII\nAnnex XLIV to Regulation (EU) No 833/2014 is amended as follows:\n(1) the following entry is deleted:\nName of the legal person, entity or body    Entry into force\n‘8. Yelo Bank (Azerbaijan)    14.5.2026’;\n(2) the following entry is added:\nName of the legal person, entity or body    Entry into force\n‘9. CJSC Eco-Islamic Bank (Kyrgyzstan)    13.8.2026’.", "role": "effective_date_and_list", "source_node_id": "E5", "support_target_type": "patch_slot", "support_targets": ["transaction_unavailable_eco_islamic"], "supported_patch_slots": ["transaction_unavailable_eco_islamic"], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A32026R1848"}, {"information_responsibility": "Regulation 2026/1848 Annex VIII把题列平台加入Annex XLV Part A，并逐项给出2026年8月13日或23日的生效日。", "node_id": "E6", "omission_effect": "缺少E6时，无法确认7月25日所有新增平台尚未生效，也无法确认8月20日Chinggis、Sberbank India和PilotFinance已生效而Rapira与Aifory Pro尚未生效。", "publisher": "Council of the European Union / EUR-Lex", "quote": "ANNEX VIII\nAnnex XLV to Regulation (EU) No 833/2014 is amended as follows:\n(1) the following entries are added to Part A (list of credit and financial institutions and entities providing crypto-assets services or payment services established outside of the Union that are significantly frustrating the purpose of the prohibitions in this Regulation and Regulation (EU) No 269/2014):\nName of the legal person, entity or body    Entry into force\n‘Rapira    23.8.2026\nAifory Pro (Sooty Ltd.)    23.8.2026\nABCeX (Nueva Cryptologia S.A.S DE C.V.)    23.8.2026\nWhiteBird    23.8.2026\nNoOnecrypto INC.    23.8.2026\nTradex (Brightum LLC)    23.8.2026\nMonease Ltd    23.8.2026\nBitPapa    23.8.2026\nExnode, Exnode Pay (Arvix)    23.8.2026\nHTX (HUOBI GLOBAL SA)    23.8.2026\nEXMO Ltd    23.8.2026\nChinggis Khaan Bank    13.8.2026\nSberbank India    13.8.2026\nIndia VTB    13.8.2026\nA7 Nigeria    13.8.2026\nA7 Africa    13.8.2026\nPilotFinance Ltd    13.8.2026’;", "role": "effective_date_and_list", "source_node_id": "E6", "support_target_type": "patch_slot", "support_targets": ["transaction_unavailable_chinggis", "transaction_unavailable_sberbank_india", "transaction_unavailable_pilotfinance"], "supported_patch_slots": ["transaction_unavailable_chinggis", "transaction_unavailable_sberbank_india", "transaction_unavailable_pilotfinance"], "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A32026R1848"}]}`
- 复核说明：把固定交易日移到case层；两案使用同一卢森堡主体和同一头寸事实，仅以7月25日/8月20日决策日跨越8月13日条目生效边界。

### SWOR-R088

- 结论：`FIX`；问题类型：L2, L7。
- 保持：保留八头寸、四合同日期/期限/修改事实、转运上限、价值、action ID 与六条 Gold 约束。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "合同签订、履行、付款、船舶和目的地均在欧盟之外；没有欧盟人员、机构、领土、船舶、航空器或清算路径参与。", "decision_date": "2026-08-04", "jurisdiction": "挪威境内能源交易", "regulated_subject": "在挪威注册的Bluehaven Energy编制2027年LNG采购与第三国转运计划"}`
- C2：`{"boundary_facts": "全部转运目的地位于欧盟和俄罗斯之外；GL-17于2021年1月15日签订、期限四年且2023年仅降低采购价格；QP-42于2022年2月23日签订、期限两年且2025年仅变更合同方地址；RT-09于2021年2月10日签订、期限三年且2024年提高合同数量；VN-31于2020年12月1日签订、期限一年且之后未修改。", "decision_date": "2026-08-04", "jurisdiction": "荷兰，欧盟", "regulated_subject": "在荷兰注册的Bluehaven Energy编制2027年俄罗斯原产LNG采购与第三国转运计划"}`
- C1 不适用原因：C1 的公司和全部交易没有欧盟属人或属地联系，目标欧盟LNG过渡条款不改变模型。
- 题内行动映射：a01-a04 是四个采购头寸，a05-a08 是配对转运头寸；Gold 只在同合同采购/转运间加依赖并封闭不满足原始合同事实的头寸。
- source 精确替换：
  - 旧：`欧盟能源贸易商的跨期LNG头寸组合。`
  - 新：`能源贸易商的跨期LNG头寸组合。`
  - 旧：`注册在荷兰的Bluehaven Energy`
  - 新：`Bluehaven Energy`
  - 旧：`2027年计划须遵守决策日已公布并适用于荷兰企业的欧盟俄罗斯原产LNG第三国转运临时安排。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Council of the European Union / EUR-Lex", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL_202601848"}], "notes": "已复核 Article 3ra(6) 保存 quote 中的合同截止日、超过一年、第三国目的地及允许修改清单；未发现 Gold 变化。"}`
- 复核说明：去掉共通 source 的荷兰注册结论；合同原始事实保留，C2 case facts 不写法律分类标签。

### SWOR-R089

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留四个100/80日包、住院日数量、效用、单选、内部退款政策和 Gold。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "四个包中的全部照护日均由患者自费，不形成Medicare临终关怀日；机构台账把这些日与Medicare受益人日分开记录。", "decision_date": "2026-08-05", "jurisdiction": "美国境内临终关怀服务", "regulated_subject": "临终关怀机构选择年度服务包"}`
- C2：`{"boundary_facts": "四个包的全部总照护日均为同一12个月窗口内的Medicare受益人临终关怀日；题列住院日均已按general inpatient或inpatient respite计费。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦Medicare临终关怀支付制度", "regulated_subject": "Medicare认证临终关怀机构选择年度服务包"}`
- C1 不适用原因：20%住院日计算使用Medicare受益人的临终关怀日；C1全部为自费日，不进入该分子与分母，故不加过滤约束。
- 题内行动映射：a01-a04 按source首次出现顺序对应四个完整服务包；没有独立退款 action，内部政策直接过滤包。
- source 精确替换：
  - 旧：`一家Medicare认证临终关怀机构`
  - 新：`一家临终关怀机构`
  - 旧：`所有住院日均为已计费的general inpatient或inpatient respite照护日，所有总天数均为选择临终关怀保障的Medicare受益人在该机构获得的照护日。`
  - 新：`各包的住院日和总照护日均按同一机构年度台账口径统计；付款来源和患者项目类别由该台账逐日记录。`
  - 旧：`机构内部硬政策只接受在适用联邦住院支付限额下无需支付调整、追偿或退款的完整服务包，题给效用不能通过退款另行折算；除住院日比例外，各方案的支付与质量条件相同。`
  - 新：`机构内部硬政策只接受无需支付调整、追偿或退款的完整服务包，题给效用不能通过退款另行折算；是否发生支付调整由年度台账中各包的付款来源、项目类别、总照护日和住院日记录确定，除此之外各方案的支付与质量条件相同。`
  - 旧：`方案须符合决策日有效的美国联邦Medicare临终关怀住院日规则。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r089_a01": "选择100总天数含25住院日方案", "swor_r089_a02": "选择100总天数含20住院日方案", "swor_r089_a03": "选择80总天数含18住院日方案", "swor_r089_a04": "选择80总天数含16住院日方案"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-B/part-418/subpart-G/section-418.302"}, {"publisher": "Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-B/part-418/subpart-A/section-418.3"}], "notes": "已复核20%住院日计算和12个月窗口的保存 quote；Gold 边界与包过滤保持。"}`
- 复核说明：Medicare患者日属性移到 case facts，source 只保留包的数量与本地政策；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R090

- 结论：`FIX`；问题类型：L2, L5, L7。
- 保持：保留Jinarc三名患者、标准治疗、三项化验、两个旧支持场次、四项容量、价值成本与 Gold。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "处方、配药、化验、库存和治疗全部在马来西亚完成，产品由马来西亚供应链交付；诊所、医生、药师和患者均没有新加坡业务联系。", "decision_date": "2026-08-04", "jurisdiction": "马来西亚", "regulated_subject": "马来西亚专科诊所安排三名患者启动Jinarc并配置化验与支持场次"}`
- C2：`{"boundary_facts": "三项启动均使用Jinarc；标准肾病治疗不使用该产品；医护教育认证场次和处方清单/库存核验场次已从本地流程中撤下，患者肝转氨酶和胆红素化验仍作为门诊可执行动作。", "decision_date": "2026-08-04", "jurisdiction": "新加坡", "regulated_subject": "新加坡专科诊所安排三名患者启动Jinarc并配置化验与支持场次"}`
- C1 不适用原因：新加坡HSA的Jinarc本地流程不支配C1中完全位于马来西亚且没有新加坡联系的诊疗与供应链，因此不加患者启动到化验的 Patch。
- 题内行动映射：a01-a03 是三名患者启动，a05-a07 是对应患者化验，a04 是独立标准治疗，a08/a09 是两个旧支持场次；三条Patch逐患者一一绑定。
- source 精确替换：
  - 旧：`新加坡肾病门诊资源安排。`
  - 新：`肾病门诊资源安排。`
  - 旧：`门诊安排须遵守决策日有效的新加坡卫生科学局关于Jinarc本地风险管理计划的要求。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Singapore Health Sciences Authority", "url": "https://www.hsa.gov.sg/announcements/update-on-the-risk-management-plan-of-jinarc-tolvaptan-discontinuation-of-healthcare-professional-hcp-education-and-certification-and-related-requirement/"}, {"publisher": "Singapore Health Sciences Authority", "url": "https://isomer-user-content.by.gov.sg/409/a6ed5d88-416a-4956-b299-4b65b841d4a9/jinarc_pmg_ver-1-0_23092022.pdf"}], "notes": "以当前HSA批准材料URL替换失效旧链接；E2改为不含省略号且保留医生主语、检查目的与启动前时间行的连续官方原文，逐患者支持三条启动—化验Patch。", "official_evidence_override": [{"information_responsibility": "HSA 2026更新撤下医护教育认证与处方清单/库存核验，但明确保留肝转氨酶和胆红素血液检查。", "node_id": "E1", "omission_effect": "缺少E1时，无法确认两个旧支持场次已撤下而患者肝功能化验仍属于当前新加坡Jinarc流程。", "publisher": "Singapore Health Sciences Authority", "quote": "15 July 2026. Otsuka will be discontinuing the Healthcare Professional (HCP) Education and Certification programme, and the verification of submitted prescribing checklists against stock balances. These changes are intended to streamline the prescribing and dispensing process. HCPs are still required to perform blood tests for hepatic transaminases and bilirubin in accordance with the Jinarc package insert.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "retained_action", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://www.hsa.gov.sg/announcements/update-on-the-risk-management-plan-of-jinarc-tolvaptan-discontinuation-of-healthcare-professional-hcp-education-and-certification-and-related-requirement/"}, {"information_responsibility": "HSA批准的患者材料以医生为主语，明确列出开始Jinarc前的肝功能血液检查。", "node_id": "E2", "omission_effect": "缺少E2时，2026更新只能证明仍需验血，不能把每名患者的Jinarc启动与其启动前化验逐一绑定。", "publisher": "Singapore Health Sciences Authority", "quote": "To check for any changes in your liver function, your doctor will conduct blood tests:\nPrior to starting treatment, at 2 weeks and 4 weeks after starting\nOnce", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["jinarc_requires_lab_chen", "jinarc_requires_lab_lim", "jinarc_requires_lab_tan"], "supported_patch_slots": ["jinarc_requires_lab_chen", "jinarc_requires_lab_lim", "jinarc_requires_lab_tan"], "url": "https://isomer-user-content.by.gov.sg/409/a6ed5d88-416a-4956-b299-4b65b841d4a9/jinarc_pmg_ver-1-0_23092022.pdf"}]}`
- 复核说明：仅将地域事实移到 case 层；Jinarc品牌和患者级动作在两案中均可观察，不改 action meaning。

### SWOR-R091

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留九票货物的化学类别、贡献值、恰选四票、单件包装与标签检查、同车运输和最大化目标；保留add_variable及逐对冲突Patch。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "每票货物分别置于密封且结构独立的货舱，各舱之间没有共同装载或储存空间，货物不能相互混合。", "decision_date": "2026-08-04", "jurisdiction": "美国州际公路运输", "regulated_subject": "美国合同承运人将四票题列货物装入一辆公路车辆"}`
- C2：`{"boundary_facts": "各包装之间没有阻止相互混合的隔离构造；承运人未使用私人承运危险废物安排或其他特别授权。", "decision_date": "2026-08-04", "jurisdiction": "美国州际公路运输", "regulated_subject": "美国合同承运人将四票题列货物装入一个未分隔的公路货舱"}`
- C1 不适用原因：C1中各票货物位于结构独立的密封舱，不共享装载或储存空间，49 CFR 177.848的同舱隔离矩阵不对这些成对选择生成冲突约束。
- 题内行动映射：a01-a09依次对应装载Aster、Beryl、Cinder、Dune、Ember、Flint、Grove、Harbor、Iris；external_rule_active及其activate约束是内部法规开关，不是公开行动；其余Patch按题列化学属性连接对应货票对。
- source 精确替换：
  - 旧：`装入同一辆车的一个不分隔货舱`
  - 新：`装入同一辆车`
  - 旧：`Harbor为不受Hazardous Materials Regulations管制的空托盘`
  - 新：`Harbor为空托盘，装运检验单显示无危险材料残留、无危险品包装或标识`
  - 旧：`货舱内不设置隔板或独立二次舱，且本次运输不使用特别批准。`
  - 新：`货物之间的物理隔离方式和运输授权状态由装载单逐票记录。`
  - 旧：`装载须遵守决策日有效的美国联邦公路危险材料隔离规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Pipeline and Hazardous Materials Safety Administration / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml?part=177"}], "notes": "已复核V1.4.4所存49 CFR 177.848隔离表、氰化物与酸以及独立舱边界的官方quote；节点与十二个Patch slot的绑定保持。"}`
- 复核说明：移出共通source中的未分隔货舱和授权事实并删除遵规提示；九个公开行动的对象在两案中不变。

### SWOR-R092

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留六批次的业务类型、收益、恰选三批、当日完成动作和最大化目标；保留单一add_constraint Patch。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "经认证的成分记录显示六个候选批次的四氯乙烯含量均为0%；各批在当天完成题列进口、加工、分销、生产或备货动作。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "美国进口商、加工商、分销商和制造商选择六个化学品供应批次中的三个"}`
- C2：`{"boundary_facts": "前五批含四氯乙烯；第四批仅用于持续干洗，第五批在完整WCPP工作场所控制下生产航空用途材料，第六批为不含四氯乙烯的水性清洁剂；全部动作当天完成。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "美国进口商、加工商、分销商和制造商选择含四氯乙烯与水性产品的供应批次"}`
- C1 不适用原因：C1六批均为0% PCE，选择动作不落入PCE制造、进口、加工或分销的规则对象，因此不加入2026年8月4日制造与进口域约束。
- 题内行动映射：a01-a06依次对应去渍剂、胶黏剂、非干洗用途溶剂、持续干洗溶剂、航空用途材料和水性清洁剂批次；唯一Patch以批次台账中的成分和当日动作激活。
- source 精确替换：
  - 旧：`美国PCE供应批次选择。`
  - 新：`美国化学品供应批次选择。`
  - 旧：`纽瓦克澄源化工要从六个供应批次中恰好选择三个：进口消费者使用的PCE去渍剂、加工消费者使用的PCE胶黏剂、向零售商分销非干洗用途PCE溶剂、生产仅用于持续干洗的PCE溶剂、在完整WCPP工作场所控制下生产PCE航空用途材料，以及备货不含PCE的水性清洁剂。`
  - 新：`纽瓦克澄源化工要从六个供应批次中恰好选择三个：进口消费者使用的去渍剂、加工消费者使用的胶黏剂、向零售商分销的非干洗用途溶剂、生产仅用于持续干洗的溶剂、在题列工作场所控制下生产航空用途材料，以及备货水性清洁剂。`
  - 旧：`前三批不属于干洗、WCPP或其他继续允许的工业商业用途；第四批仅用于继续允许的干洗，第五批已完整实施适用WCPP，第六批不含PCE。`
  - 新：`各批的化学成分、最终用途、工作场所控制和流向均记载在批次台账中。`
  - 旧：`组合须遵守决策日有效的美国TSCA PCE风险管理规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r092_a01": "进口消费者使用的去渍剂批次", "swor_r092_a02": "加工消费者使用的胶黏剂批次", "swor_r092_a03": "向零售商分销的非干洗用途溶剂批次", "swor_r092_a04": "生产仅用于持续干洗的溶剂批次", "swor_r092_a05": "在题列工作场所控制下生产航空用途材料批次", "swor_r092_a06": "备货水性清洁剂批次"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "United States Environmental Protection Agency", "url": "https://www.epa.gov/system/files/documents/2025-01/pce-fact-sheet_english.pdf"}], "notes": "已复核V1.4.4所存EPA PCE风险管理最终规则事实表关于制造、进口、加工、分销时点和继续用途分支的官方quote；Gold保持。"}`
- 复核说明：将PCE成分和WCPP分类移至case层，并同步泛化六个action meaning；收益和批次业务动作不变。

### SWOR-R093

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留同批活性组分、四个放行包、净效用、四选一和最大化目标；保留两条排除约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "四个方案均针对同一PET组分批次，生产线和批记录全部按Part 212制度运行。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦药品制造", "regulated_subject": "按21 CFR Part 212生产正电子发射断层扫描药品的制造商放行一个PET组分批次"}`
- C2：`{"boundary_facts": "四个方案均针对同一非特殊危险活性组分批次，供应商分析报告和厂内试验状态按题列方案记录。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦成品药制造", "regulated_subject": "制造供人使用的非PET、非医用气体成品药的制造商放行一个活性组分批次"}`
- C1 不适用原因：C1为Part 212 PET生产，不属于题列21 CFR 211.84成品药组分放行制度的主体，故不加入两条Part 211供应商报告/身份试验排除约束。
- 题内行动映射：a01-a04按source首次出现顺序对应仅供应商报告、经验证供应商报告加厂内身份试验、厂内全部试验、未验证供应商报告加厂内身份试验四个包。
- source 精确替换：
  - 旧：`一家在美国制备供人使用、既非正电子发射断层扫描药品也非医用气体的成品药制造商`
  - 新：`一家在美国制备供人使用药品的制造商`
  - 旧：`方案须符合决策日有效的美国联邦药品组分检验规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r093_a01": "仅凭供应商分析报告放行且不做身份试验", "swor_r093_a02": "采用已验证供应商报告并做身份试验", "swor_r093_a03": "全部属性由厂内试验", "swor_r093_a04": "采用未验证供应商报告但做身份试验"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-21.xml"}], "notes": "已复核V1.4.4所存21 CFR 211.1、211.84及PET Part 212边界quote；两条Gold约束保持。"}`
- 复核说明：仅将非PET/非医用气体主体属性移至case层并删除遵规提示；公开行动是通用放行包，无需改meaning；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R094

- 结论：`FIX`；问题类型：L2, L3, L5, L7。
- 保持：保留四种清洁方式、四种防护配置、压力与成本、两组各选一项及净效用目标；保留三条压缩空气约束。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "清洁作业、雇佣关系和设备均位于安大略省，工作场所登记由省级职业安全机构管理。", "decision_date": "2026-08-04", "jurisdiction": "加拿大安大略省", "regulated_subject": "安大略省私营包装厂雇主选择雇员班后设备清洁方法"}`
- C2：`{"boundary_facts": "清洁工况属于普通一般工业，工作场所档案未列出其他联邦机构对该工况行使职业安全权限。", "decision_date": "2026-08-04", "jurisdiction": "美国华盛顿哥伦比亚特区", "regulated_subject": "华盛顿哥伦比亚特区普通私营包装厂雇主选择雇员班后设备清洁方法"}`
- C1 不适用原因：C1全部作业位于加拿大安大略省且无美国雇佣联系，美国联邦OSHA 29 CFR 1910.242不控制该清洁选择。
- 题内行动映射：a01-a04依次为45 psi、25 psi、工业吸尘、20 psi清洁方式；a05-a08依次为无配置、仅防屑、仅PPE、两者同时配置。
- source 精确替换：
  - 旧：`华盛顿哥伦比亚特区一家普通私营包装厂安排雇员在班后清洁生产设备，没有其他联邦机构对该清洁工况行使职业安全监管权限。`
  - 新：`一家普通私营包装厂安排雇员在班后清洁生产设备；工厂所在地和监管主体由工作场所登记资料记录。`
  - 旧：`方案须遵守决策日有效的美国联邦一般工业清洁作业规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r094_a01": "采用喷嘴处实测45 psi的压缩空气清洁方案", "swor_r094_a02": "采用喷嘴处实测25 psi的压缩空气清洁方案", "swor_r094_a03": "采用工业吸尘清洁方案", "swor_r094_a04": "采用喷嘴处实测20 psi的压缩空气清洁方案", "swor_r094_a05": "不配置碎屑防护或个人防护装备", "swor_r094_a06": "仅配置有效碎屑防护", "swor_r094_a07": "仅配置完整个人防护装备", "swor_r094_a08": "同时配置有效碎屑防护和完整个人防护装备"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XVII/part-1910/subpart-A/section-1910.5"}, {"publisher": "U.S. Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XVII/part-1910/subpart-P/section-1910.242"}], "notes": "已复核V1.4.4所存OSHA一般适用边界及压缩空气清洁的30 psi、防屑与PPE官方quote；Gold保持。"}`
- 复核说明：将地点和监管主体移至case层；清洁方案、压力和防护属性在两案中相同；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R095

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四个车辆效用、两个道口、停车/不停车成本、三组各选一项和最大化目标；保留三条车辆到停车动作的依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "四辆候选车均为普通非载客货车，调度单未标示危险材料标牌、危险材料罐式车或49 CFR 392.10(a)列举的其他车辆类别。", "decision_date": "2026-08-04", "jurisdiction": "美国州际商业车辆运输", "regulated_subject": "州际商业货运承运人从四个普通非载客车辆方案中选择车辆和道口动作"}`
- C2：`{"boundary_facts": "车辆A为载客巴士，B为悬挂Division 1.1标牌的货车，C为普通货车，D为运输危险材料的罐式车辆；活动公共道口没有警察、旗手或绿灯，另一道口带州授权Exempt标志。", "decision_date": "2026-08-04", "jurisdiction": "美国州际商业车辆运输", "regulated_subject": "州际商业承运人选择一辆题列车辆和一个铁路道口通过动作"}`
- C1 不适用原因：C1四辆车均不在49 CFR 392.10(a)列举车辆类别内，因此车辆选择不生成活动道口停车依赖；基础三组选择模型保留。
- 题内行动映射：a01-a04按source首次出现顺序对应车辆A-D，a05/a06对应活动公共道口与Exempt工业支线，a07/a08对应停车与不停车。
- source 精确替换：
  - 旧：`车辆效用分别为：载客巴士20点、Division 1.1挂牌货车28点、普通货车23点、运输危险材料的罐式车辆25点。`
  - 新：`四个车辆方案A至D的效用依次为20、28、23和25点；车辆用途、标牌和货物类别由当班调度单记录。`
  - 旧：`方案须符合决策日美国联邦铁路道口规范。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r095_a01": "选择载客巴士", "swor_r095_a02": "选择Division 1.1挂牌货车", "swor_r095_a03": "选择普通货车", "swor_r095_a04": "选择危险材料罐车", "swor_r095_a05": "选择活动公共道口", "swor_r095_a06": "选择标有Exempt的工业支线道口", "swor_r095_a07": "在距轨道15至50英尺处停车", "swor_r095_a08": "不停车通过"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Motor Carrier Safety Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "已复核V1.4.4所存49 CFR 392.10车辆类别、停车动作和Exempt道口分支quote；三条Gold依赖保持。"}`
- 复核说明：将四辆车的类别移至case层；公开schema原为顺序型meaning，与两案对象不冲突；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R096

- 结论：`FIX`；问题类型：L2, L4, L5, L6, L7。
- 保持：保留八项订单的货物、收益、恰选两项和最大化目标；保留三条既有货类排除约束并补入Haven乘用车辆排除。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "航线是缅因州大陆Cumberland County与Long Island之间；每项订单均由cargo weight超过5 gross tons的roll-on and roll-off车辆承运，装卸不使用Casco Bay Island Transit District定班服务码头；航次依公开固定班表运行，不按需求临时开航。", "decision_date": "2026-08-04", "jurisdiction": "美国缅因州卡斯科湾岛屿交通区", "regulated_subject": "依据独立定班服务授权运营的定期滚装货运服务选择两项岛屿订单"}`
- C2：`{"boundary_facts": "航线是缅因州大陆Cumberland County与Long Island之间；每项订单均由cargo weight超过5 gross tons的roll-on and roll-off车辆承运，装卸不使用Casco Bay Island Transit District定班服务码头；航次按客户临时需求组成，不依任何公布或宣布的班表，也不属于运营人按固定或预设频率提供运输的模式。", "decision_date": "2026-08-04", "jurisdiction": "美国缅因州卡斯科湾岛屿交通区", "regulated_subject": "非定班滚装货运运营人选择两项岛屿订单"}`
- C1 不适用原因：C1航次由独立的定班服务授权和固定班表运行，不是35-A M.R.S. §5101-D定义的非定班岛屿滚装货运服务，故不加入该条规定的货类排除约束。
- 题内行动映射：a01-a08依次对应Atlas、Birch、Cove、Dune、Elm、Fjord、Grove、Haven订单；C2的四条Patch分别排除食品、箱装货物、饮料和不属于允许车辆/货类的乘用车辆订单。
- source 精确替换：
  - 旧：`缅因州卡斯科湾岛屿非定班滚装货运订单选择。`
  - 新：`缅因州卡斯科湾岛屿滚装货运订单选择。`
  - 旧：`承运方案须遵守决策日有效的缅因州卡斯科湾岛屿非定班滚装货运规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_element": {"after": {"coefficients": {"carry_order_haven": 1}, "meaning": "承运Haven乘用车辆订单不属于本非定班滚装货运服务允许的车辆或货类", "name": "ineligible_carry_order_haven", "rhs": 0, "sense": "="}, "name": "ineligible_carry_order_haven", "op": "add_constraint"}, "reason": "§5101-D(1)(B)的正面类别清单不包含Haven乘用车辆，原Gold只排除三种明文禁运货物而遗漏该正面资格边界。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Maine Legislature", "url": "https://legislature.maine.gov/statutes/35-a/title35-Asec5101-D.html"}], "notes": "补齐§5101-D(1)的大陆Cumberland County—Long Island路线、>5 gross tons滚装车辆及非CBITD定班码头条件，并分别保存允许/禁止货类和unscheduled定义；Haven乘用车辆不属于列举车辆或货类，新增第四条排除。", "official_evidence_override": [{"information_responsibility": "§5101-D(1)界定Mainland Cumberland County与Long Island等岛屿之间服务、滚装车辆cargo weight门槛、允许车辆/货类以及非CBITD定班码头条件。", "node_id": "E1", "omission_effect": "缺少E1时，无法确认C2的路线、车辆重量和装卸码头满足该节的Mainland service适用前提。", "publisher": "Maine Legislature", "quote": "1. Mainland service. For service between mainland Cumberland County and Long Island, Cliff Island, Little Diamond Island, Great Diamond Island and Chebeague Island and service between these islands: A. The service is for unscheduled transportation of a roll-on and roll-off vehicle, as defined by the commission by rule, with a cargo weight in excess of 5 gross tons, excluding 4-wheel trucks and cars of 10 or less gross tons unless carried in conjunction with a roll-on and roll-off vehicle with a cargo weight in excess of 5 gross tons; B. The vehicles transported: (1) Carry only commodities in bulk, construction materials, or household goods, provided that the household goods are carried in tractor trailers; or (2) Are construction equipment or special purpose vehicles, such as trash compactors and emergency equipment. Freight transported in the vehicles may not include food, beverages, perishables and wrapped or boxed freight; and C. Loading and unloading of vessels does not occur at wharves or docks used by the Casco Bay Island Transit District for its scheduled service.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://legislature.maine.gov/statutes/35-a/title35-Asec5101-D.html"}, {"information_responsibility": "§5101-D(1)(B)将可运输对象限于散装商品、建筑材料、由牵引式半挂车承运的家庭用品、建筑设备或专用车辆，并明文排除食品、饮料、易腐品及包装或箱装货物。", "node_id": "E2", "omission_effect": "缺少E2时，无法排除Atlas、Cove、Fjord和不属于列举类别的Haven订单。", "publisher": "Maine Legislature", "quote": "B. The vehicles transported: (1) Carry only commodities in bulk, construction materials, or household goods, provided that the household goods are carried in tractor trailers; or (2) Are construction equipment or special purpose vehicles, such as trash compactors and emergency equipment. Freight transported in the vehicles may not include food, beverages, perishables and wrapped or boxed freight;", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["ineligible_carry_order_atlas", "ineligible_carry_order_cove", "ineligible_carry_order_fjord", "ineligible_carry_order_haven"], "supported_patch_slots": ["ineligible_carry_order_atlas", "ineligible_carry_order_cove", "ineligible_carry_order_fjord", "ineligible_carry_order_haven"], "url": "https://legislature.maine.gov/statutes/35-a/title35-Asec5101-D.html"}, {"information_responsibility": "该节把unscheduled transportation定义为按需、非公布或宣布班表且非固定或预设频率模式的运输。", "node_id": "E3", "omission_effect": "缺少E3时，无法由C1固定公开班表确认RETAIN，也无法由C2按需且无固定频率确认该节适用。", "publisher": "Maine Legislature", "quote": "For the purposes of this section, the term \"unscheduled transportation\" means transportation that is provided on demand, not pursuant to any published or announced schedule and not as a part of a pattern of an operator in providing transportation at a regular or preset frequency.", "role": "definition", "source_node_id": "E3", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://legislature.maine.gov/statutes/35-a/title35-Asec5101-D.html"}]}`
- 复核说明：移出非定班属性并删除遵规提示；补齐路线、重量、码头与按需服务事实，并修复遗漏的Haven排除约束。

### SWOR-R097

- 结论：`FIX`；问题类型：L1, L2, L5, L7。
- 保持：保留三名用户、三个批次、每批容量、工时矩阵、每人选一批和最小化目标；保留期限与最早可行批次约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "三份通知记录的是公司自筹资金的可选优惠；三名用户均在9月1日完成内部入账准备，首批有两个处理名额。", "decision_date": "2026-08-02", "jurisdiction": "美国佛罗里达州", "regulated_subject": "一家未取得eligible telecommunications carrier身份的佛罗里达电信公司安排自有账单优惠"}`
- C2：`{"boundary_facts": "三名用户均在9月1日完成入账准备，首批有两个处理名额；客户材料、系统和人员记录均未出现延迟事实。", "decision_date": "2026-08-02", "jurisdiction": "美国佛罗里达州", "regulated_subject": "佛罗里达eligible telecommunications carrier收到三名用户Lifeline资格通知后安排账单抵免"}`
- C1 不适用原因：C1公司不是eligible telecommunications carrier且通知对应公司自筹可选优惠，不属于佛州Lifeline抵免处理链，因此不加入Lifeline期限和最早可行批次约束。
- 题内行动映射：a01-a03为用户1的sep01/sep16/oct16，a04-a06为用户2，a07-a09为用户3；deadline和earliest-practicable Patch按用户—批次变量作用。
- source 精确替换：
  - 旧：`佛罗里达Lifeline账单处理排程。`
  - 新：`佛罗里达账单优惠处理排程。`
  - 旧：`海湾电信已收到3名用户的Lifeline资格通知，要`
  - 新：`海湾电信已收到3名用户的账单优惠处理通知，要`
  - 旧：`运营记录确认3名用户从9月1日起均已具备入账条件，9月1日批次的2名处理容量全部可用，且不存在客户材料、系统或人员方面的延迟理由。`
  - 新：`运营记录确认3名用户从9月1日起均已完成内部入账准备，9月1日批次的2名处理容量全部可用，且不存在客户材料、系统或人员方面的延迟事实。`
  - 旧：`排程必须遵守佛罗里达州对合格电信承运商发放Lifeline账单抵免的现行规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Florida Legislature", "url": "https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&URL=0300-0399/0364/Sections/0364.10.html"}], "notes": "用完整连续官方句替换从单词中部开始并夹带大量无关段落的quote；句中ETC主语、as soon as practicable与60日期限足以支持两条Patch。", "official_evidence_override": [{"information_responsibility": "佛州法要求eligible telecommunications carrier尽快且最迟在收到资格通知后60日内把Lifeline抵免计入消费者账单。", "node_id": "E1", "omission_effect": "缺少E1时，无法排除10月16日批次，也无法在不存在延迟事实时要求使用9月1日最早可行批次的两个名额。", "publisher": "Florida Legislature", "quote": "An eligible telecommunications carrier shall timely credit a consumer’s bill with the Lifeline Assistance credit as soon as practicable, but no later than 60 days following receipt of notice of eligibility.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["credit_deadline", "earliest_practicable_batch"], "supported_patch_slots": ["credit_deadline", "earliest_practicable_batch"], "url": "https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&URL=0300-0399/0364/Sections/0364.10.html"}]}`
- 复核说明：将ETC身份、Lifeline通知性质和法规级及时性事实移至case层；工时和容量模型不变。

### SWOR-R098

- 结论：`FIX`；问题类型：L2, L5, L7。
- 保持：保留八个双班组合的时间结构、覆盖价值、恰选两个和最大化目标；保留add_variable开关及三条阻断约束。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "八个组合的全部值班由NAV CANADA分配，设施、人员和工作地点均在加拿大；Aurora、Delta、Forest在日班后分别休息11、10、11小时进入午夜班，Bay、Cedar、Harbor普通班间隔分别为10、9、11小时，Elm在午夜班后休息10小时，Grove包含连续第7个工作日。", "decision_date": "2026-08-04", "jurisdiction": "加拿大", "regulated_subject": "NAV CANADA空管设施在2026年度排班期选择两个双班组合"}`
- C2：`{"boundary_facts": "FAA 2026排班记录将暂停项限定在午夜班之前的间隔；午夜班之后的间隔和连续第7个工作日按各组合原始时间记录。", "decision_date": "2026-08-04", "jurisdiction": "美国FAA空管设施", "regulated_subject": "FAA空管设施在2026 Basic Watch Schedule期间选择两个双班组合"}`
- C1 不适用原因：C1由NAV CANADA在加拿大安排值班，不属于FAA设施或美国BWS系统，故外部规则开关为0且不加入Cedar、Elm、Grove三条阻断。
- 题内行动映射：a01-a08依次为Aurora、Bay、Cedar、Delta、Elm、Forest、Grove、Harbor双班组合；external_rule_active及activate_external_rule是内部开关，不是公开行动；三条阻断分别绑定a03、a05、a07。
- source 精确替换：
  - 旧：`美国FAA设施2026年度双班组合选择。`
  - 新：`空管设施2026年度双班组合选择。`
  - 旧：`排班须遵守决策日有效的FAA 2026 Basic Watch Schedule规定。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Federal Aviation Administration", "url": "https://www.faa.gov/documentLibrary/media/Notice/GENOT_N_JO_7210.966_Basic_Watch_Schedule.pdf"}, {"publisher": "U.S. Federal Aviation Administration", "url": "https://www.faa.gov/documentLibrary/media/Order/7210.3EE_Bsc_w_Chg_1_2_and_3_dtd_7-9-26.pdf"}], "notes": "把E1/E2含省略号的拼接引文拆为四个连续官方节点：2026仅暂停午夜班前12小时、午夜班后仍12小时、普通班间至少10小时、不得连续第7日工作；Gold保持。", "official_evidence_override": [{"information_responsibility": "FAA Notice明确2026 BWS只暂停午夜班之前的12小时休息要求。", "node_id": "E1", "omission_effect": "缺少E1时，无法确认Aurora、Delta与Forest的午夜班前间隔落入2026暂停项，也无法界定暂停范围。", "publisher": "U.S. Federal Aviation Administration", "quote": "THE REQUIREMENT FOR A 12-HOUR OFF DUTY PERIOD PRIOR TO A MIDNIGHT SHIFT HAS BEEN SUSPENDED FOR THE PERIOD COVERED BY THE 2026 BASIC WATCH SCHEDULE (BWS).", "role": "effective_exception", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["external_rule_active", "activate_external_rule"], "supported_patch_slots": ["external_rule_active", "activate_external_rule"], "url": "https://www.faa.gov/documentLibrary/media/Notice/GENOT_N_JO_7210.966_Basic_Watch_Schedule.pdf"}, {"information_responsibility": "同一Notice保留FAA设施管制员在午夜班之后至少12小时的休息要求。", "node_id": "E2", "omission_effect": "缺少E2时，无法排除午夜班后只休息10小时的Elm组合。", "publisher": "U.S. Federal Aviation Administration", "quote": "c. FACILITY AIR TRAFFIC MANAGERS MUST ENSURE THAT AIR TRAFFIC CONTROL SPECIALISTS (ATCS) ASSIGNED TO A POSITION OF OPERATION: SUBPARAGRAPH c1 THROUGH c3, NO CHANGE 4. HAVE AN OFF DUTY PERIOD OF AT LEAST 12 HOURS FOLLOWING THE MIDNIGHT SHIFT.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["rule_blocks_assign_pair_elm"], "supported_patch_slots": ["rule_blocks_assign_pair_elm"], "url": "https://www.faa.gov/documentLibrary/media/Notice/GENOT_N_JO_7210.966_Basic_Watch_Schedule.pdf"}, {"information_responsibility": "FAA Order要求被安排到操作席位的管制员两次值班之间至少休息10小时。", "node_id": "E3", "omission_effect": "缺少E3时，无法排除两次普通班仅间隔9小时的Cedar组合。", "publisher": "U.S. Federal Aviation Administration", "quote": "c. Facility air traffic managers must ensure that air traffic control specialists (ATCS) assigned to a position of operation: 1. Do not work more than 6 consecutive days. 2. Do not work more than a 10-hour day. 3. Have an off-duty period of at least 10 hours between watches.", "role": "operative_rule", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["rule_blocks_assign_pair_cedar"], "supported_patch_slots": ["rule_blocks_assign_pair_cedar"], "url": "https://www.faa.gov/documentLibrary/media/Order/7210.3EE_Bsc_w_Chg_1_2_and_3_dtd_7-9-26.pdf"}, {"information_responsibility": "FAA Order要求被安排到操作席位的管制员不得连续工作超过6日。", "node_id": "E4", "omission_effect": "缺少E4时，无法排除包含连续第7个工作日的Grove组合。", "publisher": "U.S. Federal Aviation Administration", "quote": "c. Facility air traffic managers must ensure that air traffic control specialists (ATCS) assigned to a position of operation: 1. Do not work more than 6 consecutive days.", "role": "operative_rule", "source_node_id": "E4", "support_target_type": "patch_slot", "support_targets": ["rule_blocks_assign_pair_grove"], "supported_patch_slots": ["rule_blocks_assign_pair_grove"], "url": "https://www.faa.gov/documentLibrary/media/Order/7210.3EE_Bsc_w_Chg_1_2_and_3_dtd_7-9-26.pdf"}]}`
- 复核说明：仅将FAA设施身份移至case层并删除遵规提示；组合时间事实和行动对象均保留。

### SWOR-R099

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L7。
- 保持：保留四个频道方案、五个容量包、效用与耗用、两组选一和最大化目标；保留七条方案—容量排除约束。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "该设施连接订户但全部线路位于私人土地和建筑内，未使用公共道路通行权；建模服务中只有这一处设施；D的1984年10月30日生效特许文本未包含商业租赁接入条款。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "视频服务运营商为一个仅在私人设施内运行的订户网络选择频道和非关联节目容量"}`
- C2：`{"boundary_facts": "A、B、C的内部台账分别把10、20、40个频道标记为有对应联邦使用或禁用命令，且每项标记均附命令文件；D的1984年10月30日生效特许文本未包含商业租赁接入条款；题列频道不可拆分，运营商与节目商没有关联关系。", "decision_date": "2026-08-04", "jurisdiction": "美国联邦有线电视服务", "regulated_subject": "有线电视运营商为一个社区有线系统选择激活频道和非关联全时商业租赁接入容量"}`
- C1 不适用原因：C1设施不使用任何公共通行权并符合47 U.S.C. 522(7)(B)排除边界，因而不按§532计算商业租赁接入保留容量，不加入七条方案—容量约束。
- 题内行动映射：a01-a04依次为频道方案A-D，a05-a09依次为划出0、4、6、12、18个频道；七条Patch连接特定频道方案与不足容量包。
- source 精确替换：
  - 旧：`美国有线电视系统频道方案与商业租赁接入容量。`
  - 新：`频道方案与商业租赁接入容量。`
  - 旧：`岬湾有线电视公司须为一个社区系统`
  - 新：`岬湾视频服务运营商须为一个社区设施`
  - 旧：`A含50个激活频道，其中10个已确认属于联邦法律要求使用或禁止使用的频道，频道服务效用130点；B含60个激活频道，其中20个属于该类频道，效用135点；C含120个激活频道，其中40个属于该类频道，效用150点；D含35个激活频道，且不存在1984年10月30日生效的特许协议所规定的商业租赁接入义务，效用110点。`
  - 新：`A含50个激活频道，内部台账把其中10个频道标记为有对应联邦使用或禁用命令，频道服务效用130点；B含60个激活频道，其中20个有对应命令记录，效用135点；C含120个激活频道，其中40个有对应命令记录，效用150点；D含35个激活频道，1984年10月30日生效的特许文本及商业租赁条款由特许档案记录，效用110点。`
  - 旧：`A至C的联邦要求或禁用频道分类已经确认，题列外地方要求不改变计算，频道不可拆分。`
  - 新：`A至C的台账标记均有对应命令文件，题列外地方频道记录不改变台账计数，频道不可拆分。`
  - 旧：`安排须遵守决策日有效的美国联邦商业租赁接入频道容量规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r099_a01": "采用50个激活频道且台账标记10个有对应联邦使用或禁用命令的方案A", "swor_r099_a02": "采用60个激活频道且台账标记20个有对应联邦使用或禁用命令的方案B", "swor_r099_a03": "采用120个激活频道且台账标记40个有对应联邦使用或禁用命令的方案C", "swor_r099_a04": "采用35个激活频道的方案D"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. House of Representatives, Office of the Law Revision Counsel", "url": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title47-section522&num=0&edition=prelim"}, {"publisher": "U.S. House of Representatives, Office of the Law Revision Counsel", "url": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title47-section532&num=0&edition=prelim"}], "notes": "补入47 U.S.C. §522(7)(B)完整定义片段，明确不使用任何公共通行权的设施不属于cable system；原§532四个分档节点和七条Gold约束保持。", "official_evidence_node_overrides": [{"information_responsibility": "§522(7)把连接多个社区订户的视频设施定义为cable system，但明确排除不使用任何公共通行权的设施。", "node_id": "E0", "omission_effect": "缺少E0时，无法由C1全部线路位于私人土地且不使用公共通行权确认其不属于cable system并RETAIN Base。", "publisher": "U.S. House of Representatives, Office of the Law Revision Counsel", "quote": "the term \"cable system\" means a facility, consisting of a set of closed transmission paths and associated signal generation, reception, and control equipment that is designed to provide cable service which includes video programming and which is provided to multiple subscribers within a community, but such term does not include (A) a facility that serves only to retransmit the television signals of 1 or more television broadcast stations; (B) a facility that serves subscribers without using any public right-of-way;", "role": "definition_and_exception", "source_node_id": "E0", "support_target_type": "exception_boundary", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title47-section522&num=0&edition=prelim"}]}`
- 复核说明：将有线系统法律身份移至case层；频道数、联邦分类和历史特许事实仍作为候选方案业务属性保留。

### SWOR-R100

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留TRS功能描述、四个配置包、100通电话口径、10秒接通数、净效用、四选一和最大化目标；保留两条低接通率排除约束。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "运营日志将题列100通电话全部标记在同一次网络故障期间，且没有任何电话来自正常运行窗口。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦电信中继服务", "regulated_subject": "TRS设施为记录有网络故障的测量窗口选择应急人员配置包"}`
- C2：`{"boundary_facts": "题列100通电话均在网络正常运行期间到达，测量日志未记录网络故障，所有电话采用相同接通统计口径。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦电信中继服务", "regulated_subject": "TRS设施为正常运行测量窗口选择人员配置包"}`
- C1 不适用原因：C1全部呼叫发生在有记录的网络故障期间，落入接听速度规则的网络故障排除窗口，故不以85%阈值排除80通与75通配置包。
- 题内行动映射：a01-a04按source首次出现顺序对应10秒内接通80、85、90、75通电话的四个配置包；Patch排除a01和a04。
- source 精确替换：
  - 旧：`设施在正常网络运行状态下选择一个完整人员配置包。`
  - 新：`设施在一个统一测量窗口内选择一个完整人员配置包；该窗口的网络运行状态由运营记录标明。`
  - 旧：`方案须符合决策日有效的美国联邦通信辅助呼叫接听速度规范。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r100_a01": "选择10秒内接听80通的方案", "swor_r100_a02": "选择10秒内接听85通的方案", "swor_r100_a03": "选择10秒内接听90通的方案", "swor_r100_a04": "选择10秒内接听75通的方案"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml"}, {"publisher": "U.S. Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml"}], "notes": "已复核V1.4.4所存47 CFR TRS定义、85%在10秒内接通标准和网络故障边界的官方quote；两条Gold排除保持。"}`
- 复核说明：将网络状态移至case层并删除遵规提示；配置包及统计口径不变；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R101

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四份委托的班次与效用、两种飞机、无陆路水路、两个气瓶处置包、三组选一及净效用目标；保留三条飞机/处置依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "每个气瓶均为空瓶，已清洗和吹扫并拆除阀门；检验记录显示瓶内没有压缩氧气、氧化性气体或危险材料残留。", "decision_date": "2026-08-04", "jurisdiction": "美国阿拉斯加州内航空运输", "regulated_subject": "航空运营人选择一份偏远诊所气瓶配送委托、飞机和处置包"}`
- C2：`{"boundary_facts": "A和C目的地每周至少有一次纯货运航班，B和D没有；客运与纯货运飞机均可调配；加强处置包使用耐火或阻燃毯固定每个气瓶并向航空器运营人发出通知。", "decision_date": "2026-08-04", "jurisdiction": "美国阿拉斯加州内航空运输", "regulated_subject": "航空运营人向没有陆路或水路通达的阿拉斯加诊所运输压缩氧气瓶"}`
- C1 不适用原因：C1气瓶为空、已清洗吹扫且无氧化性气体或危险材料残留，不是§175.34所处理的压缩氧气危险材料运输，因此不加入周班目的地飞机类型和毯包通知依赖。
- 题内行动映射：a01-a04依次为委托A-D，a05/a06为客运与纯货运飞机，a07/a08为普通与加强处置包；三条Patch分别连接A、C委托到飞机类型，并把C2任一委托连接到加强处置包。
- source 精确替换：
  - 旧：`美国阿拉斯加医用氧气航空配送。`
  - 新：`阿拉斯加偏远诊所气瓶航空配送。`
  - 旧：`本批压缩氧气瓶满足其他运输要求，但不具备通常规则所列的气瓶防火构造，只能在适用的阿拉斯加航空例外成立时运输。`
  - 新：`本批气瓶的充装物、阀门和残余物状态由装运检验单记录；题列气瓶不具备通常配置中的防火构造。`
  - 旧：`普通处置包耗用0点；例外处置包把每个气瓶完全覆盖并固定在耐火或阻燃毯内，同时完成适用的航空器运营人通知，耗用12点。不存在题列外批准或豁免。`
  - 新：`普通处置包耗用0点；加强处置包把每个气瓶完全覆盖并固定在耐火或阻燃毯内，同时完成航空器运营人通知，耗用12点。题列外运输授权状态由委托档案记录。`
  - 旧：`运输须遵守决策日适用于阿拉斯加氧化性气瓶、目的地班次和飞机类别的美国联邦规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r101_a01": "承接每周至少有一次纯货运航班的诊所A配送", "swor_r101_a02": "承接没有每周纯货运航班的诊所B配送", "swor_r101_a03": "承接每周至少有一次纯货运航班的诊所C配送", "swor_r101_a04": "承接没有每周纯货运航班的诊所D配送", "swor_r101_a05": "使用客运飞机", "swor_r101_a06": "使用纯货运飞机", "swor_r101_a07": "使用不含阿拉斯加例外措施的普通气瓶处置包", "swor_r101_a08": "使用防火毯固定与航空器运营人通知包"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Pipeline and Hazardous Materials Safety Administration / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "已复核V1.4.4所存49 CFR 175.34关于阿拉斯加目的地、周班纯货运飞机、毯包与通知的官方quote；Gold保持。"}`
- 复核说明：移出气瓶充装物和例外结论，泛化处置包名称并删除遵规提示；顺序型action meaning无需修改；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R102

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留三个停车情景贡献、三个警示响应及成本、20分钟、设备齐全、两组选一和最大化目标；保留直线与视距受阻警示依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B、C三个候选停车点均完全位于私人场院内，处于公路行车道和路肩之外；停车车辆与公路交通之间由场院围界分隔。", "decision_date": "2026-08-05", "jurisdiction": "美国商业机动车运输", "regulated_subject": "商业承运人选择一个停车地点和警示响应"}`
- C2：`{"boundary_facts": "A位于公共公路直线路肩；B位于弯道视距受阻且距弯道不足500英尺的公路路肩；C完全位于私人场院；A和B的停车原因不是交通流要求。", "decision_date": "2026-08-05", "jurisdiction": "美国商业机动车运输", "regulated_subject": "商业承运人选择一个20分钟停车地点和警示响应"}`
- C1 不适用原因：C1所有候选均在公路行车道与路肩之外的私人场院，49 CFR 392.22的公路停车警示链不为这些选择生成响应依赖。
- 题内行动映射：a01-a03依次为停车场景A-C，a04-a06依次为不部署、直线路段警示、增加视距受阻方向提前警示；两条Patch连接a01到a05/a06、a02到a06。
- source 精确替换：
  - 旧：`公共公路直线路肩停车贡献95点；弯道视距受阻且距弯道不足500英尺的公路路肩停车贡献105点；完全离开公路的私人场院停车贡献88点。`
  - 新：`直线路段场景A贡献95点；弯道视距受阻且距弯道不足500英尺的场景B贡献105点；私人场院场景C贡献88点；各场景相对公路行车道和路肩的位置由停车记录标明。`
  - 旧：`两处公路停车均非交通所必需，设备齐全。`
  - 新：`各情景的停车原因由停车记录标明，警示响应所列设备齐全。`
  - 旧：`方案须遵守决策日有效的美国联邦故障停车警示规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r102_a01": "公共公路直线路肩故障停车20分钟", "swor_r102_a02": "公共公路弯道视距受阻处故障停车20分钟", "swor_r102_a03": "完全离开公路的私人场院停车", "swor_r102_a04": "不部署停车警示装置", "swor_r102_a05": "立即开启危险警示并在10分钟内按直线路段部署装置", "swor_r102_a06": "立即开启危险警示并在10分钟内含视距受阻提前警示点部署装置"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Motor Carrier Safety Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml"}], "notes": "已复核V1.4.4所存49 CFR 392.22关于公路停车、10分钟装置和视距受阻提前警示的官方quote；Gold保持。"}`
- 复核说明：将场景相对公路的位置和停车原因移至case层；保留场景几何标签与业务贡献；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R103

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L6, L7。
- 保持：保留四名员工的接种时间或记录、贡献、三个疫苗服务及成本、培训与禁忌状态、两组选一和最大化目标；保留第15日提前服务依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "四个候选岗位均只使用密封的非生物模拟物；岗位操作没有皮肤、眼、口腔黏膜或针刺接触血液及其他潜在感染材料的路径。", "decision_date": "2026-08-05", "jurisdiction": "美国一般工业实验室", "regulated_subject": "实验室雇主选择一名员工和一项乙肝疫苗服务"}`
- C2：`{"boundary_facts": "甲和乙的岗位存在皮肤、眼、口腔黏膜或针刺接触血液的可预见路径；雇主拟到甲初次分配后的第15个工作日才向其提供乙肝疫苗，并拟于乙初次分配后的第8个工作日向其提供乙肝疫苗；丙的完整系列记录和丁的抗体记录有效。", "decision_date": "2026-08-05", "jurisdiction": "美国一般工业实验室", "regulated_subject": "实验室雇主选择一名员工和一项乙肝疫苗服务"}`
- C1 不适用原因：C1工作仅接触密封非生物模拟物且无职业暴露路径，29 CFR 1910.1030的乙肝疫苗提供时限不支配这些岗位选择，故不加甲的提前服务依赖。
- 题内行动映射：a01-a04依次为甲的第15日提供安排、乙的第8日提供安排、丙的完整系列记录和丁的抗体记录；a05-a07依次为不增加服务、把雇主向甲提供疫苗提前到第8日、重做完整系列；唯一Patch要求选择a01时同步选择a06。
- source 精确替换：
  - 旧：`甲和乙的岗位均可合理预见其皮肤、眼或口腔黏膜或者经针刺接触血液；甲初次分配该岗位但拟在第15个工作日接种，贡献105点；乙初次分配且拟在第8个工作日接种，贡献94点；丙有完整疫苗系列记录，贡献98点；丁有抗体免疫证明，贡献92点。`
  - 新：`甲初次分配岗位，雇主拟到第15个工作日才向其提供乙肝疫苗，贡献105点；乙初次分配岗位，雇主拟于第8个工作日向其提供乙肝疫苗，贡献94点；丙有完整疫苗系列记录，贡献98点；丁有抗体免疫证明，贡献92点；各岗位的接触介质和操作方式由岗位风险记录标明。`
  - 旧：`方案须遵守决策日有效的美国联邦血源性病原体防护规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r103_a01": "选择员工甲及雇主拟到第15个工作日才向其提供乙肝疫苗的岗位安排", "swor_r103_a02": "选择员工乙及雇主拟于第8个工作日向其提供乙肝疫苗的岗位安排", "swor_r103_a03": "选择已有完整乙肝疫苗系列记录的员工丙", "swor_r103_a04": "选择已有抗体免疫证明的员工丁", "swor_r103_a05": "不增加乙肝疫苗服务", "swor_r103_a06": "将雇主向甲提供乙肝疫苗的日期从第15个工作日提前到第8个工作日", "swor_r103_a07": "安排重新完成整套乙肝疫苗系列"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_element": {"after": {"coefficients": {"accelerate_within10": -1, "new_day15": 1}, "meaning": "雇主拟到第15个工作日才向甲提供乙肝疫苗时，必须配对将提供日期提前到第8个工作日的服务", "name": "day15_requires_acceleration", "rhs": 0, "sense": "<="}, "name": "day15_requires_acceleration", "op": "add_constraint"}, "reason": "官方义务是雇主在10个工作日内make vaccination available而不是保证员工在该日实际接种；数学系数不变，但Patch语义必须与纠正后的题面和IR同步。"}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}, {"publisher": "U.S. Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "已复核29 CFR 1910.1030职业暴露定义和雇主须在初次分配后10个工作日内make vaccination available的完整原文；把题面“接种”纠正为“雇主提供”，并同步公开meaning、IR meaning与Patch meaning。"}`
- 复核说明：把甲乙岗位接触路径移至case层并删除遵规提示；纠正“实际接种”与“雇主提供疫苗”的法律行动语义，数学最优解不变；删除题面中的顺序映射元说明。

### SWOR-R104

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留三个岗位贡献、三个辅助包及成本、两组选一和最大化目标；保留开放酸液岗位到快速冲洗设施的依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "A、B、C三个岗位均使用非腐蚀性物料和经认证的封闭工艺；工艺单未显示眼睛或身体接触有害腐蚀性材料的路径。", "decision_date": "2026-08-05", "jurisdiction": "美国新泽西州一般工业", "regulated_subject": "私营工厂雇主选择一个岗位和一个辅助设施包"}`
- C2：`{"boundary_facts": "A为开放式腐蚀性酸液转移，存在酸液飞溅到眼睛或身体的路径；B为全封闭酸液系统；C为无腐蚀性材料的干燥包装；题列冲洗设施位于工作区并可立即使用。", "decision_date": "2026-08-05", "jurisdiction": "美国新泽西州一般工业", "regulated_subject": "私营工厂雇主选择一个岗位和一个辅助设施包"}`
- C1 不适用原因：C1全部岗位使用非腐蚀性物料且经工艺隔离消除眼身接触路径，不进入29 CFR 1910.151(c)的腐蚀性材料暴露前提，因此不加冲洗设施依赖。
- 题内行动映射：a01-a03依次为岗位A-C，a04-a06依次为无设施、快速冲洗设施、仅护目镜面屏；唯一Patch要求C2选择a01时同步选择a05。
- source 精确替换：
  - 旧：`开放式腐蚀性酸液转移岗位会使员工眼睛或身体存在飞溅接触可能，贡献118点；全封闭且无合理暴露可能的酸液系统岗位贡献105点；无腐蚀性材料的干燥包装岗位贡献96点。`
  - 新：`三个岗位A、B、C的贡献依次为118、105和96点；各岗位的物料、工艺隔离和眼睛或身体接触路径由当班工艺单记录。`
  - 旧：`方案须遵守决策日有效的美国联邦工作场所应急冲洗规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r104_a01": "开放式腐蚀性酸液转移岗位", "swor_r104_a02": "全封闭且无合理暴露可能的酸液系统岗位", "swor_r104_a03": "无腐蚀性材料的干燥包装岗位", "swor_r104_a04": "不配置快速冲洗辅助设施", "swor_r104_a05": "配置工作区内可立即快速冲洗眼睛和身体的设施", "swor_r104_a06": "仅提供护目镜和面屏"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}, {"publisher": "U.S. Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "已复核V1.4.4所存29 CFR 1910.151(c)关于有害腐蚀性材料和工作区立即快速冲洗设施的官方quote；Gold保持。"}`
- 复核说明：将岗位物料与暴露路径移至case层；辅助包动作和数值保留；将6个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R105

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L7。
- 保持：保留四个运营方案贡献、三个虫害/隔离服务及成本、两组选一和最大化目标；保留开放线与巡逻犬的两条服务依赖。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "A为金属紧固件开放包装；B为全封闭工业液体灌装；C为非食品干货仓；D为非食品工业区的厂区安保犬巡逻。四个方案的产品、接触面和包装均不用于人用或动物食品，工厂不制造、加工、包装或持有人用或动物食品。", "decision_date": "2026-08-05", "jurisdiction": "美国", "regulated_subject": "非食品工业品制造商选择一条运营线和一项辅助服务"}`
- C2：`{"boundary_facts": "A为开放式即食食品包装线；B为害虫不能进入的全封闭食品灌装线；C为不接触食品、接触面或包装的干货仓储线；D在食品加工区使用巡逻犬。", "decision_date": "2026-08-05", "jurisdiction": "美国", "regulated_subject": "人用食品制造商选择一条运营线和一项虫害辅助服务"}`
- C1 不适用原因：C1四个方案只涉及非食品工业品，产品、接触面和包装均不用于人或动物食品，不存在Part 117或Part 507的food plant作用对象，故不加入两条食品虫害控制依赖。
- 题内行动映射：a01-a04依次为A开放包装、B封闭灌装、C干货仓、D巡逻犬运营方案；a05-a07依次为不增加服务、虫害排除、隔离巡逻犬；C2两条Patch分别连接a01到a06、a04到a07。
- source 精确替换：
  - 旧：`美国食品生产线与虫害辅助服务选择。`
  - 新：`生产线与虫害辅助服务选择。`
  - 旧：`澄湾食品厂须选择一条运营线和一个辅助服务。开放式即食食品包装线贡献126点；全封闭食品灌装线贡献112点；非食品干货仓储线贡献98点；在食品加工区内使用巡逻犬的方案贡献121点。`
  - 新：`澄湾工厂须选择一条运营线和一个辅助服务。开放式包装线贡献126点；全封闭灌装线贡献112点；干货仓储线贡献98点；使用巡逻犬的方案贡献121点；各线的产品类别、接触面和巡逻区域由工厂登记资料标明。`
  - 旧：`方案须遵守决策日有效的美国联邦食品厂卫生规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r105_a01": "选择A开放包装运营方案", "swor_r105_a02": "选择B封闭灌装运营方案", "swor_r105_a03": "选择C干货仓运营方案", "swor_r105_a04": "选择D巡逻犬运营方案", "swor_r105_a05": "不增加辅助服务", "swor_r105_a06": "实施虫害排除辅助服务", "swor_r105_a07": "将巡逻犬限制在隔离区域的辅助服务"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-21.xml"}], "notes": "已复核§117.35虫害排除、污染防护和巡逻犬限制，并额外核对§507.19(e)同样约束动物食品厂；因此弃用原动物食品C1，改为同一美国辖区内完全不涉及人用或动物食品的工业品边界，Gold保持。"}`
- 复核说明：原C1动物食品厂仍受21 CFR 507.19(e)虫害排除义务，无法RETAIN；改为非食品工业品工厂，并同步七个公开action meaning与Base/Patched IR变量meaning；删除题面中的顺序映射元说明。

### SWOR-R106

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四个计划的平均与峰值硫、贡献、四个控制包及成本、两组选一和最大化目标；保留平均值与峰值的两条控制依赖。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "四个候选计划的全部产品均为柴油，并在独立于汽油设施的生产、储存和出口系统中运行。", "decision_date": "2026-08-05", "jurisdiction": "美国路易斯安那州燃料制造", "regulated_subject": "仅生产柴油的炼厂选择一个生产期计划和一个硫控制包"}`
- C2：`{"boundary_facts": "四个候选计划的全部产品均为汽油并在制造设施出口交付；批次没有铁路或卡车进口、下游氧化物调和或Subpart G登记路径。", "decision_date": "2026-08-05", "jurisdiction": "美国路易斯安那州汽油制造", "regulated_subject": "国内汽油制造商选择一个生产期计划和一个硫控制包"}`
- C1 不适用原因：C1仅生产并隔离柴油，不制造、进口、调和或指定汽油，40 CFR Part 1090的题列汽油平均与峰值硫标准不对这些计划生成控制包依赖。
- 题内行动映射：a01-a04依次为计划A-D，a05-a08依次为不处理、平均值调和、峰值返工、联合处理；Patch按计划记录的平均/峰值把a01/a04连接到平均控制，把a02/a04连接到峰值控制。
- source 精确替换：
  - 旧：`美国汽油生产计划与硫控制包选择。`
  - 新：`燃料生产计划与硫控制包选择。`
  - 旧：`路易斯安那州蓝湾炼厂作为汽油制造商须选择一个完整合规期生产计划和一个硫控制包。`
  - 新：`路易斯安那州蓝湾炼厂须选择一个完整生产期计划和一个硫控制包。`
  - 旧：`所有汽油均在制造设施出口交付，不适用铁路或卡车进口替代规则、下游氧化物调和或Subpart G例外。`
  - 新：`所有产品均在制造设施出口交付；燃料类别、进口方式、下游调和和其他运营路径由批次台账记录。`
  - 旧：`方案须遵守决策日有效的美国联邦汽油硫标准。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r106_a01": "生产平均硫12 ppm且设施出口峰值70 ppm的汽油计划A", "swor_r106_a02": "生产平均硫9 ppm且设施出口峰值85 ppm的汽油计划B", "swor_r106_a03": "生产平均硫8 ppm且设施出口峰值75 ppm的汽油计划C", "swor_r106_a04": "生产平均硫13 ppm且设施出口峰值90 ppm的汽油计划D", "swor_r106_a05": "不增加硫控制处理", "swor_r106_a06": "采用平均值调和包使平均硫降至10 ppm", "swor_r106_a07": "采用峰值返工包使出口峰值降至80 ppm", "swor_r106_a08": "采用联合调和返工包使平均值与峰值分别降至10和80 ppm"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "已复核V1.4.4所存40 CFR汽油硫平均值、每加仑上限及制造商/进口分支的官方quote；两条Gold依赖保持。"}`
- 复核说明：把汽油产品身份和运营路径移至case层，并删除合规措辞与遵规提示；数值计划仍为相同业务对象；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R107

- 结论：`FIX`；问题类型：L1, L2, L4, L7。
- 保持：保留四个编组贡献、唯一普通无标牌缓冲棚车、插入成本、冻结顺序和最大化目标；保留A/B两条缓冲匹配依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "题列罐车已排空、清洗和吹扫，没有危险品标牌或危险材料残留；B的中间车辆为普通无标牌棚车，C为普通无标牌平车，D为普通无标牌棚车。", "decision_date": "2026-08-04", "jurisdiction": "美国铁路运输", "regulated_subject": "铁路公司安排一辆题列罐车相对机车的位置"}`
- C2：`{"boundary_facts": "A中题列罐车紧邻机车；B的中间车辆为仍悬挂危险品标牌的罐车；C为普通无标牌平车，D为普通无标牌棚车；各方案另一端均不靠近有人值守的守车。", "decision_date": "2026-08-04", "jurisdiction": "美国危险材料铁路运输", "regulated_subject": "铁路公司安排一辆仍含危险材料残留的罐车相对机车的位置"}`
- C1 不适用原因：C1题列罐车已清洗吹扫、无标牌且无危险材料残留，不是49 CFR 174.85所列危险材料车辆，故A/B不生成普通缓冲车匹配依赖。
- 题内行动映射：a01-a04依次为编组A-D，a05/a06是把唯一普通无标牌缓冲棚车插入A或B；两条Patch分别要求选择a01/a02时匹配a05/a06。
- source 精确替换：
  - 旧：`美国危险物残余罐车编组匹配。`
  - 新：`铁路罐车编组匹配。`
  - 旧：`西岭铁路公司须为一辆仍含危险物残余物的铁路罐车选择一个编组方案。`
  - 新：`西岭铁路公司须为一辆题列铁路罐车选择一个编组方案；罐车的清洗、吹扫、标牌和残余物状态由编组检验单记录。`
  - 旧：`A让该残余物罐车紧邻机车，运输贡献120点；B在机车与该车之间已有另一辆仍悬挂危险品标牌的罐车，贡献125点；C在两者之间已有一辆普通无标牌平车，贡献110点；D在两者之间已有一辆普通无标牌棚车，贡献108点。`
  - 新：`A让题列罐车紧邻机车，运输贡献120点；B至D均在机车与题列罐车之间已有一辆题列中间车辆，贡献依次为125、110和108点；中间车辆的车型和标牌状态由调度记录标明。`
  - 旧：`编组必须遵守决策日有效的美国联邦危险物残余罐车列车位置规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r107_a01": "采用题列罐车紧邻机车的编组A", "swor_r107_a02": "采用机车与题列罐车之间已有一辆题列中间车辆的编组B", "swor_r107_a03": "采用机车与题列罐车之间已有一辆题列中间车辆的编组C", "swor_r107_a04": "采用机车与题列罐车之间已有一辆题列中间车辆的编组D"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Pipeline and Hazardous Materials Safety Administration / Electronic Code of Federal Regulations", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-49.xml?section=174.85"}], "notes": "已复核V1.4.4所存49 CFR 174.85关于残余物罐车、机车间隔、普通无标牌非罐车及已有有标牌罐车不充当缓冲的官方quote；Gold保持。"}`
- 复核说明：将题列罐车残余物状态和B的中间车辆标牌移至case层，并泛化四个编组meaning；缓冲车能力映射保留。

### SWOR-R108

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四名人员的培训记录与贡献、四种模式与成本、乙的隔离区匹配、两组选一和最大化目标；保留繁忙区学员与未培训人员的两条排除约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "四名候选人员的任务均为纸面或模拟器练习；叉车未通电、未移动，任何员工都不控制实体动力工业车辆。", "decision_date": "2026-08-05", "jurisdiction": "美国印第安纳州一般工业", "regulated_subject": "雇主把人员安排到课堂或非操作性模拟器训练任务"}`
- C2：`{"boundary_facts": "甲完成本车型与场所培训及操作评估；乙和丙仅完成课堂阶段，分别位于隔离训练区和无法封闭的人车混行区；丁未参加培训且未进入学员训练程序。", "decision_date": "2026-08-05", "jurisdiction": "美国印第安纳州一般工业", "regulated_subject": "雇主选择一名人员实际操作动力工业车辆并匹配作业或训练模式"}`
- C1 不适用原因：C1仅进行纸面和非操作性模拟器练习，没有员工操作或训练于实体动力工业车辆，29 CFR 1910.178的操作员训练限制不对人员选择生成排除。
- 题内行动映射：a01-a04依次为甲乙丙丁，a05-a08依次为独立驾驶、隔离区监督、人车混行区监督、旁观；C2两条Patch排除丙与任一实际操作模式、丁与任一实际操作模式，source的乙—隔离区匹配作为基础约束保留。
- source 精确替换：
  - 旧：`印第安纳州桦港仓库须选择一名人员和一个模式执行本班叉车任务。`
  - 新：`印第安纳州桦港仓库须选择一名人员和一个训练或作业模式完成本班任务。`
  - 旧：`甲已完成适用于本车型与工作场所的培训和操作评估，贡献62点；乙只完成课堂阶段，拟在没有其他员工进入的隔离训练区继续实操，贡献68点；丙也只完成课堂阶段，但拟在人车混行且无法封闭的繁忙装卸区实操，贡献78点；丁未参加培训且不按学员训练程序工作，贡献70点。`
  - 新：`甲已完成针对题列设备与场所的培训和操作评估，贡献62点；乙只完成课堂阶段并分配到没有其他员工进入的隔离训练区，贡献68点；丙也只完成课堂阶段并分配到人车混行且无法封闭的繁忙装卸区，贡献78点；丁未参加培训且不按学员训练程序工作，贡献70点。`
  - 旧：`本题选择人员即表示该人员将实际操作叉车，因此旁观模式不与任何人员匹配，且乙只能匹配隔离区直接监督。`
  - 新：`是否操作实体叉车由当班任务单标明；旁观模式不与任何人员匹配，且乙只能匹配隔离区直接监督。`
  - 旧：`安排须遵守决策日有效的美国联邦动力工业车辆规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r108_a01": "指派已完成所需培训与工作场所操作评估的操作员甲", "swor_r108_a02": "指派仅完成课堂阶段、将在隔离训练区实操的学员乙", "swor_r108_a03": "指派仅完成课堂阶段、拟在人车混行装卸区实操的学员丙", "swor_r108_a04": "指派未参加培训且不按学员训练程序工作的员工丁", "swor_r108_a05": "安排独立驾驶叉车作业", "swor_r108_a06": "由合格培训员在隔离训练区直接监督", "swor_r108_a07": "由合格培训员在人车混行装卸区直接监督", "swor_r108_a08": "仅旁观培训且不操作叉车"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Occupational Safety and Health Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-29.xml"}], "notes": "已复核V1.4.4所存29 CFR 1910.178关于培训完成、直接监督和训练不得危及学员或他人的官方quote；Gold保持。"}`
- 复核说明：将实体叉车操作事实移至case层；人员、训练记录、模式和顺序型meaning保持；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R109

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留四个布局的火灾类别、距离、效用、四个调整包及成本、设备状态、两组选一和最大化目标；保留A布局的移动灭火器依赖。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "书面应急行动计划规定所有普通员工立即全部撤离；题列灭火器仅供训练有素的消防队使用或作为自动保护设备，普通员工没有操作权限。", "decision_date": "2026-08-05", "jurisdiction": "美国密歇根州一般工业", "regulated_subject": "工厂雇主选择一个室内应急布局和设备调整包"}`
- C2：`{"boundary_facts": "普通员工可使用题列灭火器；应急行动计划没有全员仅撤离安排，也没有把操作权限限定给少数指定人员；A和B为易燃液体危险区，C为普通可燃物区，D加工可燃金属且金属粉末、薄片或刨屑每月产生一次。", "decision_date": "2026-08-05", "jurisdiction": "美国密歇根州一般工业", "regulated_subject": "工厂雇主选择一个供普通员工使用的室内灭火器布局和设备调整包"}`
- C1 不适用原因：C1书面计划要求普通员工全部撤离且不授权其使用灭火器，满足MIOSHA仅撤离政策分支，故不加入普通员工行走距离约束。
- 题内行动映射：a01-a04依次为布局A-D，a05-a08依次为不调整、把A灭火器移至50英尺、为C增设A类站、为D增设D类站；唯一Patch要求C2选择a01时同步选择a06。
- source 精确替换：
  - 旧：`密歇根州松汀工厂须选择一个布局和一个设备调整包。`
  - 新：`松汀工厂须选择一个布局和一个设备调整包。`
  - 旧：`最近适用于易燃液体危险区的灭火器`
  - 新：`最近经设备标牌列为易燃液体用的灭火器`
  - 旧：`把A的适用于易燃液体危险区的灭火器移至50英尺处`
  - 新：`把A的易燃液体用灭火器移至50英尺处`
  - 旧：`灭火器供员工使用，工厂没有仅疏散政策或指定少数员工使用的豁免；所有设备均合格、可见、可达且维护有效。`
  - 新：`各布局的灭火器使用主体和应急行动计划由工厂书面记录；所有设备均合格、可见、可达且维护有效。`
  - 旧：`配置须遵守决策日有效的适用于密歇根州一般工业场所的灭火器规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r109_a01": "采用最近灭火器距易燃液体危险区65英尺的布局A", "swor_r109_a02": "采用最近灭火器距易燃液体危险区48英尺的布局B", "swor_r109_a03": "采用最近灭火器距普通可燃物区70英尺的布局C", "swor_r109_a04": "采用可燃金属屑仅每月产生一次且最近D类灭火剂70英尺的布局D", "swor_r109_a05": "不调整灭火设备点位", "swor_r109_a06": "移动Class B灭火器使行走距离降至50英尺", "swor_r109_a07": "增设普通可燃物区灭火器站", "swor_r109_a08": "增设可燃金属区灭火剂站"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Michigan Department of Labor and Economic Opportunity / MIOSHA", "url": "https://www.michigan.gov/leo/-/media/Project/Websites/leo/Documents/MIOSHA/Standards/General_Industry/GI_08/GI_08__01-10-2013.pdf?hash=199407A8BA5683EFB465F8F3E43A4A51&rev=d1d3f3262abd4c6e8c0ea1f07e5869be"}], "notes": "已复核V1.4.4所存MIOSHA便携灭火器标准关于员工使用、仅撤离政策及Class B 50英尺距离的官方quote；Gold保持。"}`
- 复核说明：将普通员工使用政策移至case层并删除遵规提示；布局距离和调整能力不变；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R110

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留180公里几何、边界池、十个不可拆分多站点项目、价值、恰选四项和最大化目标；保留东西向六个区段覆盖约束。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "走廊为封闭私人工业道路，仅供获准进入园区的车辆使用；欧盟TEN-T道路登记未列入该走廊，边界池和新池均只向园区车辆开放。", "decision_date": "2026-08-04", "jurisdiction": "欧盟境内私人工业道路", "regulated_subject": "工业园区走廊管理方选择四个不可拆分的多站点充电项目"}`
- C2：`{"boundary_facts": "走廊从km0延伸至km180，两个方向在km0和km180各有一座620 kW且含两个180 kW充电点的公共边界池；每座新池仅服务题列方向，在2027年12月31日前建成并同样提供620 kW和两个180 kW充电点。", "decision_date": "2026-08-04", "jurisdiction": "欧盟TEN-T核心公路网络", "regulated_subject": "走廊管理方为2027年轻型车辆公共充电网络选择四个不可拆分的多站点项目"}`
- C1 不适用原因：C1为未列入TEN-T的封闭私人工业道路且充电池不向公众开放，不进入Regulation (EU) 2023/1804的TEN-T公共轻型车辆走廊部署域，故不加入六个方向区段覆盖约束。
- 题内行动映射：a01-a10依次为项目A-J；六条Patch按项目站点几何分别覆盖东向左中右和西向左中右区段，项目仍不可拆分。
- source 精确替换：
  - 旧：`欧盟公路充电走廊组合项目。`
  - 新：`公路充电走廊组合项目。`
  - 旧：`在一段180公里的TEN-T核心公路上`
  - 新：`在一段180公里的公路走廊上`
  - 旧：`每座新池只服务题面标明的方向，将在2027年12月31日前建成并公开服务轻型电动车，提供620 kW总功率和两个180 kW充电点。`
  - 新：`每座新池只服务题面标明的方向，将在2027年12月31日前建成，提供620 kW总功率和两个180 kW充电点；走廊网络类别和充电池开放对象由项目登记资料标明。`
  - 旧：`部署须遵守决策日有效的欧盟Regulation (EU) 2023/1804关于TEN-T核心公路轻型车辆公共充电池的要求。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r110_a01": "实施A项目：东向km45与西向km135各建一座充电池", "swor_r110_a02": "实施B项目：东向km90建设一座充电池", "swor_r110_a03": "实施C项目：东向km135与西向km45各建一座充电池", "swor_r110_a04": "实施D项目：西向km90建设一座充电池", "swor_r110_a05": "实施E项目：东向km55与西向km40各建一座充电池", "swor_r110_a06": "实施F项目：东向km90与西向km140各建一座充电池", "swor_r110_a07": "实施G项目：东向km120建设一座充电池", "swor_r110_a08": "实施H项目：东向km40与西向km95各建一座充电池", "swor_r110_a09": "实施I项目：西向km120建设一座充电池", "swor_r110_a10": "实施J项目：东向km140与西向km55各建一座充电池"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "European Union / EUR-Lex", "url": "https://eur-lex.europa.eu/eli/reg/2023/1804/2026-01-08/eng"}], "notes": "已复核V1.4.4所存AFIR关于TEN-T核心公路每个行驶方向60公里、2027年600 kW及两个150 kW点的官方quote；Gold保持。"}`
- 复核说明：把TEN-T身份与公共开放属性移至case层；时间、功率、方向和项目几何保留；将10个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R111

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留同药品两个获批未过期批次、四个配送顺序及贡献、四个理由程序及成本、B的基础匹配、两组选一和最大化目标；保留C/D两条排除约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "1月旧批次和6月新批次均为PET药品，均已获批且未过期；两个批次的生产和批记录均按Part 212制度运行。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦药品制造", "regulated_subject": "按21 CFR Part 212生产PET药品的制造商选择两个获批PET药品批次的配送顺序"}`
- C2：`{"boundary_facts": "1月旧批次和6月新批次均已获批、未过期且可追溯；B的稳定性复核是有书面起止记录的短期事件，复核结束后恢复旧批次优先。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦成品药制造", "regulated_subject": "制造非PET、非医用气体成品药的制造商选择两个获批批次的配送顺序"}`
- C1 不适用原因：C1为Part 212 PET药品批次，不属于21 CFR 211.150成品药配送程序的题列产品域，因此不加入长期新批优先和旧批可用时仅发新批的排除约束。
- 题内行动映射：a01-a04依次为顺序A-D，a05-a08依次为无理由、书面限时偏离、永久销售偏好、未记录口头说明；Patch排除a03和a04，source的B—书面限时程序匹配保留。
- source 精确替换：
  - 旧：`新泽西州澄川制药厂有同一供人使用、既非正电子发射断层扫描药品也非医用气体的成品药之1月批准旧批次和6月批准新批次，二者均未过期。`
  - 新：`澄川制药厂有同一供人使用药品的1月批准旧批次和6月批准新批次，二者均未过期；产品类别和生产制度由批次登记资料标明。`
  - 旧：`安排须遵守决策日有效的美国联邦成品药配送程序规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r111_a01": "先配送1月批准的旧批次、再配送6月批准的新批次", "swor_r111_a02": "因旧批次临时稳定性复核先配送新批次、复核后立即恢复旧批次优先", "swor_r111_a03": "为提高毛利长期先配送新批次", "swor_r111_a04": "旧批次仍可用但本轮只配送新批次", "swor_r111_a05": "不建立偏离理由", "swor_r111_a06": "书面批准并记录仅持续至稳定性复核结束的偏离", "swor_r111_a07": "批准永久销售偏好", "swor_r111_a08": "仅作未记录的口头说明"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-21.xml"}], "notes": "已复核V1.4.4所存21 CFR 211.1、211.150和Part 212边界的官方quote；两条Gold排除保持。"}`
- 复核说明：把非PET/非医用气体产品类别移至case层；批次、顺序和程序动作不变；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R112

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L6, L7。
- 保持：保留四个包的产蛋后时点、温度、净效用、其他运输包装质量相同、四选一和最大化目标；把时点明确为零售场所收货并立即冷藏的时点。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "在任何候选收货动作之前，全批鸡蛋已完成经验证的专门处理；处理记录显示全部viable Salmonella被灭活并覆盖本批每枚鸡蛋。四个包均表示零售场所在所列产蛋后时点收货并立即置于所列环境温度。", "decision_date": "2026-08-05", "jurisdiction": "美国带壳鸡蛋零售分销", "regulated_subject": "直接向消费者提供食品的零售场所为已完成沙门氏菌灭活处理的带壳鸡蛋选择收货与储存包"}`
- C2：`{"boundary_facts": "批次台账没有灭活处理记录；四个包均表示零售场所在产蛋后24、40、40和60小时收货并立即置于50°F、50°F、45°F和42°F环境。", "decision_date": "2026-08-05", "jurisdiction": "美国带壳鸡蛋零售分销", "regulated_subject": "直接向消费者提供食品的零售场所为未做沙门氏菌灭活处理的带壳鸡蛋选择收货与储存包"}`
- C1 不适用原因：C1全批在零售场所收货前已经专门处理以灭活全部viable Salmonella，21 CFR 115.50(c)明确豁免§115.50(b)的及时冷藏和不高于45°F要求，故RETAIN Base。
- 题内行动映射：a01-a04依次为零售场所在产蛋后24、40、40、60小时收货并立即置于50°F、50°F、45°F、42°F的完整包；C2两条Patch分别排除a01和a02。
- source 精确替换：
  - 旧：`一家美国分销商要为一批未经专门工艺灭活全部活沙门氏菌的带壳鸡蛋选择一个完整储存包：`
  - 新：`一家美国零售场所要为一批带壳鸡蛋选择一个完整收货与储存包；该批鸡蛋的处理工艺和验证记录由批次台账标明：`
  - 旧：`产蛋24小时后置于50°F环境，库存周转净效用18点；产蛋40小时后置于50°F，24点；产蛋40小时后置于45°F，20点；产蛋60小时后置于42°F，17点。`
  - 新：`产蛋24小时后由零售场所收货并立即置于50°F环境，库存周转净效用18点；产蛋40小时后收货并立即置于50°F，24点；产蛋40小时后收货并立即置于45°F，20点；产蛋60小时后收货并立即置于42°F，17点。`
  - 旧：`方案须符合决策日有效的美国联邦带壳鸡蛋温控规则。`
  - 新：``
- output_schema meaning 修改：`{"swor_r112_a01": "产蛋24小时后由零售场所收货并立即置于50°F环境", "swor_r112_a02": "产蛋40小时后由零售场所收货并立即置于50°F环境", "swor_r112_a03": "产蛋40小时后由零售场所收货并立即置于45°F环境", "swor_r112_a04": "产蛋60小时后由零售场所收货并立即置于42°F环境"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`{"patch_elements": [{"after": {"coefficients": {"store24h50f": 1}, "meaning": "排除零售场所在产蛋后24小时收货并立即置于50°F环境的方案", "name": "exclude_24h_50f", "rhs": 0, "sense": "="}, "name": "exclude_24h_50f", "op": "add_constraint"}, {"after": {"coefficients": {"store40h50f": 1}, "meaning": "排除零售场所在产蛋后40小时收货并立即置于50°F环境的方案", "name": "exclude_40h_50f", "rhs": 0, "sense": "="}, "name": "exclude_40h_50f", "op": "add_constraint"}], "reason": "原Patch阈值与§115.50零售收货规则不符；真实规则从零售场所收货时即要求不高于45°F，因此需删除旧约束并分别排除两个50°F包。", "remove_patch_names": ["exclude_post36h_above45f"]}`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Food and Drug Administration / eCFR", "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-115/section-115.50"}], "notes": "删除与§115.50不符的旧阈值Patch，改用§115.50(a)-(c)真实零售分支：C2的50°F收货包a01/a02均排除，45°F与42°F包合法；C1由(c)的处理例外RETAIN。", "official_evidence_override": [{"information_responsibility": "§115.50定义retail establishment，并要求除(c)例外外的全部零售分销带壳蛋在零售场所收货时及时冷藏且环境温度不高于45°F。", "node_id": "E1", "omission_effect": "缺少E1时，无法确认C2直接面向消费者的零售场所属于规则主体，也无法排除收货后立即置于50°F的a01和a02。", "publisher": "U.S. Food and Drug Administration / eCFR", "quote": "(a) For purposes of this section a \"retail establishment\" is an operation that stores, prepares, packages, serves, vends, or otherwise provides food for human consumption directly to consumers. (b) Except as provided in paragraph (c) of this section, all shell eggs, whether in intrastate or interstate commerce, held for retail distribution: (1) Shall promptly be placed under refrigeration as specified in paragraph (b)(2) of this section upon receipt at a retail establishment, except that, when short delays are unavoidable, the eggs shall be placed under refrigeration, as soon as reasonably possible; and (2) Shall be stored and displayed under refrigeration at an ambient temperature not greater than 7.2 °C (45 °F) while held at a retail establishment.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["exclude_24h_50f", "exclude_40h_50f"], "supported_patch_slots": ["exclude_24h_50f", "exclude_40h_50f"], "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-115/section-115.50"}, {"information_responsibility": "§115.50(c)豁免已经专门处理以灭活全部viable Salmonella的带壳蛋。", "node_id": "E2", "omission_effect": "缺少E2时，无法确认C1已灭活批次不受(b)的零售冷藏要求约束并RETAIN Base。", "publisher": "U.S. Food and Drug Administration / eCFR", "quote": "(c) Shell eggs that have been specifically processed to destroy all viable Salmonella shall be exempt from the requirements of paragraph (b) of this section.", "role": "exception", "source_node_id": "E2", "support_target_type": "exception_boundary", "support_targets": ["non_patch_model_boundary"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-115/section-115.50"}]}`
- 复核说明：改用21 CFR 115.50零售收货分支，C1由(c)处理例外RETAIN；C2排除a01/a02，patched唯一最优为a03，目标20库存周转净效用点。

### SWOR-R113

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留两小时窗口、四个包的火焰连续性、可见排放分钟与净效用、四选一和最大化目标；保留超过5分钟与火焰中断两条排除约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "设施许可和运行记录把该火炬标为自愿安全备用设备；火炬未用于满足NSPS排放限值，许可未引用40 CFR 60.18或纳入该条的分部。", "decision_date": "2026-08-05", "jurisdiction": "美国固定源空气污染管理", "regulated_subject": "工业设施操作一座用于内部安全备用和可靠性测试的火炬"}`
- C2：`{"boundary_facts": "运行日志把该窗口标为正常运行；期间没有启动、停机、故障或紧急事件，设施许可未列出其他分部替代运行标准。", "decision_date": "2026-08-05", "jurisdiction": "美国固定源空气污染管理", "regulated_subject": "工业设施在正常连续两小时窗口操作一座纳入40 CFR 60.18控制方案的火炬"}`
- C1 不适用原因：C1火炬仅为自愿安全备用且未被任何许可、NSPS限值或纳入分部用于合规，40 CFR 60.18不支配这组内部可靠性包，故不加入两条排除约束。
- 题内行动映射：a01-a04按source首次出现顺序对应8分钟连续火焰、5分钟连续火焰、0分钟但火焰中断、2分钟连续火焰四个包；Patch排除a01与a03。
- source 精确替换：
  - 旧：`一座受联邦一般火炬要求约束的工业设施在正常运行的连续两小时窗口中选择一个包：`
  - 新：`一座工业设施在连续两小时窗口中选择一个火炬运行包：`
  - 旧：`不存在另行适用的启动、停机、故障或其他分部替代标准。`
  - 新：`该窗口的运行状态、许可条件和设施采用的排放控制标准由运行记录标明。`
  - 旧：`方案须符合决策日有效的美国联邦火炬运行规则。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r113_a01": "保持火焰但出现8分钟可见排放", "swor_r113_a02": "保持火焰且可见排放5分钟", "swor_r113_a03": "出现火焰中断但无可见排放", "swor_r113_a04": "保持火焰且可见排放2分钟"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "已复核V1.4.4所存40 CFR 60.18适用边界、连续火焰和两小时内可见排放不超过5分钟的官方quote；Gold保持。"}`
- 复核说明：把火炬控制身份、运行状态和替代标准登记移至case层；包的观测数据保持；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R114

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留陆上非运输设施、地上固定罐、最大单罐100单位、10单位降水自由高、四个设计容量及净效用、四选一和最大化目标；保留低于110单位排除约束。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "每个容量单位为10美制加仑；最大单罐1000加仑，全部地上罐合计1300加仑，完全埋地罐为0加仑；场址坡面和排水沟全部汇入没有外排口的场内衬里集液池。", "decision_date": "2026-08-05", "jurisdiction": "美国陆上储油设施", "regulated_subject": "陆上非运输储油设施选择内部围堤设计"}`
- C2：`{"boundary_facts": "每个容量单位为20美制加仑；最大单罐2000加仑，全部地上罐合计2400加仑，完全埋地罐为0加仑；场址坡面与连续排水沟连接至毗邻的美国可航水域岸线；暴雨设计另计10个容量单位自由高。", "decision_date": "2026-08-05", "jurisdiction": "美国陆上散装储油设施", "regulated_subject": "陆上非运输散装储油设施选择最大单罐的围堤设计"}`
- C1 不适用原因：C1地上总容量1300加仑、埋地容量0且场内集液池无外排路径，不满足40 CFR Part 112的容量与合理排油前提，因此不加入最大单罐加降水自由高约束。
- 题内行动映射：a01-a04按source首次出现顺序对应90、100、110、120单位围堤设计；唯一Patch排除C2的a01和a02。
- source 精确替换：
  - 旧：`一座非运输相关的陆上散装储油设施选择一个围堤容量；按地形与距离，排油可合理到达美国可航水域或毗连岸线。`
  - 新：`一座非运输相关的陆上储油设施选择一个围堤容量；设施容量和场址排油路径由工程登记资料标明。`
  - 旧：`全部题列罐体均为地上固定油罐，单个容量单位为20美制加仑，设施不开展农业、污水处理或运输业务。`
  - 新：`全部题列罐体均为地上固定油罐，设施不开展农业、污水处理或运输业务；容量单位的加仑换算及设施总容量由工程登记资料标明。`
  - 旧：`设计须符合决策日有效的美国联邦散装储油罐二次围护规则。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r114_a01": "建设90单位围堤", "swor_r114_a02": "建设100单位围堤", "swor_r114_a03": "建设110单位围堤", "swor_r114_a04": "建设120单位围堤"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Environmental Protection Agency / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-40.xml"}], "notes": "已复核V1.4.4所存40 CFR Part 112容量、合理排油路径、最大单罐与降水自由高官方quote；Gold保持。"}`
- 复核说明：以具体加仑容量、罐型和排水路径替代法规门槛结论；容量轴全部在case层固定；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R115

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四个10人组合的诊断人数、强化康复事实、普通术后去适应边界、组合价值、其他收治条件、四选一和最大化目标；保留A/D两条排除约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "该队列仅用于SNF内部质量审查；机构档案和账单均使用SNF分类与支付代码，本次审查不提交IRF分类或支付申报。", "decision_date": "2026-08-05", "jurisdiction": "美国Medicare熟练护理机构支付", "regulated_subject": "作为Medicare SNF登记并按SNF支付制度运营的机构选择10人内部质量审查队列"}`
- C2：`{"boundary_facts": "机构档案显示其不是新设IRF且审查期内没有新增床位，审查期始于2026年；题列强化康复诊断、普通术后去适应记录及其他收治条件均按患者档案固定。", "decision_date": "2026-08-05", "jurisdiction": "美国Medicare住院康复机构支付分类", "regulated_subject": "既有IRF为连续12个月审查期选择一个10人患者组合"}`
- C1 不适用原因：C1作为SNF登记、分类和付费且队列仅供内部质量审查，不请求IRF分类或支付，42 CFR 412.29的IRF 60%分类标准不对四个队列生成排除。
- 题内行动映射：a01-a04按source首次出现顺序对应患者组合A-D；Gold两条Patch排除强化康复病症比例为5/10的A和4/10的D。
- source 精确替换：
  - 旧：`密苏里州清港康复医院是既有Medicare住院康复机构，须为最近连续且适当的12个月审查期选择一个10人患者组合用于IRF分类规划。`
  - 新：`清港康复医疗机构须为一个连续12个月的内部审查期选择一个10人患者组合；机构类别、项目登记和审查用途由机构档案标明。`
  - 旧：`机构不是新IRF、没有新增床位，审查期开始于2026年。`
  - 新：`机构的新设状态、新增床位记录和审查期起始日由机构档案标明。`
  - 旧：`选择须符合决策日有效的美国联邦IRF支付分类标准。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r115_a01": "采用10人组合A：5名卒中、5名普通术后去适应患者", "swor_r115_a02": "采用10人组合B：6名脊髓损伤、4名普通术后去适应患者", "swor_r115_a03": "采用10人组合C：7名股骨髋部骨折、3名普通术后去适应患者", "swor_r115_a04": "采用10人组合D：4名烧伤、6名普通术后去适应患者"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-42.xml?part=412"}, {"publisher": "U.S. Centers for Medicare & Medicaid Services / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-42.xml?part=412"}], "notes": "已复核V1.4.4所存42 CFR 412.29连续12个月、60%阈值、列明病症及新IRF/新增床位分支的官方quote；Gold保持。"}`
- 复核说明：把IRF/SNF项目身份、审查用途和机构时间状态移至case层；患者组合本身保留；将4个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R116

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L7。
- 保持：保留八个组件、audio-only/音视频媒介、监督参与方式、共享平台与岗位、价值、启用五个和最大化目标；保留四条服务—资源依赖。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "全部就诊由患者自费，服务台账未使用G2025、RHC或FQHC账单代码，Cedar和Delta记录为诊所内部协作服务。", "decision_date": "2027-12-15", "jurisdiction": "美国私人医疗服务", "regulated_subject": "未在Medicare登记或认证为RHC/FQHC的私人乡村诊所选择就诊批次和内部技术或人员组件"}`
- C2：`{"boundary_facts": "Atlas为以G2025登记的非行为健康纯音频就诊；Birch为居家心理健康音视频就诊且最近六个月没有面诊；Cedar和Delta均以incident-to服务登记，监督者分别仅用实时音频和使用实时音视频参与。", "decision_date": "2027-12-15", "jurisdiction": "美国Medicare RHC项目", "regulated_subject": "Medicare认证的乡村健康诊所选择2027年末就诊批次和共享技术或人员组件"}`
- C1 不适用原因：C1既非Medicare认证或登记的RHC/FQHC且全部为私费内部服务，CMS的G2025、RHC/FQHC心理健康面诊和Medicare直接监督规则不支配这些组件，因此不加入四条资源依赖。
- 题内行动映射：a01-a04依次为Atlas、Birch、Cedar、Delta服务批次，a05/a06为实时音频/音视频平台，a07为Cedar现场监督岗位，a08为Birch同期面诊资源；四条Patch分别连接a01-a05、a02-a06、a03-a07、a04-a06。
- source 精确替换：
  - 旧：`美国RHC远程医疗批次与资源选择。`
  - 新：`美国乡村诊所远程服务批次与资源选择。`
  - 旧：`Medicare认证的Silver Plains Rural Health Clinic从八个组件中启用五个：Atlas非行为健康audio-only G2025就诊批次、Birch居家心理健康音视频就诊批次（最近六个月无面诊）、Cedar incident-to批次（监督者仅通过实时音频参与）、Delta incident-to批次（监督者通过实时音视频参与）、Atlas与Cedar共用的实时音频平台、Birch与Delta共用的实时音视频平台、Cedar现场监督执业者岗位、Birch同期面诊资源。`
  - 新：`Silver Plains乡村诊所从八个组件中启用五个：Atlas非行为健康audio-only就诊批次、Birch居家心理健康音视频就诊批次、Cedar协作服务批次（监督者仅通过实时音频参与）、Delta协作服务批次（监督者通过实时音视频参与）、Atlas与Cedar共用的实时音频平台、Birch与Delta共用的实时音视频平台、Cedar现场监督执业者岗位、Birch同期面诊资源；诊所项目身份、收费类型和最近面诊记录由服务台账标明。`
  - 旧：`方案须遵守决策日有效的Medicare RHC远程服务与直接监督规定。`
  - 新：``
- output_schema meaning 修改：`{"swor_r116_a01": "安排Atlas非行为健康audio-only就诊批次", "swor_r116_a02": "安排Birch居家心理健康音视频就诊批次", "swor_r116_a03": "安排Cedar协作服务批次，监督者仅通过实时音频参与", "swor_r116_a04": "安排Delta协作服务批次，监督者通过实时音视频参与"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Centers for Medicare & Medicaid Services", "url": "https://www.cms.gov/fqhc-rhc-news-announcements"}], "notes": "已于2026-08-26复核CMS官方页面；V1.4.4单节点quote为合成式摘要，本记录以三个原文节点覆盖并分别绑定G2025、心理健康面诊时点和直接监督媒介，Gold模型不变。", "official_evidence_override": [{"information_responsibility": "确认RHC/FQHC非行为健康电信就诊在2027年末仍可使用G2025且包括纯音频服务。", "node_id": "E1", "omission_effect": "缺少E1时，无法把Atlas的2027年末纯音频G2025批次绑定到实时音频平台。", "publisher": "U.S. Centers for Medicare & Medicaid Services", "quote": "Telecommunications Services - non-behavioral health visits furnished via telecommunication technology can continue to be reported with HCPCS code G2025, including services furnished using audio-only communications technology through December 31, 2027.", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["atlas_needs_audio"], "supported_patch_slots": ["atlas_needs_audio"], "url": "https://www.cms.gov/fqhc-rhc-news-announcements"}, {"information_responsibility": "确认RHC/FQHC心理健康远程服务的面诊时间要求推迟到2028年1月1日之后。", "node_id": "E2", "omission_effect": "缺少E2时，无法确定Birch在2027年12月15日没有近六个月面诊时仍沿用音视频批次与平台的时间边界。", "publisher": "U.S. Centers for Medicare & Medicaid Services", "quote": "Telecommunications Services – The requirement that an in-person mental health visit must occur within 6 months before a telehealth mental health service at least every 12 months while a beneficiary receives telecommunications services for diagnosis, evaluation, or treatment of mental health disorders in RHCs and FQHCs will not take effect until after January 1, 2028.", "role": "effective_date", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["birch_needs_av"], "supported_patch_slots": ["birch_needs_av"], "url": "https://www.cms.gov/fqhc-rhc-news-announcements"}, {"information_responsibility": "确认电信方式的直接监督永久要求实时音频与视频互动并排除纯音频。", "node_id": "E3", "omission_effect": "缺少E3时，无法区分Cedar纯音频监督与Delta实时音视频监督所需的现场岗位或音视频平台。", "publisher": "U.S. Centers for Medicare & Medicaid Services", "quote": "Telecommunications Services - permanently adopted a definition of direct supervision that allows the physician or supervising practitioner to provide such supervision through real-time audio and visual interactive telecommunications (excluding audio-only).", "role": "operative_rule", "source_node_id": "E3", "support_target_type": "patch_slot", "support_targets": ["cedar_needs_onsite", "delta_needs_av"], "supported_patch_slots": ["cedar_needs_onsite", "delta_needs_av"], "url": "https://www.cms.gov/fqhc-rhc-news-announcements"}]}`
- 复核说明：把Medicare/RHC身份、G2025/incident-to收费类型和最近面诊事实移至case层；服务媒介与资源能力保留；官方证据拆为三个原文节点。

### SWOR-R117

- 结论：`FIX`；问题类型：L1, L2, L4, L5, L6, L7。
- 保持：保留十一份委内瑞拉原产油品合同、争议解决地、收益、恰选三份和最大化目标；保留前三个论坛排除约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "十一份合同均直接与Petróleos de Venezuela, S.A. (PdVSA)签订并在欧洲或亚洲目的地交付；签约、融资、付款和争议履行均在美国境外，付款使用欧元并经瑞士银行清算，参与人员和代理均为非美国人员。", "decision_date": "2026-08-04", "jurisdiction": "瑞士及合同列示的非美国履行地", "regulated_subject": "在瑞士设立并从苏黎世运营的非美国贷款人选择三份油品合同提供融资"}`
- C2：`{"boundary_facts": "十一份合同均直接与Petróleos de Venezuela, S.A. (PdVSA)签订并选择纽约州法；PdVSA由非中国主体独立控制且未与中国主体共同经营；承运船舶筛查未列出冻结记录；商业合理的美元付款进入指定账户。", "decision_date": "2026-08-04", "jurisdiction": "美国", "regulated_subject": "2022年在特拉华州注册的公司为进口美国的委内瑞拉原产油品合同提供融资"}`
- C1 不适用原因：C1贷款人、合同履行、进口目的地、欧元清算及参与人员均在美国境外且无美国联系，OFAC GL 46C对美国人及美国进口交易的论坛条件不支配这些融资选择。
- 题内行动映射：a01-a11依次对应日内瓦、迪拜、多伦多、伦敦、巴黎、新加坡、纽约、休斯敦、特拉华、芝加哥、波士顿争议解决地合同；三条Patch排除C2的a01-a03。
- source 精确替换：
  - 旧：`2022年在特拉华州注册的Atlantic Meridian Finance要从十一份委内瑞拉原产油品进口合同中选择三份提供融资。`
  - 新：`Atlantic Meridian Finance要从十一份委内瑞拉原产油品合同中选择三份提供融资；公司注册地和每份合同的进口目的地由交易档案标明。`
  - 旧：`十一份合同均由该公司为进口至美国而签订，均约定适用纽约州法；交易对手不在受限制辖区，也不受中国主体控制或共同经营；承运船舶未被冻结；付款均为商业合理的美元付款并按财政部要求进入指定账户。`
  - 新：`十一份合同的准据法、交易对手注册与控制关系、承运船舶状态、付款币种、清算路径和收款账户均由交易档案逐项记录。`
  - 旧：`融资组合须遵守决策日有效的美国财政部OFAC委内瑞拉制裁一般许可证。`
  - 新：``
- output_schema meaning 修改：`{}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`{"corrections": [{"location": "private/applicability_gold.jsonl:C1", "new": {"accepted_equivalents": [{"unit": "万美元", "value": 63.0}, {"unit": "美元", "value": 630000.0}], "canonical_unit": "万美元", "canonical_value": 63.0}, "old": {"accepted_equivalents": [{"unit": "万美元", "value": 63.0}, {"unit": "美元", "value": 63.0}], "canonical_unit": "万美元", "canonical_value": 63.0}}], "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。"}`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of the Treasury, Office of Foreign Assets Control", "url": "https://ofac.treasury.gov/media/935661/download?inline="}], "notes": "把含省略号的E1替换为GL 46C(a)连续完整原文，补齐established U.S. entity、美国进口、PdVSA合同和允许论坛的前提；另存6月10日替代46B的完整生效句。", "official_evidence_override": [{"information_responsibility": "GL 46C授权established U.S. entity为进口美国而开展通常附带且必要的委内瑞拉原产油品交易，并要求与PdVSA等主体的合同适用美国辖区法律且争议解决限于美国、英国、法国或新加坡。", "node_id": "E1", "omission_effect": "缺少E1时，无法把C2的美国实体、美国进口、PdVSA合同和纽约州法事实绑定到三个不允许论坛的排除Patch。", "publisher": "U.S. Department of the Treasury, Office of Foreign Assets Control", "quote": "Except as provided in paragraph (b) of this general license, all transactions prohibited by the Venezuela Sanctions Regulations, 31 CFR part 591 (the VSR), including those involving the Government of Venezuela, Petróleos de Venezuela, S.A. (PdVSA), or any entity in which PdVSA owns, directly or indirectly, a 50 percent or greater interest (collectively, “PdVSA Entities”), that are ordinarily incident and necessary to the lifting, exportation, reexportation, sale, resale, supply, storage, marketing, purchase, delivery, or transportation of Venezuelan-origin oil, including the refining of such oil, or of Venezuelan-origin petrochemical products for importation into the United States, by an established U.S. entity are authorized, provided that: (1) Any contract for such transactions with the Government of Venezuela, PdVSA, or PdVSA Entities shall require that (i) the terms of the contract be construed and interpreted in accordance with the laws of a state or other jurisdiction within the United States and (ii) dispute resolution proceedings relating to the contract occur in the United States, the United Kingdom, France, or Singapore;", "role": "operative_rule_and_applicability", "source_node_id": "E1", "support_target_type": "patch_slot", "support_targets": ["current_forum_ineligible_geneva_forum", "current_forum_ineligible_dubai_forum", "current_forum_ineligible_toronto_forum"], "supported_patch_slots": ["current_forum_ineligible_geneva_forum", "current_forum_ineligible_dubai_forum", "current_forum_ineligible_toronto_forum"], "url": "https://ofac.treasury.gov/media/935661/download?inline="}, {"information_responsibility": "GL 46C自2026年6月10日起取代GL 46B，早于题列2026年8月4日决策日。", "node_id": "E2", "omission_effect": "缺少E2时，无法确认题列决策日应使用46C而非46B的论坛清单。", "publisher": "U.S. Department of the Treasury, Office of Foreign Assets Control", "quote": "Effective June 10, 2026, General License No. 46B, dated March 13, 2026, is replaced and superseded in its entirety by this General License No. 46C.", "role": "effective_date", "source_node_id": "E2", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://ofac.treasury.gov/media/935661/download?inline="}]}`
- 复核说明：把美国实体、进口目的地、PdVSA交易对手、准据法、控制关系、船舶和支付路径移至case层；合同与论坛行动及Gold保持；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。

### SWOR-R118

- 结论：`FIX`；问题类型：L1, L2, L3, L5, L7。
- 保持：保留四个基金、四个汇入日及贡献、银行通道、两组选一和最大化目标；保留小型计划第9日排除约束。
- 主差异轴：`boundary_facts`。
- C1：`{"boundary_facts": "工资与授权记录把全部题列款项标为工会会费，收款人为工会账户；款项不是参与者退休计划缴款、参与者贷款还款或ERISA计划资产。", "decision_date": "2026-08-04", "jurisdiction": "美国工资代扣与工会授权", "regulated_subject": "雇主按独立check-off授权处理工会会费并选择资金配置与汇入日"}`
- C2：`{"boundary_facts": "款项为员工工资代扣的参与者缴款，收款人为计划账户；工资核对记录显示最迟可在原应付工资日后的第6个营业日从公司一般资产分离。", "decision_date": "2026-08-04", "jurisdiction": "美国ERISA员工福利计划", "regulated_subject": "年初有82名参与者的ERISA退休计划处理员工工资代扣缴款"}`
- C1 不适用原因：C1款项为独立check-off授权下的工会会费而非ERISA参与者缴款、贷款还款或计划资产，29 CFR 2510.3-102的小型计划汇入期限不支配该款，因此不排除第9日。
- 题内行动映射：a01-a04依次为成长、平衡、债券、本金保全基金，a05-a08依次为第4、6、7、9营业日；唯一Patch排除C2的a08。
- source 精确替换：
  - 旧：`青石设备公司须处理一次从员工工资中代扣的ERISA退休计划缴款。`
  - 新：`青石设备公司须处理一次从工资结算系统划出的款项；款项性质和收款安排由工资与授权记录标明。`
  - 旧：`该计划在本计划年开始时有82名参与者；资料表明该笔代扣款最迟在工资原应支付日后的第6个营业日即可从公司一般资产中合理分离；四个列出的汇入日均为财务系统实际可执行日期。`
  - 新：`计划或授权类别、年初参与者数、款项可从公司一般资产分离的日期均由工资与授权记录标明；四个列出的汇入日均为财务系统实际可执行日期。`
  - 旧：`款项不是工会会费，所有列出的银行通道均可使用。`
  - 新：`所有列出的银行通道均可使用。`
  - 旧：`安排须遵守决策日适用于该计划规模和代扣款性质的美国联邦规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r118_a01": "将缴款配置到成长基金", "swor_r118_a02": "将缴款配置到债券基金", "swor_r118_a03": "在第6个营业日汇入缴款", "swor_r118_a04": "在第9个营业日汇入缴款", "swor_r118_a05": "将缴款配置到平衡基金", "swor_r118_a06": "将缴款配置到本金保全基金", "swor_r118_a07": "在第4个营业日汇入缴款", "swor_r118_a08": "在第7个营业日汇入缴款"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Department of Labor / eCFR", "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XXV/subchapter-B/part-2510/section-2510.3-102"}, {"publisher": "U.S. Department of Labor, Employee Benefits Security Administration", "url": "https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/faqs/retirement-plans-and-erisa"}], "notes": "已复核V1.4.4所存DOL关于参与者缴款成为计划资产、少于100人计划7营业日safe harbor和工会会费边界的官方quote；Gold保持。"}`
- 复核说明：将款项性质、计划规模和可分离日移至case层；基金与汇入日仍是题内业务行动；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R119

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留四类呼叫贡献、四项主叫信息策略及成本、两组选一和最大化目标；保留普通隐私、电话营销禁用隐私阻断与身份策略三条约束。
- 主差异轴：`regulated_subject`。
- C1：`{"boundary_facts": "四类呼叫均在同一企业专用网络内起止；网络不连接PSTN，目的端均为内部分机，不连接911、ANI订户、公共紧急线路或消费者号码。", "decision_date": "2026-08-05", "jurisdiction": "美国企业内部通信", "regulated_subject": "企业VoIP管理员为封闭专用编号网络选择一类内部呼叫和主叫信息策略"}`
- C2：`{"boundary_facts": "A为拨打*67的普通州际SS7住宅呼叫；B由被叫方付费且被叫方订购ANI/计费号码服务；C拨打公共机构911线路；D代表营利商家进行电话营销；卖方客服号码真实有效，运行记录没有威胁调查。", "decision_date": "2026-08-05", "jurisdiction": "美国联邦互联VoIP与PSTN通信", "regulated_subject": "互联VoIP提供商选择一类PSTN呼叫和主叫信息策略"}`
- C1 不适用原因：C1管理员仅运营封闭企业专网，既不作为题列公共通信主体也没有呼叫进入PSTN、911、ANI订户或消费者端，47 CFR主叫号码与电话营销规则不生成三条策略约束。
- 题内行动映射：a01-a04依次为呼叫业务A-D，a05-a08依次为隐私抑制、传CPN/ANI、卖方身份与客服号码、执法受限披露；三条Patch连接A-a05，并使D排除a05且要求a07。
- source 精确替换：
  - 旧：`北岸互联VoIP服务商须选择一种PSTN呼叫业务和一种主叫信息策略。业务为拨打*67的普通州际SS7住宅呼叫（80点）、由被叫方付费且被叫方订购ANI/计费号码服务的州际呼叫（76点）、拨打公共机构911紧急线路的呼叫（70点）或代表营利商家发起的电话营销呼叫（85点）。`
  - 新：`北岸互联VoIP服务商须从四种呼叫业务A至D和四种主叫信息策略中各选择一项。四种业务贡献依次为80、76、70和85点；每项业务的网络路径、付费方式、呼叫目的和运营主体由当次业务单记录。`
  - 旧：`电话营销卖方客服号码真实有效；本题没有威胁呼叫或执法调查，服务商使用SS7并提供基于SS7的号码功能。`
  - 新：`相关客服号码、网络信令功能、威胁记录和调查状态由当次业务单固定。`
  - 旧：`安排须遵守决策日有效的美国联邦主叫号码传递、隐私和电话营销规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r119_a01": "承载拨打*67的普通州际SS7住宅呼叫", "swor_r119_a02": "承载由被叫方付费且被叫方订购ANI/计费号码服务的州际呼叫", "swor_r119_a03": "承载拨打公共机构911紧急线路的呼叫", "swor_r119_a04": "承载营利商家的电话营销呼叫", "swor_r119_a05": "识别隐私指示且不向被叫方传递或揭示主叫号码与姓名", "swor_r119_a06": "不作隐私阻断并传输分配给主叫方的CPN或ANI", "swor_r119_a07": "传输所代表卖方名称及可在营业时间接收拒接请求的客服号码", "swor_r119_a08": "仅依执法机关指示安全披露受限CPN并执行调查访问控制"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml"}], "notes": "已复核V1.4.4所存47 CFR关于SS7 CPN、*67隐私、ANI/911分支和电话营销识别的官方quote；Gold保持。"}`
- 复核说明：把PSTN业务种类、信令、客服号码和调查状态移至case层；四项策略能力保留；将8个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

### SWOR-R120

- 结论：`FIX`；问题类型：L1, L2, L3, L4, L5, L7。
- 保持：保留九款手机、HAC认证状态与价值、同一digital air interface、恰选六款和最大化目标；保留add_variable开关与组合HAC下限约束。
- 主差异轴：`jurisdiction`。
- C1：`{"boundary_facts": "运营牌照、门店、客户账户和销售目录全部位于日本；九款候选手机仅在日本销售和供使用，美国销售与供使用目录为空。", "decision_date": "2026-08-04", "jurisdiction": "日本移动通信市场", "regulated_subject": "仅持有日本运营牌照的移动服务商选择六款手机组成日本产品组合"}`
- C2：`{"boundary_facts": "决策日在2027年6月14日之前；入选六款是在美国经所有air interface销售或供使用的完整机型清单，题列HAC认证状态来自当前FCC技术认证记录。", "decision_date": "2026-08-04", "jurisdiction": "美国全国性数字移动服务", "regulated_subject": "美国全国性移动服务商选择六款手机组成其完整美国在售或供使用机型组合"}`
- C1 不适用原因：C1服务商、牌照、销售与供使用活动全部位于日本且美国机型目录为空，47 CFR 20.19的美国移动手机组合比例不支配该六款日本组合，故外部规则开关为0。
- 题内行动映射：a01-a09依次为Alder、Birch、Cedar、Dover、Elm、Flint、Grove、Harbor、Inlet；external_rule_active及activate_external_rule是内部开关；C2恰选6款时85%向下取整要求至少5款HAC，由pre_2027_hac_portfolio_floor连接六个HAC行动。
- source 精确替换：
  - 旧：`美国全国性移动运营商手机组合。`
  - 新：`移动运营商手机组合。`
  - 旧：`Summit Wireless要在一个digital air interface中从九款候选手机里恰好提供6款，且Summit Wireless在美国除这六款入选机型外，不通过该air interface或其他air interface提供任何其他在售或使用的手机型号。`
  - 新：`Summit Wireless要在一个digital air interface中从九款候选手机里恰好提供6款；运营地域及该公司在各地通过所有air interface销售或供使用的完整机型清单由产品登记资料标明。`
  - 旧：`Summit Wireless是nationwide service provider。`
  - 新：`Summit Wireless的服务范围由运营牌照记录。`
  - 旧：`产品组合须遵守决策日有效的美国联邦移动手机hearing-aid compatibility规定。`
  - 新：``
  - 旧：`题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。`
  - 新：`请按output_schema中的action_id返回最优行动，并给出目标值及其单位。`
- output_schema meaning 修改：`{"swor_r120_a01": "在该air interface提供Alder手机", "swor_r120_a02": "在该air interface提供Birch手机", "swor_r120_a03": "在该air interface提供Cedar手机", "swor_r120_a04": "在该air interface提供Dover手机", "swor_r120_a05": "在该air interface提供Elm手机", "swor_r120_a06": "在该air interface提供Flint手机", "swor_r120_a07": "在该air interface提供Grove手机", "swor_r120_a08": "在该air interface提供Harbor手机", "swor_r120_a09": "在该air interface提供Inlet手机"}`
- IR 目标 meaning 修改：`null`
- Gold 修改：`null`
- 目标单位修正：`null`
- 证据复核：`{"access_date": "2026-08-26", "basis": [{"publisher": "U.S. Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-47.xml"}, {"publisher": "U.S. Federal Communications Commission / eCFR", "url": "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-20/section-20.19"}], "notes": "修复两个证据节点node_id/source_node_id互换并重复E2的问题：E1为美国handset model portfolio定义，E2为全国性服务商2027年6月14日前85%向下取整规则；官方原文自身写作“eight-five”，按逐字证据保留而不擅自纠错。", "official_evidence_override": [{"information_responsibility": "§20.19(a)把handset model portfolio界定为制造商或服务商在美国销售或供使用的全部机型。", "node_id": "E1", "omission_effect": "缺少E1时，无法由C1美国目录为空确认RETAIN，也无法确认C2题列六款是规则分母中的完整美国组合。", "publisher": "U.S. Federal Communications Commission / eCFR", "quote": "Handset model portfolio refers to all of the handset models that a handset manufacturer or service provider offers for sale or use in the United States.", "role": "definition", "source_node_id": "E1", "support_target_type": "applicability_gate", "support_targets": ["applicability_decision"], "supported_patch_slots": [], "url": "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-20/section-20.19"}, {"information_responsibility": "§20.19(c)(3)要求nationwide service provider在2027年6月14日前提供的机型中至少向下取整85%为HAC。", "node_id": "E2", "omission_effect": "缺少E2时，无法由六款完整组合计算至少五款HAC，也无法支持外部开关及组合下限Patch。", "publisher": "U.S. Federal Communications Commission / eCFR", "quote": "Nationwide service providers—Number of hearing aid-compatible handsets models offered prior to June 14, 2027. At least eight-five (85) percent of those handset models (rounded down to the nearest whole number) must be hearing aid-compatible as defined under paragraph (b)(1) of this section.", "role": "operative_rule", "source_node_id": "E2", "support_target_type": "patch_slot", "support_targets": ["external_rule_active", "activate_external_rule", "pre_2027_hac_portfolio_floor"], "supported_patch_slots": ["external_rule_active", "activate_external_rule", "pre_2027_hac_portfolio_floor"], "url": "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-B/part-20/section-20.19"}]}`
- 复核说明：把美国全国性身份、完整美国组合和运营地域移至case层；HAC标签、手机行动和Gold保持，并归一证据节点ID；将9个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义；删除题面中的顺序映射元说明。

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
