# SearchWorthyOR

[中文说明](README.md) · [English reproduction guide](docs/REPRODUCIBILITY_EN.md)

SearchWorthyOR studies how optimization agents discover external rules, determine whether they apply to a task, and incorporate supporting evidence into mathematical models and final decisions. SWAgent maintains an information–evidence table to connect unresolved conditions, source support, and model revision or retention.

## Current public release

This repository publishes SearchWorthy Agent `i01-lite-007-c2fix-002-format001`, its frozen runtime configuration, and single-case preparation and validation scripts.

**The benchmark files and `release_manifest.json` are not currently included on `main`.** The published scripts require those files. Installation and code inspection are possible now; data validation, case preparation, isolation checks, and live task execution require a matching dataset and manifest. The commands below are documented for use once those prerequisites are available.

The published launcher currently targets `datasets/SearchWorthyOR-v1.6.2/`. It is separate from the paper's frozen v1.6.3 subset (100 source tasks, 300 condition-specific cases) and the newer six-group evaluation tools. Neither the v1.6.3 dataset nor those tools are included in this documentation update. See the [version and availability notes](docs/REPRODUCIBILITY_EN.md#version-and-availability).

## Repository contents

| Path | Purpose |
|---|---|
| [agent/lite_worker.py](agent/lite_worker.py) | Single-case worker and input-access checks |
| [agent/searchworthy/table_loop.py](agent/searchworthy/table_loop.py) | Information table, evidence acquisition, and model updates |
| [agent/searchworthy/api_lite.py](agent/searchworthy/api_lite.py) | Model and search transport |
| [agent/searchworthy/page_read.py](agent/searchworthy/page_read.py) | Web-page and PDF reading |
| [agent/searchworthy/compiler.py](agent/searchworthy/compiler.py) | Mathematical-model compilation |
| [agent/adapters/solver.py](agent/adapters/solver.py) | Gurobi adapter |
| [agent/configs/i01_lite_runtime.json](agent/configs/i01_lite_runtime.json) | Frozen model settings and resource limits |
| [scripts/run_case.py](scripts/run_case.py) | Prepare or execute one public case |
| [scripts/validate_release.py](scripts/validate_release.py) | Offline source and dataset validation |

## Installation and API configuration

Use Python 3.12, a working Gurobi license, and UTF-8 for Chinese task files. From the repository root:

```powershell
python -m pip install -r requirements.txt
```

The dependency versions are recorded in [requirements.txt](requirements.txt). Python environments, API credentials, and solver licenses are not bundled.

The published transport uses the Shubiaobiao API for model calls and search. Its requested model settings are `gpt-5.6-luna`, reasoning effort `xhigh`, and temperature `1`. Per-case limits are 12 model calls, 3 logical searches, 6 page reads, 90 seconds per solve, and 1,200 seconds overall, with at most 2 technical retries under the shared call budget and deadline. The configuration and implementation define the exact counting rules.

Create a local `.env` using [.env.example](.env.example) and set your own `OPENOR_API_KEY`, or supply the variable through your environment. A different credential file can be selected with `--env-file` or `SEARCHWORTHY_ENV_FILE`. Keep the original provider and model configuration when reproducing that configuration; changing a model name does not guarantee compatibility with another provider.

## Reproduction steps

After obtaining the dataset and manifest matching the published launcher:

1. Validate source hashes, data structure, and public/reference separation with `python -B -X utf8 scripts/validate_release.py`.
2. Select an `eval_id` from `public/cases_zh.jsonl` and prepare a new output directory with `scripts/run_case.py`.
3. Add `--check-isolation` for a worker-access check, or `--run` for real model, search, and solver calls. These options are mutually exclusive.
4. Preserve each run's input, configuration, request/response records, solver records, and failures when evaluating results.

The [English reproduction guide](docs/REPRODUCIBILITY_EN.md) provides copyable PowerShell commands, input-field explanations, output locations, and evaluation guidance. File validation and successful execution are not new benchmark scores.

## Benchmark conditions

| Condition | Meaning |
|---|---|
| C1 | The target external requirement does not apply to the instance facts. |
| C2 | An applicable requirement is omitted from the task description. |
| C3 | The applicable requirement is already supplied in the task. |

The benchmark task language remains Chinese. English documentation does not translate task inputs or change their semantics. Private evaluation materials, including condition labels, reference rules, models, and answers, must not be passed to the inference worker.

Documentation updated: 2026-11-12.
