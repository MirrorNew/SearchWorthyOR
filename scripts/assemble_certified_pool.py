#!/usr/bin/env python3
"""Assemble the fail-closed, doubly reviewed source pool.

This stage never certifies a source.  It only promotes rows that already pass
their source audit, whose frozen artifacts still match their recorded hashes
and solver certificate, and that receive pass decisions from both independent
source-review files.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


TARGET_SIZE = 100
EXPECTED_CERTIFIED_COUNTS = {
    "optminer": 30,
    "supplemental_base": 38,
    "supplemental_reserve": 40,
    "supplemental_reserve2": 40,
}
TOLERANCE = 1e-6
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")

OPTMINER_AUDIT = Path("audits/optminer_source_certification.jsonl")
SUPPLEMENTAL_AUDIT = Path("staging/supplemental_base_audit.jsonl")
RESERVE_AUDIT = Path("staging/supplemental_reserve_audit.jsonl")
RESERVE2_AUDIT = Path("staging/supplemental_reserve2_audit.jsonl")
BASE_CANDIDATES = Path("staging/base_candidates.jsonl")
SUPPLEMENTAL_MANIFEST = Path("staging/supplemental_certification_manifest.json")
RESERVE_MANIFEST = Path(
    "staging/supplemental_reserve_certification_manifest.json"
)
RESERVE2_MANIFEST = Path(
    "staging/supplemental_reserve2_certification_manifest.json"
)
REDTEAM_REVIEW = Path("audits/source_redteam.jsonl")
REDTEAM_REVIEW_RESERVE2 = Path("audits/source_redteam_reserve2.jsonl")
REVIEW_B = Path("audits/source_review_b.jsonl")
REVIEW_B_RESERVE2 = Path("audits/source_review_b_reserve2.jsonl")

POOL_OUTPUT = Path("staging/certified_base_candidates.jsonl")
SUMMARY_OUTPUT = Path("reports/certified_pool_summary.json")
POOL_MANIFEST_OUTPUT = Path("staging/certified_pool_manifest.json")
INSPIRATION_OUTPUT = Path("staging/reviewed_inspiration_pool.jsonl")
INSPIRATION_SUMMARY_OUTPUT = Path(
    "reports/reviewed_inspiration_pool_summary.json"
)
INSPIRATION_MANIFEST_OUTPUT = Path(
    "staging/reviewed_inspiration_pool_manifest.json"
)

SUPPLEMENTAL_FILE_KEYS = {
    "canonical_ir",
    "semantic_mapping",
    "solver_certificate",
    "source_snapshot",
}
REVIEW_B_REQUIRED_CHECKS = {
    "problem_hash_verified",
    "artifact_hashes_verified",
    "ir_hash_verified",
    "semantic_mapping_verified",
    "action_projection_verified",
    "stored_gurobi_certificate_verified",
    "stored_copt_certificate_verified",
    "independent_gurobi_resolve_verified",
    "independent_copt_resolve_verified",
}

FAMILIES = (
    "routing_transport",
    "scheduling_workforce",
    "production_capacity",
    "assignment_matching",
    "facility_network",
    "inventory_supply_chain",
    "energy_environment",
    "healthcare_resources",
    "finance_portfolio",
    "telecom_service",
)
FAMILY_TERMS = {
    "routing_transport": {
        "routing": 10,
        "route": 8,
        "transportation": 9,
        "transport": 7,
        "vehicle": 6,
        "delivery": 7,
        "shipment": 6,
        "truck": 6,
        "fleet": 6,
        "shortest path": 9,
        "travel": 4,
        "distance": 3,
    },
    "scheduling_workforce": {
        "scheduling": 10,
        "schedule": 8,
        "workforce": 9,
        "worker": 6,
        "shift": 8,
        "employee": 6,
        "staffing": 8,
        "job": 4,
        "deadline": 5,
        "overtime": 6,
        "labor": 5,
        "crew": 5,
    },
    "production_capacity": {
        "production": 10,
        "produce": 7,
        "manufacturing": 9,
        "product mix": 9,
        "factory": 7,
        "raw material": 7,
        "processing": 4,
        "machine": 4,
        "yield": 4,
        "capacity planning": 8,
    },
    "assignment_matching": {
        "assignment": 10,
        "assign": 8,
        "matching": 10,
        "match": 7,
        "pairing": 8,
        "pair": 5,
        "one-to-one": 10,
        "exactly one": 5,
    },
    "facility_network": {
        "facility location": 10,
        "facility": 8,
        "location": 5,
        "opening": 7,
        "open a": 5,
        "hub": 7,
        "depot": 7,
        "distribution center": 8,
        "warehouse location": 9,
        "network design": 7,
    },
    "inventory_supply_chain": {
        "inventory": 10,
        "stock": 7,
        "replenishment": 9,
        "supply chain": 10,
        "supplier": 6,
        "procurement": 7,
        "order quantity": 8,
        "holding cost": 8,
        "shortage": 6,
        "demand period": 5,
    },
    "energy_environment": {
        "energy": 9,
        "electricity": 8,
        "power": 5,
        "emission": 9,
        "carbon": 8,
        "fuel": 6,
        "renewable": 8,
        "solar": 7,
        "wind": 6,
        "kwh": 8,
        "environmental": 6,
    },
    "healthcare_resources": {
        "healthcare": 10,
        "health care": 10,
        "hospital": 9,
        "patient": 8,
        "nurse": 8,
        "doctor": 7,
        "clinic": 7,
        "medical": 7,
        "surgery": 7,
        "bed": 5,
        "treatment": 5,
    },
    "finance_portfolio": {
        "finance": 9,
        "financial": 8,
        "portfolio": 10,
        "investment": 8,
        "invest": 7,
        "asset": 6,
        "stock": 5,
        "loan": 6,
        "return": 4,
        "risk": 4,
        "capital": 4,
    },
    "telecom_service": {
        "telecom": 10,
        "telecommunication": 10,
        "communication": 7,
        "bandwidth": 9,
        "wireless": 8,
        "server": 6,
        "cloud": 6,
        "data center": 8,
        "channel": 5,
        "antenna": 8,
        "base station": 9,
    },
}
FAMILY_STRUCTURE_TERMS = {
    "routing_transport": ("arc", "edge", "flow", "route", "path", "vehicle"),
    "scheduling_workforce": ("start_time", "completion", "shift", "worker", "job"),
    "production_capacity": ("production", "product", "machine", "capacity"),
    "assignment_matching": ("assign", "match", "pair"),
    "facility_network": ("open_facility", "facility", "hub", "depot"),
    "inventory_supply_chain": ("inventory", "stock", "order", "period"),
    "energy_environment": ("energy", "power", "emission", "fuel"),
    "healthcare_resources": ("patient", "nurse", "doctor", "hospital"),
    "finance_portfolio": ("portfolio", "asset", "investment", "return", "risk"),
    "telecom_service": ("bandwidth", "server", "channel", "antenna", "telecom"),
}


class PoolAssemblyError(RuntimeError):
    """A fail-closed assembly error with machine-readable details."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.details = details


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PoolAssemblyError("required JSON file is missing", path=str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PoolAssemblyError(
            "cannot read required JSON file",
            path=str(path),
            error=f"{type(error).__name__}:{error}",
        ) from error
    if not isinstance(value, dict):
        raise PoolAssemblyError("JSON root must be an object", path=str(path))
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise PoolAssemblyError("required JSONL file is missing", path=str(path))
    rows: list[dict[str, Any]] = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise PoolAssemblyError(
            "cannot read required JSONL file",
            path=str(path),
            error=f"{type(error).__name__}:{error}",
        ) from error
    for line_number, raw_line in enumerate(raw_lines, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise PoolAssemblyError(
                "invalid JSONL row",
                path=str(path),
                line=line_number,
                error=str(error),
            ) from error
        if not isinstance(row, dict):
            raise PoolAssemblyError(
                "JSONL row must be an object",
                path=str(path),
                line=line_number,
            )
        rows.append(row)
    if not rows:
        raise PoolAssemblyError("required JSONL file is empty", path=str(path))
    return rows


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def normalized_text_sha256(text: str) -> str:
    normalized = re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", text)
    ).strip()
    return sha256_bytes(normalized.encode("utf-8"))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
        for row in rows
    ).encode("utf-8")


def relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_relative(root: Path, relative: Any, *, base: Path | None = None) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("path must be a non-empty string")
    normalized = relative.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or ":" in pure.parts[0]:
        raise ValueError(f"unsafe relative path: {relative!r}")
    parent = root if base is None else base
    resolved_root = root.resolve()
    resolved = parent.joinpath(*pure.parts).resolve()
    if os.path.commonpath([str(resolved_root), str(resolved)]) != str(
        resolved_root
    ):
        raise ValueError(f"path escapes dataset root: {relative!r}")
    return resolved


def require_sha256(value: Any, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or HEX_SHA256.fullmatch(value) is None:
        errors.append(f"{label}:invalid_sha256")
        return None
    return value


def is_close(left: Any, right: Any) -> bool:
    try:
        return math.isclose(
            float(left), float(right), rel_tol=1e-7, abs_tol=TOLERANCE
        )
    except (TypeError, ValueError):
        return False


def append_unique(errors: list[str], message: str) -> None:
    if message not in errors:
        errors.append(message)


def check_ir_structure(ir: Any, errors: list[str]) -> None:
    if not isinstance(ir, dict):
        errors.append("canonical_ir:not_object")
        return
    variables = ir.get("variables")
    constraints = ir.get("constraints")
    objective = ir.get("objective")
    projection = ir.get("action_projection")
    if not isinstance(variables, list) or not variables:
        errors.append("canonical_ir:variables_missing")
        return
    if not isinstance(constraints, list):
        errors.append("canonical_ir:constraints_missing")
        return
    if not isinstance(objective, dict) or not isinstance(
        objective.get("terms"), dict
    ):
        errors.append("canonical_ir:objective_missing")
        return
    names = [
        variable.get("name")
        for variable in variables
        if isinstance(variable, dict)
    ]
    if (
        len(names) != len(variables)
        or any(not isinstance(name, str) or not name for name in names)
        or len(names) != len(set(names))
    ):
        errors.append("canonical_ir:variable_names_invalid")
        return
    name_set = set(names)
    if (
        not isinstance(projection, list)
        or len(projection) != len(set(projection))
        or not set(projection).issubset(name_set)
    ):
        errors.append("canonical_ir:action_projection_invalid")
    if not set(objective["terms"]).issubset(name_set):
        errors.append("canonical_ir:objective_unknown_variable")
    constraint_names: list[Any] = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            errors.append("canonical_ir:constraint_not_object")
            continue
        constraint_names.append(constraint.get("name"))
        terms = constraint.get("terms")
        if not isinstance(terms, dict) or not set(terms).issubset(name_set):
            errors.append(
                f"canonical_ir:{constraint.get('name')}:unknown_variable"
            )
        if constraint.get("sense") not in {"<=", ">=", "=="}:
            errors.append(
                f"canonical_ir:{constraint.get('name')}:invalid_sense"
            )
    if (
        any(not isinstance(name, str) or not name for name in constraint_names)
        or len(constraint_names) != len(set(constraint_names))
    ):
        errors.append("canonical_ir:constraint_names_invalid")


def assignment_certificate_errors(
    solver_name: str,
    ir: dict[str, Any],
    solver: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    variables = {
        variable["name"]: variable for variable in ir["variables"]
    }
    assignment = solver.get("assignment")
    if not isinstance(assignment, dict) or set(assignment) != set(variables):
        return [f"solver_certificate:{solver_name}:assignment_set_mismatch"]
    numeric: dict[str, float] = {}
    for name, value in assignment.items():
        try:
            numeric[name] = float(value)
        except (TypeError, ValueError):
            errors.append(
                f"solver_certificate:{solver_name}:{name}:assignment_not_numeric"
            )
    if errors:
        return errors
    for name, variable in variables.items():
        value = numeric[name]
        lower = variable.get("lb")
        upper = variable.get("ub")
        if lower is not None and value < float(lower) - TOLERANCE:
            errors.append(
                f"solver_certificate:{solver_name}:{name}:lower_bound_violation"
            )
        if upper is not None and value > float(upper) + TOLERANCE:
            errors.append(
                f"solver_certificate:{solver_name}:{name}:upper_bound_violation"
            )
        if variable.get("vartype") in {"I", "B"} and abs(
            value - round(value)
        ) > TOLERANCE:
            errors.append(
                f"solver_certificate:{solver_name}:{name}:integrality_violation"
            )
        if variable.get("vartype") == "B" and not (
            -TOLERANCE <= value <= 1.0 + TOLERANCE
        ):
            errors.append(
                f"solver_certificate:{solver_name}:{name}:binary_domain_violation"
            )
    objective = float(ir["objective"].get("constant", 0.0)) + sum(
        float(coefficient) * numeric[name]
        for name, coefficient in ir["objective"]["terms"].items()
    )
    if not is_close(objective, solver.get("objective")):
        errors.append(
            f"solver_certificate:{solver_name}:objective_recompute_mismatch"
        )
    if "objective_recomputed" in solver and not is_close(
        objective, solver.get("objective_recomputed")
    ):
        errors.append(
            f"solver_certificate:{solver_name}:stored_recompute_mismatch"
        )
    projection = solver.get("projected_action")
    expected_projection = [numeric[name] for name in ir["action_projection"]]
    if (
        not isinstance(projection, list)
        or len(projection) != len(expected_projection)
        or any(
            not is_close(actual, expected)
            for actual, expected in zip(
                projection, expected_projection, strict=True
            )
        )
    ):
        errors.append(
            f"solver_certificate:{solver_name}:action_projection_mismatch"
        )
    for constraint in ir["constraints"]:
        lhs = sum(
            float(coefficient) * numeric[name]
            for name, coefficient in constraint["terms"].items()
        )
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs - rhs)
        elif constraint["sense"] == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        if violation > TOLERANCE:
            errors.append(
                f"solver_certificate:{solver_name}:{constraint['name']}:"
                "constraint_violation"
            )
    return errors


def check_solver_certificate(
    ir: Any, certificate: Any, errors: list[str]
) -> None:
    if not isinstance(ir, dict) or not isinstance(certificate, dict):
        errors.append("solver_certificate:invalid_object")
        return
    checks = certificate.get("checks")
    if not isinstance(checks, dict) or checks.get("passed") is not True:
        errors.append("solver_certificate:checks_not_passed")
    elif any(value is False for value in checks.values()):
        errors.append("solver_certificate:false_check_present")
    solvers: list[dict[str, Any]] = []
    for solver_name in ("gurobi", "copt"):
        solver = certificate.get(solver_name)
        if not isinstance(solver, dict):
            errors.append(f"solver_certificate:{solver_name}:missing")
            continue
        solvers.append(solver)
        if solver.get("status") != "OPTIMAL":
            errors.append(
                f"solver_certificate:{solver_name}:status_not_optimal"
            )
        for alternatives in (
            ("max_constraint_violation",),
            ("max_bound_violation", "bound_violation"),
            ("max_integrality_violation", "integrality_violation"),
        ):
            if not any(field in solver for field in alternatives):
                errors.append(
                    f"solver_certificate:{solver_name}:{alternatives[0]}:missing"
                )
        for field in (
            "max_constraint_violation",
            "max_bound_violation",
            "max_integrality_violation",
        ):
            if field in solver:
                try:
                    if float(solver[field]) > TOLERANCE:
                        errors.append(
                            f"solver_certificate:{solver_name}:{field}"
                        )
                except (TypeError, ValueError):
                    errors.append(
                        f"solver_certificate:{solver_name}:{field}:not_numeric"
                    )
        for field in (
            "max_constraint_violation",
            "bound_violation",
            "integrality_violation",
        ):
            if field in solver:
                try:
                    if float(solver[field]) > TOLERANCE:
                        errors.append(
                            f"solver_certificate:{solver_name}:{field}"
                        )
                except (TypeError, ValueError):
                    errors.append(
                        f"solver_certificate:{solver_name}:{field}:not_numeric"
                    )
        if "assignment" in solver:
            errors.extend(
                assignment_certificate_errors(solver_name, ir, solver)
            )
    if len(solvers) == 2 and not is_close(
        solvers[0].get("objective"), solvers[1].get("objective")
    ):
        errors.append("solver_certificate:objectives_disagree")


def check_semantic_mapping(
    mapping: Any,
    ir: Any,
    candidate_id: str,
    source_id: str,
    source_problem_sha256: str,
    errors: list[str],
) -> None:
    if not isinstance(mapping, dict) or not isinstance(ir, dict):
        errors.append("semantic_mapping:invalid_object")
        return
    for field, expected in (
        ("candidate_id", candidate_id),
        ("source_id", source_id),
        ("problem_sha256", source_problem_sha256),
    ):
        if mapping.get(field) != expected:
            errors.append(f"semantic_mapping:{field}_mismatch")
    completeness = mapping.get("completeness_check")
    if (
        not isinstance(completeness, dict)
        or not completeness
        or any(value is not True for value in completeness.values())
    ):
        errors.append("semantic_mapping:incomplete")
    if mapping.get("semantic_risks") != []:
        errors.append("semantic_mapping:unresolved_risks")
    if mapping.get("formulation_authority") != "problem_text_only":
        errors.append("semantic_mapping:invalid_formulation_authority")
    mapping_variables = mapping.get("variables")
    mapping_constraints = mapping.get("constraints")
    mapping_objective = mapping.get("objective")
    if not isinstance(mapping_variables, list):
        errors.append("semantic_mapping:variables_missing")
    else:
        mapped_names = {
            row.get("name") for row in mapping_variables if isinstance(row, dict)
        }
        ir_names = {
            row.get("name")
            for row in ir.get("variables", [])
            if isinstance(row, dict)
        }
        if mapped_names != ir_names:
            errors.append("semantic_mapping:variable_set_mismatch")
    if not isinstance(mapping_constraints, list):
        errors.append("semantic_mapping:constraints_missing")
    else:
        mapped_names = {
            row.get("name")
            for row in mapping_constraints
            if isinstance(row, dict)
        }
        ir_names = {
            row.get("name")
            for row in ir.get("constraints", [])
            if isinstance(row, dict)
        }
        if mapped_names != ir_names:
            errors.append("semantic_mapping:constraint_set_mismatch")
    if not isinstance(mapping_objective, dict):
        errors.append("semantic_mapping:objective_missing")
    else:
        if mapping_objective.get("direction") != ir.get("sense"):
            errors.append("semantic_mapping:objective_direction_mismatch")
        mapped_terms = mapping_objective.get("terms")
        ir_terms = ir.get("objective", {}).get("terms")
        if not isinstance(mapped_terms, dict) or not isinstance(ir_terms, dict):
            errors.append("semantic_mapping:objective_terms_missing")
        elif set(mapped_terms) != set(ir_terms) or any(
            not is_close(mapped_terms[name], ir_terms[name])
            for name in mapped_terms
        ):
            errors.append("semantic_mapping:objective_terms_mismatch")


def normalize_group(row: Mapping[str, Any]) -> str:
    raw_group = row.get("source_group")
    source_list = row.get("source_list")
    if raw_group == "optminer":
        if source_list not in {None, "optminer"}:
            raise PoolAssemblyError(
                "review source_group and source_list disagree",
                source_group=raw_group,
                source_list=source_list,
                source_id=row.get("source_id"),
            )
        return "optminer"
    if raw_group in {"supplemental", "supplemental_base"}:
        if source_list not in {None, "base"}:
            raise PoolAssemblyError(
                "review source_group and source_list disagree",
                source_group=raw_group,
                source_list=source_list,
                source_id=row.get("source_id"),
            )
        return "supplemental_base"
    if raw_group == "supplemental_reserve":
        if source_list not in {None, "reserve"}:
            raise PoolAssemblyError(
                "review source_group and source_list disagree",
                source_group=raw_group,
                source_list=source_list,
                source_id=row.get("source_id"),
            )
        return "supplemental_reserve"
    if raw_group == "supplemental_reserve2":
        if source_list not in {None, "reserve2"}:
            raise PoolAssemblyError(
                "review source_group and source_list disagree",
                source_group=raw_group,
                source_list=source_list,
                source_id=row.get("source_id"),
            )
        return "supplemental_reserve2"
    raise PoolAssemblyError(
        "review row has an unknown source group",
        source_group=raw_group,
        source_list=source_list,
        source_id=row.get("source_id"),
    )


def index_reviews(
    rows: list[dict[str, Any]], *, review_name: str
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row_number, row in enumerate(rows, start=1):
        group = normalize_group(row)
        source_id = row.get("source_id")
        candidate_id = row.get("candidate_id")
        if not isinstance(source_id, str) or not source_id:
            raise PoolAssemblyError(
                "review row has no source_id",
                review=review_name,
                row=row_number,
            )
        if not isinstance(candidate_id, str) or not candidate_id:
            raise PoolAssemblyError(
                "review row has no candidate_id",
                review=review_name,
                row=row_number,
            )
        key = (group, source_id)
        if key in indexed:
            raise PoolAssemblyError(
                "duplicate review row",
                review=review_name,
                source_group=group,
                source_id=source_id,
            )
        indexed[key] = row
    return indexed


def verify_redteam_review(
    candidate: dict[str, Any], review: dict[str, Any] | None
) -> tuple[list[str], dict[str, Any]]:
    if review is None:
        return ["review_redteam:missing"], {"decision": "missing"}
    errors: list[str] = []
    for field in ("candidate_id", "source_dataset", "source_id"):
        if review.get(field) != candidate[field]:
            errors.append(f"review_redteam:{field}_mismatch")
    if (
        review.get("reserve_rank") is not None
        and review.get("reserve_rank") != candidate["reserve_rank"]
    ):
        errors.append("review_redteam:reserve_rank_mismatch")
    if review.get("verdict") != "pass":
        errors.append("review_redteam:verdict_not_pass")
    if review.get("reason_codes") != []:
        errors.append("review_redteam:reason_codes_not_empty")
    checks = review.get("checks")
    if not isinstance(checks, dict):
        errors.append("review_redteam:checks_missing")
        checks = {}
    if checks.get("source_snapshot_matches_frozen_source") is not True:
        errors.append("review_redteam:source_snapshot_not_verified")
    if checks.get("semantic_text_to_ir_verdict") != "pass":
        errors.append("review_redteam:semantic_mapping_not_pass")
    if checks.get("artifact_hashes_match") is not True:
        errors.append("review_redteam:artifact_hashes_not_verified")
    solver_recheck = checks.get("independent_solver_recheck")
    if (
        not isinstance(solver_recheck, dict)
        or solver_recheck.get("pass") is not True
    ):
        errors.append("review_redteam:solver_recheck_not_pass")
    if checks.get("legacy_answer_dataflow_to_formulation_observed") is not False:
        errors.append("review_redteam:legacy_answer_dataflow_not_excluded")
    computed_hashes = checks.get("computed_file_sha256")
    if not isinstance(computed_hashes, dict):
        errors.append("review_redteam:computed_hashes_missing")
    else:
        normalized_hashes = {
            str(path).replace("\\", "/"): digest
            for path, digest in computed_hashes.items()
        }
        for path, digest in candidate["_artifact_hashes"].items():
            if normalized_hashes.get(path) != digest:
                errors.append(
                    f"review_redteam:computed_hash_mismatch:{path}"
                )
    if candidate["source_group"] == "optminer":
        structural = review.get(
            "structural_gate_verdict", checks.get("structural_gate_verdict")
        )
        current = review.get(
            "current_audit_status", checks.get("current_audit_status")
        )
        if structural != "pass":
            errors.append("review_redteam:structural_gate_not_pass")
        if current != "certified":
            errors.append("review_redteam:current_audit_status_not_certified")
    return errors, {
        "decision": review.get("verdict"),
        "warnings": review.get("warnings", []),
        "checks": checks,
    }


def verify_review_b(
    candidate: dict[str, Any], review: dict[str, Any] | None
) -> tuple[list[str], dict[str, Any]]:
    if review is None:
        return ["review_b:missing"], {"decision": "missing"}
    errors: list[str] = []
    for field in ("candidate_id", "source_dataset", "source_id"):
        if review.get(field) != candidate[field]:
            errors.append(f"review_b:{field}_mismatch")
    if (
        review.get("reserve_rank") is not None
        and review.get("reserve_rank") != candidate["reserve_rank"]
    ):
        errors.append("review_b:reserve_rank_mismatch")
    if review.get("decision") != "pass":
        errors.append("review_b:decision_not_pass")
    if review.get("reasons") != []:
        errors.append("review_b:reasons_not_empty")
    checks = review.get("checks")
    if not isinstance(checks, dict):
        errors.append("review_b:checks_missing")
        checks = {}
    missing = sorted(REVIEW_B_REQUIRED_CHECKS - set(checks))
    if missing:
        errors.append("review_b:required_checks_missing:" + ",".join(missing))
    for field in REVIEW_B_REQUIRED_CHECKS:
        if checks.get(field) is not True:
            errors.append(f"review_b:{field}_not_true")
    for field, value in checks.items():
        if isinstance(value, bool) and value is not True:
            append_unique(errors, f"review_b:{field}_not_true")
    if (
        review.get("source_problem_sha256") is not None
        and review.get("source_problem_sha256")
        != candidate["source_hashes"]["normalized_problem_sha256"]
    ):
        errors.append("review_b:source_problem_sha256_mismatch")
    if (
        review.get("canonical_ir_sha256") is not None
        and review.get("canonical_ir_sha256")
        != candidate["source_hashes"]["canonical_ir_content_sha256"]
    ):
        errors.append("review_b:canonical_ir_sha256_mismatch")
    declared_artifacts = review.get("artifact_sha256")
    if declared_artifacts is not None:
        expected_by_name = {
            Path(path).stem: digest
            for path, digest in candidate["_artifact_hashes"].items()
        }
        if (
            not isinstance(declared_artifacts, dict)
            or declared_artifacts != expected_by_name
        ):
            errors.append("review_b:artifact_sha256_mismatch")
    return errors, {
        "decision": review.get("decision"),
        "checks": checks,
    }


def load_artifact(
    root: Path, path: Path, label: str, errors: list[str]
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{label}:missing")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"{label}:invalid_json")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}:not_object")
        return None
    return value


def verify_snapshot(
    snapshot: Any,
    *,
    candidate_id: str,
    source_dataset: str,
    source_id: str,
    expected_problem_hash: str,
    errors: list[str],
) -> str:
    if not isinstance(snapshot, dict):
        errors.append("source_snapshot:invalid_object")
        return ""
    problem_text = snapshot.get("problem_text")
    if not isinstance(problem_text, str) or not problem_text.strip():
        errors.append("source_snapshot:problem_text_missing")
        return ""
    for field, expected in (
        ("candidate_id", candidate_id),
        ("source_dataset", source_dataset),
        ("source_id", source_id),
    ):
        if snapshot.get(field) != expected:
            errors.append(f"source_snapshot:{field}_mismatch")
    normalized_hash = normalized_text_sha256(problem_text)
    if normalized_hash != expected_problem_hash:
        errors.append("source_snapshot:problem_hash_mismatch")
    for field in (
        "normalized_source_sha256_recomputed",
        "source_hash",
    ):
        if snapshot.get(field) != expected_problem_hash:
            errors.append(f"source_snapshot:{field}_mismatch")
    if snapshot.get("legacy_answer_excluded_from_snapshot") is not True:
        errors.append("source_snapshot:legacy_answer_not_excluded")
    if snapshot.get("legacy_code_excluded") is not True:
        errors.append("source_snapshot:legacy_code_not_excluded")
    return problem_text


def supplemental_candidate(
    root: Path,
    audit: dict[str, Any],
    source_group: str,
    manifest_artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    candidate_id = audit.get("candidate_id")
    source_dataset = audit.get("source_dataset")
    source_id = audit.get("source_id")
    source_problem_hash = audit.get("source_problem_sha256")
    if not all(
        isinstance(value, str) and value
        for value in (
            candidate_id,
            source_dataset,
            source_id,
            source_problem_hash,
        )
    ):
        errors.append("audit:identity_or_source_hash_missing")
    require_sha256(source_problem_hash, "audit:source_problem", errors)
    if audit.get("status") != "unchanged_pass":
        errors.append("audit:status_not_unchanged_pass")
    for field in (
        "solver_certificate_passed",
        "semantic_mapping_complete",
        "single_objective",
    ):
        if audit.get(field) is not True:
            errors.append(f"audit:{field}_not_true")
    if audit.get("legacy_answer_used_as_gold") is not False:
        errors.append("audit:legacy_answer_used_as_gold_not_false")
    if audit.get("legacy_code_used") is not False:
        errors.append("audit:legacy_code_used_not_false")
    files = audit.get("files")
    if files is None and source_group == "supplemental_reserve2":
        files = {
            name: (
                f"certified_sources/supplemental_reserve2/{source_id}/"
                f"{name}.json"
            )
            for name in SUPPLEMENTAL_FILE_KEYS
        }
    paths: dict[str, Path] = {}
    if not isinstance(files, dict) or set(files) != SUPPLEMENTAL_FILE_KEYS:
        errors.append("audit:required_artifact_set_mismatch")
    else:
        for name, relative in files.items():
            try:
                paths[name] = resolve_relative(
                    root, relative, base=root / "staging"
                )
            except ValueError:
                errors.append(f"audit:{name}:unsafe_path")
        if len(set(paths.values())) != len(paths):
            errors.append("audit:artifact_paths_not_unique")
    artifact_hashes: dict[str, str] = {}
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"artifact:{name}:missing")
            continue
        relative = relative_path(root, path)
        digest = file_sha256(path)
        artifact_hashes[relative] = digest
        if manifest_artifacts.get(relative) != digest:
            errors.append(f"artifact:{name}:manifest_hash_mismatch")
    snapshot = (
        load_artifact(root, paths["source_snapshot"], "source_snapshot", errors)
        if "source_snapshot" in paths
        else None
    )
    mapping = (
        load_artifact(
            root, paths["semantic_mapping"], "semantic_mapping", errors
        )
        if "semantic_mapping" in paths
        else None
    )
    ir = (
        load_artifact(root, paths["canonical_ir"], "canonical_ir", errors)
        if "canonical_ir" in paths
        else None
    )
    certificate = (
        load_artifact(
            root, paths["solver_certificate"], "solver_certificate", errors
        )
        if "solver_certificate" in paths
        else None
    )
    problem_text = verify_snapshot(
        snapshot,
        candidate_id=str(candidate_id),
        source_dataset=str(source_dataset),
        source_id=str(source_id),
        expected_problem_hash=str(source_problem_hash),
        errors=errors,
    )
    check_ir_structure(ir, errors)
    if isinstance(ir, dict):
        if canonical_json_sha256(ir) != audit.get("canonical_ir_sha256"):
            errors.append("canonical_ir:canonical_hash_mismatch")
        for field, expected in (
            ("candidate_id", candidate_id),
            ("source_dataset", source_dataset),
            ("source_id", source_id),
            ("source_problem_sha256", source_problem_hash),
        ):
            if ir.get(field) != expected:
                errors.append(f"canonical_ir:{field}_mismatch")
        if ir.get("single_objective") is not True:
            errors.append("canonical_ir:single_objective_not_true")
    check_semantic_mapping(
        mapping,
        ir,
        str(candidate_id),
        str(source_id),
        str(source_problem_hash),
        errors,
    )
    check_solver_certificate(ir, certificate, errors)
    reserve_rank = (
        audit.get("reserve_rank")
        if source_group in {"supplemental_reserve", "supplemental_reserve2"}
        else None
    )
    if source_group in {"supplemental_reserve", "supplemental_reserve2"} and (
        not isinstance(reserve_rank, int) or isinstance(reserve_rank, bool)
        or reserve_rank < 1
    ):
        errors.append("audit:reserve_rank_invalid")
    return {
        "candidate_id": candidate_id,
        "source_group": source_group,
        "source_dataset": source_dataset,
        "source_id": source_id,
        "reserve_rank": reserve_rank,
        "original_problem_text": problem_text,
        "source_snapshot": snapshot,
        "semantic_mapping": mapping,
        "certified_ir_path": (
            relative_path(root, paths["canonical_ir"])
            if "canonical_ir" in paths
            else None
        ),
        "semantic_mapping_path": (
            relative_path(root, paths["semantic_mapping"])
            if "semantic_mapping" in paths
            else None
        ),
        "source_snapshot_path": (
            relative_path(root, paths["source_snapshot"])
            if "source_snapshot" in paths
            else None
        ),
        "solver_certificate_path": (
            relative_path(root, paths["solver_certificate"])
            if "solver_certificate" in paths
            else None
        ),
        "source_hashes": {
            "normalized_problem_sha256": source_problem_hash,
            "canonical_ir_content_sha256": audit.get(
                "canonical_ir_sha256"
            ),
        },
        "source_status": {
            "audit_status": audit.get("status"),
            "semantic_mapping_complete": audit.get(
                "semantic_mapping_complete"
            ),
            "solver_certificate_passed": audit.get(
                "solver_certificate_passed"
            ),
        },
        "_artifact_hashes": artifact_hashes,
        "_ir": ir,
        "_local_errors": errors,
    }


def optminer_candidate(
    root: Path,
    audit: dict[str, Any],
    base_candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    errors: list[str] = []
    source_id = audit.get("source_id")
    if base_candidate is None:
        errors.append("base_candidate:missing")
        base_candidate = {}
    candidate_id = base_candidate.get("candidate_id")
    source_dataset = base_candidate.get("source_dataset")
    problem_text = base_candidate.get("problem_zh_or_en")
    source_hash = base_candidate.get("source_hash")
    if audit.get("status") != "certified":
        errors.append("audit:status_not_certified")
    if audit.get("legacy_answer_policy") != "not_read_not_gold":
        errors.append("audit:legacy_answer_policy_invalid")
    if source_dataset != "OptMinerBench":
        errors.append("base_candidate:source_dataset_mismatch")
    if base_candidate.get("source_id") != source_id:
        errors.append("base_candidate:source_id_mismatch")
    if base_candidate.get("status") != "selected_for_manual_review":
        errors.append("base_candidate:status_not_selected_for_manual_review")
    if not isinstance(problem_text, str) or not problem_text.strip():
        errors.append("base_candidate:problem_text_missing")
        problem_text = ""
    if normalized_text_sha256(problem_text) != source_hash:
        errors.append("base_candidate:normalized_source_hash_mismatch")
    raw_problem_hash = sha256_bytes(problem_text.encode("utf-8"))
    if raw_problem_hash != audit.get("problem_sha256"):
        errors.append("audit:raw_problem_hash_mismatch")
    for field in ("problem_sha256", "ir_sha256", "certificate_sha256"):
        require_sha256(audit.get(field), f"audit:{field}", errors)
    paths: dict[str, Path] = {}
    path_specs = {
        "canonical_ir": audit.get("ir_path"),
        "solver_certificate": audit.get("certificate_path"),
        "source_snapshot": audit.get("source_snapshot_path"),
        "semantic_mapping": audit.get("semantic_mapping_path"),
    }
    for name, relative in path_specs.items():
        if relative is None:
            if name in {"source_snapshot", "semantic_mapping"}:
                errors.append(f"artifact:{name}:path_missing")
            else:
                errors.append(f"artifact:{name}:path_missing")
            continue
        try:
            paths[name] = resolve_relative(root, relative)
        except ValueError:
            errors.append(f"artifact:{name}:unsafe_path")
    artifact_hashes: dict[str, str] = {}
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"artifact:{name}:missing")
            continue
        relative = relative_path(root, path)
        digest = file_sha256(path)
        artifact_hashes[relative] = digest
        if name == "canonical_ir" and digest != audit.get("ir_sha256"):
            errors.append("artifact:canonical_ir:audit_hash_mismatch")
        if (
            name == "solver_certificate"
            and digest != audit.get("certificate_sha256")
        ):
            errors.append("artifact:solver_certificate:audit_hash_mismatch")
    snapshot = (
        load_artifact(root, paths["source_snapshot"], "source_snapshot", errors)
        if "source_snapshot" in paths
        else None
    )
    mapping = (
        load_artifact(
            root, paths["semantic_mapping"], "semantic_mapping", errors
        )
        if "semantic_mapping" in paths
        else None
    )
    ir = (
        load_artifact(root, paths["canonical_ir"], "canonical_ir", errors)
        if "canonical_ir" in paths
        else None
    )
    certificate = (
        load_artifact(
            root, paths["solver_certificate"], "solver_certificate", errors
        )
        if "solver_certificate" in paths
        else None
    )
    if isinstance(snapshot, dict):
        snapshot_text = verify_snapshot(
            snapshot,
            candidate_id=str(candidate_id),
            source_dataset=str(source_dataset),
            source_id=str(source_id),
            expected_problem_hash=str(source_hash),
            errors=errors,
        )
        if snapshot_text != problem_text:
            errors.append("source_snapshot:problem_text_not_original")
    check_ir_structure(ir, errors)
    if isinstance(ir, dict):
        if ir.get("canonical_sha256") != audit.get("canonical_ir_sha256"):
            errors.append("canonical_ir:canonical_hash_mismatch")
    if isinstance(mapping, dict):
        check_semantic_mapping(
            mapping,
            ir,
            str(candidate_id),
            str(source_id),
            str(source_hash),
            errors,
        )
    check_solver_certificate(ir, certificate, errors)
    solver_checks = audit.get("solver_checks")
    if not isinstance(solver_checks, dict) or solver_checks.get("passed") is not True:
        errors.append("audit:solver_checks_not_passed")
    safety = audit.get("ast_safety_screen")
    if not isinstance(safety, dict) or safety.get("passed") is not True:
        errors.append("audit:ast_safety_screen_not_passed")
    return {
        "candidate_id": candidate_id,
        "source_group": "optminer",
        "source_dataset": source_dataset,
        "source_id": source_id,
        "reserve_rank": None,
        "original_problem_text": problem_text,
        "source_snapshot": snapshot,
        "semantic_mapping": mapping,
        "certified_ir_path": (
            relative_path(root, paths["canonical_ir"])
            if "canonical_ir" in paths
            else None
        ),
        "semantic_mapping_path": (
            relative_path(root, paths["semantic_mapping"])
            if "semantic_mapping" in paths
            else None
        ),
        "source_snapshot_path": (
            relative_path(root, paths["source_snapshot"])
            if "source_snapshot" in paths
            else None
        ),
        "solver_certificate_path": (
            relative_path(root, paths["solver_certificate"])
            if "solver_certificate" in paths
            else None
        ),
        "source_hashes": {
            "normalized_problem_sha256": source_hash,
            "raw_problem_sha256": audit.get("problem_sha256"),
            "canonical_ir_content_sha256": audit.get(
                "canonical_ir_sha256"
            ),
        },
        "source_status": {
            "audit_status": audit.get("status"),
            "semantic_mapping_complete": isinstance(mapping, dict),
            "solver_certificate_passed": (
                isinstance(solver_checks, dict)
                and solver_checks.get("passed") is True
            ),
        },
        "_artifact_hashes": artifact_hashes,
        "_ir": ir,
        "_local_errors": errors,
    }


def candidate_order(candidate: Mapping[str, Any]) -> int:
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str):
        return sys.maxsize
    match = re.search(r"(\d+)$", candidate_id)
    return int(match.group(1)) if match else sys.maxsize


def selection_order(candidate: Mapping[str, Any]) -> tuple[int, int, str]:
    group_order = {
        "optminer": 0,
        "supplemental_base": 1,
        "supplemental_reserve": 2,
        "supplemental_reserve2": 3,
    }
    rank = (
        candidate.get("reserve_rank")
        if candidate.get("source_group")
        in {"supplemental_reserve", "supplemental_reserve2"}
        else candidate_order(candidate)
    )
    return (
        group_order.get(str(candidate.get("source_group")), sys.maxsize),
        rank if isinstance(rank, int) else sys.maxsize,
        str(candidate.get("candidate_id")),
    )


def formulation_text(candidate: Mapping[str, Any]) -> str:
    values: list[str] = []
    ir = candidate.get("_ir")
    if isinstance(ir, dict):
        for variable in ir.get("variables", []):
            if isinstance(variable, dict):
                values.extend(
                    str(variable.get(field) or "")
                    for field in ("name", "semantic_name")
                )
        for constraint in ir.get("constraints", []):
            if isinstance(constraint, dict):
                values.append(str(constraint.get("name") or ""))
        objective = ir.get("objective")
        if isinstance(objective, dict):
            values.append(str(objective.get("name") or ""))
    mapping = candidate.get("semantic_mapping")
    if isinstance(mapping, dict):
        for section in ("variables", "constraints"):
            for row in mapping.get(section, []):
                if isinstance(row, dict):
                    values.extend(
                        str(row.get(field) or "")
                        for field in ("name", "meaning", "equation", "unit")
                    )
        objective = mapping.get("objective")
        if isinstance(objective, dict):
            values.extend(
                str(objective.get(field) or "")
                for field in ("name", "unit")
            )
    return " ".join(values).casefold()


def term_count(text: str, term: str) -> int:
    return len(
        re.findall(
            rf"(?<!\w){re.escape(term.casefold())}(?!\w)",
            text,
        )
    )


def family_evidence(
    candidate: Mapping[str, Any], family: str
) -> dict[str, Any]:
    problem_text = str(candidate.get("original_problem_text") or "").casefold()
    mapping = candidate.get("semantic_mapping")
    mapping_text = (
        json.dumps(mapping, ensure_ascii=False, sort_keys=True).casefold()
        if isinstance(mapping, dict)
        else ""
    )
    structure_text = formulation_text(candidate)
    evidence: list[dict[str, Any]] = []
    lexical_score = 0
    structural_score = 0
    for term, weight in FAMILY_TERMS[family].items():
        problem_hits = min(term_count(problem_text, term), 3)
        if problem_hits:
            contribution = problem_hits * weight
            lexical_score += contribution
            evidence.append(
                {
                    "source": "problem_text",
                    "term": term,
                    "matches": problem_hits,
                    "score": contribution,
                }
            )
        mapping_hits = min(term_count(mapping_text, term), 2)
        if mapping_hits:
            contribution = mapping_hits * max(1, weight // 2)
            lexical_score += contribution
            evidence.append(
                {
                    "source": "semantic_mapping",
                    "term": term,
                    "matches": mapping_hits,
                    "score": contribution,
                }
            )
    for term in FAMILY_STRUCTURE_TERMS[family]:
        hits = min(term_count(structure_text, term), 3)
        if hits:
            contribution = 3 * hits
            structural_score += contribution
            evidence.append(
                {
                    "source": "formulation_structure",
                    "term": term,
                    "matches": hits,
                    "score": contribution,
                }
            )
    ir = candidate.get("_ir")
    if family == "assignment_matching" and isinstance(ir, dict):
        binary_count = sum(
            isinstance(variable, dict) and variable.get("vartype") == "B"
            for variable in ir.get("variables", [])
        )
        equality_count = sum(
            isinstance(constraint, dict) and constraint.get("sense") == "=="
            for constraint in ir.get("constraints", [])
        )
        if binary_count >= 2 and equality_count >= 2:
            structural_score += 4
            evidence.append(
                {
                    "source": "formulation_structure",
                    "feature": "binary_variables_with_multiple_equalities",
                    "matches": 1,
                    "score": 4,
                }
            )
    return {
        "score": lexical_score + structural_score,
        "lexical_score": lexical_score,
        "structural_score": structural_score,
        "matched_evidence": evidence,
    }


def add_flow_edge(
    graph: list[list[list[int]]],
    source: int,
    target: int,
    capacity: int,
    cost: int,
) -> list[int]:
    forward = [target, len(graph[target]), capacity, cost]
    reverse = [source, len(graph[source]), 0, -cost]
    graph[source].append(forward)
    graph[target].append(reverse)
    return forward


def min_cost_flow(
    graph: list[list[list[int]]],
    source: int,
    sink: int,
    required_flow: int,
) -> int:
    node_count = len(graph)
    potential = [0] * node_count
    flow = 0
    infinity = 10**30
    while flow < required_flow:
        distance = [infinity] * node_count
        previous_node = [-1] * node_count
        previous_edge = [-1] * node_count
        distance[source] = 0
        queue: list[tuple[int, int]] = [(0, source)]
        while queue:
            current_distance, node = heapq.heappop(queue)
            if current_distance != distance[node]:
                continue
            for edge_index, edge in enumerate(graph[node]):
                target, _, capacity, cost = edge
                if capacity <= 0:
                    continue
                candidate_distance = (
                    current_distance + cost + potential[node] - potential[target]
                )
                if candidate_distance < distance[target]:
                    distance[target] = candidate_distance
                    previous_node[target] = node
                    previous_edge[target] = edge_index
                    heapq.heappush(queue, (candidate_distance, target))
        if distance[sink] == infinity:
            break
        for node, value in enumerate(distance):
            if value < infinity:
                potential[node] += value
        node = sink
        while node != source:
            parent = previous_node[node]
            edge_index = previous_edge[node]
            edge = graph[parent][edge_index]
            edge[2] -= 1
            graph[node][edge[1]][2] += 1
            node = parent
        flow += 1
    return flow


def balanced_family_selection(
    eligible: list[dict[str, Any]],
    disqualified: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(eligible) < TARGET_SIZE:
        reason_counts = Counter(
            reason for row in disqualified for reason in row["reasons"]
        )
        raise PoolAssemblyError(
            "fewer than 100 candidates pass every certification and review gate",
            target=TARGET_SIZE,
            eligible=len(eligible),
            eligible_by_source_group=dict(
                sorted(
                    Counter(
                        candidate["source_group"] for candidate in eligible
                    ).items()
                )
            ),
            disqualified=len(disqualified),
            disqualification_reason_counts=dict(sorted(reason_counts.items())),
        )
    scores = [
        {
            family: family_evidence(candidate, family)
            for family in FAMILIES
        }
        for candidate in eligible
    ]
    family_candidate_report = {
        family: {
            "positive_candidate_count": sum(
                score_row[family]["score"] > 0 for score_row in scores
            ),
            "maximum_score": max(
                score_row[family]["score"] for score_row in scores
            ),
        }
        for family in FAMILIES
    }
    impossible = {
        family: report
        for family, report in family_candidate_report.items()
        if report["positive_candidate_count"] < 10
        or report["maximum_score"] <= 0
    }
    if impossible:
        raise PoolAssemblyError(
            "at least one frozen family has fewer than ten evidence-backed candidates",
            family_candidate_report=family_candidate_report,
            impossible_families=impossible,
        )

    candidate_count = len(eligible)
    source = 0
    candidate_offset = 1
    family_offset = candidate_offset + candidate_count
    sink = family_offset + len(FAMILIES)
    graph: list[list[list[int]]] = [[] for _ in range(sink + 1)]
    edge_lookup: dict[tuple[int, int], list[int]] = {}
    maximum_score = max(
        family_score["score"]
        for score_row in scores
        for family_score in score_row.values()
    )
    tier_cost = {
        "optminer": 0,
        "supplemental_base": 100_000_000,
        "supplemental_reserve": 200_000_000,
        "supplemental_reserve2": 300_000_000,
    }
    for candidate_index, candidate in enumerate(eligible):
        order = selection_order(candidate)[1]
        selection_cost = tier_cost[candidate["source_group"]] + min(
            order, 999_999
        ) * 10_000
        add_flow_edge(
            graph,
            source,
            candidate_offset + candidate_index,
            1,
            selection_cost,
        )
        for family_index, family in enumerate(FAMILIES):
            score = scores[candidate_index][family]["score"]
            if score <= 0:
                continue
            edge_lookup[(candidate_index, family_index)] = add_flow_edge(
                graph,
                candidate_offset + candidate_index,
                family_offset + family_index,
                1,
                (maximum_score - score) * 100 + family_index,
            )
    for family_index in range(len(FAMILIES)):
        add_flow_edge(
            graph,
            family_offset + family_index,
            sink,
            10,
            0,
        )
    achieved_flow = min_cost_flow(graph, source, sink, TARGET_SIZE)
    if achieved_flow != TARGET_SIZE:
        raise PoolAssemblyError(
            "no evidence-backed exact 10-by-10 family assignment exists",
            target_flow=TARGET_SIZE,
            achieved_flow=achieved_flow,
            family_candidate_report=family_candidate_report,
        )

    selected: list[dict[str, Any]] = []
    assigned_scores: dict[str, list[int]] = {family: [] for family in FAMILIES}
    for candidate_index, candidate in enumerate(eligible):
        assigned_family_index = next(
            (
                family_index
                for family_index in range(len(FAMILIES))
                if (candidate_index, family_index) in edge_lookup
                and edge_lookup[(candidate_index, family_index)][2] == 0
            ),
            None,
        )
        if assigned_family_index is None:
            continue
        family = FAMILIES[assigned_family_index]
        evidence = scores[candidate_index][family]
        if evidence["score"] <= 0 or not evidence["matched_evidence"]:
            raise PoolAssemblyError(
                "family assignment has no auditable evidence",
                candidate_id=candidate["candidate_id"],
                family=family,
            )
        candidate["_family_assignment"] = {
            "family": family,
            **evidence,
            "alternative_positive_scores": {
                other_family: scores[candidate_index][other_family]["score"]
                for other_family in FAMILIES
                if scores[candidate_index][other_family]["score"] > 0
                and other_family != family
            },
        }
        assigned_scores[family].append(evidence["score"])
        selected.append(candidate)
    selected.sort(key=selection_order)
    assigned_counts = Counter(
        candidate["_family_assignment"]["family"] for candidate in selected
    )
    if len(selected) != TARGET_SIZE or any(
        assigned_counts[family] != 10 for family in FAMILIES
    ):
        raise PoolAssemblyError(
            "internal family-balance invariant failed",
            selected=len(selected),
            assigned_counts=dict(assigned_counts),
        )
    report = {
        family: {
            **family_candidate_report[family],
            "assigned_count": assigned_counts[family],
            "assigned_score_min": min(assigned_scores[family]),
            "assigned_score_max": max(assigned_scores[family]),
            "assigned_score_average": (
                sum(assigned_scores[family]) / len(assigned_scores[family])
            ),
        }
        for family in FAMILIES
    }
    return selected, report


def public_record(
    candidate: dict[str, Any],
    pool_index: int,
    *,
    inspiration_only: bool,
) -> dict[str, Any]:
    family_assignment = (
        None if inspiration_only else candidate["_family_assignment"]
    )
    return {
        "pool_index": pool_index,
        "role": (
            "reviewed_background_inspiration_only"
            if inspiration_only
            else "certified_base_candidate"
        ),
        "source_correspondence_claim": not inspiration_only,
        "candidate_id": candidate["candidate_id"],
        "source_group": candidate["source_group"],
        "source_dataset": candidate["source_dataset"],
        "source_id": candidate["source_id"],
        "reserve_rank": candidate["reserve_rank"],
        "family": None if inspiration_only else family_assignment["family"],
        "family_assignment": family_assignment,
        "original_problem_text": candidate["original_problem_text"],
        "source_snapshot": candidate["source_snapshot"],
        "source_snapshot_path": candidate["source_snapshot_path"],
        "certified_ir_path": candidate["certified_ir_path"],
        "semantic_mapping": candidate["semantic_mapping"],
        "semantic_mapping_path": candidate["semantic_mapping_path"],
        "solver_certificate_path": candidate["solver_certificate_path"],
        "artifact_sha256": candidate["_artifact_hashes"],
        "source_hashes": candidate["source_hashes"],
        "source_status": {
            **candidate["source_status"],
            "artifact_hashes_match": True,
            "source_hashes_match": True,
            "dual_blind_review_passed": True,
        },
        "blind_reviews": candidate["_reviews"],
    }


def source_mix(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    return {
        "by_source_group": dict(
            sorted(Counter(row["source_group"] for row in rows).items())
        ),
        "by_source_dataset": dict(
            sorted(Counter(row["source_dataset"] for row in rows).items())
        ),
    }


def verify_expected_counts(
    optminer_rows: list[dict[str, Any]],
    supplemental_rows: list[dict[str, Any]],
    reserve_rows: list[dict[str, Any]],
    reserve2_rows: list[dict[str, Any]],
) -> None:
    observed = {
        "optminer": sum(row.get("status") == "certified" for row in optminer_rows),
        "supplemental_base": sum(
            row.get("status") == "unchanged_pass" for row in supplemental_rows
        ),
        "supplemental_reserve": sum(
            row.get("status") == "unchanged_pass" for row in reserve_rows
        ),
        "supplemental_reserve2": sum(
            row.get("status") == "unchanged_pass" for row in reserve2_rows
        ),
    }
    if observed != EXPECTED_CERTIFIED_COUNTS:
        raise PoolAssemblyError(
            "certified input counts do not match the frozen assembly contract",
            expected=EXPECTED_CERTIFIED_COUNTS,
            observed=observed,
        )
    for group, rows in (
        ("supplemental_reserve", reserve_rows),
        ("supplemental_reserve2", reserve2_rows),
    ):
        ranks = [
            row.get("reserve_rank")
            for row in rows
            if row.get("status") == "unchanged_pass"
        ]
        if any(
            not isinstance(rank, int) or isinstance(rank, bool)
            for rank in ranks
        ):
            raise PoolAssemblyError(
                "reserve rank must be an integer",
                source_group=group,
                observed=ranks,
            )
        ranks.sort()
        expected = list(
            range(1, EXPECTED_CERTIFIED_COUNTS[group] + 1)
        )
        if ranks != expected:
            raise PoolAssemblyError(
                "reserve ranks must be the exact contiguous range 1..40",
                source_group=group,
                observed=ranks,
            )


def assemble(
    root: Path, *, inspiration_only: bool = False
) -> dict[str, Any]:
    """Validate every gate and return complete output payloads without writing."""

    root = root.resolve()
    # The review files are intentionally read before any output is prepared.
    redteam_rows = read_jsonl(root / REDTEAM_REVIEW) + read_jsonl(
        root / REDTEAM_REVIEW_RESERVE2
    )
    review_b_rows = read_jsonl(root / REVIEW_B) + read_jsonl(
        root / REVIEW_B_RESERVE2
    )
    redteam = index_reviews(redteam_rows, review_name="source_redteam")
    review_b = index_reviews(review_b_rows, review_name="source_review_b")

    optminer_rows = read_jsonl(root / OPTMINER_AUDIT)
    supplemental_rows = read_jsonl(root / SUPPLEMENTAL_AUDIT)
    reserve_rows = read_jsonl(root / RESERVE_AUDIT)
    reserve2_rows = read_jsonl(root / RESERVE2_AUDIT)
    verify_expected_counts(
        optminer_rows, supplemental_rows, reserve_rows, reserve2_rows
    )

    base_rows = read_jsonl(root / BASE_CANDIDATES)
    base_optminer: dict[str, dict[str, Any]] = {}
    for row in base_rows:
        if row.get("source_dataset") != "OptMinerBench":
            continue
        source_id = row.get("source_id")
        if source_id in base_optminer:
            raise PoolAssemblyError(
                "duplicate OptMiner base source",
                source_id=source_id,
            )
        base_optminer[source_id] = row

    supplemental_manifest = read_json(root / SUPPLEMENTAL_MANIFEST)
    reserve_manifest = read_json(root / RESERVE_MANIFEST)
    reserve2_manifest = read_json(root / RESERVE2_MANIFEST)
    supplemental_hashes = supplemental_manifest.get("artifacts")
    reserve_hashes = reserve_manifest.get("artifacts")
    reserve2_hashes = reserve2_manifest.get("artifacts")
    if not isinstance(supplemental_hashes, dict) or not isinstance(
        reserve_hashes, dict
    ) or not isinstance(reserve2_hashes, dict):
        raise PoolAssemblyError(
            "certification manifest has no artifact hash map"
        )

    candidates: list[dict[str, Any]] = []
    for audit in optminer_rows:
        if audit.get("status") == "certified":
            candidates.append(
                optminer_candidate(
                    root, audit, base_optminer.get(audit.get("source_id"))
                )
            )
    for audit in supplemental_rows:
        if audit.get("status") == "unchanged_pass":
            candidates.append(
                supplemental_candidate(
                    root,
                    audit,
                    "supplemental_base",
                    supplemental_hashes,
                )
            )
    for audit in reserve_rows:
        if audit.get("status") == "unchanged_pass":
            candidates.append(
                supplemental_candidate(
                    root,
                    audit,
                    "supplemental_reserve",
                    reserve_hashes,
                )
            )
    for audit in reserve2_rows:
        if audit.get("status") == "unchanged_pass":
            candidates.append(
                supplemental_candidate(
                    root,
                    audit,
                    "supplemental_reserve2",
                    reserve2_hashes,
                )
            )

    identity_counts = Counter(
        (candidate["source_dataset"], candidate["source_id"])
        for candidate in candidates
    )
    duplicate_sources = sorted(
        [list(key) for key, count in identity_counts.items() if count != 1]
    )
    candidate_id_counts = Counter(
        candidate["candidate_id"] for candidate in candidates
    )
    duplicate_candidate_ids = sorted(
        str(key) for key, count in candidate_id_counts.items() if count != 1
    )
    if duplicate_sources or duplicate_candidate_ids:
        raise PoolAssemblyError(
            "candidate identities are not unique",
            duplicate_sources=duplicate_sources,
            duplicate_candidate_ids=duplicate_candidate_ids,
        )

    disqualified: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        key = (candidate["source_group"], candidate["source_id"])
        redteam_errors, redteam_record = verify_redteam_review(
            candidate, redteam.get(key)
        )
        review_b_errors, review_b_record = verify_review_b(
            candidate, review_b.get(key)
        )
        candidate["_reviews"] = {
            "source_redteam": redteam_record,
            "source_review_b": review_b_record,
        }
        errors = (
            list(candidate["_local_errors"])
            + redteam_errors
            + review_b_errors
        )
        if errors:
            disqualified.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "source_group": candidate["source_group"],
                    "source_dataset": candidate["source_dataset"],
                    "source_id": candidate["source_id"],
                    "reserve_rank": candidate["reserve_rank"],
                    "reasons": sorted(set(errors)),
                }
            )
        else:
            eligible.append(candidate)

    if inspiration_only:
        if len(eligible) < TARGET_SIZE:
            reason_counts = Counter(
                reason for row in disqualified for reason in row["reasons"]
            )
            raise PoolAssemblyError(
                "fewer than 100 candidates pass every certification and review gate",
                target=TARGET_SIZE,
                eligible=len(eligible),
                eligible_by_source_group=dict(
                    sorted(
                        Counter(
                            candidate["source_group"]
                            for candidate in eligible
                        ).items()
                    )
                ),
                disqualified=len(disqualified),
                disqualification_reason_counts=dict(
                    sorted(reason_counts.items())
                ),
            )
        selected_candidates = sorted(
            eligible, key=selection_order
        )[:TARGET_SIZE]
        family_report = None
    else:
        selected_candidates, family_report = balanced_family_selection(
            eligible, disqualified
        )

    source_keys = [
        (candidate["source_dataset"], candidate["source_id"])
        for candidate in selected_candidates
    ]
    normalized_hashes = [
        candidate["source_hashes"]["normalized_problem_sha256"]
        for candidate in selected_candidates
    ]
    if (
        len(set(source_keys)) != TARGET_SIZE
        or len(set(normalized_hashes)) != TARGET_SIZE
    ):
        raise PoolAssemblyError(
            "selected pool is not source-unique",
            unique_source_keys=len(set(source_keys)),
            unique_problem_hashes=len(set(normalized_hashes)),
        )

    records = [
        public_record(
            candidate,
            pool_index,
            inspiration_only=inspiration_only,
        )
        for pool_index, candidate in enumerate(
            selected_candidates, start=1
        )
    ]
    mix = source_mix(records)
    reason_counts = Counter(
        reason for row in disqualified for reason in row["reasons"]
    )
    selected_reserve_ranks = [
        row["reserve_rank"]
        for row in records
        if row["source_group"] == "supplemental_reserve"
    ]
    selected_reserve2_ranks = [
        row["reserve_rank"]
        for row in records
        if row["source_group"] == "supplemental_reserve2"
    ]
    if inspiration_only:
        output_path = INSPIRATION_OUTPUT
        summary_path = INSPIRATION_SUMMARY_OUTPUT
        manifest_path = INSPIRATION_MANIFEST_OUTPUT
        family_counts: dict[str, int] = {"null": len(records)}
        priority_policy = [
            "optminer certified rows in base-candidate order",
            "main supplemental unchanged_pass rows in candidate order",
            "supplemental reserve unchanged_pass rows in reserve_rank order",
            "supplemental reserve2 unchanged_pass rows in reserve_rank order",
        ]
    else:
        output_path = POOL_OUTPUT
        summary_path = SUMMARY_OUTPUT
        manifest_path = POOL_MANIFEST_OUTPUT
        family_counts = dict(
            sorted(Counter(row["family"] for row in records).items())
        )
        priority_policy = [
            "optminer certified rows in base-candidate order",
            "main supplemental unchanged_pass rows in candidate order",
            "supplemental reserve unchanged_pass rows in reserve_rank order",
            "supplemental reserve2 unchanged_pass rows in reserve_rank order",
            "evidence-backed exact 10-by-10 frozen family assignment",
        ]
    summary = {
        "schema_version": "1.0",
        "mode": "inspiration_only" if inspiration_only else "strict_certified_base",
        "status": "pass",
        "role": (
            "reviewed_background_inspiration_only"
            if inspiration_only
            else "certified_base_candidate"
        ),
        "source_correspondence_claim": not inspiration_only,
        "target_size": TARGET_SIZE,
        "selected_count": len(records),
        "selection_policy": {
            "priority": priority_policy,
            "required_gates": [
                "frozen source audit pass",
                "current source and artifact hashes match",
                "stored solver certificate recomputes and passes",
                "source_redteam verdict pass",
                "source_review_b decision pass",
            ],
            "family_assignment": (
                "disabled; family is null for every background-inspiration row"
                if inspiration_only
                else "required exact 10-by-10 evidence-backed assignment"
            ),
            "threshold_relaxation_allowed": False,
        },
        "source_mix": mix,
        "preferred_selected": sum(
            row["source_group"]
            not in {"supplemental_reserve", "supplemental_reserve2"}
            for row in records
        ),
        "reserve_selected": (
            len(selected_reserve_ranks) + len(selected_reserve2_ranks)
        ),
        "reserve1_selected": len(selected_reserve_ranks),
        "reserve2_selected": len(selected_reserve2_ranks),
        "selected_reserve_ranks": selected_reserve_ranks,
        "selected_reserve2_ranks": selected_reserve2_ranks,
        "family_counts": family_counts,
        "family_candidate_and_assignment_report": family_report,
        "eligible_after_all_gates": len(eligible),
        "disqualified_count": len(disqualified),
        "disqualification_reason_counts": dict(
            sorted(reason_counts.items())
        ),
        "selected_candidate_ids": [row["candidate_id"] for row in records],
        "selected_source_keys": [
            {
                "source_dataset": row["source_dataset"],
                "source_id": row["source_id"],
            }
            for row in records
        ],
    }
    pool_payload = jsonl_bytes(records)
    summary_payload = json_bytes(summary)
    input_paths = [
        OPTMINER_AUDIT,
        SUPPLEMENTAL_AUDIT,
        RESERVE_AUDIT,
        RESERVE2_AUDIT,
        BASE_CANDIDATES,
        SUPPLEMENTAL_MANIFEST,
        RESERVE_MANIFEST,
        RESERVE2_MANIFEST,
        REDTEAM_REVIEW,
        REDTEAM_REVIEW_RESERVE2,
        REVIEW_B,
        REVIEW_B_RESERVE2,
    ]
    manifest = {
        "schema_version": "1.0",
        "mode": summary["mode"],
        "role": summary["role"],
        "source_correspondence_claim": summary[
            "source_correspondence_claim"
        ],
        "hash_algorithm": "sha256",
        "target_size": TARGET_SIZE,
        "selected_count": len(records),
        "selection_policy": summary["selection_policy"],
        "source_mix": mix,
        "family_counts": summary["family_counts"],
        "family_candidate_and_assignment_report": family_report,
        "inputs": {
            path.as_posix(): {
                "sha256": file_sha256(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in input_paths
        },
        "outputs": {
            output_path.as_posix(): {
                "sha256": sha256_bytes(pool_payload),
                "bytes": len(pool_payload),
                "records": len(records),
            },
            summary_path.as_posix(): {
                "sha256": sha256_bytes(summary_payload),
                "bytes": len(summary_payload),
            },
        },
        "selected_artifacts": [
            {
                "candidate_id": row["candidate_id"],
                "source_group": row["source_group"],
                "source_dataset": row["source_dataset"],
                "source_id": row["source_id"],
                "reserve_rank": row["reserve_rank"],
                "family": row["family"],
                "family_score": (
                    None
                    if row["family_assignment"] is None
                    else row["family_assignment"]["score"]
                ),
                "artifact_sha256": row["artifact_sha256"],
            }
            for row in records
        ],
        "self_excluded": manifest_path.as_posix(),
    }
    return {
        "records": records,
        "summary": summary,
        "manifest": manifest,
        "payloads": {
            output_path: pool_payload,
            summary_path: summary_payload,
            manifest_path: json_bytes(manifest),
        },
        "output_paths": [output_path, summary_path, manifest_path],
    }


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_outputs(root: Path, result: Mapping[str, Any]) -> None:
    payloads = result["payloads"]
    for relative in result["output_paths"]:
        atomic_write(root / relative, payloads[relative])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble exactly 100 doubly reviewed certified sources."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="SearchWorthyOR-100 dataset root",
    )
    parser.add_argument(
        "--inspiration-only",
        action="store_true",
        help=(
            "write only the reviewed background-inspiration pool; "
            "never claim source correspondence or a certified base"
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        result = assemble(root, inspiration_only=args.inspiration_only)
        write_outputs(root, result)
    except PoolAssemblyError as error:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error": str(error),
                    "details": error.details,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": "pass",
                "mode": result["summary"]["mode"],
                "selected_count": result["summary"]["selected_count"],
                "source_mix": result["summary"]["source_mix"],
                "outputs": [
                    path.as_posix() for path in result["output_paths"]
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
