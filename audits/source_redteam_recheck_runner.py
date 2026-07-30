"""Independent, resumable Gurobi/COPT recheck for source-red-team auditing.

This script is intentionally separate from both source-certification generators.
It reads frozen IR artifacts, recompiles them in both solvers, recomputes the
objective and all residual classes from returned assignments, and appends one
hash-bound result per IR to a private checkpoint cache.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from typing import Any

import coptpy as cp
import gurobipy as gp
from coptpy import COPT
from gurobipy import GRB


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "audits" / ".source_redteam_solver_cache.jsonl"
TIME_LIMIT = 30.0
TOL = 1e-6


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignment_hash(assignment: dict[str, float]) -> str:
    rounded = {
        name: (
            int(round(value))
            if abs(value - round(value)) <= 1e-7
            else round(value, 10)
        )
        for name, value in sorted(assignment.items())
    }
    return canonical_hash(rounded)


def inspect(ir: dict[str, Any], assignment: dict[str, float]) -> dict[str, Any]:
    objective = float(ir["objective"].get("constant", 0.0)) + sum(
        float(coefficient) * assignment[name]
        for name, coefficient in ir["objective"]["terms"].items()
    )
    max_integrality = 0.0
    max_bound = 0.0
    for variable in ir["variables"]:
        value = assignment[variable["name"]]
        if variable["vartype"] in {"B", "I"}:
            max_integrality = max(max_integrality, abs(value - round(value)))
        if variable.get("lb") is not None:
            max_bound = max(max_bound, float(variable["lb"]) - value)
        if variable.get("ub") is not None:
            max_bound = max(max_bound, value - float(variable["ub"]))
    max_constraint = 0.0
    for constraint in ir["constraints"]:
        lhs = sum(
            float(coefficient) * assignment[name]
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
        "objective_recomputed": objective,
        "max_integrality_violation": max(0.0, max_integrality),
        "max_bound_violation": max(0.0, max_bound),
        "max_constraint_violation": max(0.0, max_constraint),
        "assignment_sha256": assignment_hash(assignment),
        "assignment_count": len(assignment),
    }


def solve_gurobi(ir: dict[str, Any]) -> dict[str, Any]:
    model = gp.Model("source_redteam_gurobi")
    model.Params.OutputFlag = 0
    model.Params.Threads = 1
    model.Params.Seed = 20260730
    model.Params.TimeLimit = TIME_LIMIT
    variables: dict[str, Any] = {}
    for variable in ir["variables"]:
        lb = (
            -float(GRB.INFINITY)
            if variable.get("lb") is None
            else float(variable["lb"])
        )
        ub = (
            float(GRB.INFINITY)
            if variable.get("ub") is None
            else float(variable["ub"])
        )
        variables[variable["name"]] = model.addVar(
            lb=lb,
            ub=ub,
            vtype=variable["vartype"],
            name=variable["name"],
        )
    model.update()
    objective = gp.LinExpr(float(ir["objective"].get("constant", 0.0)))
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
            model.addConstr(lhs <= rhs)
        elif constraint["sense"] == ">=":
            model.addConstr(lhs >= rhs)
        else:
            model.addConstr(lhs == rhs)
    try:
        model.optimize()
    except Exception as error:
        model.dispose()
        return {
            "status": "ERROR",
            "error": f"{type(error).__name__}:{error}",
            "version": ".".join(map(str, gp.gurobi.version())),
        }
    status = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.TIME_LIMIT: "TIME_LIMIT",
    }.get(model.Status, f"STATUS_{model.Status}")
    result: dict[str, Any] = {
        "status": status,
        "version": ".".join(map(str, gp.gurobi.version())),
    }
    if model.Status == GRB.OPTIMAL:
        assignment = {
            name: float(variable.X) for name, variable in variables.items()
        }
        result["objective"] = float(model.ObjVal)
        result.update(inspect(ir, assignment))
    model.dispose()
    return result


def solve_copt(ir: dict[str, Any], environment: Any) -> dict[str, Any]:
    model = environment.createModel("source_redteam_copt")
    model.setParam(COPT.Param.Logging, 0)
    model.setParam(COPT.Param.Threads, 1)
    model.setParam(COPT.Param.TimeLimit, TIME_LIMIT)
    variable_types = {
        "B": COPT.BINARY,
        "I": COPT.INTEGER,
        "C": COPT.CONTINUOUS,
    }
    variables: dict[str, Any] = {}
    for variable in ir["variables"]:
        lb = (
            -float(COPT.INFINITY)
            if variable.get("lb") is None
            else float(variable["lb"])
        )
        ub = (
            float(COPT.INFINITY)
            if variable.get("ub") is None
            else float(variable["ub"])
        )
        variables[variable["name"]] = model.addVar(
            lb=lb,
            ub=ub,
            vtype=variable_types[variable["vartype"]],
            name=variable["name"],
        )
    objective: Any = float(ir["objective"].get("constant", 0.0))
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
            model.addConstr(lhs <= rhs)
        elif constraint["sense"] == ">=":
            model.addConstr(lhs >= rhs)
        else:
            model.addConstr(lhs == rhs)
    version = importlib.metadata.version("coptpy")
    try:
        model.solve()
    except Exception as error:
        return {
            "status": "ERROR",
            "error": f"{type(error).__name__}:{error}",
            "version": version,
        }
    status = {
        COPT.OPTIMAL: "OPTIMAL",
        COPT.INFEASIBLE: "INFEASIBLE",
        COPT.UNBOUNDED: "UNBOUNDED",
        COPT.INF_OR_UNB: "INF_OR_UNBD",
        COPT.TIMEOUT: "TIME_LIMIT",
    }.get(model.status, f"STATUS_{model.status}")
    result: dict[str, Any] = {"status": status, "version": version}
    if model.status == COPT.OPTIMAL:
        assignment = {
            name: float(variable.x) for name, variable in variables.items()
        }
        result["objective"] = float(model.objval)
        result.update(inspect(ir, assignment))
    return result


def ir_targets() -> list[tuple[str, str, Path]]:
    targets: list[tuple[str, str, Path]] = []
    for group in (
        "supplemental",
        "supplemental_reserve",
        "supplemental_reserve2",
    ):
        group_root = ROOT / "staging" / "certified_sources" / group
        for directory in sorted(path for path in group_root.iterdir() if path.is_dir()):
            ir_path = directory / "canonical_ir.json"
            if ir_path.exists():
                targets.append((group, directory.name, ir_path))
    current_optminer = {
        row["source_id"]
        for row in (
            json.loads(line)
            for line in (
                ROOT / "audits" / "optminer_source_certification.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if row.get("ir_sha256") and row.get("certificate_sha256")
    }
    for source_id in sorted(current_optminer):
        targets.append(
            (
                "optminer",
                source_id,
                ROOT
                / "staging"
                / "certified_sources"
                / "optminer"
                / f"{source_id}.canonical_ir.json",
            )
        )
    return targets


def main() -> int:
    cached_rows = []
    if CACHE.exists():
        cached_rows = [
            json.loads(line)
            for line in CACHE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    cached_keys = {
        (row["source_group"], row["source_id"], row["ir_file_sha256"])
        for row in cached_rows
    }
    environment = cp.Envr()
    for source_group, source_id, ir_path in ir_targets():
        ir_file_sha256 = file_hash(ir_path)
        key = (source_group, source_id, ir_file_sha256)
        if key in cached_keys:
            continue
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        counts = ir.get("structural_counts", {})
        oversize = (
            int(counts.get("variables", len(ir.get("variables", [])))) > 2000
            or int(
                counts.get("linear_constraints", len(ir.get("constraints", [])))
            )
            > 2000
        )
        if oversize:
            # These instances already fail the release size/license gate.  Do
            # not spend minutes rebuilding up to 1.5 million variables merely
            # to reproduce the expected restricted-license failure.
            gurobi = {
                "status": "SKIPPED_OVERSIZE",
                "version": ".".join(map(str, gp.gurobi.version())),
            }
            copt = {
                "status": "SKIPPED_OVERSIZE",
                "version": importlib.metadata.version("coptpy"),
            }
        else:
            gurobi = solve_gurobi(ir)
            copt = solve_copt(ir, environment)
        objectives_agree = (
            gurobi.get("status") == copt.get("status") == "OPTIMAL"
            and math.isclose(
                float(gurobi["objective"]),
                float(copt["objective"]),
                rel_tol=1e-7,
                abs_tol=TOL,
            )
        )
        residuals_pass = objectives_agree and all(
            float(result.get(field, math.inf)) <= TOL
            for result in (gurobi, copt)
            for field in (
                "max_integrality_violation",
                "max_bound_violation",
                "max_constraint_violation",
            )
        )
        row = {
            "source_group": source_group,
            "source_id": source_id,
            "ir_file_sha256": ir_file_sha256,
            "gurobi": gurobi,
            "copt": copt,
            "optimal_objective_agreement": objectives_agree,
            "residual_bound_integrality_pass": residuals_pass,
            "pass": objectives_agree and residuals_pass,
        }
        with CACHE.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
        cached_keys.add(key)
        print(
            json.dumps(
                {
                    "source_group": source_group,
                    "source_id": source_id,
                    "pass": row["pass"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
