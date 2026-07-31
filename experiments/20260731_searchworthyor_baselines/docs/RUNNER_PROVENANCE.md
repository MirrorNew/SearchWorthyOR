# Runner provenance

## OPTIMUS launch snapshot

The three OPTIMUS-inspired full-corpus shard processes were launched with
`scripts/run_codex_cli_prompt_adapter.py` at:

- SHA-256: `1f351bb021c0e420b825844b66ddf75dba345476abe665b39e5b282767a58701`
- bytes: `24698`

During that run, the resume gate was tightened for future fresh processes.
The stricter resume-gate source used by the CoE full-corpus launch is:

- SHA-256: `ed26a28def2319faed4fde6528a3abead16c018ba0952a1a62e3725c0c4d05e2`
- bytes: `24972`

The only launch-to-current change in the runner is this resume condition:

```diff
- if reuse_existing_response and events_path.exists():
-     existing_events = events_path.read_text(encoding="utf-8")
-     if existing_events.strip():
-         raise RuntimeError(
-             f"{stage} has existing events without a response; "
-             "refusing to call the model again"
-         )
+ if reuse_existing_response:
+     existing_events = (
+         events_path.read_text(encoding="utf-8")
+         if events_path.exists()
+         else ""
+     )
+     existing_stderr = (
+         stderr_path.read_text(encoding="utf-8")
+         if stderr_path.exists()
+         else ""
+     )
+     if existing_events.strip() or existing_stderr.strip():
+         raise RuntimeError(
+             f"{stage} has existing events or stderr without a "
+             "response; refusing to call the model again"
+         )
```

The running OPTIMUS processes retained the launch version in memory.
Qualification of any OPTIMUS recovery is therefore manually checked against
the stricter three-part rule: no response, zero events, and empty stderr.
The CoE full processes retained `ed26a28...` in memory.

## CoE recovery snapshot

The two one-time CoE infrastructure recoveries were launched after further
auditing changes to the shared prompt-adapter source:

- SHA-256: `54dbf133a5417d96a8695d01d50d628ed2001fccf6bec32d3d73e2ceba0dd58d`
- bytes: `26425`

They are recovery attempts, not replacements for the main-run identity.
SWOR078 and SWOR087 preserve their original `failure.json`; recovery outcome
is recorded separately.

## OptiMiner compatibility launch snapshot

All three OptiMiner full-corpus shard processes record the same runner hashes:

| File | SHA-256 |
|---|---|
| `run_codex_cli_optiminer.py` | `fb2179c716bbae9f98b30235386a0e58820b92056854b9315646b4233214b6c9` |
| `controlled_retrieval.py` | `6f86eb1debc2a08d426db6704f5b99291b9754a77902c1ce974ebb8315d3bf1b` |
| `run_codex_cli_prompt_adapter.py` | `54dbf133a5417d96a8695d01d50d628ed2001fccf6bec32d3d73e2ceba0dd58d` |
| `run_codex_cli_one_shot.py` | `0c48cb3ebeb40ce71f83a3c2c1dbfda69e34a5ffbbd7f736cbae8afb1d905baa` |

The first launch command omitted the required `--condition` argument and
exited at argparse before any model call. Its logs are preserved. The actual
full runs use an independent second launch with `--condition corpus_search`.

### OptiMiner recovery outcome

The original three shards naturally reached 100 terminal task states before
any recovery: 89 submissions and 11 failures. Only SWOR039, SWOR026, and
SWOR040 satisfied the exact gate of missing response, zero events, and empty
stderr. Each was resumed once with the same runner, model, effort, condition,
turn budget, output root, and sterile root; targeted selection used the
default `1/0` shard parameters after filtering by task ID.

All three recovered to Gurobi `OPTIMAL`. The previously completed controller
stages were reused, the final model response was not. SWOR095 was not retried:
its response and events were empty, but stderr contained a 401-byte remote
plugin synchronization warning. Seven max-turn failures were also not
retried.

Before each recovery, the complete task directory and shard-root manifest/
aggregates were copied outside the main run tree. Targeted-run root artifacts
and before/after hashes are stored under
`runs/codex_cli_optiminer/corpus_full_recovery_provenance/`. After recovery,
the original shard-root files were restored byte-for-byte; task-level
submission, stale failure, and `resume_resolution.json` remain together.

## Merge authority

Targeted recovery can rewrite a shard-level aggregate file even when the
immutable per-task artifacts remain intact. Therefore the final merger treats
`SWOR*/submission.json` and `SWOR*/failure.json` as authoritative and does not
trust shard-level `submissions.jsonl` after recovery. A regression fixture
checks this case. The final OptiMiner merge audit reports expected=100,
merged=92, active=8, recovered=3, and no duplicates, unknown IDs, or uncovered
tasks.
