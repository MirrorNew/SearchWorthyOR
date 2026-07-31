import gurobipy as gp
import json
import math

model = gp.Model("SWOR018")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_coefficients = {
    "x_0": 1005,
    "x_1": 963,
    "x_2": 902,
    "x_3": 841,
    "x_4": 799,
    "x_5": 738,
    "x_6": 696
}
model.setObjective(gp.quicksum(objective_coefficients[name] * x[name] for name in names), gp.GRB.MAXIMIZE)

constraints = [
    ("max_enabled_units", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("grid_resource_capacity", "<=", 6, {"x_0": 1, "x_1": 2, "x_2": 3, "x_3": 4, "x_4": 1, "x_5": 2, "x_6": 3}),
    ("minimum_clean_capability", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("minimum_backup_capability", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("exactly_one_core_backup_emergency", "==", 1, {"x_1": 1, "x_4": 1, "x_6": 1})
]

for constraint_name, constraint_sense, rhs, terms in constraints:
    expression = gp.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if constraint_sense == "<=":
        model.addConstr(expression <= rhs, name=constraint_name)
    elif constraint_sense == ">=":
        model.addConstr(expression >= rhs, name=constraint_name)
    else:
        model.addConstr(expression == rhs, name=constraint_name)

model.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
    gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    violations = []
    for constraint_name, constraint_sense, rhs, terms in constraints:
        lhs = sum(coefficient * values[name] for name, coefficient in terms.items())
        if constraint_sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif constraint_sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for name in names:
        violations.append(max(0.0, -values[name], values[name] - 1.0))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations) if violations else 0.0,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
