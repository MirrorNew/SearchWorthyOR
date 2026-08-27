from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    MODEL,
    REASONING_EFFORT,
    SMOKE_SUMMARY_PATH,
    TEMPERATURE,
    TERMINAL_STATUSES,
    count_api_key_leaks,
    public_cases,
    read_json,
    read_jsonl,
    smoke_ids,
    write_json,
)


METHODS = {
    "direct": "Direct-v2 Base-Solve Gated Search",
    "coe": "CoE",
    "optimus": "OptiMUS",
    "optiminer": "optiminer-training-free",
    "search_first": "Search-First Gated Raw-NL",
}
SEARCH_METHODS = {"direct", "search_first"}
FORBIDDEN = (
    "selected_gold",
    "gold_action_set",
    "gold_objective",
    "gold_patch_elements",
    "official_support",
    "patched_ir",
    "solve_result",
    "\\private\\",
    "/private/",
)


def audit_requests(root: Path) -> tuple[int, int, dict[str, int], dict[str, int]]:
    configuration = leakage = 0
    success = {method: 0 for method in METHODS}
    final_calls = {method: 0 for method in METHODS}
    for method in METHODS:
        for path in sorted((root / method).glob("SWOR-R*/attempt_*/api_calls.jsonl")):
            for row in read_jsonl(path):
                if row.get("actual_model") == MODEL:
                    success[method] += 1
                if row.get("purpose") == "final_model_and_solve" and row.get("actual_model") == MODEL:
                    final_calls[method] += 1
                if (
                    row.get("requested_model") != MODEL
                    or row.get("reasoning_effort") != REASONING_EFFORT
                    or row.get("temperature") != TEMPERATURE
                    or (row.get("actual_model") is not None and row.get("actual_model") != MODEL)
                ):
                    configuration += 1
        for path in sorted((root / method).glob("SWOR-R*/attempt_*/llm_calls/*_request.json")):
            payload = read_json(path)
            text = json.dumps(payload, ensure_ascii=False).lower()
            if any(marker in text for marker in FORBIDDEN):
                leakage += 1
    return configuration, leakage, success, final_calls


