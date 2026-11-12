# Reproducing the published SWAgent

[English README](../README_EN.md) · [中文说明](../README.md)

This guide documents the code currently published on `MirrorNew/SearchWorthyOR/main`. Commands use PowerShell and an existing Python 3.12 environment.

## Version and availability

| Component | Public status |
|---|---|
| Frozen Agent code and runtime configuration | Included |
| Single-case launcher and release validator | Included |
| Dataset and `release_manifest.json` | Not currently included |
| Paper's v1.6.3 subset and six-group evaluation launcher | Not included in this documentation update |

The current `scripts/run_case.py` and `scripts/validate_release.py` expect `datasets/SearchWorthyOR-v1.6.2/` and a matching root-level `release_manifest.json`. The validator checks 120 source tasks and 360 cases for that historical version. The paper's later frozen v1.6.3 subset instead has 100 source tasks and 300 cases. Do not rename or substitute the subset to satisfy the older launcher: its manifest, counts, and evaluation configuration must match the chosen release.

Data-dependent commands below require the matching files. This guide does not claim that a fresh clone can already reproduce the benchmark results, and it does not introduce new experiment results.

## Environment and credentials

Install the versions in [requirements.txt](../requirements.txt) and configure a working Gurobi license:

```powershell
python --version
python -m pip install -r requirements.txt
```

Prepare a credential file without replacing an existing one:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

Edit `.env` locally to set `OPENOR_API_KEY`. Do not commit credentials. You can instead set this environment variable using your usual credential-management process. The launcher accepts `--env-file` for an existing credential file; its default is `SEARCHWORTHY_ENV_FILE` when set, otherwise the repository's `.env`.

## Model, search, and resource settings

The published configuration is [agent/configs/i01_lite_runtime.json](../agent/configs/i01_lite_runtime.json). Model calls and search use the Shubiaobiao transport in [api_lite.py](../agent/searchworthy/api_lite.py); web/PDF reading uses [page_read.py](../agent/searchworthy/page_read.py).

| Configuration field | Published value |
|---|---|
| `model.name` and `search_model.name` | `gpt-5.6-luna` |
| `model.reasoning_effort` and `search_model.reasoning_effort` | `xhigh` |
| `model.temperature` and `search_model.temperature` | `1` |
| `budgets.model` | `12` |
| `budgets.search` | `3` |
| `budgets.read` | `6` |
| `budgets.solve_seconds` | `90` |
| `budgets.wall_seconds` | `1200` |
| `budgets.technical_retries` | `2` |

Technical retries share the original call budget and deadline. These are ceilings, not measured resource consumption. Record provider, requested/returned model identifiers, configuration, and actual usage for a new experiment. Changing providers or settings creates a new experimental configuration.

## Dataset fields and inference boundary

The following paths are expected by the published scripts once the matching dataset is available:

| Path or field | Meaning |
|---|---|
| `public/cases_zh.jsonl` | Condition-specific public tasks; select evaluation inputs from this file |
| `eval_id` | Public case identifier used by `--eval-id` |
| `prompt_zh` | Chinese task text passed to the worker as `prompt` |
| `output_schema` | Required response schema passed to the worker unchanged |
| `public/tasks_zh.jsonl` | Source-task records; not a replacement for the condition-specific cases |
| `private/case_gold.jsonl` | Reference answers and model paths for evaluation |
| `private/eval_identity_map.jsonl` | Source-task/condition mapping for the controller and evaluator |
| `models/` | Reference model files |

The launcher constructs exactly `{"id": eval_id, "prompt": prompt_zh, "output_schema": output_schema}` for the inference input. Do not add condition labels, reference rules, reference answers, or other cases to that payload. Here `private` describes the inference-access boundary, not GitHub repository visibility.

## Validate and prepare a case

Once the matching dataset and manifest are present, run offline validation:

```powershell
python -B -X utf8 scripts/validate_release.py
```

This checks source hashes, JSONL structure, identifiers, expected condition counts, reference-model paths, and Python syntax. It makes no model, search, or solver calls. A passing file check does not validate every rule interpretation.

Choose an identifier from the public case file, then prepare a new directory:

```powershell
$publicCase = Get-Content -LiteralPath 'datasets/SearchWorthyOR-v1.6.2/public/cases_zh.jsonl' -Encoding UTF8 -TotalCount 1 | ConvertFrom-Json
$caseId = $publicCase.eval_id
python -B -X utf8 scripts/run_case.py --eval-id $caseId --output runs/example_prepare
```

Preparation copies the Agent source, extracts only the public input, and writes configuration/provenance files. It does not call the model, search service, or solver. The output directory must not already exist.

## Check access isolation

Use another new directory inside the repository:

```powershell
python -B -X utf8 scripts/run_case.py --eval-id $caseId --output runs/example_isolation --check-isolation
```

The worker checks its configured data-access restrictions without model, search, or solver requests. This is a process-level Python audit-hook check, not a claim of an operating-system sandbox.

## Execute a case

With valid credentials, provider access, and a Gurobi license, choose a new output directory and explicitly enable execution:

```powershell
python -B -X utf8 scripts/run_case.py --eval-id $caseId --output runs/example_live --run
```

This command makes real model/search requests and solver calls. The launcher refuses an existing output directory. Retain failed and timed-out attempts rather than selecting reruns according to answer correctness.

## Output layout and evaluation

| Output location | Contents |
|---|---|
| `<output>/inputs/<eval_id>.json` | The exact public inference payload |
| `<output>/source/` | Copied source and runtime configuration |
| `<output>/manifest.json` | Source hashes and upstream version information |
| `<output>/cases/<eval_id>/` | Live-run result, access log, and runtime artifacts |
| `<output>/isolation/<eval_id>/` | Isolation-check records when that mode is selected |

Interpret outputs using the case's `output_schema` and the matching reference package. A successful process exit is not an answer-correctness label. Answer correctness, complete mathematical-model correctness, and evidence support are separate checks: a correct optimal answer does not prove that every constraint is correct, and a URL alone does not prove that its text supports the model.

Use fixed case counts, include failures and missing outputs, and report C1/C2/C3 separately. Report model/search/read operations, token coverage, and timing with an explicit definition of whether failed requests and retries are included. Keep unknown usage distinct from zero. Repeated reviews of one trajectory are not independent task runs.

The single-case launcher is not a full scoring harness. Reproducing a paper table additionally requires its matching task list, scoring implementation, repetition protocol, and experiment configuration.

Documentation updated: 2026-11-12.
