import gurobipy as gp
import json
import math

ir = {
    "sense": "max",
    "variables": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1009, "x_1": 948, "x_2": 906, "x_3": 845, "x_4": 803, "x_5": 742, "x_6": 700, "x_7": 639}
    },
    "constraints": [
        {"name": "c_max_enabled", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "c_resource_capacity", "sense": "<=", "rhs": 8, "terms": {"x_0": 3, "x_1": 4, "x_2": 1, "x_3": 2, "x_4": 3, "x_5": 4, "x_6": 1, "x_7": 2}},
        {"name": "c_min_clean", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "c_min_backup", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "c_min_core", "sense": ">=", "rhs": 2, "terms": {"x_0": 1, "x_1": 1, "x_2": 1}},
        {"name": "c_external_ab_incompatibility", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model("SWOR098_patched")
model.Params.OutputFlag = 0
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in ir["variables"]}
model.setObjective(ir["objective"]["constant"] + gp.quicksum(coef * x[name] for name, coef in ir["objective"]["terms"].items()), gp.GRB.MAXIMIZE)
for constraint in ir["constraints"]:
    lhs = gp.quicksum(coef * x[name] for name, coef in constraint["terms"].items())
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])
model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
if model.SolCount > 0:
    values = {name: float(x[name].X) for name in ir["variables"]}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(coef * values[name] for name, coef in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violations.append(max(0.0, lhs_value - constraint["rhs"]))
        elif constraint["sense"] == ">=":
            violations.append(max(0.0, constraint["rhs"] - lhs_value))
        else:
            violations.append(abs(lhs_value - constraint["rhs"]))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in values.values())
    objective = float(model.ObjVal)
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