def validate_smoke() -> dict[str, Any]:
    root = EXPERIMENT_ROOT / "runs" / "smoke"
    expected_ids = smoke_ids()
    public = public_cases()
    terminal = identity = duplicates = runner_failures = 0
    raw_nl_binding_failures = raw_nl_nonempty_instances = 0
    gate_missing = budget_violations = final_answer_missing = 0
    base_stage_missing = base_solve_completed = base_failure_unaccounted = base_provider_failures = 0
    search_backend_violations = 0
    status_counts: dict[str, dict[str, int]] = {}
    seen: set[tuple[str, str]] = set()
    for method_dir, method in METHODS.items():
        counts: dict[str, int] = {}
        for case_id in expected_ids:
            paths = list((root / method_dir / case_id).glob("unified_output.json"))
            duplicates += max(0, len(paths) - 1)
            if len(paths) != 1:
                continue
            output = read_json(paths[0])
            key = (method, case_id)
            duplicates += int(key in seen)
            seen.add(key)
            if (
                output.get("task_id") != public[case_id]["id"]
                or output.get("case_id") != case_id
                or output.get("method") != method
                or output.get("phase") != "smoke"
            ):
                identity += 1
            status = str(output.get("status"))
            if status in TERMINAL_STATUSES:
                terminal += 1
            counts[status] = counts.get(status, 0) + 1
            runner_failures += int(status in {"RUNNER_FAILURE", "CONFIGURATION_VIOLATION"})

            if method_dir in SEARCH_METHODS:
                gate = output.get("search_gate")
                gate_missing += int(not isinstance(gate, dict) or gate.get("status") not in {"TRIGGERED", "NOT_TRIGGERED", "GATE_FAILURE"})
                search = output.get("search") if isinstance(output.get("search"), dict) else {}
                query_count = search.get("search_count")
                readable = search.get("readable_page_count")
                attempts = search.get("page_open_attempt_count")
                budget_violations += int(
                    not isinstance(query_count, int)
                    or not 0 <= query_count <= 3
                    or not isinstance(readable, int)
                    or not 0 <= readable <= 9
                    or not isinstance(attempts, int)
                    or not 0 <= attempts <= 18
                )
                search_backend_violations += int(
                    search.get("search_backend") != "shubiaobiao_responses_web_search"
                    or search.get("backend_fallback") is not False
                )
                final_answer_missing += int(output.get("answer_present") is not True)
                if method_dir == "direct":
                    base = output.get("base_model")
                    base_solve = output.get("base_solve")
                    base_stage_status = output.get("base_stage_status")
                    base_solve_ok = (
                        isinstance(base, dict)
                        and isinstance(base.get("mathematical_model"), dict)
                        and isinstance(base_solve, dict)
                        and base_solve.get("attempted") is True
                        and base_solve.get("status") == "OPTIMAL_EXACT_ACTION_MAPPING"
                        and output.get("base_model_contract_errors") == []
                    )
                    # Outputs generated before base_stage_attempted was added are
                    # still unambiguous when an actual Base solver run exists.
                    base_stage_attempted = output.get("base_stage_attempted") is True or base_solve_ok
                    base_stage_missing += int(not base_stage_attempted)
                    base_solve_completed += int(base_solve_ok)
                    base_provider_failures += int(base_stage_status == "PROVIDER_FAILURE")
                    base_failure_unaccounted += int(
                        not base_solve_ok and base_stage_status != "PROVIDER_FAILURE"
                    )
                else:
                    raw_nl = output.get("retrieved_evidence_raw_nl")
                    verified = output.get("verified_evidence")
                    if not isinstance(raw_nl, str) or not raw_nl.strip() or not isinstance(verified, list):
                        raw_nl_binding_failures += 1
                    raw_nl_nonempty_instances += int(isinstance(raw_nl, str) and bool(raw_nl.strip()))
            elif method_dir in {"coe", "optimus"}:
                search_backend_violations += int(output.get("native_web_search_allowed") is not False)
            elif method_dir == "optiminer":
                search_backend_violations += int(output.get("native_search_backend") != "arxiv_document")
        status_counts[method] = counts

    configuration, leakage, provider_success, final_calls = audit_requests(root)
    api_key_leakage = count_api_key_leaks(root)
    summary = {
        "schema_version": "searchworthyor.v151.five_baselines.smoke_summary.v1",
        "status": "PASS",
        "terminal_instances": terminal,
        "configuration_violations": configuration,
        "gold_leakage": leakage,
        "api_key_leakage": api_key_leakage,
        "identity_mismatch": identity,
        "duplicate_terminal_outputs": duplicates,
        "harness_runner_failures": runner_failures,
        "search_gate_missing": gate_missing,
        "search_budget_violations": budget_violations,
        "search_backend_violations": search_backend_violations,
        "direct_base_stage_missing": base_stage_missing,
        "direct_base_solve_completed": base_solve_completed,
        "direct_base_provider_failures": base_provider_failures,
        "direct_base_failure_unaccounted": base_failure_unaccounted,
        "search_final_answer_missing": final_answer_missing,
        "raw_nl_binding_failures": raw_nl_binding_failures,
        "raw_nl_nonempty_instances": raw_nl_nonempty_instances,
        "provider_success_by_method": provider_success,
        "search_final_calls": {method: final_calls[method] for method in SEARCH_METHODS},
        "status_counts": status_counts,
    }
    failed = (
        terminal != 10
        or configuration
        or leakage
        or api_key_leakage
        or identity
        or duplicates
        or runner_failures
        or gate_missing
        or budget_violations
        or search_backend_violations
        or base_stage_missing
        or base_solve_completed < 1
        or base_failure_unaccounted
        or final_answer_missing
        or raw_nl_binding_failures
        or raw_nl_nonempty_instances != 2
        or any(provider_success[method] == 0 for method in METHODS)
        or any(final_calls[method] != 2 for method in SEARCH_METHODS)
    )
    if failed:
        summary["status"] = "FAIL"
    write_json(SMOKE_SUMMARY_PATH, summary)
    if summary["status"] != "PASS":
        raise RuntimeError(f"Smoke gate failed: {summary}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["smoke"], required=True)
    parser.parse_args()
    print(json.dumps(validate_smoke(), ensure_ascii=False))


if __name__ == "__main__":
    main()
