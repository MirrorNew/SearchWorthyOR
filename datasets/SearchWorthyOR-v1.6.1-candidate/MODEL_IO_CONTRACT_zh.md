# SearchWorthyOR-v1.6.1 统一输入输出合同

## 正式模型输入

每次调用仅传入盲化的 `eval_id` 与 `prompt_zh`。`eval_id` 不编码 source task、C1/C2/C3 或状态；这些映射只存在于 `private/eval_identity_map.jsonl`。

`prompt_zh` 的确定性顺序为：本 case 权威事实；若题面已提供规则，则加入随题规则材料；优化骨架；公开 `output_schema`。单题不重复数据集级的语义合同或解释优先级。

## Agent 输出

```json
{
  "decision_state": "RETAIN or PATCH_CHANGES or NO_SEARCH",
  "search_performed": false,
  "applicability": true,
  "patch": [],
  "actions": [{"id": "public_action_id", "value": 0}],
  "objective": {"sense": "min or max", "value": 0.0, "unit": "unit"}
}
```

- `RETAIN`：需要检索以判断边界，规则不适用，初始与最终均为 Base，Patch 为空。
- `PATCH_CHANGES`：需要检索，Base 经非空 typed Patch 变成 Full，最终决策改变。
- `NO_SEARCH`：题面规则信息已足以建立 Full，初始与最终均为 Full，Patch 为空。
- `patch=[]` 不能单独决定状态；scorer 同时核对状态、适用性、搜索、初始/最终模型、行动与目标。

`private/` 中的身份映射、状态、证据、Patch、IR 路径、行动 Gold、目标 Gold 和变量映射不得注入模型输入。
