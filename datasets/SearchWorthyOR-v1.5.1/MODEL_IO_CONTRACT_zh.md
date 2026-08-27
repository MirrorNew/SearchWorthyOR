# SearchWorthyOR-v1.5.1 统一输入输出合同

## 输入

每个模型调用只使用 `id`、`case_id` 和 `prompt_zh`。`prompt_zh` 已包含本 case 客观事实、基础优化语义合同、解释优先级、优化骨架和公开 `output_schema`。不得向模型提供 `private/` 中的状态、证据 Gold、Patch、行动 Gold、目标 Gold 或变量映射。

## Agent 输出

```json
{
  "decision_state": "RETAIN or PATCH_CHANGES",
  "applicability": true,
  "patch": [],
  "actions": [{"id": "public_action_id", "value": 0}],
  "objective": {"sense": "min or max", "value": 0.0, "unit": "unit"}
}
```

- `RETAIN`：`applicability=false` 且 `patch=[]`，行动与目标来自 Base IR。
- `PATCH_CHANGES`：`applicability=true` 且 `patch` 非空，行动与目标来自 patched IR。
- `actions` 完整覆盖公开 action ID；`objective` 给出方向、数值与单位。
- 本版本不允许 `PATCH_STABLE`。

JSON 格式纠错、重试和格式微调仍属于实验 runner，不属于数据集 Gold。
