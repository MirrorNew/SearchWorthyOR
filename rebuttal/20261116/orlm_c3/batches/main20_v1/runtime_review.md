# Runtime review — main20_v1

## Completion and protocol

- `completion.json` reports `complete=true`; `progress.json` has 40/40 terminal records. All 40 `execution.json` records have `returncode=0` and `watchdog_timeout=false`. At the worker level, 35 runs ended `FINISHED` with COPT `OPTIMAL`; five ended with method-level errors. The five failures remain in the denominator.
- This is a user-assigned **C3-style** sample. The source manifest marks deployment provenance unverified; these results do not establish real-deployment provenance.
- The run used `standard-online` with `legacy_knowledge_v1` and `swagent-online`, both configured for `deepseek-flash` (`high`) and the shared COPT/free-variable adapter.

## Public input and model audit

- `public_cases.jsonl` contains 20 tasks. Its SHA-256 is `e7818e7338a9bc24170f86d256640fe6e7fa7a7141a3f6608c7bd4e0bc7c2bae`. `source_manifest.json` records 20 problem statements and 110 direct `data/*.csv` files, with `answers_excluded=true`; its SHA-256 is `196acb77690299d00eaf51a56ed6dc5547bfb28eaa41f86a13b3b979aa78bd4f`.
- All 40 run inputs exactly matched the corresponding public `id`, `prompt`, and `output_schema`; all 40 isolation checks passed (200 blocked probes total). `verification.json` also reports a pass and matched paired inputs/configs. This is a project-root access guard, not an OS-wide sandbox.
- The 90 completed provider responses all identify the actual model as `deepseek-flash`. The five failed/timed-out API calls have no returned `actual_model`; their requested model was `deepseek-flash`. API-call totals: 90 `CONSUMED`, one `TIMED_OUT`, and four `FAILED`.

## Terminal failures and API errors

- SWAgent `ORLM-SFT1991-B02_00054`: `Citations must identify observed task or body references`.
- Standard `ORLM-SFT1991-B03_00206`: `Invalid model keys`; an earlier API attempt ended with `TimeoutError: The read operation timed out`, followed by a consumed response from `deepseek-flash`.
- Standard and SWAgent `ORLM-SFT1991-P52_B04_L0055_high`: both terminal results report `FAILED [784abbf8f1ca4ce88c50fdb236769eee]: ValueError: Provider reported a failed or incomplete response` and `FAILED [4ccc74071a5c4e5d93fb09eda0e3f6e9]: ValueError: Provider reported a failed or incomplete response`, respectively. The API error detail for each is `ValueError: Provider reported a failed or incomplete response`; neither returned an actual model or usage.
- Standard `ORLM-SFT1991-SFTREAL_OP_RB2607_001`: `Invalid bounds`.
- SWAgent `ORLM-SFT1991-P122_high` and `ORLM-SFT1991-SFTREAL_OP_RB2607_001` each had an API-call error `IncompleteRead: IncompleteRead(0 bytes read)` before later consumed `deepseek-flash` responses and an `OPTIMAL` terminal result. These are call-level errors, not terminal run failures.

## Recorded usage and reproducibility

- Provider-reported usage for the 90 completed responses totals 1,427,335 input, 1,621,879 output, and 3,049,214 total tokens. Standard totals 1,405,062 tokens; SWAgent totals 1,644,152. Five failed/timed-out calls have unknown usage and are excluded from these sums.
- No billed monetary amount is recorded (`objective_summary.json` has `recorded_monetary_cost: null`); this review does not infer a dollar cost from token counts.
- Commands for a new run with the recorded parameters (PowerShell; requires the complete local runtime and source package described in `../../README.md`; use a fresh batch name):

```powershell
$env:PYTHONUTF8='1'
& 'E:\my_evns\py312_torch28\python.exe' -B -X utf8 'D:\LLM-CodexProject\SWAgent-for-ICLR\rebuttal\20261116\orlm_c3\convert_public_cases.py'
& 'E:\my_evns\py312_torch28\python.exe' -B -X utf8 'D:\LLM-CodexProject\SWAgent-for-ICLR\rebuttal\20261116\orlm_c3\run_batch.py' --name NEW_UNIQUE_BATCH --workers 8 --check-isolation --run
& 'E:\my_evns\py312_torch28\python.exe' -B -X utf8 'D:\LLM-CodexProject\SWAgent-for-ICLR\rebuttal\20261116\score_orlm_runs.py' NEW_UNIQUE_BATCH
& 'E:\my_evns\py312_torch28\python.exe' -B -X utf8 'D:\LLM-CodexProject\SWAgent-for-ICLR\rebuttal\20261116\verify_orlm_batch.py' NEW_UNIQUE_BATCH
```

Objective-match scoring and its metric definition are in `../../RESULTS_20261116.md` and `../../SCORING_PROTOCOL.md`. Objective match is not full-model correctness or an independent business-feasibility certificate.
