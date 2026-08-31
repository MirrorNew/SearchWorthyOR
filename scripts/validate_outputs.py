"""Validate the public three-method output shell and summarize cost/speed."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    INFRASTRUCTURE_STATUSES,
    MODEL,
    TERMINAL_STATUSES,
    configuration_digest,
    input_digest,
    public_cases,
    read_json,
    searchworthy_smoke_ids,
    smoke_ids,
    write_json,
)


METHODS = {
    "direct": "Direct-v2 Base-Solve Gated Search",
    "search_first": "Search-First Gated Raw-NL",
    "searchworthy": "SearchWorthy",
}
ACCEPTED_TERMINALS = {"OK", "ABSTAIN", "RETRIEVAL_FAILURE"}


def expected_ids(phase: str) -> dict[str, list[str]]:
    if phase == "formal":
        all_ids = list(public_cases())
        return {slug: all_ids for slug in METHODS}
    shared = smoke_ids()
    return {
        "direct": shared,
        "search_first": shared,
        "searchworthy": searchworthy_smoke_ids(),
    }


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def validate(phase: str) -> dict[str, Any]:
    expected = expected_ids(phase)
    expected_instances = sum(len(ids) for ids in expected.values())
    current_input_digest = input_digest()
    current_configuration_digest = configuration_digest()
    counters: Counter[str] = Counter()
    provider_success = {slug: 0 for slug in METHODS}
    per_method: dict[str, Any] = {}
    terminal_instances = 0

    for slug, method in METHODS.items():
        status_counts: Counter[str] = Counter()
        calls = total_tokens = 0
        wall_seconds = 0.0
        usage_complete_instances = 0
        for eval_id in expected[slug]:
            path = EXPERIMENT_ROOT / "runs" / phase / slug / eval_id / "unified_output.json"
            if not path.is_file():
                counters["missing_outputs"] += 1
                continue
            try:
                output = read_json(path)
            except Exception:  # malformed terminal artifacts are counted, not hidden
                counters["identity_failures"] += 1
                continue

            if (
                output.get("schema_version") != "searchworthyor.v161.unified_output.v1"
                or output.get("eval_id") != eval_id
                or output.get("method") != method
                or output.get("phase") != phase
            ):
                counters["identity_failures"] += 1
            if (
                output.get("input_digest") != current_input_digest
                or output.get("configuration_digest") != current_configuration_digest
            ):
                counters["digest_failures"] += 1

            status = str(output.get("status"))
            status_counts[status] += 1
            if status in TERMINAL_STATUSES:
                terminal_instances += 1
            else:
                counters["terminal_status_failures"] += 1
            if status not in ACCEPTED_TERMINALS:
                counters["terminal_status_failures"] += 1
            if status in INFRASTRUCTURE_STATUSES:
                counters["infrastructure_failures"] += 1

            accounting = output.get("accounting")
            if not isinstance(accounting, dict):
                counters["accounting_failures"] += 1
                continue
            call_count = accounting.get("calls")
            token_count = accounting.get("total_tokens")
            wall_total = _number(accounting.get("wall_total_seconds"))
            if (
                not isinstance(call_count, int)
                or isinstance(call_count, bool)
                or call_count < 1
                or not isinstance(token_count, int)
                or isinstance(token_count, bool)
                or token_count < 0
                or wall_total is None
            ):
                counters["accounting_failures"] += 1
                continue
            calls += call_count
            total_tokens += token_count
            wall_seconds += wall_total
            usage_complete_instances += 1
            if MODEL in (output.get("actual_models") or []):
                provider_success[slug] += 1

        per_method[slug] = {
            "method": method,
            "expected": len(expected[slug]),
            "status_counts": dict(status_counts),
            "calls": calls,
            "total_tokens": total_tokens,
            "wall_total_seconds": wall_seconds,
            "tokens_per_second": total_tokens / wall_seconds if wall_seconds > 0 else None,
            "mean_tokens_per_instance": total_tokens / len(expected[slug]) if expected[slug] else None,
            "mean_seconds_per_instance": wall_seconds / len(expected[slug]) if expected[slug] else None,
            "usage_complete_instances": usage_complete_instances,
        }

    for key in (
        "missing_outputs",
        "identity_failures",
        "digest_failures",
        "terminal_status_failures",
        "infrastructure_failures",
        "accounting_failures",
    ):
        counters.setdefault(key, 0)
    provider_gate_failed = any(value < 1 for value in provider_success.values())
    status = "PASS" if not any(counters.values()) and not provider_gate_failed else "FAIL"
    return {
        "schema_version": "searchworthyor.v161.three_methods.output_validation.v1",
        "phase": phase,
        "status": status,
        "expected_instances": expected_instances,
        "terminal_instances": terminal_instances,
        "input_digest": current_input_digest,
        "configuration_digest": current_configuration_digest,
        **dict(counters),
        "provider_success_by_method": provider_success,
        "provider_gate_failed": provider_gate_failed,
        "per_method": per_method,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate three-method outputs and summarize token/time usage")
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    args = parser.parse_args()
    summary = validate(args.phase)
    output = EXPERIMENT_ROOT / "runs" / args.phase / "validation_summary.json"
    write_json(output, summary)
    print(output.read_text(encoding="utf-8"))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
