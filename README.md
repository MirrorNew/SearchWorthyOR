# SearchWorthyOR

本仓库整理了三条可运行的公开流程：Direct、Search-First 和 SearchWorthy Agent，以及 SearchWorthyOR V1.6.1 candidate 的公共数据。

> **数据状态：NOT A VALIDATED RELEASE。** 当前 V1.6.1 validator 为 `FAIL / 1424 errors`，只能用于开发、schema 和 Harness 联调，不能报告正式 benchmark 分数。详见 [`datasets/SearchWorthyOR-v1.6.1-candidate/README.md`](datasets/SearchWorthyOR-v1.6.1-candidate/README.md)。

## 仓库范围

保留：

- Direct-v2：Base 建模/求解后触发搜索。
- Search-First：先判断并搜索，再以 Raw-NL 证据建模/求解。
- SearchWorthy：OR-specific 信息审查、impact probe、证据准入、事务化 Patch、重新求解。
- 三方法共享的公开输入、API、检索、候选代码执行、并发启动和 token/速度统计。

不包含：CoE、OptiMUS、optiminer-training-free、private Gold、scorer、旧运行结果、API trace 和 recovery controller。

## 快速开始

测试环境为 Python 3.12。Gurobi 需要可用许可证。

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env.local
```

在 `.env.local` 中填写现有 API key；运行时只接受 `OPENOR_BASE_URL` 和 `OPENOR_API_KEY` 两项。凭据文件已被 Git 忽略。

先跑不访问网络的离线测试：

```powershell
python -X utf8 -m pytest -q -p no:cacheprovider
```

再验证一次 chat 和一次 hosted search：

```powershell
python -X utf8 scripts/preflight.py
```

完整 8-instance Smoke（三方法并发）：

```powershell
python -X utf8 scripts/run_all.py --phase smoke
```

Smoke 验证通过后，运行 3 × 360 = 1080 个正式实例。每个 source task 的 C1/C2/C3 都会运行：

```powershell
python -X utf8 scripts/run_all.py --phase formal
```

输出保存在 `runs/<phase>/<method>/<eval_id>/`。`runs/<phase>/validation_summary.json` 同时给出每个方法的 calls、total tokens、总耗时、平均每题 token/秒数和 tokens/s。

## 代码入口

- `EXPERIMENT_CONFIG.json`：三方法唯一实验配置。
- `inputs/public_cases.jsonl`：传给 Runner 的 360 行二字段输入，只含 `eval_id + prompt_zh`。
- `scripts/run_all.py`：薄并发入口。
- `scripts/gated_search_pipeline.py`：Direct / Search-First 共享实现。
- `searchworthy/pipeline.py`：SearchWorthy 科学 workflow。
- `scripts/validate_outputs.py`：公开输出、token 与速度校验。
- [`docs/ARCHITECTURE_ZH.md`](docs/ARCHITECTURE_ZH.md)：人工审查顺序、模块职责与数据流。

## 重要边界

- `public/cases_zh.jsonl` 是审查材料；Runner 不会把原始整行传给模型。
- Formal 必须绑定当前 config/input digest、通过当前 Preflight 与 Smoke；旧输出不能静默复用。
- SearchWorthy 每个 case 的 hosted-search 全局预算最多为 3，页面结果必须经过 URL、原文 quote 和 Evidence→Patch 绑定检查。
- 本仓库目前没有许可证文件；代码和数据的再分发/复用许可尚未确定。
