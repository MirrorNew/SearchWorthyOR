"""Canonical binary-MILP solvers and exact certificates for SearchWorthyOR-100."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from typing import Any


TOL = 1e-6
_COPT_ENV = None


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def objective_value(ir: dict[str, Any], assignment: dict[str, float]) -> float:
    objective = ir["objective"]
    return float(objective.get("constant", 0.0)) + sum(
        float(coef) * float(assignment.get(name, 0.0))
        for name, coef in objective["terms"].items()
    )


def constraint_lhs(constraint: dict[str, Any], assignment: dict[str, float]) -> float:
    return sum(
        float(coef) * float(assignment.get(name, 0.0))
        for name, coef in constraint["terms"].items()
    )


def constraint_violation(
    constraint: dict[str, Any], assignment: dict[str, float]
) -> float:
    lhs = constraint_lhs(constraint, assignment)
    rhs = float(constraint["rhs"])
    if constraint["sense"] == "<=":
        return max(0.0, lhs - rhs)
    if constraint["sense"] == ">=":
        return max(0.0, rhs - lhs)
    if constraint["sense"] == "==":
        return abs(lhs - rhs)
    raise ValueError(f"Unsupported constraint sense: {constraint['sense']}")


def inspect_assignment(
    ir: dict[str, Any], assignment: dict[str, float]
) -> dict[str, Any]:
    residuals = {
        constraint["name"]: {
            "lhs": constraint_lhs(constraint, assignment),
            "sense": constraint["sense"],
            "rhs": float(constraint["rhs"]),
            "violation": constraint_violation(constraint, assignment),
        }
        for constraint in ir["constraints"]
    }
    integrality_violation = max(
        (
            abs(float(assignment[var["name"]]) - round(float(assignment[var["name"]])))
            for var in ir["variables"]
            if var["vartype"] in {"B", "I"}
        ),
        default=0.0,
    )
    bound_violation = 0.0
    for var in ir["variables"]:
        value = float(assignment[var["name"]])
        bound_violation = max(
            bound_violation,
            max(0.0, float(var.get("lb", 0.0)) - value),
            max(0.0, value - float(var.get("ub", 1.0))),
        )
    return {
        "objective_recomputed": objective_value(ir, assignment),
        "constraint_residuals": residuals,
        "max_constraint_violation": max(
            (entry["violation"] for entry in residuals.values()), default=0.0
        ),
        "integrality_violation": integrality_violation,
        "bound_violation": bound_violation,
    }


def project_action(
    ir: dict[str, Any], assignment: dict[str, float]
) -> tuple[int | float, ...]:
    """Project solver assignments without corrupting continuous decisions."""

    variable_types = {
        variable["name"]: variable["vartype"] for variable in ir["variables"]
    }
    projected: list[int | float] = []
    for name in ir["action_projection"]:
        value = float(assignment[name])
        if variable_types[name] in {"B", "I"}:
            projected.append(int(round(value)))
        else:
            projected.append(value)
    return tuple(projected)


def enumerate_optimal_actions(
    ir: dict[str, Any], epsilon: float = TOL
) -> dict[str, Any]:
    variables = ir["variables"]
    if any(var["vartype"] != "B" for var in variables):
        raise ValueError("The exact enumerator currently accepts binary variables only.")
    names = [var["name"] for var in variables]
    feasible: list[tuple[float, dict[str, float]]] = []
    for bits in itertools.product((0.0, 1.0), repeat=len(names)):
        assignment = dict(zip(names, bits, strict=True))
        inspection = inspect_assignment(ir, assignment)
        if (
            inspection["max_constraint_violation"] <= epsilon
            and inspection["bound_violation"] <= epsilon
        ):
            feasible.append((objective_value(ir, assignment), assignment))
    if not feasible:
        return {
            "status": "INFEASIBLE",
            "objective": None,
            "optimal_actions": [],
            "optimal_assignments": [],
            "feasible_assignment_count": 0,
            "complete": True,
        }
    sense = ir["sense"]
    best = (
        max(value for value, _ in feasible)
        if sense == "max"
        else min(value for value, _ in feasible)
    )
    acceptable = [
        assignment
        for value, assignment in feasible
        if (
            value >= best - epsilon
            if sense == "max"
            else value <= best + epsilon
        )
    ]
    actions = sorted({project_action(ir, assignment) for assignment in acceptable})
    return {
        "status": "OPTIMAL",
        "objective": best,
        "optimal_actions": [list(action) for action in actions],
        "optimal_assignments": acceptable,
        "feasible_assignment_count": len(feasible),
        "complete": True,
    }


def solve_gurobi(ir: dict[str, Any]) -> dict[str, Any]:
    import gurobipy as gp
    from gurobipy import GRB

    model = gp.Model(ir["model_id"])
    model.Params.OutputFlag = 0
    model.Params.Seed = 20260730
    model.Params.Threads = 1
    variables = {}
    for var in ir["variables"]:
        vtype = {"B": GRB.BINARY, "I": GRB.INTEGER, "C": GRB.CONTINUOUS}[
            var["vartype"]
        ]
        variables[var["name"]] = model.addVar(
            lb=float(var.get("lb", 0.0)),
            ub=float(var.get("ub", 1.0)),
            vtype=vtype,
            name=var["name"],
        )
    model.update()
    objective = gp.LinExpr(float(ir["objective"].get("constant", 0.0)))
    for name, coef in ir["objective"]["terms"].items():
        objective += float(coef) * variables[name]
    model.setObjective(objective, GRB.MAXIMIZE if ir["sense"] == "max" else GRB.MINIMIZE)
    for constraint in ir["constraints"]:
        lhs = gp.LinExpr()
        for name, coef in constraint["terms"].items():
            lhs += float(coef) * variables[name]
        if constraint["sense"] == "<=":
            model.addConstr(lhs <= float(constraint["rhs"]), name=constraint["name"])
        elif constraint["sense"] == ">=":
            model.addConstr(lhs >= float(constraint["rhs"]), name=constraint["name"])
        elif constraint["sense"] == "==":
            model.addConstr(lhs == float(constraint["rhs"]), name=constraint["name"])
        else:
            raise ValueError(constraint["sense"])
    model.optimize()
    status_name = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
    }.get(model.Status, f"STATUS_{model.Status}")
    if model.Status != GRB.OPTIMAL:
        return {
            "solver": "gurobi",
            "version": ".".join(map(str, gp.gurobi.version())),
            "status": status_name,
        }
    assignment = {name: float(var.X) for name, var in variables.items()}
    inspection = inspect_assignment(ir, assignment)
    return {
        "solver": "gurobi",
        "version": ".".join(map(str, gp.gurobi.version())),
        "status": status_name,
        "objective": float(model.ObjVal),
        "assignment": assignment,
        "projected_action": list(project_action(ir, assignment)),
        **inspection,
    }


def solve_copt(ir: dict[str, Any]) -> dict[str, Any]:
    import coptpy as cp
    from coptpy import COPT

    global _COPT_ENV
    if _COPT_ENV is None:
        _COPT_ENV = cp.Envr()
    model = _COPT_ENV.createModel(ir["model_id"])
    model.setParam(COPT.Param.Logging, 0)
    variables = {}
    for var in ir["variables"]:
        vtype = {"B": COPT.BINARY, "I": COPT.INTEGER, "C": COPT.CONTINUOUS}[
            var["vartype"]
        ]
        variables[var["name"]] = model.addVar(
            lb=float(var.get("lb", 0.0)),
            ub=float(var.get("ub", 1.0)),
            vtype=vtype,
            name=var["name"],
        )
    objective = float(ir["objective"].get("constant", 0.0))
    for name, coef in ir["objective"]["terms"].items():
        objective += float(coef) * variables[name]
    model.setObjective(objective, COPT.MAXIMIZE if ir["sense"] == "max" else COPT.MINIMIZE)
    for constraint in ir["constraints"]:
        lhs = 0.0
        for name, coef in constraint["terms"].items():
            lhs += float(coef) * variables[name]
        if constraint["sense"] == "<=":
            model.addConstr(lhs <= float(constraint["rhs"]), name=constraint["name"])
        elif constraint["sense"] == ">=":
            model.addConstr(lhs >= float(constraint["rhs"]), name=constraint["name"])
        elif constraint["sense"] == "==":
            model.addConstr(lhs == float(constraint["rhs"]), name=constraint["name"])
        else:
            raise ValueError(constraint["sense"])
    model.solve()
    status_name = {
        COPT.OPTIMAL: "OPTIMAL",
        COPT.INFEASIBLE: "INFEASIBLE",
        COPT.UNBOUNDED: "UNBOUNDED",
        COPT.INF_OR_UNB: "INF_OR_UNBD",
    }.get(model.status, f"STATUS_{model.status}")
    if model.status != COPT.OPTIMAL:
        return {"solver": "copt", "version": "8.0.5", "status": status_name}
    assignment = {name: float(var.x) for name, var in variables.items()}
    inspection = inspect_assignment(ir, assignment)
    return {
        "solver": "copt",
        "version": "8.0.5",
        "status": status_name,
        "objective": float(model.objval),
        "assignment": assignment,
        "projected_action": list(project_action(ir, assignment)),
        **inspection,
    }


def certify_ir(ir: dict[str, Any], epsilon: float = TOL) -> dict[str, Any]:
    exact = enumerate_optimal_actions(ir, epsilon)
    gurobi = solve_gurobi(ir)
    copt = solve_copt(ir)
    checks = {
        "all_optimal": all(
            result["status"] == "OPTIMAL" for result in (exact, gurobi, copt)
        ),
        "objectives_agree": False,
        "solver_actions_in_exact_set": False,
        "residuals_pass": False,
        "integrality_pass": False,
    }
    if checks["all_optimal"]:
        objectives = [exact["objective"], gurobi["objective"], copt["objective"]]
        checks["objectives_agree"] = max(objectives) - min(objectives) <= epsilon
        exact_actions = {tuple(action) for action in exact["optimal_actions"]}
        checks["solver_actions_in_exact_set"] = (
            tuple(gurobi["projected_action"]) in exact_actions
            and tuple(copt["projected_action"]) in exact_actions
        )
        checks["residuals_pass"] = (
            gurobi["max_constraint_violation"] <= epsilon
            and copt["max_constraint_violation"] <= epsilon
            and gurobi["bound_violation"] <= epsilon
            and copt["bound_violation"] <= epsilon
        )
        checks["integrality_pass"] = (
            gurobi["integrality_violation"] <= epsilon
            and copt["integrality_violation"] <= epsilon
        )
    checks["passed"] = all(checks.values())
    return {"exact_enumeration": exact, "gurobi": gurobi, "copt": copt, "checks": checks}


def certify_world_pair(
    base_ir: dict[str, Any], patched_ir: dict[str, Any], epsilon: float = TOL
) -> dict[str, Any]:
    base = certify_ir(base_ir, epsilon)
    patched = certify_ir(patched_ir, epsilon)
    base_actions = {
        tuple(action) for action in base["exact_enumeration"]["optimal_actions"]
    }
    patched_actions = {
        tuple(action) for action in patched["exact_enumeration"]["optimal_actions"]
    }
    intersection = sorted(base_actions & patched_actions)
    return {
        "epsilon": epsilon,
        "certificate_method": "complete_binary_enumeration",
        "base": base,
        "patched": patched,
        "base_acceptable_actions": [list(action) for action in sorted(base_actions)],
        "patched_acceptable_actions": [
            list(action) for action in sorted(patched_actions)
        ],
        "intersection": [list(action) for action in intersection],
        "intersection_empty": not intersection,
        "complete_action_sets": True,
        "passed": base["checks"]["passed"]
        and patched["checks"]["passed"]
        and not intersection,
    }


def assert_close(left: float, right: float, tolerance: float = TOL) -> None:
    if not math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(f"{left} != {right} within {tolerance}")
