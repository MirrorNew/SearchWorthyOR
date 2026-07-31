from __future__ import annotations

import argparse
import collections
import importlib.util
import itertools
import json
import math
from pathlib import Path
from typing import Any


TOL = 1e-6


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_solver_backend(dataset_root: Path):
    path = dataset_root / "scripts" / "solver_backend.py"
    spec = importlib.util.spec_from_file_location("searchworthyor_solver_backend", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import solver backend from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_action(value: Any) -> tuple[int | float, ...] | None:
    if not isinstance(value, list):
        return None
    normalized: list[int | float] = []
    for item in value:
        number = float(item)
        if abs(number - round(number)) <= TOL:
            normalized.append(int(round(number)))
        else:
            normalized.append(number)
    return tuple(normalized)


def close(left: Any, right: Any) -> bool:
    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError):
        return False
    return math.isclose(left_value, right_value, rel_tol=TOL, abs_tol=TOL)


def canonical_equal(left: Any, right: Any) -> bool:
    return json.dumps(
        left, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) == json.dumps(
        right, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def rounded(value: Any) -> int | float:
    number = float(value)
    if abs(number - round(number)) <= TOL:
        return int(round(number))
    return round(number, 8)


def canonical_constraint_row(
    constraint: dict[str, Any],
    variable_order: list[str],
) -> tuple[Any, ...]:
    coefficients = [
        float(constraint.get("terms", {}).get(name, 0.0))
        for name in variable_order
    ]
    rhs = float(constraint["rhs"])
    sense = constraint["sense"]
    pivot = next(
        (value for value in coefficients if abs(value) > TOL),
        rhs if abs(rhs) > TOL else 1.0,
    )
    if pivot < 0:
        coefficients = [-value for value in coefficients]
        rhs = -rhs
        sense = {"<=": ">=", ">=": "<=", "==": "=="}[sense]
        pivot = -pivot
    scale = abs(pivot) if abs(pivot) > TOL else 1.0
    return (
        sense,
        *(rounded(value / scale) for value in coefficients),
        rounded(rhs / scale),
    )


def semantic_ir_signature(ir: Any) -> dict[str, Any] | None:
    if not isinstance(ir, dict):
        return None
    try:
        variables = ir["variables"]
        action_projection = list(ir["action_projection"])
        variable_by_name = {row["name"]: row for row in variables}
        remaining = [
            row["name"]
            for row in variables
            if row["name"] not in action_projection
        ]
        variable_order = action_projection + remaining
        if set(variable_order) != set(variable_by_name):
            return None
        domains = [
            (
                variable_by_name[name]["vartype"],
                rounded(variable_by_name[name].get("lb", 0.0)),
                rounded(variable_by_name[name].get("ub", 1.0)),
            )
            for name in variable_order
        ]
        objective = (
            ir["sense"],
            rounded(ir["objective"].get("constant", 0.0)),
            *(
                rounded(ir["objective"]["terms"].get(name, 0.0))
                for name in variable_order
            ),
        )
        constraints = sorted(
            canonical_constraint_row(row, variable_order)
            for row in ir["constraints"]
        )
        return {
            "action_count": len(action_projection),
            "variable_count": len(variable_order),
            "domains": domains,
            "objective": objective,
            "constraints": constraints,
        }
    except (KeyError, TypeError, ValueError):
        return None


def semantic_patch_signature(
    base_ir: Any,
    patched_ir: Any,
) -> dict[str, Any] | None:
    base = semantic_ir_signature(base_ir)
    patched = semantic_ir_signature(patched_ir)
    if base is None or patched is None:
        return None
    base_constraints = collections.Counter(
        json.dumps(row, ensure_ascii=False)
        for row in base["constraints"]
    )
    patched_constraints = collections.Counter(
        json.dumps(row, ensure_ascii=False)
        for row in patched["constraints"]
    )
    return {
        "action_count_before": base["action_count"],
        "action_count_after": patched["action_count"],
        "variables_added": max(
            0, patched["variable_count"] - base["variable_count"]
        ),
        "variables_removed": max(
            0, base["variable_count"] - patched["variable_count"]
        ),
        "domain_changes": [
            [index, before, after]
            for index, (before, after) in enumerate(
                zip(base["domains"], patched["domains"])
            )
            if before != after
        ],
        "objective_changed": base["objective"] != patched["objective"],
        "constraints_added": sorted(
            (patched_constraints - base_constraints).elements()
        ),
        "constraints_removed": sorted(
            (base_constraints - patched_constraints).elements()
        ),
    }


def code_ir_consistent(submission: dict[str, Any]) -> bool:
    usage = submission.get("usage", {})
    execution = usage.get("model_code_execution", {})
    if not execution.get("passed"):
        return False
    code_result = execution.get("result", {})
    trusted = submission.get("gurobi_result", {})
    code_status = code_result.get("status")
    trusted_status = trusted.get("status")
    status_match = (
        code_status == trusted_status
        or (
            code_status == 2
            and trusted_status == "OPTIMAL"
        )
    )
    code_action = normalize_action(
        code_result.get("projected_action")
    )
    trusted_action = normalize_action(
        trusted.get("projected_action")
    )
    trusted_optimal_actions = {
        normalized
        for action in usage.get(
            "trusted_exact_enumeration", {}
        ).get("optimal_actions", [])
        if (normalized := normalize_action(action)) is not None
    }
    action_match = (
        code_action in trusted_optimal_actions
        if trusted_optimal_actions
        else code_action == trusted_action
    )
    return (
        status_match
        and close(code_result.get("objective"), trusted.get("objective"))
        and code_action is not None
        and action_match
    )


def mapping_evidence_consistent(
    submission: dict[str, Any],
    retrieval_required: bool,
) -> bool:
    selected = set(
        str(item) for item in selected_ids(submission)
    )
    patch = submission.get("typed_patch", {})
    operations = patch.get("ops", []) if isinstance(patch, dict) else []
    mappings = submission.get("claim_to_model_mapping", [])
    if not retrieval_required:
        return not selected and not operations and not mappings
    if not selected or not operations or not mappings:
        return False
    references = []
    for row in [*operations, *mappings]:
        if not isinstance(row, dict):
            return False
        evidence_id = row.get("evidence_id")
        if evidence_id:
            references.append(str(evidence_id))
    local_prefixes = (
        "TASK",
        "PUBLIC_TASK",
        "LOCAL",
        "BASE",
        "DERIVED",
    )
    external_references = [
        reference
        for reference in references
        if not reference.upper().startswith(local_prefixes)
    ]
    return bool(external_references) and all(
        reference in selected for reference in external_references
    )


def applicability_all_true(submission: dict[str, Any]) -> bool:
    applicability = submission.get("applicability", {})
    keys = [
        "authority",
        "effective_at_decision_time",
        "jurisdiction_match",
        "subject_match",
        "exception_resolved",
    ]
    return all(applicability.get(key) is True for key in keys)


def projected_feasible_actions(
    ir: Any,
    solver_backend: Any,
) -> set[tuple[int | float, ...]] | None:
    if not isinstance(ir, dict):
        return None
    variables = ir.get("variables", [])
    if (
        len(variables) > 20
        or any(row.get("vartype") != "B" for row in variables)
    ):
        return None
    names = [row["name"] for row in variables]
    actions: set[tuple[int | float, ...]] = set()
    try:
        for bits in itertools.product((0.0, 1.0), repeat=len(names)):
            assignment = dict(zip(names, bits, strict=True))
            inspection = solver_backend.inspect_assignment(
                ir, assignment
            )
            if (
                inspection["max_constraint_violation"] <= TOL
                and inspection["bound_violation"] <= TOL
            ):
                actions.add(
                    solver_backend.project_action(ir, assignment)
                )
    except (KeyError, TypeError, ValueError):
        return None
    return actions


def flatten_retrieved_refs(submission: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for event in submission.get("search_trace", []):
        for result in event.get("results", []):
            if isinstance(result, str):
                candidates = [result]
            else:
                candidates = [result.get("id"), result.get("url")]
            for reference in candidates:
                if reference and reference not in refs:
                    refs.append(reference)
    return refs


def selected_ids(submission: dict[str, Any]) -> list[str]:
    value = submission.get("selected_evidence_ids", [])
    if isinstance(value, str):
        refs = [value]
    else:
        refs = [str(item) for item in value]
    urls = submission.get("selected_urls", [])
    if isinstance(urls, str):
        urls = [urls]
    return refs + [str(item) for item in urls]


def replay_model_ir(
    ir: Any,
    solver_backend: Any,
) -> dict[str, Any] | None:
    if not isinstance(ir, dict) or not ir:
        return None
    try:
        gurobi = solver_backend.solve_gurobi(ir)
        exact = solver_backend.enumerate_optimal_actions(ir)
        return {"gurobi": gurobi, "exact": exact}
    except Exception as exc:  # noqa: BLE001 - recorded as an experiment failure
        return {
            "gurobi": {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"},
            "exact": {"status": "ERROR"},
        }


def replay_ir(
    submission: dict[str, Any],
    solver_backend: Any,
) -> dict[str, Any] | None:
    return replay_model_ir(submission.get("patched_ir"), solver_backend)


def score_one(
    submission: dict[str, Any],
    gold: dict[str, Any],
    dataset_root: Path,
    solver_backend: Any,
) -> dict[str, Any]:
    task_id = submission["task_id"]
    solver_gold = json.loads(
        (dataset_root / "models" / task_id / "solver_results.json").read_text(
            encoding="utf-8"
        )
    )
    gold_base_ir = json.loads(
        (dataset_root / "models" / task_id / "base_ir.json").read_text(
            encoding="utf-8"
        )
    )
    gold_patched_ir = json.loads(
        (dataset_root / "models" / task_id / "patched_ir.json").read_text(
            encoding="utf-8"
        )
    )
    gold_actions = {
        tuple(action) for action in solver_gold["patched"]["exact_enumeration"]["optimal_actions"]
    }
    gold_objective = solver_gold["patched"]["exact_enumeration"]["objective"]
    gold_base_actions = {
        tuple(action)
        for action in solver_gold["base"]["exact_enumeration"][
            "optimal_actions"
        ]
    }
    gold_base_objective = solver_gold["base"]["exact_enumeration"][
        "objective"
    ]
    gold_evidence = gold["applicability"]["selected_evidence_id"]

    retrieved = flatten_retrieved_refs(submission)
    selected = selected_ids(submission)
    reported_result = submission.get("gurobi_result", {})
    action = normalize_action(reported_result.get("projected_action"))
    action_correct = action in gold_actions if action is not None else False
    objective_correct = close(reported_result.get("objective"), gold_objective)
    base_action_correct = (
        action in gold_base_actions if action is not None else False
    )
    base_objective_correct = close(
        reported_result.get("objective"), gold_base_objective
    )
    status_optimal = reported_result.get("status") == "OPTIMAL"
    gold_url = gold.get("source_passport", {}).get("url")
    gold_refs = {gold_evidence}
    if gold_url:
        gold_refs.add(gold_url)
    evidence_hit_at_1 = bool(retrieved) and retrieved[0] in gold_refs
    evidence_hit_at_5 = bool(gold_refs & set(retrieved[:5]))
    evidence_selected = bool(gold_refs & set(selected))
    applicability_present = bool(submission.get("applicability"))
    typed_patch = submission.get("typed_patch")
    typed_patch_present = (
        isinstance(typed_patch, dict)
        and isinstance(typed_patch.get("ops"), list)
        and bool(typed_patch["ops"])
    )
    claim_mapping_present = bool(submission.get("claim_to_model_mapping"))
    trace_complete = (
        applicability_present and typed_patch_present and claim_mapping_present
    )
    base_ir_exact_match = canonical_equal(
        submission.get("base_ir"), gold_base_ir
    )
    patched_ir_exact_match = canonical_equal(
        submission.get("patched_ir"), gold_patched_ir
    )
    applicability_exact_match = canonical_equal(
        submission.get("applicability"), gold.get("applicability")
    )
    typed_patch_exact_match = canonical_equal(
        submission.get("typed_patch"), gold.get("typed_patch")
    )
    claim_mapping_exact_match = canonical_equal(
        submission.get("claim_to_model_mapping"),
        gold.get("claim_to_model_mapping"),
    )

    base_replay = replay_model_ir(submission.get("base_ir"), solver_backend)
    replay = replay_ir(submission, solver_backend)
    replay_action_correct = False
    replay_objective_correct = False
    replay_executable = False
    predicted_action_jaccard = None
    if replay is not None:
        replay_executable = replay["gurobi"].get("status") == "OPTIMAL"
        replay_objective_correct = close(
            replay["gurobi"].get("objective"), gold_objective
        )
        replay_action = normalize_action(replay["gurobi"].get("projected_action"))
        replay_action_correct = replay_action in gold_actions if replay_action else False
        predicted = {
            tuple(row) for row in replay["exact"].get("optimal_actions", [])
        }
        union = predicted | gold_actions
        predicted_action_jaccard = (
            len(predicted & gold_actions) / len(union) if union else 1.0
        )

    condition = submission.get("condition")
    retrieval_required = condition in {
        "corpus_search",
        "live_web",
        "oracle_evidence",
        "distractor_only",
        "counterfactual_swap",
    }
    outcome_match = status_optimal and action_correct and objective_correct
    base_outcome_match = (
        status_optimal
        and base_action_correct
        and base_objective_correct
    )
    replay_available = replay is not None
    model_success = (
        outcome_match
        and replay_available
        and replay_executable
        and replay_action_correct
        and replay_objective_correct
    )
    strict_e2e = (
        model_success
        and trace_complete
        and (evidence_selected if retrieval_required else True)
        and base_ir_exact_match
        and patched_ir_exact_match
        and applicability_exact_match
        and typed_patch_exact_match
        and claim_mapping_exact_match
    )

    reasoning_reported_high = (
        submission.get("requested_reasoning_effort") == "high"
        and not submission.get("reasoning_fallback", False)
    )
    reasoning_validated = (
        reasoning_reported_high
        and submission.get("reasoning_metadata_verified", False) is True
    )
    predicted_base_signature = semantic_ir_signature(
        submission.get("base_ir")
    )
    predicted_patched_signature = semantic_ir_signature(
        submission.get("patched_ir")
    )
    gold_base_signature = semantic_ir_signature(gold_base_ir)
    gold_patched_signature = semantic_ir_signature(gold_patched_ir)
    semantic_base_ir_match = (
        predicted_base_signature is not None
        and predicted_base_signature == gold_base_signature
    )
    semantic_patched_ir_match = (
        predicted_patched_signature is not None
        and predicted_patched_signature == gold_patched_signature
    )
    predicted_patch_signature = semantic_patch_signature(
        submission.get("base_ir"), submission.get("patched_ir")
    )
    gold_patch_signature = semantic_patch_signature(
        gold_base_ir, gold_patched_ir
    )
    semantic_patch_match = (
        predicted_patch_signature is not None
        and predicted_patch_signature == gold_patch_signature
    )
    model_structurally_changed = (
        predicted_base_signature is not None
        and predicted_patched_signature is not None
        and predicted_base_signature != predicted_patched_signature
    )
    generated_code_ir_consistent = code_ir_consistent(submission)
    claim_evidence_consistent = mapping_evidence_consistent(
        submission, retrieval_required
    )
    applicability_valid = (
        applicability_all_true(submission)
        if retrieval_required
        else not submission.get("selected_evidence_ids")
    )
    predicted_base_actions = (
        {
            tuple(row)
            for row in base_replay["exact"].get("optimal_actions", [])
        }
        if base_replay is not None
        else set()
    )
    base_model_success = (
        base_replay is not None
        and base_replay["gurobi"].get("status") == "OPTIMAL"
        and base_replay["exact"].get("complete") is True
        and predicted_base_actions == gold_base_actions
        and close(
            base_replay["gurobi"].get("objective"),
            gold_base_objective,
        )
        and semantic_base_ir_match
    )
    semantic_e2e = (
        outcome_match
        and evidence_selected
        and semantic_base_ir_match
        and semantic_patched_ir_match
        and semantic_patch_match
        and generated_code_ir_consistent
        and claim_evidence_consistent
        and applicability_valid
    )
    predicted_feasible_actions = projected_feasible_actions(
        submission.get("patched_ir"), solver_backend
    )
    gold_feasible_actions = projected_feasible_actions(
        gold_patched_ir, solver_backend
    )
    projected_feasible_set_match = (
        predicted_feasible_actions is not None
        and predicted_feasible_actions == gold_feasible_actions
    )
    predicted_optimal_actions = (
        {
            tuple(row)
            for row in replay["exact"].get("optimal_actions", [])
        }
        if replay is not None
        else set()
    )
    optimal_action_set_match = (
        bool(predicted_optimal_actions)
        and predicted_optimal_actions == gold_actions
    )
    decision_changed_from_base = (
        bool(predicted_optimal_actions)
        and not (predicted_optimal_actions & gold_base_actions)
    )
    decision_model_equivalent = (
        projected_feasible_set_match
        and optimal_action_set_match
        and replay_objective_correct
    )
    decision_e2e = (
        decision_model_equivalent
        and evidence_selected
        and semantic_base_ir_match
        and generated_code_ir_consistent
        and claim_evidence_consistent
        and applicability_valid
    )
    evidence_driven_model_change = (
        model_structurally_changed
        and decision_changed_from_base
        and evidence_selected
        and model_success
    )
    return {
        "task_id": task_id,
        "baseline": submission.get("baseline"),
        "condition": condition,
        "reasoning_reported_high": reasoning_reported_high,
        "reasoning_validated": reasoning_validated,
        "evidence_hit_at_1": evidence_hit_at_1,
        "evidence_hit_at_5": evidence_hit_at_5,
        "evidence_selected": evidence_selected,
        "evidence_match_mode": "exact_document_id_or_url",
        "reported_gurobi_optimal": status_optimal,
        "action_correct": action_correct,
        "objective_correct": objective_correct,
        "base_action_correct": base_action_correct,
        "base_objective_correct": base_objective_correct,
        "base_outcome_match": base_outcome_match,
        "outcome_match": outcome_match,
        "replay_available": replay_available,
        "trace_complete": trace_complete,
        "base_ir_exact_match": base_ir_exact_match,
        "patched_ir_exact_match": patched_ir_exact_match,
        "applicability_exact_match": applicability_exact_match,
        "typed_patch_exact_match": typed_patch_exact_match,
        "claim_mapping_exact_match": claim_mapping_exact_match,
        "semantic_base_ir_match": semantic_base_ir_match,
        "semantic_patched_ir_match": semantic_patched_ir_match,
        "semantic_patch_match": semantic_patch_match,
        "model_structurally_changed": model_structurally_changed,
        "generated_code_ir_consistent": generated_code_ir_consistent,
        "claim_evidence_consistent": claim_evidence_consistent,
        "applicability_valid": applicability_valid,
        "base_model_success": base_model_success,
        "semantic_e2e": semantic_e2e,
        "projected_feasible_set_match": projected_feasible_set_match,
        "optimal_action_set_match": optimal_action_set_match,
        "decision_changed_from_base": decision_changed_from_base,
        "decision_model_equivalent": decision_model_equivalent,
        "decision_e2e": decision_e2e,
        "evidence_driven_model_change": evidence_driven_model_change,
        "model_success": model_success,
        "strict_e2e": strict_e2e,
        "base_replay": base_replay,
        "replay": replay,
        "replay_action_jaccard": predicted_action_jaccard,
        "gold_objective": gold_objective,
        "gold_actions": [list(action) for action in sorted(gold_actions)],
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[(str(row["baseline"]), str(row["condition"]))].append(row)
    metrics = [
        "reasoning_reported_high",
        "reasoning_validated",
        "evidence_hit_at_1",
        "evidence_hit_at_5",
        "evidence_selected",
        "reported_gurobi_optimal",
        "action_correct",
        "objective_correct",
        "base_action_correct",
        "base_objective_correct",
        "base_outcome_match",
        "outcome_match",
        "replay_available",
        "trace_complete",
        "base_ir_exact_match",
        "patched_ir_exact_match",
        "applicability_exact_match",
        "typed_patch_exact_match",
        "claim_mapping_exact_match",
        "semantic_base_ir_match",
        "semantic_patched_ir_match",
        "semantic_patch_match",
        "model_structurally_changed",
        "generated_code_ir_consistent",
        "claim_evidence_consistent",
        "applicability_valid",
        "base_model_success",
        "semantic_e2e",
        "projected_feasible_set_match",
        "optimal_action_set_match",
        "decision_changed_from_base",
        "decision_model_equivalent",
        "decision_e2e",
        "evidence_driven_model_change",
        "model_success",
        "strict_e2e",
    ]
    result = {}
    for key, group in sorted(grouped.items()):
        result["|".join(key)] = {
            "n": len(group),
            **{
                metric: sum(bool(row[metric]) for row in group) / len(group)
                for metric in metrics
            },
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--submissions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    gold_rows = read_jsonl(args.dataset_root / "private" / "gold.jsonl")
    gold_by_id = {row["id"]: row for row in gold_rows}
    submissions = read_jsonl(args.submissions)
    solver_backend = load_solver_backend(args.dataset_root)

    scored = []
    for submission in submissions:
        task_id = submission.get("task_id")
        if task_id not in gold_by_id:
            raise ValueError(f"Unknown task_id: {task_id}")
        scored.append(
            score_one(
                submission,
                gold_by_id[task_id],
                args.dataset_root,
                solver_backend,
            )
        )
    output = {"summary": aggregate(scored), "rows": scored}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
