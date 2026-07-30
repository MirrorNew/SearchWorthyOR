#!/usr/bin/env python3
"""Independent blind verifier for the frozen supplemental reserve2 pool."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from source_review_b_verify import (
    TOL,
    assignment_checks,
    canonical_json_sha256,
    file_sha256,
    normalized_text_sha256,
    objective_value,
    read_json,
    read_jsonl,
    solve_with_copt,
    solve_with_gurobi,
    verify_stored_solver,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT.parents[1]
BENCHMARK_PATH = WORKFLOW_ROOT / "benchmark" / "nlp4lp.jsonl"
AUDIT_LOG = ROOT / "staging" / "supplemental_reserve2_audit.jsonl"
MANIFEST_PATH = (
    ROOT / "staging" / "supplemental_reserve2_certification_manifest.json"
)
ARTIFACT_ROOT = (
    ROOT / "staging" / "certified_sources" / "supplemental_reserve2"
)
ARTIFACT_FILENAMES = {
    "source_snapshot": "source_snapshot.json",
    "semantic_mapping": "semantic_mapping.json",
    "canonical_ir": "canonical_ir.json",
    "solver_certificate": "solver_certificate.json",
}

# Filled only after the independent semantic pass. An empty mapping never turns
# a generator status into a pass; mechanical and semantic checks still run.
SEMANTIC_REJECTIONS: dict[tuple[str, str], list[str]] = {}


def load_rows() -> list[dict[str, Any]]:
    return [
        row
        for row in read_jsonl(AUDIT_LOG)
        if row.get("status") == "unchanged_pass"
    ]


def load_benchmark_problems() -> dict[str, str]:
    return {row["id"]: row["problem"] for row in read_jsonl(BENCHMARK_PATH)}


def artifact_paths(row: dict[str, Any]) -> dict[str, Path]:
    folder = ARTIFACT_ROOT / row["source_id"]
    return {
        name: folder / filename for name, filename in ARTIFACT_FILENAMES.items()
    }


def verify_projection_contract(
    ir: dict[str, Any], certificate: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    contract = certificate.get("action_projection_contract")
    if not isinstance(contract, dict):
        return ["action_projection_contract:missing"]
    if contract.get("variable_order") != ir["action_projection"]:
        errors.append("action_projection_contract:variable_order_mismatch")
    if contract.get("continuous_preserved_as_float") is not True:
        errors.append("action_projection_contract:continuous_policy_false")
    if contract.get("integer_and_binary_emitted_as_int") is not True:
        errors.append("action_projection_contract:integer_policy_false")
    variable_by_name = {variable["name"]: variable for variable in ir["variables"]}
    expected_types = [
        "float" if variable_by_name[name]["vartype"] == "C" else "int"
        for name in ir["action_projection"]
    ]
    for solver_name in ("gurobi", "copt"):
        stored = certificate[solver_name]
        if stored.get("projected_action_types") != expected_types:
            errors.append(
                f"{solver_name}:projected_action_types_mismatch"
            )
        for name, value in zip(
            ir["action_projection"], stored["projected_action"]
        ):
            vartype = variable_by_name[name]["vartype"]
            if vartype == "C" and type(value) is not float:
                errors.append(
                    f"{solver_name}:{name}:continuous_action_not_float"
                )
            if vartype in {"I", "B"} and type(value) is not int:
                errors.append(
                    f"{solver_name}:{name}:discrete_action_not_int"
                )
    return errors


def verify_row(
    row: dict[str, Any],
    manifest_artifacts: dict[str, str],
    benchmark_problems: dict[str, str],
) -> dict[str, Any]:
    errors: list[str] = []
    paths = artifact_paths(row)
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"{name}:missing")
    if errors:
        return {
            "source_dataset": row["source_dataset"],
            "source_id": row["source_id"],
            "candidate_id": row["candidate_id"],
            "reserve_rank": row["reserve_rank"],
            "passed": False,
            "errors": errors,
        }
    snapshot = read_json(paths["source_snapshot"])
    mapping = read_json(paths["semantic_mapping"])
    ir = read_json(paths["canonical_ir"])
    certificate = read_json(paths["solver_certificate"])
    artifact_hashes: dict[str, str] = {}
    for name, path in paths.items():
        relative = path.relative_to(ROOT).as_posix()
        actual_hash = file_sha256(path)
        artifact_hashes[name] = actual_hash
        if manifest_artifacts.get(relative) != actual_hash:
            errors.append(f"{name}:manifest_file_hash_mismatch")
    expected_problem_hash = row["source_problem_sha256"]
    problem_text = snapshot["problem_text"]
    normalized_hash = normalized_text_sha256(problem_text)
    raw_hash = hashlib.sha256(problem_text.encode("utf-8")).hexdigest()
    benchmark_problem = benchmark_problems.get(row["source_id"])
    if benchmark_problem is None:
        errors.append("source_snapshot:benchmark_source_missing")
    elif problem_text != benchmark_problem:
        errors.append("source_snapshot:benchmark_text_mismatch")
    for label, actual in (
        ("snapshot_normalized", normalized_hash),
        (
            "snapshot_declared",
            snapshot["normalized_source_sha256_recomputed"],
        ),
        ("snapshot_source_hash", snapshot["source_hash"]),
        ("mapping_problem_hash", mapping["problem_sha256"]),
        ("ir_problem_hash", ir["source_problem_sha256"]),
    ):
        if actual != expected_problem_hash:
            errors.append(f"{label}:problem_hash_mismatch")
    if raw_hash != snapshot["raw_text_sha256"]:
        errors.append("source_snapshot:raw_text_hash_mismatch")
    ir_hash = canonical_json_sha256(ir)
    if ir_hash != row["canonical_ir_sha256"]:
        errors.append("canonical_ir_hash_mismatch")
    for artifact_name, artifact in (
        ("snapshot", snapshot),
        ("mapping", mapping),
        ("ir", ir),
    ):
        if artifact["source_id"] != row["source_id"]:
            errors.append(f"{artifact_name}:source_id_mismatch")
    for artifact_name, artifact in (("snapshot", snapshot), ("ir", ir)):
        if artifact["source_dataset"] != row["source_dataset"]:
            errors.append(f"{artifact_name}:source_dataset_mismatch")
        if artifact["candidate_id"] != row["candidate_id"]:
            errors.append(f"{artifact_name}:candidate_id_mismatch")
    if mapping["candidate_id"] != row["candidate_id"]:
        errors.append("mapping:candidate_id_mismatch")
    if snapshot["reserve_rank"] != row["reserve_rank"]:
        errors.append("snapshot:reserve_rank_mismatch")
    variable_names = [variable["name"] for variable in ir["variables"]]
    if variable_names != ir["action_projection"]:
        errors.append("ir:action_projection_not_all_variables_in_ir_order")
    if len(variable_names) != len(set(variable_names)):
        errors.append("ir:duplicate_variable_name")
    for constraint in ir["constraints"]:
        if not set(constraint["terms"]).issubset(variable_names):
            errors.append(f"ir:{constraint['name']}:unknown_variable")
    if not set(ir["objective"]["terms"]).issubset(variable_names):
        errors.append("ir:objective_unknown_variable")
    errors.extend(verify_projection_contract(ir, certificate))
    for solver_name in ("gurobi", "copt"):
        errors.extend(
            verify_stored_solver(solver_name, ir, certificate[solver_name])
        )
    stored_objective = float(certificate["gurobi"]["objective"])
    if abs(stored_objective - float(certificate["copt"]["objective"])) > TOL:
        errors.append("stored_solver_objectives_disagree")
    if abs(stored_objective - float(row["certified_objective"])) > TOL:
        errors.append("audit_certified_objective_mismatch")
    try:
        gurobi_objective, gurobi_assignment, gurobi_status = solve_with_gurobi(
            ir
        )
        if gurobi_status != "OPTIMAL":
            errors.append(f"independent_gurobi_status:{gurobi_status}")
        gurobi_projection = [
            gurobi_assignment[name] for name in ir["action_projection"]
        ]
        if assignment_checks(ir, gurobi_assignment, gurobi_projection):
            errors.append("independent_gurobi_assignment_invalid")
        if abs(gurobi_objective - stored_objective) > TOL:
            errors.append("independent_gurobi_objective_mismatch")
    except Exception as exc:  # pragma: no cover - diagnostic path
        gurobi_objective = float("nan")
        errors.append(f"independent_gurobi_error:{type(exc).__name__}:{exc}")
    try:
        copt_objective, copt_assignment, copt_status = solve_with_copt(ir)
        if copt_status != "OPTIMAL":
            errors.append(f"independent_copt_status:{copt_status}")
        copt_projection = [
            copt_assignment[name] for name in ir["action_projection"]
        ]
        if assignment_checks(ir, copt_assignment, copt_projection):
            errors.append("independent_copt_assignment_invalid")
        if abs(copt_objective - stored_objective) > TOL:
            errors.append("independent_copt_objective_mismatch")
    except Exception as exc:  # pragma: no cover - diagnostic path
        copt_objective = float("nan")
        errors.append(f"independent_copt_error:{type(exc).__name__}:{exc}")
    return {
        "source_dataset": row["source_dataset"],
        "source_id": row["source_id"],
        "candidate_id": row["candidate_id"],
        "reserve_rank": row["reserve_rank"],
        "problem_hash": normalized_hash,
        "canonical_ir_hash": ir_hash,
        "artifact_file_hashes": artifact_hashes,
        "stored_objective": stored_objective,
        "independent_gurobi_objective": gurobi_objective,
        "independent_copt_objective": copt_objective,
        "passed": not errors,
        "errors": errors,
    }


def print_semantic_packet(
    rows: list[dict[str, Any]], offset: int
) -> None:
    for index, row in enumerate(rows, start=offset + 1):
        paths = artifact_paths(row)
        snapshot = read_json(paths["source_snapshot"])
        mapping = read_json(paths["semantic_mapping"])
        ir = read_json(paths["canonical_ir"])
        certificate = read_json(paths["solver_certificate"])
        print(
            f"\n### {index} rank={row['reserve_rank']} "
            f"{row['candidate_id']} {row['source_id']}"
        )
        print(f"TEXT: {snapshot['problem_text']}")
        print("VARS: " + json.dumps(ir["variables"], ensure_ascii=False))
        print(
            "OBJ: "
            + json.dumps(
                {"sense": ir["sense"], **ir["objective"]},
                ensure_ascii=False,
            )
        )
        print(
            "CONS: " + json.dumps(mapping["constraints"], ensure_ascii=False)
        )
        print(
            "PROJECTION: "
            + json.dumps(
                {
                    "names": ir["action_projection"],
                    "gurobi": certificate["gurobi"]["projected_action"],
                    "copt": certificate["copt"]["projected_action"],
                },
                ensure_ascii=False,
            )
        )
        print(
            "INTERPRETATION: "
            + json.dumps(
                mapping.get("interpretation_decisions", []),
                ensure_ascii=False,
            )
        )


def all_manifest_checks(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    artifact_checks = []
    for relative, expected in manifest["artifacts"].items():
        path = ROOT / relative
        artifact_checks.append(
            {
                "path": relative,
                "passed": path.is_file() and file_sha256(path) == expected,
            }
        )
    input_checks = []
    for relative, expected in manifest["inputs"].items():
        path = (
            WORKFLOW_ROOT / relative
            if relative.startswith("benchmark/")
            else ROOT / relative
        )
        input_checks.append(
            {
                "path": relative,
                "passed": path.is_file() and file_sha256(path) == expected,
            }
        )
    return artifact_checks, input_checks


def checks_for_result(
    result: dict[str, Any], semantic_reasons: list[str]
) -> dict[str, bool]:
    mechanical_errors = result["errors"]

    def lacks(fragment: str) -> bool:
        return not any(fragment in error for error in mechanical_errors)

    return {
        "problem_hash_verified": lacks("problem_hash_mismatch")
        and lacks("raw_text_hash_mismatch")
        and lacks("benchmark_text_mismatch")
        and lacks("benchmark_source_missing"),
        "artifact_hashes_verified": lacks("manifest_file_hash_mismatch"),
        "ir_hash_verified": lacks("canonical_ir_hash_mismatch"),
        "semantic_mapping_verified": not semantic_reasons,
        "action_projection_verified": lacks("projected_action")
        and lacks("action_projection"),
        "stored_gurobi_certificate_verified": not any(
            error.startswith("gurobi:") for error in mechanical_errors
        ),
        "stored_copt_certificate_verified": not any(
            error.startswith("copt:") for error in mechanical_errors
        ),
        "independent_gurobi_resolve_verified": not any(
            error.startswith("independent_gurobi")
            for error in mechanical_errors
        ),
        "independent_copt_resolve_verified": not any(
            error.startswith("independent_copt")
            for error in mechanical_errors
        ),
    }


def write_review(
    results: list[dict[str, Any]],
    artifact_checks: list[dict[str, Any]],
    input_checks: list[dict[str, Any]],
) -> None:
    review_rows = []
    for result in results:
        key = (result["source_dataset"], result["source_id"])
        semantic_reasons = SEMANTIC_REJECTIONS.get(key, [])
        reasons = [*result["errors"], *semantic_reasons]
        review_rows.append(
            {
                "source_dataset": result["source_dataset"],
                "source_id": result["source_id"],
                "source_group": "supplemental_reserve2",
                "source_list": "reserve2",
                "candidate_id": result["candidate_id"],
                "reserve_rank": result["reserve_rank"],
                "decision": "pass" if not reasons else "reject",
                "reasons": reasons,
                "source_problem_sha256": result["problem_hash"],
                "canonical_ir_sha256": result["canonical_ir_hash"],
                "artifact_sha256": result["artifact_file_hashes"],
                "certified_objective": result["stored_objective"],
                "independent_objectives": {
                    "gurobi": result["independent_gurobi_objective"],
                    "copt": result["independent_copt_objective"],
                },
                "solver_versions": {"gurobi": "12.0.2", "copt": "8.0.5"},
                "checks": checks_for_result(result, semantic_reasons),
            }
        )
    output_path = ROOT / "audits" / "source_review_b_reserve2.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in review_rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    summary = {
        "schema_version": "1.0",
        "reviewer": "independent_blind_source_review_b",
        "completed_at_utc": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "scope": {
            "source_group": "supplemental_reserve2",
            "located_rows": 40,
            "reviewed_rows": len(review_rows),
            "unique_source_keys": len(
                {
                    (row["source_dataset"], row["source_id"])
                    for row in review_rows
                }
            ),
            "reserve_rank_min": min(row["reserve_rank"] for row in review_rows),
            "reserve_rank_max": max(row["reserve_rank"] for row in review_rows),
        },
        "decisions": {
            "pass": sum(row["decision"] == "pass" for row in review_rows),
            "reject": sum(row["decision"] == "reject" for row in review_rows),
            "rejected_source_keys": [
                {
                    "source_dataset": row["source_dataset"],
                    "source_id": row["source_id"],
                }
                for row in review_rows
                if row["decision"] == "reject"
            ],
        },
        "verification": {
            "review_jsonl_sha256": file_sha256(output_path),
            "benchmark_snapshot_exact_matches": sum(
                row["checks"]["problem_hash_verified"] for row in review_rows
            ),
            "row_artifact_files_hash_verified": sum(
                4 if row["checks"]["artifact_hashes_verified"] else 0
                for row in review_rows
            ),
            "manifest_artifacts_checked": len(artifact_checks),
            "manifest_artifacts_passed": sum(
                item["passed"] for item in artifact_checks
            ),
            "manifest_inputs_checked": len(input_checks),
            "manifest_inputs_passed": sum(
                item["passed"] for item in input_checks
            ),
            "mechanical_certificate_rows_passed": sum(
                result["passed"] for result in results
            ),
            "independent_gurobi_resolves_passed": sum(
                row["checks"]["independent_gurobi_resolve_verified"]
                for row in review_rows
            ),
            "independent_copt_resolves_passed": sum(
                row["checks"]["independent_copt_resolve_verified"]
                for row in review_rows
            ),
            "solver_versions": {"gurobi": "12.0.2", "copt": "8.0.5"},
        },
        "review_boundaries": {
            "historical_answer_used": False,
            "historical_code_used": False,
            "generator_status_used_as_decision": False,
            "other_source_redteam_reviews_read": False,
            "original_78_review_modified": False,
        },
    }
    summary_path = (
        ROOT / "audits" / "source_review_b_reserve2_summary.json"
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic-packet", action="store_true")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--write-review", action="store_true")
    args = parser.parse_args()
    rows = load_rows()
    selected_rows = rows[args.offset :]
    if args.limit is not None:
        selected_rows = selected_rows[: args.limit]
    if args.semantic_packet:
        print_semantic_packet(selected_rows, args.offset)
        return 0
    manifest = read_json(MANIFEST_PATH)
    benchmark_problems = load_benchmark_problems()
    results = [
        verify_row(row, manifest["artifacts"], benchmark_problems)
        for row in selected_rows
    ]
    artifact_checks, input_checks = all_manifest_checks(manifest)
    if args.verbose:
        for result in results:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for result in results:
            if not result["passed"]:
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    summary = {
        "checked": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "unique_source_keys": len(
            {(result["source_dataset"], result["source_id"]) for result in results}
        ),
        "manifest_artifacts_checked": len(artifact_checks),
        "manifest_artifacts_passed": sum(
            item["passed"] for item in artifact_checks
        ),
        "manifest_inputs_checked": len(input_checks),
        "manifest_inputs_passed": sum(item["passed"] for item in input_checks),
    }
    if args.write_review:
        if args.offset != 0 or args.limit is not None:
            raise ValueError("--write-review requires all 40 rows")
        write_review(results, artifact_checks, input_checks)
    print(json.dumps({"summary": summary}, ensure_ascii=False, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
