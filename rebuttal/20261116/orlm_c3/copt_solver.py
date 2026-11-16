"""COPT backend for the ORLM adapter; consumes the compiled linear IR only."""
from __future__ import annotations

import math
import re


STATUS_NAMES = {
    "OPTIMAL": "OPTIMAL",
    "INFEASIBLE": "INFEASIBLE",
    "UNBOUNDED": "UNBOUNDED",
    "INF_OR_UNB": "INF_OR_UNB",
    "TIMEOUT": "TIME_LIMIT",
    "NODELIMIT": "NODE_LIMIT",
    "INTERRUPTED": "INTERRUPTED",
}


def _name(raw: str, used: set[str], prefix: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", str(raw))
    if not value or not re.match(r"[A-Za-z_]", value):
        value = prefix + value
    value = value[:180]
    candidate = value
    suffix = 1
    while candidate in used:
        tail = f"_{suffix}"
        candidate = value[:180 - len(tail)] + tail
        suffix += 1
    used.add(candidate)
    return candidate


def _bound(value, default, infinity):
    if value is None:
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        return infinity if numeric > 0 else -infinity
    if numeric >= infinity:
        return infinity
    if numeric <= -infinity:
        return -infinity
    return numeric


def _empty_result(status, solver_status=None, conflicts=None):
    return {
        "status": status,
        "solver_status": solver_status,
        "feasible": False,
        "actions": None,
        "objective": None,
        "conflict_constraints": list(conflicts or []),
        "solver": "COPT",
    }


def solve(ir, timeout=90):
    """Solve the agent-compiled linear MILP, preserving the agent's exact IR."""
    import coptpy as cp

    env = cp.Envr()
    model = env.createModel("orlm_c3")
    model.setParam(cp.COPT.Param.LogToConsole, 0)
    model.setParam(cp.COPT.Param.LogLevel, 0)
    model.setParam(cp.COPT.Param.Threads, 1)
    model.setParam(cp.COPT.Param.TimeLimit, max(0.001, float(timeout)))

    types = {
        "BINARY": cp.COPT.BINARY,
        "INTEGER": cp.COPT.INTEGER,
        "CONTINUOUS": cp.COPT.CONTINUOUS,
    }
    solver_names: dict[str, str] = {}
    used_var_names: set[str] = set()
    variables = {}
    for row in ir["variables"]:
        kind = row["type"]
        if kind not in types:
            raise ValueError(f"Unsupported variable type: {kind}")
        solver_name = _name(row["id"], used_var_names, "v_")
        solver_names[row["id"]] = solver_name
        variables[row["id"]] = model.addVar(
            lb=_bound(row.get("lb"), -cp.COPT.INFINITY, cp.COPT.INFINITY),
            ub=_bound(row.get("ub"), cp.COPT.INFINITY, cp.COPT.INFINITY),
            vtype=types[kind],
            name=solver_name,
        )

    objective = ir["objective"]
    expression = sum(
        float(coefficient) * variables[name]
        for name, coefficient in objective["terms"].items()
    ) + float(objective.get("constant", 0.0))
    sense = cp.COPT.MINIMIZE if objective["direction"] == "min" else cp.COPT.MAXIMIZE
    model.setObjective(expression, sense)

    used_con_names: set[str] = set()
    for row in ir["constraints"]:
        terms = row["terms"]
        rhs = float(row["rhs"])
        if not terms:
            satisfies = {
                "<=": 0.0 <= rhs,
                ">=": 0.0 >= rhs,
                "==": 0.0 == rhs,
            }[row["sense"]]
            if not satisfies:
                return _empty_result("INFEASIBLE", conflicts=[row["name"]])
            continue
        lhs = sum(float(coef) * variables[name] for name, coef in terms.items())
        name = _name(row["name"], used_con_names, "c_")
        if row["sense"] == "<=":
            model.addConstr(lhs <= rhs, name=name)
        elif row["sense"] == ">=":
            model.addConstr(lhs >= rhs, name=name)
        elif row["sense"] == "==":
            model.addConstr(lhs == rhs, name=name)
        else:
            raise ValueError(f"Unsupported constraint sense: {row['sense']}")

    model.solve()
    raw_status = int(model.status)
    status = next(
        (label for label in STATUS_NAMES if getattr(cp.COPT, label, object()) == raw_status),
        "UNKNOWN",
    )
    has_solution = bool(model.HasSol)
    result = {
        "status": STATUS_NAMES.get(status, status),
        "solver_status": raw_status,
        "feasible": has_solution,
        "actions": None,
        "objective": None,
        "conflict_constraints": [],
        "solver": "COPT",
        "solver_seconds": float(model.solvingtime),
    }
    if has_solution:
        actions = {}
        for row in ir["variables"]:
            if row.get("visibility", "public") != "public":
                continue
            value = float(variables[row["id"]].x)
            if row["type"] in {"BINARY", "INTEGER"} and abs(value - round(value)) <= 1e-5:
                value = int(round(value))
            actions[row["id"]] = value
        result["actions"] = actions
        result["objective"] = {
            "value": float(model.objval),
            "unit": objective["unit"],
            "direction": objective["direction"],
        }
    return result
