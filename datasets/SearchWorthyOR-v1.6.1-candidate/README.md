# SearchWorthyOR V1.6.1 Candidate

> **NOT A VALIDATED RELEASE.** 当前 validator 结果为 `FAIL / 1424 errors`。本目录仅用于开发、schema 测试和运行代码联调，不能据此报告正式 benchmark 分数。

## 当前范围

- 120 个 source tasks，360 个公开 cases。
- C1、C2、C3 各 120 个；三类 case 都进入全量实验计划。
- 88 个 source tasks 仍标记为 `NEEDS_FIX`，当前报告还包含 43 条内容漂移错误。
- Formal、人工法律复核、独立 public-first review 和 evidence-omission 实验均未完成。

## 模型输入边界

Runner 只能向模型传递：

```text
eval_id
prompt_zh
```

`public/cases_zh.jsonl` 和 `public/tasks_zh.jsonl` 是公开审查材料；原始整行不得直接传给模型。仓库运行入口使用根目录 `inputs/public_cases.jsonl` 中已经完成的二字段投影。

本目录不包含 private Gold、Patch、IR、scorer、模型解或 evidence source。完整字段边界见 `MODEL_IO_CONTRACT_zh.md`。

## 文件

- `dataset_status.json`：机器可读状态和禁止声明。
- `validation_report.json`：当前原始 `FAIL / 1424` 报告，未改写为 PASS。
- `public/tasks_zh.jsonl`：120 个 source-task 公开审查记录。
- `public/cases_zh.jsonl`：360 个公开 case。

稳定目录名 `SearchWorthyOR-v1.6.1` 只能在 validator 达到 `PASS / 0 errors` 后另行发布。当前代码和数据许可均尚未确定；涉及第三方规则文本时还需单独处理来源与许可声明。
