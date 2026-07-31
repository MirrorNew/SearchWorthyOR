from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import score_submissions


CORE_METRICS = [
    "reasoning_reported_high",
    "reasoning_validated",
    "trace_complete",
    "evidence_hit_at_1",
    "evidence_hit_at_5",
    "base_model_success",
    "evidence_selected",
    "claim_evidence_consistent",
    "applicability_valid",
    "model_structurally_changed",
    "generated_code_ir_consistent",
    "projected_feasible_set_match",
    "optimal_action_set_match",
    "decision_changed_from_base",
    "outcome_match",
    "model_success",
    "semantic_e2e",
    "decision_model_equivalent",
    "decision_e2e",
    "strict_e2e",
    "evidence_driven_model_change",
]

RETRIEVAL_CONDITIONS = {
    "corpus_search",
    "live_web",
    "oracle_evidence",
    "distractor_only",
    "counterfactual_swap",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def discover_submissions(run_root: Path) -> tuple[dict[str, Any], list[str]]:
    by_id = {}
    duplicates = []
    for path in sorted(run_root.rglob("submission.json")):
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        task_id = row["task_id"]
        if task_id in by_id:
            duplicates.append(task_id)
            continue
        by_id[task_id] = row
    return by_id, sorted(set(duplicates))


def failure_inventory(
    run_root: Path,
    submission_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active = []
    recovered = []
    for path in sorted(run_root.rglob("failure.json")):
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        row["artifact"] = str(path.resolve())
        if row.get("task_id") in submission_ids:
            recovered.append(row)
        else:
            active.append(row)
    return active, recovered


def rates(
    rows: list[dict[str, Any]],
    denominator: int,
) -> dict[str, dict[str, float | int]]:
    payload = {}
    for metric in CORE_METRICS:
        successes = sum(row.get(metric) is True for row in rows)
        payload[metric] = {
            "successes": successes,
            "expected_denominator": denominator,
            "expected_rate": successes / denominator if denominator else 0.0,
            "submitted_denominator": len(rows),
            "submitted_rate": successes / len(rows) if rows else 0.0,
        }
    return payload


def grouped_rates(
    expected_ids: list[str],
    scores: dict[str, dict[str, Any]],
    gold: dict[str, dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    for task_id in expected_ids:
        groups[str(gold[task_id][field])].append(task_id)
    payload = {}
    for name, task_ids in sorted(groups.items()):
        rows = [scores[task_id] for task_id in task_ids if task_id in scores]
        payload[name] = {
            "expected": len(task_ids),
            "submitted": len(rows),
            "metrics": rates(rows, len(task_ids)),
        }
    return payload


def usage_summary(submissions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    final_only_keys = [
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "wall_seconds",
        "controller_call_count",
        "search_call_count",
        "adapter_stage_count",
    ]
    aggregate_keys = [
        "e2e_input_tokens",
        "e2e_cached_input_tokens",
        "e2e_output_tokens",
        "e2e_reasoning_output_tokens",
        "e2e_model_wall_seconds",
        "model_call_count",
    ]
    payload = {}
    for key in final_only_keys + aggregate_keys:
        values = []
        for row in submissions.values():
            usage = row.get("usage", {})
            components = [usage]
            nested_records = list(usage.get("adapter_stages", []))
            nested_records.extend(usage.get("controller_calls", []))
            components.extend(
                record.get("usage", {}) for record in nested_records
            )
            if key.startswith("e2e_") and key != "e2e_model_wall_seconds":
                source_key = key.removeprefix("e2e_")
                numeric = [
                    component.get(source_key)
                    for component in components
                    if isinstance(
                        component.get(source_key), (int, float)
                    )
                ]
                value = sum(numeric) if numeric else None
            elif key == "e2e_model_wall_seconds":
                wall_values = [
                    usage.get("wall_seconds")
                ] + [
                    record.get("wall_seconds")
                    for record in nested_records
                ]
                numeric = [
                    item
                    for item in wall_values
                    if isinstance(item, (int, float))
                ]
                value = sum(numeric) if numeric else None
            elif key == "model_call_count":
                value = 1 + len(nested_records)
            else:
                value = usage.get(key)
            if key == "search_call_count" and not isinstance(
                value, (int, float)
            ):
                trace = row.get("search_trace")
                if isinstance(trace, list):
                    value = len(trace)
                elif isinstance(trace, dict) and trace.get("query"):
                    value = 1
            if key == "search_call_count" and not isinstance(
                value, (int, float)
            ):
                value = (
                    usage.get("event_audit", {})
                    .get("completed_web_searches")
                )
            if isinstance(value, (int, float)):
                values.append(float(value))
        if values:
            payload[key] = {
                "count": len(values),
                "sum": sum(values),
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
            }
    return payload


def process_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_required = any(
        row.get("condition") in RETRIEVAL_CONDITIONS for row in rows
    )
    checks = {
        "base_model_failure": lambda row: not row.get("base_model_success"),
        "generated_code_ir_inconsistent": lambda row: not row.get(
            "generated_code_ir_consistent"
        ),
    }
    if retrieval_required:
        checks.update(
            {
                "model_change_missing": lambda row: not row.get(
                    "model_structurally_changed"
                ),
                "decision_model_mismatch": lambda row: not row.get(
                    "decision_model_equivalent"
                ),
                "final_decision_e2e_failure": lambda row: not row.get(
                    "decision_e2e"
                ),
                "evidence_selection_failure": lambda row: not row.get(
                    "evidence_selected"
                ),
                "claim_evidence_inconsistent": lambda row: not row.get(
                    "claim_evidence_consistent"
                ),
                "applicability_invalid": lambda row: not row.get(
                    "applicability_valid"
                ),
                "representation_mismatch_despite_decision_equivalence": (
                    lambda row: row.get("decision_model_equivalent") is True
                    and row.get("semantic_e2e") is not True
                ),
            }
        )
    return {
        "submitted_denominator": len(rows),
        "retrieval_required": retrieval_required,
        "counts": {
            name: sum(bool(check(row)) for row in rows)
            for name, check in checks.items()
        },
    }


def classify_active_failures(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    by_stage: Counter[str] = Counter()
    by_cause: Counter[str] = Counter()
    for row in rows:
        message = str(row.get("message", ""))
        stage_match = re.search(
            r"\b(?:coe|optimus)_([A-Za-z][A-Za-z0-9]*)\b",
            message,
        )
        if stage_match:
            stage = stage_match.group(1)
        elif re.search(r"\bcontroller_turn_\d+\b", message):
            stage = "Controller"
        elif "OptiMiner" in message:
            stage = "Controller"
        else:
            stage = "unattributed"
        by_stage[stage] += 1

        lowered = message.lower()
        if "mcp_tool_call" in lowered:
            cause = "forbidden_mcp_tool_call"
        elif "exceeded max research turns without final" in lowered:
            cause = "max_research_turns_without_final"
        elif "stopped before any search" in lowered:
            cause = "stopped_before_search"
        elif "forbidden empty or identifier query" in lowered:
            cause = "invalid_search_query"
        elif (
            "cli failed with code" in lowered
            or "return code" in lowered
            or "returncode" in lowered
            or "exit code" in lowered
        ):
            cause = "cli_process_failure"
        elif "event audit failed" in lowered:
            cause = "event_audit_other"
        elif "schema" in lowered or "parse" in lowered or "json" in lowered:
            cause = "response_parse_or_schema"
        elif "timeout" in lowered or "timed out" in lowered:
            cause = "timeout"
        else:
            cause = str(row.get("type") or "unknown")
        by_cause[cause] += 1
    return {
        "by_stage": dict(sorted(by_stage.items())),
        "by_cause": dict(sorted(by_cause.items())),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['label']} full-run summary",
        "",
        f"- Expected: {payload['coverage']['expected']}",
        f"- Submitted: {payload['coverage']['submitted']}",
        f"- Active failures: {payload['coverage']['active_failure_count']}",
        f"- Recovered infrastructure failures: "
        f"{payload['coverage']['recovered_failure_count']}",
        f"- Missing: {payload['coverage']['missing_count']}",
        "",
        "| Metric | Success / expected | Rate | Success / submitted | Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for metric in CORE_METRICS:
        row = payload["metrics"][metric]
        lines.append(
            f"| `{metric}` | {row['successes']}/{row['expected_denominator']} "
            f"| {row['expected_rate']:.1%} | "
            f"{row['successes']}/{row['submitted_denominator']} "
            f"| {row['submitted_rate']:.1%} |"
        )
    diagnostics = payload["process_diagnostics"]
    lines.extend(
        [
            "",
            "## Process diagnostics",
            "",
            "| Failure category | Count / submitted |",
            "|---|---:|",
        ]
    )
    for name, count in diagnostics["counts"].items():
        lines.append(
            f"| `{name}` | {count}/{diagnostics['submitted_denominator']} |"
        )
    failure_taxonomy = payload["active_failure_taxonomy"]
    if failure_taxonomy["by_cause"]:
        lines.extend(
            [
                "",
                "## Active pipeline failure taxonomy",
                "",
                "| Cause | Count |",
                "|---|---:|",
            ]
        )
        for name, count in failure_taxonomy["by_cause"].items():
            lines.append(f"| `{name}` | {count} |")
        lines.extend(
            [
                "",
                "| Stage | Count |",
                "|---|---:|",
            ]
        )
        for name, count in failure_taxonomy["by_stage"].items():
            lines.append(f"| `{name}` | {count} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--scope", choices=["all", "public_web"], default="all")
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    public_rows = read_jsonl(args.dataset_root / "public" / "tasks_zh.jsonl")
    gold_rows = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
    gold = {row["id"]: row for row in gold_rows}
    public_id_set = {row["id"] for row in public_rows}
    expected_ids = [
        row["id"]
        for row in public_rows
        if args.scope == "all" or "HTTPS" in row["problem_zh"]
    ]
    expected_set = set(expected_ids)
    submissions, duplicates = discover_submissions(args.run_root)
    scoped_submissions = {
        task_id: submission
        for task_id, submission in submissions.items()
        if task_id in expected_set
    }
    scoped_duplicates = [
        task_id for task_id in duplicates if task_id in expected_set
    ]
    all_active_failures, all_recovered_failures = failure_inventory(
        args.run_root, set(submissions)
    )
    active_failures = [
        row
        for row in all_active_failures
        if row.get("task_id") in expected_set
    ]
    recovered_failures = [
        row
        for row in all_recovered_failures
        if row.get("task_id") in expected_set
    ]
    backend = score_submissions.load_solver_backend(args.dataset_root)
    score_rows = []
    scoring_failures = []
    for task_id, submission in submissions.items():
        if task_id not in expected_set:
            continue
        try:
            score_rows.append(
                score_submissions.score_one(
                    submission,
                    gold[task_id],
                    args.dataset_root,
                    backend,
                )
            )
        except Exception as exc:  # noqa: BLE001 - experiment audit
            scoring_failures.append(
                {
                    "task_id": task_id,
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            )
    scores = {row["task_id"]: row for row in score_rows}
    missing = sorted(expected_set - set(scores))
    unexpected = sorted(set(submissions) - public_id_set)
    failure_types = Counter(row["type"] for row in active_failures)
    payload = {
        "label": args.label,
        "scope": args.scope,
        "run_root": str(args.run_root.resolve()),
        "coverage": {
            "expected": len(expected_ids),
            "submitted": len(set(submissions) & expected_set),
            "scored": len(score_rows),
            "active_failure_count": len(active_failures),
            "recovered_failure_count": len(recovered_failures),
            "missing_count": len(missing),
            "missing": missing,
            "duplicates": scoped_duplicates,
            "unexpected": unexpected,
            "scoring_failures": scoring_failures,
            "active_failure_types": dict(sorted(failure_types.items())),
        },
        "metrics": rates(score_rows, len(expected_ids)),
        "by_family": grouped_rates(
            expected_ids, scores, gold, "family"
        ),
        "by_patch_class": grouped_rates(
            expected_ids, scores, gold, "patch_class"
        ),
        "by_evidence_mode": grouped_rates(
            expected_ids, scores, gold, "evidence_mode"
        ),
        "usage": usage_summary(scoped_submissions),
        "process_diagnostics": process_diagnostics(score_rows),
        "active_failure_taxonomy": classify_active_failures(
            active_failures
        ),
        "active_failures": active_failures,
        "recovered_failures": recovered_failures,
        "rows": score_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(
            render_markdown(payload),
            encoding="utf-8",
        )
    print(json.dumps(payload["coverage"], ensure_ascii=False))
    return (
        0
        if not scoped_duplicates and not unexpected and not scoring_failures
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
