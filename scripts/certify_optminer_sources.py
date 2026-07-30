#!/usr/bin/env python3
"""Safely extract and dual-solver certify linear OptMinerBench source models.

The legacy benchmark answer is never read.  Legacy code is treated only as an
executable source artifact and is run in a fresh isolated subprocess after a
conservative AST side-effect screen.  The worker blocks filesystem access and
captures every ``gurobipy.Model`` constructor call; exactly one final model is
then exported to a solver-neutral linear/MILP IR.

IR bound convention: ``null`` lower/upper bounds denote -/+ infinity.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import contextlib
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any


DATASET_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PATH = PROJECT_ROOT / "benchmark" / "optminer_bench.jsonl"
BASE_CANDIDATES_PATH = DATASET_ROOT / "staging" / "base_candidates.jsonl"
OUTPUT_ROOT = DATASET_ROOT / "staging" / "certified_sources" / "optminer"
AUDIT_PATH = DATASET_ROOT / "audits" / "optminer_source_certification.jsonl"
SUMMARY_PATH = DATASET_ROOT / "audits" / "optminer_source_certification_summary.json"

LINEAR_TYPES = {"LP", "IP", "MILP"}
EXTRA_ELIGIBLE_LINEAR_IDS = {"OMB107", "OMB112", "OMB119", "OMB123", "OMB125"}
PRIOR_NONLINEAR_CANDIDATE_IDS = {
    "OMB005",
    "OMB008",
    "OMB016",
    "OMB021",
    "OMB041",
    "OMB052",
    "OMB089",
    "OMB093",
}
WORKER_TIMEOUT_SECONDS = 180
SOLVER_TIME_LIMIT_SECONDS = 120.0
ABS_TOL = 1e-6
REL_TOL = 1e-7
_COPT_ENV: Any = None

ALLOWED_IMPORT_ROOTS = {
    "collections",
    "functools",
    "gurobipy",
    "itertools",
    "json",
    "math",
    "numpy",
    "operator",
    "statistics",
}
BLOCKED_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "exit",
    "input",
    "open",
    "quit",
}
BLOCKED_ATTRIBUTE_CALLS = {
    "chdir",
    "connect",
    "dump",
    "dump_model",
    "dumps_model",
    "fromfile",
    "genfromtxt",
    "load",
    "loadtxt",
    "mkdir",
    "makedirs",
    "open",
    "read",
    "read_csv",
    "read_excel",
    "remove",
    "rename",
    "replace",
    "request",
    "rmdir",
    "save",
    "savez",
    "savez_compressed",
    "send",
    "socket",
    "system",
    "to_csv",
    "to_excel",
    "touch",
    "unlink",
    "urlopen",
    "write_text",
    "write_bytes",
}
NEUTRALIZED_ATTRIBUTE_CALLS = {"write"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    path.write_text(payload, encoding="utf-8", newline="\n")


def omb_id(raw_id: Any) -> str:
    return f"OMB{int(raw_id):03d}"


def suggest_source_family(source: dict[str, Any]) -> dict[str, Any]:
    text = (
        f"{source.get('scenario', '')}\n{source.get('problem', '')}"
    ).lower()
    rules = [
        (
            "healthcare_resources",
            ("patient", "hospital", "healthcare", "medical", "clinic", "nurse"),
        ),
        (
            "energy_environment",
            ("energy", "power grid", "emission", "environment", "electricity"),
        ),
        (
            "inventory_supply_chain",
            ("inventory", "stock", "replenish", "supply chain", "order quantity"),
        ),
        (
            "facility_network",
            (
                "facility",
                "warehouse",
                "site selection",
                "open a",
                "network design",
                "anchor hub",
                "data vault",
            ),
        ),
        (
            "scheduling_workforce",
            ("schedule", "shift", "workforce", "crew", "staff", "time slot"),
        ),
        (
            "assignment_matching",
            ("assign", "assignment", "matching", "pairing", "pair each"),
        ),
        (
            "routing_transport",
            (
                "route",
                "routing",
                "vehicle",
                "delivery",
                "transport",
                "shortest path",
                "travel",
                "plasmid sequence",
            ),
        ),
        (
            "production_capacity",
            (
                "production",
                "manufactur",
                "factory",
                "machine",
                "capacity planning",
                "harvest",
                "product line",
            ),
        ),
        (
            "finance_portfolio",
            ("portfolio", "invest", "finance", "loan", "asset", "financial"),
        ),
        (
            "telecom_service",
            (
                "telecommunication",
                "server",
                "cloud",
                "channel",
                "bandwidth",
                "service system",
            ),
        ),
    ]
    matches: list[tuple[str, list[str]]] = []
    for family, keywords in rules:
        hits = [keyword for keyword in keywords if keyword in text]
        if hits:
            matches.append((family, hits))
    if not matches:
        return {
            "family": "unresolved",
            "method": "keyword_suggestion_not_adjudication",
            "matched_keywords": [],
            "risk": "manual_family_adjudication_required",
        }
    family, hits = matches[0]
    return {
        "family": family,
        "method": "ordered_keyword_suggestion_not_adjudication",
        "matched_keywords": hits,
        "alternative_matches": [
            {"family": other_family, "matched_keywords": other_hits}
            for other_family, other_hits in matches[1:]
        ],
        "risk": (
            "multiple_family_signals_manual_adjudication_required"
            if len(matches) > 1
            else "manual_confirmation_required"
        ),
    }


def problem_objective_direction(problem: str) -> str:
    lowered = problem.lower()
    min_hits = any(
        token in lowered
        for token in ("minimize", "minimise", "minimum", "lowest", "least cost")
    )
    max_hits = any(
        token in lowered
        for token in ("maximize", "maximise", "maximum", "highest", "greatest")
    )
    if min_hits and not max_hits:
        return "min"
    if max_hits and not min_hits:
        return "max"
    return "ambiguous"


def semantic_risk_record(
    source: dict[str, Any], ir: dict[str, Any] | None = None
) -> dict[str, Any]:
    text_direction = problem_objective_direction(str(source.get("problem") or ""))
    ir_direction = ir.get("sense") if ir is not None else None
    flags = [
        "legacy_reference_code_not_gold",
        "no_line_by_line_problem_to_equation_adjudication_in_this_stage",
        "variable_and_constraint_scope_not_traced_to_problem_spans",
        "units_and_action_projection_not_independently_adjudicated",
    ]
    if ir_direction is not None and text_direction != "ambiguous":
        if text_direction != ir_direction:
            flags.append("objective_direction_text_ir_mismatch")
    else:
        flags.append("objective_direction_text_screen_ambiguous_or_ir_unavailable")
    return {
        "status": "not_semantically_certified",
        "problem_objective_direction_screen": text_direction,
        "ir_objective_direction": ir_direction,
        "risk_flags": flags,
        "required_next_gate": (
            "two_blind_reviewers_must_trace_problem_spans_to_sets_parameters_"
            "variables_objective_constraints_units_and_action_projection"
        ),
    }


def ast_safety_screen(code: str) -> dict[str, Any]:
    """Reject code with imports or calls that can access external state."""

    findings: list[dict[str, Any]] = []
    neutralized_calls: list[dict[str, Any]] = []
    imports: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return {
            "passed": False,
            "imports": [],
            "findings": [
                {
                    "kind": "syntax_error",
                    "line": error.lineno,
                    "detail": error.msg,
                }
            ],
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                imports.add(alias.name)
                if root not in ALLOWED_IMPORT_ROOTS:
                    findings.append(
                        {
                            "kind": "blocked_import",
                            "line": node.lineno,
                            "detail": alias.name,
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            imports.add(module)
            if node.level or root not in ALLOWED_IMPORT_ROOTS:
                findings.append(
                    {
                        "kind": "blocked_import",
                        "line": node.lineno,
                        "detail": ("." * node.level) + module,
                    }
                )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALL_NAMES:
                findings.append(
                    {
                        "kind": "blocked_call",
                        "line": node.lineno,
                        "detail": node.func.id,
                    }
                )
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in BLOCKED_ATTRIBUTE_CALLS
            ):
                findings.append(
                    {
                        "kind": "blocked_attribute_call",
                        "line": node.lineno,
                        "detail": node.func.attr,
                    }
                )
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in NEUTRALIZED_ATTRIBUTE_CALLS
            ):
                # The benchmark contains diagnostic ``model.write("model.ilp")``
                # branches.  The worker replaces these calls with a no-op so
                # native Gurobi code cannot bypass the blocked Python ``open``.
                neutralized_calls.append(
                    {
                        "kind": "neutralized_attribute_call",
                        "line": node.lineno,
                        "detail": node.func.attr,
                    }
                )
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            # Harmless for most benchmark scripts; recorded for audit only.
            pass

    return {
        "passed": not findings,
        "imports": sorted(imports),
        "findings": findings,
        "neutralized_calls": neutralized_calls,
    }


class _CappedText(io.TextIOBase):
    """Discard legacy prints after a small audit tail to avoid memory blow-up."""

    def __init__(self, limit: int = 32_768) -> None:
        self.limit = limit
        self.parts: list[str] = []
        self.size = 0
        self.truncated = False

    def writable(self) -> bool:
        return True

    def write(self, value: str) -> int:
        text = str(value)
        remaining = self.limit - self.size
        if remaining > 0:
            fragment = text[:remaining]
            self.parts.append(fragment)
            self.size += len(fragment)
        if len(text) > max(remaining, 0):
            self.truncated = True
        return len(text)

    def getvalue(self) -> str:
        return "".join(self.parts)


class _NeutralizeWrites(ast.NodeTransformer):
    """Replace attribute ``.write(...)`` calls with a side-effect-free ``None``."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in NEUTRALIZED_ATTRIBUTE_CALLS
        ):
            return ast.copy_location(ast.Constant(value=None), node)
        return node


