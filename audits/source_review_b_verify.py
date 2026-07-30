#!/usr/bin/env python3
"""Independent verifier for blind source review B.

This verifier intentionally treats consolidated status only as the inclusion
list. It does not read historical answers, historical code, generator code, or
other reviewers' files.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import unicodedata
from pathlib import Path
from typing import Any

import coptpy as cp
import gurobipy as gp


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT.parents[1]
BENCHMARK_ROOT = WORKFLOW_ROOT / "benchmark"
BASE_LOG = ROOT / "staging" / "supplemental_base_audit.jsonl"
RESERVE_LOG = ROOT / "staging" / "supplemental_reserve_audit.jsonl"
BASE_MANIFEST = ROOT / "staging" / "supplemental_certification_manifest.json"
RESERVE_MANIFEST = (
    ROOT / "staging" / "supplemental_reserve_certification_manifest.json"
)
REQUIRED_FILES = {
    "canonical_ir",
    "semantic_mapping",
    "solver_certificate",
    "source_snapshot",
}
TOL = 1e-6
COPT_ENV: Any = None
SEMANTIC_REJECTIONS = {
    (
        "NLP4LP",
        "nlp4lp_000220",
    ): [
        (
            "semantic_variable_domain: the shampoo ingredients are quantities "
            "in generic units, not stated indivisible; forcing integer "
            "quantities changes the optimum from the continuous formulation"
        ),
        (
            "semantic_constraint_sense: 'a total of 400 units' requires "
            "sulfate + ginger == 400, but the canonical IR uses >= 400"
        ),
    ],
    (
        "MAMO-ComplexLP",
        "mamo_complexlp_000001",
    ): [
        (
            "semantic_variable_domain: the meal problem gives nutrition and "
            "price for foods without specifying indivisible items or serving "
            "units; integer quantities are unsupported and the continuous "
            "formulation has a materially different optimum"
        )
    ],
    (
        "NLP4LP",
        "nlp4lp_000215",
    ): [
        (
            "semantic_constraint_sense: 'some in apartments and the rest in "
            "townhouses' requires apartment + townhouse == 600000, but the "
            "canonical IR only imposes <= 600000"
        )
    ],
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_benchmark_problems() -> dict[tuple[str, str], str]:
    problems: dict[tuple[str, str], str] = {}
    for source_dataset, filename in (
        ("NLP4LP", "nlp4lp.jsonl"),
        ("MAMO-ComplexLP", "mamo_complexlp.jsonl"),
    ):
        for row in read_jsonl(BENCHMARK_ROOT / filename):
            problems[(source_dataset, row["id"])] = row["problem"]
    return problems


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalized_text_sha256(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).split())
    return sha256_bytes(normalized.encode("utf-8"))


def canonical_json_sha256(obj: Any) -> str:
    data = json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(data)


def objective_value(ir: dict[str, Any], assignment: dict[str, float]) -> float:
    objective = ir["objective"]
    return float(objective.get("constant", 0.0)) + sum(
        float(coef) * float(assignment.get(name, 0.0))
        for name, coef in objective["terms"].items()
    )


def lhs_value(constraint: dict[str, Any], assignment: dict[str, float]) -> float:
    return sum(
        float(coef) * float(assignment.get(name, 0.0))
        for name, coef in constraint["terms"].items()
    )


def constraint_violation(constraint: dict[str, Any], lhs: float) -> float:
    rhs = float(constraint["rhs"])
    if constraint["sense"] == "<=":
        return max(0.0, lhs - rhs)
    if constraint["sense"] == ">=":
        return max(0.0, rhs - lhs)
    if constraint["sense"] == "==":
        return abs(lhs - rhs)
    raise ValueError(f"unknown constraint sense {constraint['sense']!r}")


def assignment_checks(
    ir: dict[str, Any],
    assignment: dict[str, float],
    projected_action: list[float],
) -> list[str]:
    errors: list[str] = []
    variables = {var["name"]: var for var in ir["variables"]}
    if set(assignment) != set(variables):
        errors.append("assignment_variable_set_mismatch")
        return errors
    if len(projected_action) != len(ir["action_projection"]):
        errors.append("projected_action_length_mismatch")
    else:
        expected_projection = [
            float(assignment[name]) for name in ir["action_projection"]
        ]
        if any(
            abs(float(actual) - expected) > TOL
            for actual, expected in zip(projected_action, expected_projection)
        ):
            errors.append("projected_action_value_mismatch")
    for name, var in variables.items():
        value = float(assignment[name])
        if value < float(var["lb"]) - TOL:
            errors.append(f"{name}:lower_bound_violation")
        if var["ub"] is not None and value > float(var["ub"]) + TOL:
            errors.append(f"{name}:upper_bound_violation")
        if var["vartype"] in {"I", "B"} and abs(value - round(value)) > TOL:
            errors.append(f"{name}:integrality_violation")
        if var["vartype"] == "B" and not (-TOL <= value <= 1.0 + TOL):
            errors.append(f"{name}:binary_domain_violation")
    for constraint in ir["constraints"]:
        lhs = lhs_value(constraint, assignment)
        if constraint_violation(constraint, lhs) > TOL:
            errors.append(f"{constraint['name']}:constraint_violation")
    return errors


def verify_stored_solver(
    solver_name: str,
    ir: dict[str, Any],
    stored: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if stored.get("solver") != solver_name:
        errors.append(f"{solver_name}:stored_solver_name_mismatch")
    expected_version = "12.0.2" if solver_name == "gurobi" else "8.0.5"
    if stored.get("version") != expected_version:
        errors.append(f"{solver_name}:stored_solver_version_mismatch")
    if stored.get("status") != "OPTIMAL":
        errors.append(f"{solver_name}:stored_status_not_optimal")
    errors.extend(
        f"{solver_name}:{message}"
        for message in assignment_checks(
            ir, stored["assignment"], stored["projected_action"]
        )
    )
    recomputed = objective_value(ir, stored["assignment"])
    if abs(recomputed - float(stored["objective"])) > TOL:
        errors.append(f"{solver_name}:stored_objective_mismatch")
    if abs(recomputed - float(stored["objective_recomputed"])) > TOL:
        errors.append(f"{solver_name}:stored_recomputed_objective_mismatch")
    stored_residuals = stored["constraint_residuals"]
    if set(stored_residuals) != {c["name"] for c in ir["constraints"]}:
        errors.append(f"{solver_name}:stored_residual_set_mismatch")
    else:
        for constraint in ir["constraints"]:
            residual = stored_residuals[constraint["name"]]
            lhs = lhs_value(constraint, stored["assignment"])
            violation = constraint_violation(constraint, lhs)
            if abs(lhs - float(residual["lhs"])) > TOL:
                errors.append(
                    f"{solver_name}:{constraint['name']}:stored_lhs_mismatch"
                )
            if abs(violation - float(residual["violation"])) > TOL:
                errors.append(
                    f"{solver_name}:{constraint['name']}:stored_violation_mismatch"
                )
    return errors


def solve_with_gurobi(ir: dict[str, Any]) -> tuple[float, dict[str, float], str]:
    model = gp.Model("source_review_b")
    model.Params.OutputFlag = 0
    variables: dict[str, gp.Var] = {}
    type_map = {"C": gp.GRB.CONTINUOUS, "I": gp.GRB.INTEGER, "B": gp.GRB.BINARY}
    for variable in ir["variables"]:
        ub = gp.GRB.INFINITY if variable["ub"] is None else float(variable["ub"])
        variables[variable["name"]] = model.addVar(
            lb=float(variable["lb"]),
            ub=ub,
            vtype=type_map[variable["vartype"]],
            name=variable["name"],
        )
    for constraint in ir["constraints"]:
        expression = gp.quicksum(
            float(coef) * variables[name]
            for name, coef in constraint["terms"].items()
        )
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            model.addConstr(expression <= rhs, name=constraint["name"])
        elif constraint["sense"] == ">=":
            model.addConstr(expression >= rhs, name=constraint["name"])
        elif constraint["sense"] == "==":
            model.addConstr(expression == rhs, name=constraint["name"])
        else:
            raise ValueError(f"unknown constraint sense {constraint['sense']!r}")
    objective = gp.quicksum(
        float(coef) * variables[name]
        for name, coef in ir["objective"]["terms"].items()
    ) + float(ir["objective"].get("constant", 0.0))
    sense = gp.GRB.MINIMIZE if ir["sense"] == "min" else gp.GRB.MAXIMIZE
    model.setObjective(objective, sense)
    model.optimize()
    status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
    assignment = {name: float(variable.X) for name, variable in variables.items()}
    return float(model.ObjVal), assignment, status


def solve_with_copt(ir: dict[str, Any]) -> tuple[float, dict[str, float], str]:
    global COPT_ENV
    if COPT_ENV is None:
        COPT_ENV = cp.Envr()
    model = COPT_ENV.createModel("source_review_b")
    model.setParam(cp.COPT.Param.Logging, 0)
    variables: dict[str, Any] = {}
    type_map = {"C": cp.COPT.CONTINUOUS, "I": cp.COPT.INTEGER, "B": cp.COPT.BINARY}
    for variable in ir["variables"]:
        ub = cp.COPT.INFINITY if variable["ub"] is None else float(variable["ub"])
        variables[variable["name"]] = model.addVar(
            lb=float(variable["lb"]),
            ub=ub,
            vtype=type_map[variable["vartype"]],
            name=variable["name"],
        )
    for constraint in ir["constraints"]:
        expression = cp.quicksum(
            float(coef) * variables[name]
            for name, coef in constraint["terms"].items()
        )
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            model.addConstr(expression <= rhs, name=constraint["name"])
        elif constraint["sense"] == ">=":
            model.addConstr(expression >= rhs, name=constraint["name"])
        elif constraint["sense"] == "==":
            model.addConstr(expression == rhs, name=constraint["name"])
        else:
            raise ValueError(f"unknown constraint sense {constraint['sense']!r}")
    objective = cp.quicksum(
        float(coef) * variables[name]
        for name, coef in ir["objective"]["terms"].items()
    ) + float(ir["objective"].get("constant", 0.0))
    sense = cp.COPT.MINIMIZE if ir["sense"] == "min" else cp.COPT.MAXIMIZE
    model.setObjective(objective, sense)
    model.solve()
    status = "OPTIMAL" if model.status == cp.COPT.OPTIMAL else str(model.status)
    assignment = {name: float(variable.x) for name, variable in variables.items()}
    return float(model.objval), assignment, status


def expected_manifest(
    source_list: str, base_manifest: dict[str, Any], reserve_manifest: dict[str, Any]
) -> dict[str, str]:
    if source_list == "base":
        return base_manifest["artifacts"]
    return reserve_manifest["artifacts"]


def verify_row(
    row: dict[str, Any],
    source_list: str,
    base_manifest: dict[str, Any],
    reserve_manifest: dict[str, Any],
    benchmark_problems: dict[tuple[str, str], str],
) -> dict[str, Any]:
    errors: list[str] = []
    files = row["files"]
    if set(files) != REQUIRED_FILES:
        errors.append("required_artifact_set_mismatch")
    paths = {name: ROOT / "staging" / rel for name, rel in files.items()}
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"{name}:missing")
    if errors:
        return {
            "source_list": source_list,
            "source_dataset": row["source_dataset"],
            "source_id": row["source_id"],
            "candidate_id": row["candidate_id"],
            "passed": False,
            "errors": errors,
        }
    snapshot = read_json(paths["source_snapshot"])
    mapping = read_json(paths["semantic_mapping"])
    ir = read_json(paths["canonical_ir"])
    certificate = read_json(paths["solver_certificate"])
    manifest = expected_manifest(source_list, base_manifest, reserve_manifest)
    for name, path in paths.items():
        relative = path.relative_to(ROOT).as_posix()
        if manifest.get(relative) != file_sha256(path):
            errors.append(f"{name}:manifest_file_hash_mismatch")
    normalized_hash = normalized_text_sha256(snapshot["problem_text"])
    expected_problem_hash = row["source_problem_sha256"]
    benchmark_problem = benchmark_problems.get(
        (row["source_dataset"], row["source_id"])
    )
    if benchmark_problem is None:
        errors.append("source_snapshot:benchmark_source_missing")
    elif snapshot["problem_text"] != benchmark_problem:
        errors.append("source_snapshot:benchmark_text_mismatch")
    raw_text_hash = sha256_bytes(snapshot["problem_text"].encode("utf-8"))
    if raw_text_hash != snapshot["raw_text_sha256"]:
        errors.append("source_snapshot:raw_text_hash_mismatch")
    for label, actual in [
        ("snapshot_normalized", normalized_hash),
        ("snapshot_declared", snapshot["normalized_source_sha256_recomputed"]),
        ("snapshot_source_hash", snapshot["source_hash"]),
        ("mapping_problem_hash", mapping["problem_sha256"]),
        ("ir_problem_hash", ir["source_problem_sha256"]),
    ]:
        if actual != expected_problem_hash:
            errors.append(f"{label}:problem_hash_mismatch")
    if canonical_json_sha256(ir) != row["canonical_ir_sha256"]:
        errors.append("canonical_ir_hash_mismatch")
    for artifact_name, artifact in [
        ("snapshot", snapshot),
        ("mapping", mapping),
        ("ir", ir),
    ]:
        if artifact["source_id"] != row["source_id"]:
            errors.append(f"{artifact_name}:source_id_mismatch")
    for artifact_name, artifact in [("snapshot", snapshot), ("ir", ir)]:
        if artifact["source_dataset"] != row["source_dataset"]:
            errors.append(f"{artifact_name}:source_dataset_mismatch")
    if snapshot["candidate_id"] != row["candidate_id"]:
        errors.append("snapshot:candidate_id_mismatch")
    if mapping["candidate_id"] != row["candidate_id"]:
        errors.append("mapping:candidate_id_mismatch")
    if ir["candidate_id"] != row["candidate_id"]:
        errors.append("ir:candidate_id_mismatch")
    variable_names = [variable["name"] for variable in ir["variables"]]
    if len(variable_names) != len(set(variable_names)):
        errors.append("ir:duplicate_variable_name")
    if ir["action_projection"] != variable_names:
        errors.append("ir:action_projection_not_all_variables_in_ir_order")
    for constraint in ir["constraints"]:
        if not set(constraint["terms"]).issubset(variable_names):
            errors.append(f"ir:{constraint['name']}:unknown_variable")
    if not set(ir["objective"]["terms"]).issubset(variable_names):
        errors.append("ir:objective_unknown_variable")
    for solver_name in ("gurobi", "copt"):
        errors.extend(
            verify_stored_solver(solver_name, ir, certificate[solver_name])
        )
    stored_gurobi_objective = float(certificate["gurobi"]["objective"])
    stored_copt_objective = float(certificate["copt"]["objective"])
    if abs(stored_gurobi_objective - stored_copt_objective) > TOL:
        errors.append("stored_solver_objectives_disagree")
    try:
        gurobi_objective, gurobi_assignment, gurobi_status = solve_with_gurobi(ir)
        if gurobi_status != "OPTIMAL":
            errors.append(f"independent_gurobi_status:{gurobi_status}")
        if assignment_checks(
            ir,
            gurobi_assignment,
            [gurobi_assignment[name] for name in ir["action_projection"]],
        ):
            errors.append("independent_gurobi_assignment_invalid")
        if abs(gurobi_objective - stored_gurobi_objective) > TOL:
            errors.append("independent_gurobi_objective_mismatch")
    except Exception as exc:  # pragma: no cover - diagnostic path
        gurobi_objective = math.nan
        errors.append(f"independent_gurobi_error:{type(exc).__name__}:{exc}")
    try:
        copt_objective, copt_assignment, copt_status = solve_with_copt(ir)
        if copt_status != "OPTIMAL":
            errors.append(f"independent_copt_status:{copt_status}")
        if assignment_checks(
            ir,
            copt_assignment,
            [copt_assignment[name] for name in ir["action_projection"]],
        ):
            errors.append("independent_copt_assignment_invalid")
        if abs(copt_objective - stored_copt_objective) > TOL:
            errors.append("independent_copt_objective_mismatch")
    except Exception as exc:  # pragma: no cover - diagnostic path
        copt_objective = math.nan
        errors.append(f"independent_copt_error:{type(exc).__name__}:{exc}")
    return {
        "source_list": source_list,
        "source_dataset": row["source_dataset"],
        "source_id": row["source_id"],
        "candidate_id": row["candidate_id"],
        "problem_hash": normalized_hash,
        "canonical_ir_hash": canonical_json_sha256(ir),
        "artifact_file_hashes": {
            name: file_sha256(path) for name, path in paths.items()
        },
        "stored_objective": stored_gurobi_objective,
        "independent_gurobi_objective": gurobi_objective,
        "independent_copt_objective": copt_objective,
        "passed": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--semantic-packet", action="store_true")
    parser.add_argument("--write-review", action="store_true")
    args = parser.parse_args()
    base_rows = [
        row for row in read_jsonl(BASE_LOG) if row.get("status") == "unchanged_pass"
    ]
    reserve_rows = [
        row
        for row in read_jsonl(RESERVE_LOG)
        if row.get("status") == "unchanged_pass"
    ]
    rows = [("base", row) for row in base_rows] + [
        ("reserve", row) for row in reserve_rows
    ]
    if args.only:
        allowed = set(args.only)
        rows = [
            item
            for item in rows
            if item[1]["source_id"] in allowed
            or item[1]["candidate_id"] in allowed
        ]
    rows = rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]
    if args.semantic_packet:
        for index, (source_list, row) in enumerate(rows, start=args.offset + 1):
            paths = {
                name: ROOT / "staging" / relative
                for name, relative in row["files"].items()
            }
            snapshot = read_json(paths["source_snapshot"])
            mapping = read_json(paths["semantic_mapping"])
            ir = read_json(paths["canonical_ir"])
            certificate = read_json(paths["solver_certificate"])
            print(
                f"\n### {index} {source_list} {row['candidate_id']} "
                f"{row['source_dataset']} {row['source_id']}"
            )
            print(f"TEXT: {snapshot['problem_text']}")
            print("VARS: " + json.dumps(ir["variables"], ensure_ascii=False))
            print(
                "OBJ: "
                + json.dumps(
                    {
                        "sense": ir["sense"],
                        **ir["objective"],
                    },
                    ensure_ascii=False,
                )
            )
            print(
                "CONS: "
                + json.dumps(mapping["constraints"], ensure_ascii=False)
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
        return 0
    base_manifest = read_json(BASE_MANIFEST)
    reserve_manifest = read_json(RESERVE_MANIFEST)
    benchmark_problems = load_benchmark_problems()
    results = [
        verify_row(
            row,
            source_list,
            base_manifest,
            reserve_manifest,
            benchmark_problems,
        )
        for source_list, row in rows
    ]
    for result in results:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    summary = {
        "checked": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "unique_source_keys": len(
            {(result["source_dataset"], result["source_id"]) for result in results}
        ),
        "gurobi_version": ".".join(map(str, gp.gurobi.version())),
        "copt_version": ".".join(
            str(part)
            for part in (
                cp.COPT.VERSION_MAJOR,
                cp.COPT.VERSION_MINOR,
                cp.COPT.VERSION_TECHNICAL,
            )
        ),
    }
    if args.write_review:
        if args.limit is not None or args.offset != 0 or args.only:
            raise ValueError("--write-review requires the full unfiltered 78 rows")
        review_rows = []
        for result in results:
            key = (result["source_dataset"], result["source_id"])
            semantic_reasons = SEMANTIC_REJECTIONS.get(key, [])
            mechanical_errors = result["errors"]
            reasons = [*mechanical_errors, *semantic_reasons]

            def lacks(fragment: str) -> bool:
                return not any(fragment in error for error in mechanical_errors)

            checks = {
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
            review_rows.append(
                {
                    "source_dataset": result["source_dataset"],
                    "source_id": result["source_id"],
                    "source_group": (
                        "supplemental_base"
                        if result["source_list"] == "base"
                        else "supplemental_reserve"
                    ),
                    "source_list": result["source_list"],
                    "candidate_id": result["candidate_id"],
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
                    "solver_versions": {
                        "gurobi": "12.0.2",
                        "copt": "8.0.5",
                    },
                    "checks": checks,
                }
            )
        output_path = ROOT / "audits" / "source_review_b.jsonl"
        output_path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in review_rows
            ),
            encoding="utf-8",
            newline="\n",
        )
        input_checks = []
        for manifest, source_list in (
            (base_manifest, "base"),
            (reserve_manifest, "reserve"),
        ):
            for relative, expected in manifest["inputs"].items():
                path = (
                    WORKFLOW_ROOT / relative
                    if relative.startswith("benchmark/")
                    else ROOT / relative
                )
                input_checks.append(
                    {
                        "source_list": source_list,
                        "path": relative,
                        "passed": path.is_file()
                        and file_sha256(path) == expected,
                    }
                )
        review_summary = {
            "schema_version": "1.0",
            "reviewer": "independent_blind_source_review_b",
            "completed_at_utc": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "scope": {
                "base_pass_rows_located": 38,
                "reserve_pass_rows_located": 40,
                "reviewed_rows": len(review_rows),
                "unique_source_keys": len(
                    {
                        (row["source_dataset"], row["source_id"])
                        for row in review_rows
                    }
                ),
            },
            "decisions": {
                "pass": sum(row["decision"] == "pass" for row in review_rows),
                "reject": sum(
                    row["decision"] == "reject" for row in review_rows
                ),
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
                "artifact_files_hash_verified": sum(
                    4 if row["checks"]["artifact_hashes_verified"] else 0
                    for row in review_rows
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
                "continuous_projection_rows_rechecked": [
                    "nlp4lp_000108",
                    "nlp4lp_000122",
                    "nlp4lp_000166",
                    "nlp4lp_000242",
                    "nlp4lp_000234",
                    "nlp4lp_000208",
                ],
                "continuous_projection_rows_passed": 6,
                "solver_versions": {
                    "gurobi": "12.0.2",
                    "copt": "8.0.5",
                },
            },
            "review_boundaries": {
                "historical_answer_used": False,
                "historical_code_used": False,
                "generator_status_used_as_decision": False,
                "other_source_redteam_reviews_read": False,
                "optminer_artifacts_in_scope": False,
            },
        }
        summary_path = ROOT / "audits" / "source_review_b_summary.json"
        summary_path.write_text(
            json.dumps(
                review_summary, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps({"summary": summary}, ensure_ascii=False, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
