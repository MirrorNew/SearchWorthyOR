from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    MODEL,
    REASONING_EFFORT,
    TEMPERATURE,
    TERMINAL_STATUSES,
    count_api_key_leaks,
    load_config,
    output_schema_for,
    public_cases,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)


RUN_ROOT = EXPERIMENT_ROOT / "runs" / "formal"
GOLD_PATH = EXPERIMENT_ROOT / "private" / "selected_gold.jsonl"
SCORE_PATH = EXPERIMENT_ROOT / "private" / "formal_scores.jsonl"
REPORT_ROOT = EXPERIMENT_ROOT / "reports"
METHOD_DIRS = {
    "Direct-v2 Base-Solve Gated Search": "direct",
    "CoE": "coe",
    "OptiMUS": "optimus",
    "optiminer-training-free": "optiminer",
    "Search-First Gated Raw-NL": "search_first",
}
SEARCH_METHODS = {"Direct-v2 Base-Solve Gated Search", "Search-First Gated Raw-NL"}


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def action_key(value: Any) -> tuple[tuple[str, int], ...] | None:
    if not isinstance(value, list) or not value:
        return None
    rows: list[tuple[str, int]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            return None
        action_id = item["id"]
        action_value = item.get("value")
        if action_id in seen or not isinstance(action_value, int) or isinstance(action_value, bool):
            return None
        seen.add(action_id)
        rows.append((action_id, action_value))
    return tuple(sorted(rows))


def objective_observed(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("sense") in {"min", "max"}
        and isinstance(value.get("value"), (int, float))
        and not isinstance(value.get("value"), bool)
        and math.isfinite(float(value["value"]))
        and isinstance(value.get("unit"), str)
    )


def objective_correct(value: Any, gold: dict[str, Any]) -> bool:
    if not objective_observed(value) or value["sense"] != gold["objective_sense"]:
        return False
    return any(
        value["unit"] == equivalent.get("unit")
        and isinstance(equivalent.get("value"), (int, float))
        and math.isclose(float(value["value"]), float(equivalent["value"]), rel_tol=0.0, abs_tol=1e-6)
        for equivalent in gold["gold_objective"]["accepted_equivalents"]
    )


def call_metrics(task_dir: Path) -> dict[str, Any]:
    calls = [row for path in sorted(task_dir.glob("attempt_*/api_calls.jsonl")) for row in read_jsonl(path)]
    totals: list[int] = []
    for row in calls:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        total = usage.get("total_tokens")
        if not isinstance(total, int):
            prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
            completion = usage.get("completion_tokens", usage.get("output_tokens"))
            total = prompt + completion if isinstance(prompt, int) and isinstance(completion, int) else None
        if isinstance(total, int):
            totals.append(total)
    violations = sum(
        row.get("requested_model") != MODEL
        or row.get("reasoning_effort") != REASONING_EFFORT
        or row.get("temperature") != TEMPERATURE
        or (row.get("actual_model") is not None and row.get("actual_model") != MODEL)
        for row in calls
    )
    return {
        "calls": len(calls),
        "upstream_attempts": sum(int(row.get("upstream_attempts") or 0) for row in calls),
        "tokens": sum(totals) if len(totals) == len(calls) else None,
        "observed_tokens": sum(totals),
        "usage_missing_calls": len(calls) - len(totals),
        "llm_wall_seconds": sum(float(row.get("wall_seconds") or 0.0) for row in calls),
        "configuration_violations": violations,
    }


def score_one(method: str, output: dict[str, Any], gold: dict[str, Any], schema: dict[str, Any], task_dir: Path) -> dict[str, Any]:
    state = output.get("decision_state")
    state_observed = state in {"RETAIN", "PATCH_CHANGES"}
    applicability = output.get("applicability")
    app_observed = isinstance(applicability, bool)
    patch = output.get("patch", output.get("patch_elements"))
    patch_observed = isinstance(patch, list)
    predicted_patch = Counter(canonical(row) for row in patch) if patch_observed else Counter()
    gold_patch = Counter(canonical(row) for row in gold["gold_patch_elements"])

    actions = action_key(output.get("actions"))
    expected_ids = {str(row["id"]) for row in schema["actions"]}
    action_observed = actions is not None and {item[0] for item in actions} == expected_ids
    gold_actions = {action_key(row) for row in gold["gold_action_set"]}
    action_ok = action_observed and actions in gold_actions
    objective = output.get("objective")
    objective_seen = objective_observed(objective)
    objective_ok = objective_correct(objective, gold)

    state_ok = state_observed and state == gold["decision_state"]
    app_ok = app_observed and applicability is gold["applicability"]
    patch_ok = patch_observed and predicted_patch == gold_patch
    search = output.get("search") if isinstance(output.get("search"), dict) else {}
    gate = output.get("search_gate") if isinstance(output.get("search_gate"), dict) else search.get("gate")
    gate_observed = method in SEARCH_METHODS and isinstance(gate, dict) and gate.get("status") in {"TRIGGERED", "NOT_TRIGGERED"}
    search_triggered = gate.get("status") == "TRIGGERED" if gate_observed else None
    search_trigger_ok = gate_observed and search_triggered is bool(gold["specific_official_rule_required"])
    flags = output.get("failure_flags") if isinstance(output.get("failure_flags"), dict) else {}
    calls = call_metrics(task_dir)
    return {
        "task_id": gold["task_id"],
        "source_task_id": gold["source_task_id"],
        "case_id": gold["case_id"],
        "pair_id": gold["pair_id"],
        "method": method,
        "task_mode": gold["task_mode"],
        "gold_decision_state": gold["decision_state"],
        "gold_applicability": gold["applicability"],
        "changed_factor": gold["changed_factor"],
        "status": output.get("status"),
        "decision_state_observed": state_observed,
        "decision_state_correct": state_ok,
        "applicability_observed": app_observed,
        "applicability_prediction": applicability if app_observed else None,
        "applicability_correct": app_ok,
        "patch_observed": patch_observed,
        "patch_tp": sum((predicted_patch & gold_patch).values()),
        "patch_fp": sum((predicted_patch - gold_patch).values()),
        "patch_fn": sum((gold_patch - predicted_patch).values()),
        "patch_exact": patch_ok,
        "action_observed": action_observed,
        "action_correct": action_ok,
        "objective_observed": objective_seen,
        "objective_correct": objective_ok,
        "final_answer_observed": action_observed and objective_seen,
        "final_answer_joint": action_ok and objective_ok,
        "full_agent_observed": state_observed and app_observed and patch_observed and action_observed and objective_seen,
        "full_agent_joint": state_ok and app_ok and patch_ok and action_ok and objective_ok,
        "search_gate_observed": gate_observed,
        "search_triggered": search_triggered,
        "search_trigger_correct": search_trigger_ok,
        "retrieval_observed": method in SEARCH_METHODS,
        "retrieval_pass": output.get("retrieval_status") == "RETRIEVAL_COMPLETE" if method in SEARCH_METHODS else None,
        "search_count": int(search.get("search_count") or 0),
        "page_open_attempt_count": int(search.get("page_open_attempt_count") or 0),
        "readable_page_count": int(search.get("readable_page_count") or 0),
        "verified_quote_count": int(search.get("verified_quote_count") or 0),
        "provider_failure": bool(flags.get("provider_failure")),
        "runner_failure": bool(flags.get("runner_failure")),
        "retrieval_failure": bool(flags.get("retrieval_failure")),
        "parse_failure": bool(flags.get("parse_failure")),
        "output_contract_failure": bool(flags.get("output_contract_failure")),
        "solver_failure": bool(flags.get("solver_failure")),
        "configuration_violation": bool(flags.get("configuration_violation")) or calls["configuration_violations"] > 0,
        "wall_seconds": (output.get("accounting") or {}).get("wall_total_seconds"),
        **calls,
    }


def binary_metrics(rows: list[dict[str, Any]], correct_key: str, observed_key: str) -> dict[str, Any]:
    observed = [row for row in rows if row[observed_key]]
    correct = sum(bool(row[correct_key]) for row in rows)
    observed_correct = sum(bool(row[correct_key]) for row in observed)
    return {
        "planned_n": len(rows),
        "planned_correct": correct,
        "planned_accuracy": ratio(correct, len(rows)),
        "observed_n": len(observed),
        "observed_correct": observed_correct,
        "observed_accuracy": ratio(observed_correct, len(observed)),
        "not_observed": len(rows) - len(observed),
    }


def applicability_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = binary_metrics(rows, "applicability_correct", "applicability_observed")
    positive = [row for row in rows if row["gold_applicability"]]
    negative = [row for row in rows if not row["gold_applicability"]]
    positive_recall = ratio(sum(row["applicability_prediction"] is True for row in positive), len(positive))
    negative_recall = ratio(sum(row["applicability_prediction"] is False for row in negative), len(negative))
    result.update(
        {
            "positive_recall": positive_recall,
            "negative_recall": negative_recall,
            "balanced_accuracy": (positive_recall + negative_recall) / 2 if positive_recall is not None and negative_recall is not None else None,
        }
    )
    return result


def patch_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [row for row in rows if row["patch_observed"]]
    tp = sum(row["patch_tp"] for row in rows)
    fp = sum(row["patch_fp"] for row in rows)
    fn = sum(row["patch_fn"] for row in rows)
    return {
        "planned_n": len(rows),
        "observed_n": len(observed),
        "not_observed": len(rows) - len(observed),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "exact_correct": sum(row["patch_exact"] for row in rows),
        "exact_match": ratio(sum(row["patch_exact"] for row in rows), len(rows)),
        "observed_exact_match": ratio(sum(row["patch_exact"] for row in observed), len(observed)),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_rows = [row for row in rows if row["retrieval_observed"]]
    token_values = [row["tokens"] for row in rows]
    return {
        "n": len(rows),
        "decision_state": binary_metrics(rows, "decision_state_correct", "decision_state_observed"),
        "applicability": applicability_metrics(rows),
        "patch": patch_metrics(rows),
        "action": binary_metrics(rows, "action_correct", "action_observed"),
        "objective": binary_metrics(rows, "objective_correct", "objective_observed"),
        "final_answer_joint": binary_metrics(rows, "final_answer_joint", "final_answer_observed"),
        "full_agent_joint": binary_metrics(rows, "full_agent_joint", "full_agent_observed"),
        "search_trigger": binary_metrics(rows, "search_trigger_correct", "search_gate_observed"),
        "retrieval_pass": {
            "observed_n": len(retrieval_rows),
            "pass": sum(row["retrieval_pass"] is True for row in retrieval_rows),
            "rate": ratio(sum(row["retrieval_pass"] is True for row in retrieval_rows), len(retrieval_rows)),
        },
        "status_counts": dict(sorted(Counter(str(row["status"]) for row in rows).items())),
        "failures": {key: sum(row[key] for row in rows) for key in ("provider_failure", "runner_failure", "retrieval_failure", "parse_failure", "output_contract_failure", "solver_failure", "configuration_violation")},
        "retrieval": {key: sum(row[key] for row in rows) for key in ("search_count", "page_open_attempt_count", "readable_page_count", "verified_quote_count")},
        "accounting": {
            "calls": sum(row["calls"] for row in rows),
            "upstream_attempts": sum(row["upstream_attempts"] for row in rows),
            "tokens": sum(token_values) if all(isinstance(value, int) for value in token_values) else None,
            "observed_tokens": sum(row["observed_tokens"] for row in rows),
            "usage_missing_calls": sum(row["usage_missing_calls"] for row in rows),
            "llm_wall_seconds": sum(row["llm_wall_seconds"] for row in rows),
            "task_wall_seconds": sum(float(row["wall_seconds"] or 0.0) for row in rows),
        },
    }


def exact_mcnemar(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, index) for index in range(min(wins, losses) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def paired_comparison(rows_by_method: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    direct_name = "Direct-v2 Base-Solve Gated Search"
    other_name = "Search-First Gated Raw-NL"
    direct = {row["case_id"]: row for row in rows_by_method[direct_name]}
    other = {row["case_id"]: row for row in rows_by_method[other_name]}
    wins = sum(direct[key]["final_answer_joint"] and not other[key]["final_answer_joint"] for key in direct)
    losses = sum(other[key]["final_answer_joint"] and not direct[key]["final_answer_joint"] for key in direct)
    return [
        {
            "method_a": direct_name,
            "method_b": other_name,
            "endpoint": "final_answer_joint",
            "a_wins": wins,
            "a_losses": losses,
            "ties": 240 - wins - losses,
            "accuracy_difference_a_minus_b": (wins - losses) / 240,
            "mcnemar_exact_two_sided_p": exact_mcnemar(wins, losses),
        }
    ]


def request_audit() -> dict[str, int]:
    violations = leakage = 0
    forbidden = ("selected_gold", "gold_action_set", "gold_objective", "gold_patch_elements", "official_support", "patched_ir", "solve_result", "\\private\\", "/private/")
    paths = sorted(RUN_ROOT.glob("*/SWOR-R*/attempt_*/llm_calls/*_request.json"))
    for path in paths:
        payload = read_json(path)
        effort = payload.get("reasoning_effort")
        if effort is None and isinstance(payload.get("reasoning"), dict):
            effort = payload["reasoning"].get("effort")
        if payload.get("model") != MODEL or payload.get("temperature") != TEMPERATURE or effort != REASONING_EFFORT:
            violations += 1
        text = json.dumps(payload, ensure_ascii=False).lower()
        if any(marker in text for marker in forbidden):
            leakage += 1
    return {
        "request_files": len(paths),
        "configuration_violations": violations,
        "gold_leakage": leakage,
        "api_key_leakage": count_api_key_leaks(RUN_ROOT),
    }


def report_markdown(summary: dict[str, Any]) -> str:
    def pct(value: float | None) -> str:
        return "NA" if value is None else f"{100 * value:.2f}%"

    lines = [
        "# SearchWorthyOR V1.5.1 五个 Baseline 正式实验报告",
        "",
        "固定实验为 240 个 paired case × 5 方法 = 1,200 个新实例；模型与 provider 锁定为 `gpt-5.6-luna / xhigh / temperature=1 / Shubiaobiao`。",
        "",
        "| 方法 | Search Trigger | Retrieval Pass | Decision State | Patch Exact | Action | Objective | Final Answer Joint | Full Agent Joint |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, strata in summary["methods"].items():
        overall = strata["Overall"]
        trigger = overall["search_trigger"]
        trigger_text = "NOT_OBSERVED" if trigger["observed_n"] == 0 else f"{trigger['planned_correct']}/{trigger['planned_n']} ({pct(trigger['planned_accuracy'])})"
        retrieval = overall["retrieval_pass"]
        retrieval_text = "NOT_OBSERVED" if retrieval["observed_n"] == 0 else f"{retrieval['pass']}/{retrieval['observed_n']} ({pct(retrieval['rate'])})"
        patch = overall["patch"]
        patch_text = "NOT_OBSERVED" if patch["observed_n"] == 0 else f"{patch['exact_correct']}/240 ({pct(patch['exact_match'])})"
        lines.append(
            f"| {method} | {trigger_text} | {retrieval_text} | "
            f"{overall['decision_state']['planned_correct']}/240 ({pct(overall['decision_state']['planned_accuracy'])}) | "
            f"{patch_text} | {overall['action']['planned_correct']}/240 ({pct(overall['action']['planned_accuracy'])}) | "
            f"{overall['objective']['planned_correct']}/240 ({pct(overall['objective']['planned_accuracy'])}) | "
            f"{overall['final_answer_joint']['planned_correct']}/240 ({pct(overall['final_answer_joint']['planned_accuracy'])}) | "
            f"{overall['full_agent_joint']['planned_correct']}/240 ({pct(overall['full_agent_joint']['planned_accuracy'])}) |"
        )
    comparison = summary["paired_comparisons"][0]
    lines.extend(
        [
            "",
            "Decision State、Applicability、Patch 对未显式输出这些字段的原生方法保持 `NOT_OBSERVED`，不从 Action、搜索行为或 Gold 反推。",
            "",
            f"Direct-v2 相对 Search-First 的 Final Answer Joint 差值：{comparison['accuracy_difference_a_minus_b']:+.4f}；McNemar exact p={comparison['mcnemar_exact_two_sided_p']:.6g}。",
            "",
            f"正式终态实例：{summary['acceptance']['formal_instances']}；身份错位：{summary['acceptance']['identity_mismatch']}；配置违规：{summary['acceptance']['configuration_violations']}；Gold 泄漏：{summary['acceptance']['gold_leakage']}。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    public = public_cases()
    gold = {str(row["case_id"]): row for row in read_jsonl(GOLD_PATH)}
    if len(gold) != 240:
        raise RuntimeError("selected scorer-only Gold must contain exactly 240 case rows")
    rows_by_method: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    identity_mismatch = duplicate = 0
    for method, method_dir in METHOD_DIRS.items():
        rows: list[dict[str, Any]] = []
        for case_id in sorted(gold):
            matches = list((RUN_ROOT / method_dir / case_id).glob("unified_output.json"))
            if len(matches) != 1:
                duplicate += max(0, len(matches) - 1)
                raise RuntimeError(f"missing or duplicate terminal output: {method_dir}/{case_id}")
            output = read_json(matches[0])
            if (
                output.get("task_id") != public[case_id]["id"]
                or output.get("case_id") != case_id
                or output.get("method") != method
                or output.get("phase") != "formal"
            ):
                identity_mismatch += 1
                raise RuntimeError(f"formal identity mismatch: {method_dir}/{case_id}")
            if output.get("status") not in TERMINAL_STATUSES:
                raise RuntimeError(f"non-terminal status: {method_dir}/{case_id}")
            rows.append(score_one(method, output, gold[case_id], output_schema_for(public[case_id]), matches[0].parent))
        rows_by_method[method] = rows
        all_rows.extend(rows)

    audit = request_audit()
    configuration_violations = audit["configuration_violations"] + sum(row["configuration_violation"] for row in all_rows)
    acceptance = {
        "formal_instances": len(all_rows),
        "instances_per_method": {method: len(rows) for method, rows in rows_by_method.items()},
        "unique_method_case": len({(row["method"], row["case_id"]) for row in all_rows}),
        "identity_mismatch": identity_mismatch,
        "configuration_violations": configuration_violations,
        "gold_leakage": audit["gold_leakage"],
        "api_key_leakage": audit["api_key_leakage"],
        "duplicate_terminal_outputs": duplicate,
    }
    expected_acceptance = {
        "formal_instances": 1200,
        "instances_per_method": {method: 240 for method in METHOD_DIRS},
        "unique_method_case": 1200,
        "identity_mismatch": 0,
        "configuration_violations": 0,
        "gold_leakage": 0,
        "api_key_leakage": 0,
        "duplicate_terminal_outputs": 0,
    }
    if acceptance != expected_acceptance:
        raise RuntimeError(f"formal acceptance failed: {acceptance}")
    comparisons = paired_comparison(rows_by_method)
    methods: dict[str, Any] = {}
    for method, rows in rows_by_method.items():
        methods[method] = {
            "Overall": aggregate(rows),
            "Single": aggregate([row for row in rows if row["task_mode"] == "single_hop_control"]),
            "Multi": aggregate([row for row in rows if row["task_mode"] == "multi_hop_revision"]),
            "Retain": aggregate([row for row in rows if row["gold_decision_state"] == "RETAIN"]),
            "PatchChanges": aggregate([row for row in rows if row["gold_decision_state"] == "PATCH_CHANGES"]),
        }
    orchestration_path = RUN_ROOT / "orchestration" / "summary.json"
    summary = {
        "schema_version": "searchworthyor.v151.five_baselines.formal_summary.v1",
        "configuration": {**config["model"], "provider": config["provider"]["name"]},
        "scoring_policy": {
            "decision_applicability_patch_not_inferred": True,
            "objective_requires_sense_value_and_accepted_unit": True,
            "action_position_mapping_allowed": False,
            "fixed_denominator_per_method": 240,
        },
        "acceptance": acceptance,
        "request_audit": audit,
        "orchestration": read_json(orchestration_path) if orchestration_path.is_file() else None,
        "methods": methods,
        "paired_comparisons": comparisons,
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    write_jsonl(SCORE_PATH, all_rows)
    write_json(REPORT_ROOT / "summary.json", summary)
    write_json(REPORT_ROOT / "paired_comparisons.json", {"comparisons": comparisons})
    (REPORT_ROOT / "REPORT_zh.md").write_text(report_markdown(summary), encoding="utf-8")
    print(json.dumps({"status": "SCORED", "formal_instances": 1200}, ensure_ascii=False))


if __name__ == "__main__":
    main()