def compile_sanitized(code: str, filename: str) -> Any:
    tree = ast.parse(code, filename=filename, mode="exec")
    tree = _NeutralizeWrites().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")


def _finite_or_none(value: float, *, lower: bool, infinity: float) -> float | None:
    if lower and value <= -0.9 * infinity:
        return None
    if not lower and value >= 0.9 * infinity:
        return None
    return float(value)


def _safe_text(value: Any) -> str:
    """Make solver-originated names JSON-safe without hiding byte-decoding loss."""

    return str(value).encode("utf-8", errors="backslashreplace").decode("utf-8")


def _normalize_surrogate_pairs(value: str) -> str:
    """Combine JSON-decoded UTF-16 pairs and replace genuinely unpaired units."""

    return value.encode("utf-16", errors="surrogatepass").decode(
        "utf-16", errors="replace"
    )


def _export_gurobi_ir(model: Any, source_id: str) -> dict[str, Any]:
    import gurobipy as gp
    from gurobipy import GRB

    model.update()
    structural_counts = {
        "variables": int(model.NumVars),
        "linear_constraints": int(model.NumConstrs),
        "quadratic_constraints": int(model.NumQConstrs),
        "general_constraints": int(model.NumGenConstrs),
        "sos_constraints": int(model.NumSOS),
        "objective_quadratic_nnz": int(model.NumQNZs),
        "objectives": int(model.NumObj),
    }
    non_linear = {
        key: value
        for key, value in structural_counts.items()
        if key
        in {
            "quadratic_constraints",
            "general_constraints",
            "sos_constraints",
            "objective_quadratic_nnz",
        }
        and value
    }
    if structural_counts["objectives"] != 1:
        raise ValueError(
            f"expected exactly one objective, got {structural_counts['objectives']}"
        )
    if non_linear:
        raise ValueError(f"nonlinear_or_nonlinearizable_structure:{non_linear}")

    variables = list(model.getVars())
    canonical_names = {var.index: f"v{index:06d}" for index, var in enumerate(variables)}
    ir_variables: list[dict[str, Any]] = []
    allowed_vtypes = {GRB.BINARY, GRB.INTEGER, GRB.CONTINUOUS}
    for index, var in enumerate(variables):
        if var.VType not in allowed_vtypes:
            raise ValueError(f"unsupported_variable_type:{var.VType}:{var.VarName}")
        ir_variables.append(
            {
                "name": canonical_names[var.index],
                "source_name": _safe_text(var.VarName),
                "index": index,
                "lb": _finite_or_none(
                    float(var.LB), lower=True, infinity=float(GRB.INFINITY)
                ),
                "ub": _finite_or_none(
                    float(var.UB), lower=False, infinity=float(GRB.INFINITY)
                ),
                "vartype": str(var.VType),
            }
        )

    objective_terms = {
        canonical_names[var.index]: float(var.Obj)
        for var in variables
        if abs(float(var.Obj)) > 0.0
    }
    constraints: list[dict[str, Any]] = []
    sense_map = {"<": "<=", ">": ">=", "=": "=="}
    for index, constraint in enumerate(model.getConstrs()):
        row = model.getRow(constraint)
        terms: dict[str, float] = {}
        for term_index in range(row.size()):
            var = row.getVar(term_index)
            name = canonical_names[var.index]
            terms[name] = terms.get(name, 0.0) + float(row.getCoeff(term_index))
        terms = {name: coef for name, coef in terms.items() if abs(coef) > 0.0}
        constraints.append(
            {
                "name": f"c{index:06d}",
                "source_name": _safe_text(constraint.ConstrName),
                "index": index,
                "sense": sense_map[str(constraint.Sense)],
                "rhs": float(constraint.RHS),
                "terms": terms,
            }
        )

    ir: dict[str, Any] = {
        "schema_version": "searchworthyor.canonical-linear-ir.v1",
        "model_id": source_id,
        "source_model_name": _safe_text(model.ModelName),
        "sense": "min" if int(model.ModelSense) == 1 else "max",
        "variables": ir_variables,
        "objective": {
            "constant": float(model.ObjCon),
            "terms": objective_terms,
        },
        "constraints": constraints,
        "action_projection": [
            var["name"] for var in ir_variables if var["vartype"] in {"B", "I"}
        ],
        "structural_counts": structural_counts,
    }
    ir["canonical_sha256"] = sha256_bytes(canonical_bytes(ir))
    return ir


def _blocked_open(*_args: Any, **_kwargs: Any) -> Any:
    raise PermissionError("legacy benchmark code may not access the filesystem")


def _worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one screened legacy script and return its captured final IR."""

    code = _normalize_surrogate_pairs(str(payload["code"]))
    source_id = str(payload["source_id"])
    capture = _CappedText()
    models: list[Any] = []
    original_gurobi_observation: dict[str, Any] | None = None
    validation_ir_error: dict[str, str] | None = None

    import gurobipy as gp

    original_model_constructor = gp.Model

    def tracking_model(*args: Any, **kwargs: Any) -> Any:
        model = original_model_constructor(*args, **kwargs)
        models.append(model)
        return model

    original_open = builtins.open
    original_model = gp.Model
    original_env = dict(os.environ)
    execution_warning: dict[str, str] | None = None
    try:
        gp.Model = tracking_model
        builtins.open = _blocked_open
        # Prevent accidental credential/proxy discovery by legacy code.  The
        # process itself has no allowed network imports after the AST screen.
        os.environ.clear()
        os.environ.update(
            {
                "PYTHONUTF8": "1",
                "GRB_LICENSE_FILE": original_env.get("GRB_LICENSE_FILE", ""),
                "COPT_LICENSE_DIR": original_env.get("COPT_LICENSE_DIR", ""),
            }
        )
        namespace = {
            "__name__": "__main__",
            "__file__": f"<{source_id}-legacy-code>",
            "__builtins__": builtins.__dict__,
        }
        compiled = compile_sanitized(code, f"<{source_id}-legacy-code>")
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            try:
                exec(compiled, namespace, namespace)
            except SystemExit as error:
                # A final ``sys.exit(0)`` is harmless.  Nonzero exits are
                # preserved as execution failures.
                if error.code not in (None, 0):
                    raise RuntimeError(f"legacy SystemExit({error.code})") from error
            except gp.GurobiError as error:
                # A restricted local license can reject optimize() after model
                # construction.  Preserve that limitation, but still export
                # the completely built model for solver-neutral certification.
                if models and "Model too large for size-limited license" in str(error):
                    execution_warning = {
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                else:
                    raise

        if not models:
            raise RuntimeError("no_gurobi_model_captured")
        final_model = models[-1]
        from gurobipy import GRB

        original_status_code = int(final_model.Status)
        original_status_name = {
            GRB.LOADED: "LOADED_NOT_SOLVED",
            GRB.OPTIMAL: "OPTIMAL",
            GRB.INFEASIBLE: "INFEASIBLE",
            GRB.UNBOUNDED: "UNBOUNDED",
            GRB.INF_OR_UNBD: "INF_OR_UNBD",
            GRB.TIME_LIMIT: "TIME_LIMIT",
        }.get(original_status_code, f"STATUS_{original_status_code}")
        original_gurobi_observation = {
            "status": (
                "LICENSE_SIZE_LIMIT"
                if execution_warning is not None
                else original_status_name
            ),
            "raw_status_code": original_status_code,
            "objective": (
                float(final_model.ObjVal)
                if original_status_code == GRB.OPTIMAL
                else None
            ),
        }
        ir = _export_gurobi_ir(final_model, source_id)
        validation_ir = None
        counts = ir["structural_counts"]
        if counts["variables"] > 2000 or counts["linear_constraints"] > 2000:
            # The local Gurobi license checks post-presolve size.  Export the
            # raw canonical model above, then ask Gurobi for its deterministic
            # equivalent presolved model solely for the Gurobi validation leg.
            final_model.Params.OutputFlag = 0
            final_model.Params.Threads = 1
            try:
                presolved_model = final_model.presolve()
                validation_ir = _export_gurobi_ir(
                    presolved_model, f"{source_id}_gurobi_presolved"
                )
                validation_ir["transform"] = {
                    "kind": "gurobi_presolve_equivalent",
                    "source_canonical_sha256": ir["canonical_sha256"],
                    "gurobi_version": ".".join(map(str, gp.gurobi.version())),
                }
                validation_ir["canonical_sha256"] = sha256_bytes(
                    canonical_bytes(
                        {
                            key: value
                            for key, value in validation_ir.items()
                            if key != "canonical_sha256"
                        }
                    )
                )
            except gp.GurobiError as error:
                validation_ir_error = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
        return {
            "ok": True,
            "ir": ir,
            "gurobi_validation_ir": validation_ir,
            "capture": {
                "model_count": len(models),
                "model_names": [_safe_text(model.ModelName) for model in models],
                "stdout_stderr_excerpt": _safe_text(capture.getvalue()[-4000:]),
                "stdout_stderr_truncated": capture.truncated,
                "legacy_execution_warning": execution_warning,
                "original_gurobi_observation": original_gurobi_observation,
                "gurobi_presolve_error": validation_ir_error,
            },
        }
    except BaseException as error:  # worker must serialize every failure
        return {
            "ok": False,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback_tail": traceback.format_exc()[-8000:],
            "capture": {
                "model_count": len(models),
                "model_names": [
                    _safe_text(model.ModelName) for model in models
                ],
                "stdout_stderr_excerpt": _safe_text(capture.getvalue()[-4000:]),
                "stdout_stderr_truncated": capture.truncated,
                "legacy_execution_warning": execution_warning,
                "original_gurobi_observation": original_gurobi_observation,
                "gurobi_presolve_error": validation_ir_error,
            },
        }
    finally:
        builtins.open = original_open
        gp.Model = original_model
        os.environ.clear()
        os.environ.update(original_env)


def _bound(value: float | None, *, lower: bool, infinity: float) -> float:
    if value is None:
        return -infinity if lower else infinity
    return float(value)


def solve_ir_gurobi(ir: dict[str, Any]) -> dict[str, Any]:
    import gurobipy as gp
    from gurobipy import GRB

    model = gp.Model(f"{ir['model_id']}_gurobi_rebuild")
    model.Params.OutputFlag = 0
    model.Params.Threads = 1
    model.Params.Seed = 20260730
    model.Params.TimeLimit = SOLVER_TIME_LIMIT_SECONDS
    variables: dict[str, Any] = {}
    for item in ir["variables"]:
        variables[item["name"]] = model.addVar(
            lb=_bound(item["lb"], lower=True, infinity=float(GRB.INFINITY)),
            ub=_bound(item["ub"], lower=False, infinity=float(GRB.INFINITY)),
            vtype=item["vartype"],
            name=item["name"],
        )
    model.update()
    objective = gp.LinExpr(float(ir["objective"]["constant"]))
    for name, coefficient in ir["objective"]["terms"].items():
        objective += float(coefficient) * variables[name]
    model.setObjective(
        objective, GRB.MINIMIZE if ir["sense"] == "min" else GRB.MAXIMIZE
    )
    for constraint in ir["constraints"]:
        lhs = gp.LinExpr()
        for name, coefficient in constraint["terms"].items():
            lhs += float(coefficient) * variables[name]
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            model.addConstr(lhs <= rhs, name=constraint["name"])
        elif constraint["sense"] == ">=":
            model.addConstr(lhs >= rhs, name=constraint["name"])
        else:
            model.addConstr(lhs == rhs, name=constraint["name"])
    try:
        model.optimize()
    except gp.GurobiError as error:
        status = (
            "LICENSE_SIZE_LIMIT"
            if "Model too large for size-limited license" in str(error)
            else "SOLVER_ERROR"
        )
        model.dispose()
        return {
            "solver": "gurobi",
            "version": ".".join(map(str, gp.gurobi.version())),
            "status": status,
            "error": str(error),
        }
    status = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.TIME_LIMIT: "TIME_LIMIT",
    }.get(model.Status, f"STATUS_{model.Status}")
    result: dict[str, Any] = {
        "solver": "gurobi",
        "version": ".".join(map(str, gp.gurobi.version())),
        "status": status,
    }
    if model.Status == GRB.OPTIMAL:
        result["objective"] = float(model.ObjVal)
        assignment = {
            name: float(variable.X) for name, variable in variables.items()
        }
        violations = inspect_ir_assignment(ir, assignment)
        result.update(violations)
    model.dispose()
    return result


def solve_ir_copt(ir: dict[str, Any]) -> dict[str, Any]:
    import coptpy as cp
    from coptpy import COPT

    copt_version = ".".join(str(cp.GetLibVersion(index)) for index in range(3))
    global _COPT_ENV
    if _COPT_ENV is None:
        _COPT_ENV = cp.Envr()
    model = _COPT_ENV.createModel(f"{ir['model_id']}_copt_rebuild")
    model.setParam(COPT.Param.Logging, 0)
    model.setParam(COPT.Param.Threads, 1)
    model.setParam(COPT.Param.TimeLimit, SOLVER_TIME_LIMIT_SECONDS)
    variables: dict[str, Any] = {}
    vtype_map = {"B": COPT.BINARY, "I": COPT.INTEGER, "C": COPT.CONTINUOUS}
    for item in ir["variables"]:
        variables[item["name"]] = model.addVar(
            lb=_bound(item["lb"], lower=True, infinity=float(COPT.INFINITY)),
            ub=_bound(item["ub"], lower=False, infinity=float(COPT.INFINITY)),
            vtype=vtype_map[item["vartype"]],
            name=item["name"],
        )
    objective: Any = float(ir["objective"]["constant"])
    for name, coefficient in ir["objective"]["terms"].items():
        objective += float(coefficient) * variables[name]
    model.setObjective(
        objective, COPT.MINIMIZE if ir["sense"] == "min" else COPT.MAXIMIZE
    )
    for constraint in ir["constraints"]:
        lhs: Any = 0.0
        for name, coefficient in constraint["terms"].items():
            lhs += float(coefficient) * variables[name]
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            model.addConstr(lhs <= rhs, name=constraint["name"])
        elif constraint["sense"] == ">=":
            model.addConstr(lhs >= rhs, name=constraint["name"])
        else:
            model.addConstr(lhs == rhs, name=constraint["name"])
    try:
        model.solve()
    except cp.CoptError as error:
        return {
            "solver": "copt",
            "version": copt_version,
            "status": "SOLVER_ERROR",
            "error": str(error),
        }
    status = {
        COPT.OPTIMAL: "OPTIMAL",
        COPT.INFEASIBLE: "INFEASIBLE",
        COPT.UNBOUNDED: "UNBOUNDED",
        COPT.INF_OR_UNB: "INF_OR_UNBD",
        COPT.TIMEOUT: "TIME_LIMIT",
    }.get(model.status, f"STATUS_{model.status}")
    result: dict[str, Any] = {
        "solver": "copt",
        "version": copt_version,
        "status": status,
    }
    if model.status == COPT.OPTIMAL:
        result["objective"] = float(model.objval)
        assignments = {
            name: float(variable.x) for name, variable in variables.items()
        }
        result.update(inspect_ir_assignment(ir, assignments))
    return result


def inspect_ir_assignment(
    ir: dict[str, Any], assignments: dict[str, float]
) -> dict[str, float]:
    max_integrality = 0.0
    max_bound = 0.0
    for item in ir["variables"]:
        value = assignments[item["name"]]
        if item["vartype"] in {"B", "I"}:
            max_integrality = max(max_integrality, abs(value - round(value)))
        if item["lb"] is not None:
            max_bound = max(max_bound, float(item["lb"]) - value)
        if item["ub"] is not None:
            max_bound = max(max_bound, value - float(item["ub"]))
    max_constraint = 0.0
    for constraint in ir["constraints"]:
        lhs = sum(
            float(coefficient) * assignments[name]
            for name, coefficient in constraint["terms"].items()
        )
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            violation = lhs - rhs
        elif constraint["sense"] == ">=":
            violation = rhs - lhs
        else:
            violation = abs(lhs - rhs)
        max_constraint = max(max_constraint, violation)
    return {
        "max_integrality_violation": max(0.0, max_integrality),
        "max_constraint_violation": max(0.0, max_constraint),
        "max_bound_violation": max(0.0, max_bound),
    }


def certify_ir(
    ir: dict[str, Any], gurobi_validation_ir: dict[str, Any] | None = None
) -> dict[str, Any]:
    gurobi_target = gurobi_validation_ir or ir
    gurobi = solve_ir_gurobi(gurobi_target)
    gurobi["model_representation"] = (
        "gurobi_presolved_equivalent"
        if gurobi_validation_ir is not None
        else "raw_canonical_ir"
    )
    copt = solve_ir_copt(ir)
    copt["model_representation"] = "raw_canonical_ir"
    copt_on_validation_ir = (
        solve_ir_copt(gurobi_validation_ir)
        if gurobi_validation_ir is not None
        else None
    )
    if copt_on_validation_ir is not None:
        copt_on_validation_ir[
            "model_representation"
        ] = "gurobi_presolved_equivalent"
    both_optimal = gurobi["status"] == copt["status"] == "OPTIMAL"
    all_objectives = [
        result["objective"]
        for result in (gurobi, copt, copt_on_validation_ir)
        if result is not None and result["status"] == "OPTIMAL"
    ]
    objectives_agree = both_optimal and len(all_objectives) == (
        3 if copt_on_validation_ir is not None else 2
    ) and all(
        math.isclose(
            float(all_objectives[0]),
            float(value),
            rel_tol=REL_TOL,
            abs_tol=ABS_TOL,
        )
        for value in all_objectives[1:]
    )
    result_set = [gurobi, copt]
    if copt_on_validation_ir is not None:
        result_set.append(copt_on_validation_ir)
    residuals_pass = both_optimal and all(
        float(result.get(key, math.inf)) <= ABS_TOL
        for result in result_set
        for key in (
            "max_integrality_violation",
            "max_constraint_violation",
            "max_bound_violation",
        )
    )
    return {
        "gurobi": gurobi,
        "copt": copt,
        "copt_on_gurobi_validation_ir": copt_on_validation_ir,
        "gurobi_validation_model": (
            "gurobi_presolved_equivalent"
            if gurobi_validation_ir is not None
            else "raw_canonical_ir"
        ),
        "checks": {
            "both_optimal": both_optimal,
            "objectives_agree": objectives_agree,
            "residuals_and_integrality_pass": residuals_pass,
            "passed": both_optimal and objectives_agree and residuals_pass,
        },
    }


def execute_worker(code: str, source_id: str) -> dict[str, Any]:
    payload = json.dumps(
        {"code": code, "source_id": source_id},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).resolve()), "--worker"],
            input=payload,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(OUTPUT_ROOT),
            timeout=WORKER_TIMEOUT_SECONDS,
            check=False,
            env={
                "PYTHONUTF8": "1",
                "GRB_LICENSE_FILE": os.environ.get("GRB_LICENSE_FILE", ""),
                "COPT_LICENSE_DIR": os.environ.get("COPT_LICENSE_DIR", ""),
            },
        )
    except subprocess.TimeoutExpired as error:
        return {
            "ok": False,
            "error_type": "WorkerTimeout",
            "error": f"worker exceeded {WORKER_TIMEOUT_SECONDS}s",
            "stdout_tail": (error.stdout or "")[-4000:],
            "stderr_tail": (error.stderr or "")[-4000:],
        }
    if completed.returncode != 0:
        return {
            "ok": False,
            "error_type": "WorkerProcessError",
            "error": f"worker return code {completed.returncode}",
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-8000:],
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return {
            "ok": False,
            "error_type": "WorkerProtocolError",
            "error": str(error),
            "stdout_tail": completed.stdout[-8000:],
            "stderr_tail": completed.stderr[-8000:],
        }


def build_audit() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    selected_rows = [
        row
        for row in read_jsonl(BASE_CANDIDATES_PATH)
        if row["source_dataset"] == "OptMinerBench"
    ]
    selected_ids = {row["source_id"] for row in selected_rows}
    target_ids = selected_ids | EXTRA_ELIGIBLE_LINEAR_IDS
    benchmark_by_id = {
        omb_id(row["id"]): row for row in read_jsonl(BENCHMARK_PATH)
    }
    missing_ids = sorted(target_ids - benchmark_by_id.keys())
    if missing_ids:
        raise ValueError(f"benchmark rows missing: {missing_ids}")

    rows: list[dict[str, Any]] = []
    for source_id in sorted(target_ids):
        source = benchmark_by_id[source_id]
        problem_type = str(source.get("type") or "").upper()
        raw_code = str(source.get("code") or "")
        code = _normalize_surrogate_pairs(raw_code)
        source_origin = (
            "staging_selected_60"
            if source_id in selected_ids
            else "statically_eligible_outside_original_quota"
        )
        audit: dict[str, Any] = {
            "source_id": source_id,
            "source_origin": source_origin,
            "declared_type": problem_type,
            "scenario": str(source.get("scenario") or ""),
            "problem_sha256": sha256_bytes(
                str(source.get("problem") or "").encode("utf-8")
            ),
            "legacy_code_sha256": sha256_bytes(
                raw_code.encode("utf-8", errors="surrogatepass")
            ),
            "legacy_answer_policy": "not_read_not_gold",
            "source_family_suggestion": suggest_source_family(source),
            "problem_to_ir_semantic_risk": semantic_risk_record(source),
        }
        if problem_type not in LINEAR_TYPES:
            audit.update(
                {
                    "status": "excluded",
                    "stage": "declared_type_gate",
                    "reason": f"nonlinear_declared_type:{problem_type}",
                    "actual_linearity": {
                        "status": "excluded_by_declared_nonlinear_type",
                        "evidence": problem_type,
                    },
                }
            )
            rows.append(audit)
            continue

        safety = ast_safety_screen(code)
        audit["ast_safety_screen"] = safety
        if not safety["passed"]:
            audit.update(
                {
                    "status": "failed",
                    "stage": "ast_safety_screen",
                    "reason": "unsafe_legacy_code",
                    "actual_linearity": {
                        "status": "unknown_not_executed",
                        "evidence": "ast_safety_screen_failed",
                    },
                }
            )
            rows.append(audit)
            continue

        worker = execute_worker(code, source_id)
        audit["worker_capture"] = worker.get("capture", {})
        if not worker.get("ok"):
            worker_reason = str(worker.get("error", "unknown_worker_failure"))
            nonlinear_evidence = worker_reason.startswith(
                "nonlinear_or_nonlinearizable_structure:"
            )
            audit.update(
                {
                    "status": "failed",
                    "stage": "legacy_execution_or_ir_export",
                    "reason": worker_reason,
                    "actual_linearity": {
                        "status": (
                            "not_linear_milp"
                            if nonlinear_evidence
                            else "unknown_export_failed"
                        ),
                        "evidence": worker_reason,
                    },
                    "worker_error_type": worker.get("error_type"),
                    "worker_traceback_tail": worker.get("traceback_tail")
                    or worker.get("stderr_tail"),
                    "solver_results": {
                        "legacy_gurobi_execution": audit["worker_capture"].get(
                            "original_gurobi_observation"
                        ),
                        "gurobi_rebuild": {
                            "status": "NOT_ATTEMPTED_IR_EXPORT_FAILED",
                            "objective": None,
                        },
                        "copt_rebuild": {
                            "status": "NOT_ATTEMPTED_IR_EXPORT_FAILED",
                            "objective": None,
                        },
                    },
                }
            )
            rows.append(audit)
            continue

        ir = worker["ir"]
        gurobi_validation_ir = worker.get("gurobi_validation_ir")
        audit["actual_linearity"] = {
            "status": "linear_or_mixed_integer_linear",
            "evidence": ir["structural_counts"],
        }
        audit["problem_to_ir_semantic_risk"] = semantic_risk_record(source, ir)
        ir_path = OUTPUT_ROOT / f"{source_id}.canonical_ir.json"
        ir_path.write_text(
            json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        try:
            solver_certificate = certify_ir(ir, gurobi_validation_ir)
        except BaseException as error:
            audit.update(
                {
                    "status": "failed",
                    "stage": "dual_solver_rebuild",
                    "reason": f"{type(error).__name__}:{error}",
                    "traceback_tail": traceback.format_exc()[-8000:],
                    "ir_path": str(ir_path.relative_to(DATASET_ROOT)),
                    "ir_sha256": sha256_bytes(ir_path.read_bytes()),
                    "canonical_ir_sha256": ir["canonical_sha256"],
                }
            )
            rows.append(audit)
            continue

        validation_ir_path = None
        validation_ir_sha256 = None
        if gurobi_validation_ir is not None:
            validation_ir_path = OUTPUT_ROOT / f"{source_id}.gurobi_presolved_ir.json"
            validation_ir_path.write_text(
                json.dumps(
                    gurobi_validation_ir,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            validation_ir_sha256 = sha256_bytes(validation_ir_path.read_bytes())

        certificate_path = OUTPUT_ROOT / f"{source_id}.solver_certificate.json"
        certificate_path.write_text(
            json.dumps(
                solver_certificate, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        passed = bool(solver_certificate["checks"]["passed"])
        if passed:
            failure_reason = None
        elif solver_certificate["gurobi"]["status"] == "LICENSE_SIZE_LIMIT":
            failure_reason = "gurobi_license_size_limit"
        elif solver_certificate["gurobi"]["status"] != "OPTIMAL":
            failure_reason = (
                f"gurobi_nonoptimal:{solver_certificate['gurobi']['status']}"
            )
        elif solver_certificate["copt"]["status"] != "OPTIMAL":
            failure_reason = f"copt_nonoptimal:{solver_certificate['copt']['status']}"
        elif not solver_certificate["checks"]["objectives_agree"]:
            failure_reason = "gurobi_copt_objective_mismatch"
        else:
            failure_reason = "solver_residual_or_integrality_failure"
        audit.update(
            {
                "status": "certified" if passed else "failed",
                "stage": "complete" if passed else "dual_solver_rebuild",
                "reason": failure_reason,
                "ir_path": str(ir_path.relative_to(DATASET_ROOT)),
                "certificate_path": str(certificate_path.relative_to(DATASET_ROOT)),
                "gurobi_validation_ir_path": (
                    str(validation_ir_path.relative_to(DATASET_ROOT))
                    if validation_ir_path is not None
                    else None
                ),
                "ir_sha256": sha256_bytes(ir_path.read_bytes()),
                "certificate_sha256": sha256_bytes(certificate_path.read_bytes()),
                "gurobi_validation_ir_sha256": validation_ir_sha256,
                "canonical_ir_sha256": ir["canonical_sha256"],
                "structural_counts": ir["structural_counts"],
                "solver_checks": solver_certificate["checks"],
                "solver_results": {
                    "legacy_gurobi_execution": audit["worker_capture"].get(
                        "original_gurobi_observation"
                    ),
                    "gurobi": solver_certificate["gurobi"],
                    "copt": solver_certificate["copt"],
                    "copt_on_gurobi_validation_ir": solver_certificate.get(
                        "copt_on_gurobi_validation_ir"
                    ),
                },
            }
        )
        rows.append(audit)

    counts = Counter(row["status"] for row in rows)
    reasons = Counter(
        str(row.get("reason")) for row in rows if row["status"] != "certified"
    )
    certified_ids = [row["source_id"] for row in rows if row["status"] == "certified"]
    failed_ids = [row["source_id"] for row in rows if row["status"] == "failed"]
    excluded_ids = [row["source_id"] for row in rows if row["status"] == "excluded"]
    actual_linearity_counts = Counter(
        str(row.get("actual_linearity", {}).get("status", "missing")) for row in rows
    )
    actual_linear_ids = [
        row["source_id"]
        for row in rows
        if row.get("actual_linearity", {}).get("status")
        == "linear_or_mixed_integer_linear"
    ]
    actual_nonlinear_ids = [
        row["source_id"]
        for row in rows
        if row.get("actual_linearity", {}).get("status") == "not_linear_milp"
    ]
    family_suggestion_counts = Counter(
        str(row["source_family_suggestion"]["family"]) for row in rows
    )
    summary = {
        "schema_version": "searchworthyor.optminer-source-certification-summary.v1",
        "benchmark_path": str(BENCHMARK_PATH),
        "benchmark_sha256": sha256_bytes(BENCHMARK_PATH.read_bytes()),
        "base_candidates_sha256": sha256_bytes(BASE_CANDIDATES_PATH.read_bytes()),
        "target_count": len(rows),
        "original_selected_count": len(selected_ids),
        "extra_eligible_linear_ids": sorted(EXTRA_ELIGIBLE_LINEAR_IDS),
        "prior_nonlinear_candidate_exclusions": sorted(PRIOR_NONLINEAR_CANDIDATE_IDS),
        "declared_linear_count": sum(
            row["declared_type"] in LINEAR_TYPES for row in rows
        ),
        "status_counts": dict(sorted(counts.items())),
        "actual_linearity_counts": dict(sorted(actual_linearity_counts.items())),
        "actual_linear_ids": actual_linear_ids,
        "actual_nonlinear_ids": actual_nonlinear_ids,
        "source_family_suggestion_counts": dict(
            sorted(family_suggestion_counts.items())
        ),
        "failure_or_exclusion_reasons": dict(sorted(reasons.items())),
        "certified_ids": certified_ids,
        "failed_ids": failed_ids,
        "excluded_ids": excluded_ids,
        "legacy_answer_policy": "not_read_not_gold",
        "passed": len(certified_ids) == 57 and not failed_ids,
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Run declared-type and AST safety gates without executing legacy code.",
    )
    args = parser.parse_args()

    if args.worker:
        payload = json.loads(sys.stdin.read())
        sys.stdout.write(
            json.dumps(_worker(payload), ensure_ascii=True, separators=(",", ":"))
        )
        return 0

    if args.scan_only:
        selected_ids = {
            row["source_id"]
            for row in read_jsonl(BASE_CANDIDATES_PATH)
            if row["source_dataset"] == "OptMinerBench"
        }
        target_ids = selected_ids | EXTRA_ELIGIBLE_LINEAR_IDS
        benchmark_by_id = {
            omb_id(row["id"]): row for row in read_jsonl(BENCHMARK_PATH)
        }
        scan_rows = []
        for source_id in sorted(target_ids):
            row = benchmark_by_id[source_id]
            problem_type = str(row.get("type") or "").upper()
            safety = ast_safety_screen(
                _normalize_surrogate_pairs(str(row.get("code") or ""))
            )
            scan_rows.append(
                {
                    "source_id": source_id,
                    "declared_type": problem_type,
                    "linear_type": problem_type in LINEAR_TYPES,
                    "ast_safety_screen": safety,
                }
            )
        print(json.dumps(scan_rows, ensure_ascii=False, indent=2))
        return 0 if all(
            not row["linear_type"] or row["ast_safety_screen"]["passed"]
            for row in scan_rows
        ) else 2

    audit_rows, summary = build_audit()
    write_jsonl(AUDIT_PATH, audit_rows)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
