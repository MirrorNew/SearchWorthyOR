import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR070_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1001, "x_1": 959, "x_2": 898, "x_3": 856, "x_4": 795, "x_5": 753}
    },
    "constraints": [
        {"name": "maximum_enabled_plans", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "grid_resource_capacity", "sense": "<=", "rhs": 8, "terms": {"x_0": 3, "x_1": 4, "x_2": 1, "x_3": 2, "x_4": 3, "x_5": 4}},
        {"name": "minimum_clean_capability", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
        {"name": "minimum_backup_capability", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "terminal_guarantee_exclusion", "sense": "<=", "rhs": 1, "terms": {"x_4": 1, "x_5": 1}},
        {"name": "policy_minimum_compatible_guarantee", "sense": ">=", "rhs": 1, "terms": {"x_4": 1, "x_5": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
x = {}
for variable in ir["variables"]:
    x[variable["name"]] = model.addVar(
        vtype=gp.GRB.BINARY,
        lb=variable["lb"],
        ub=variable["ub"],
        name=variable["name"]
    )

objective = gp.LinExpr()
objective.addConstant(float(ir["objective"]["constant"]))
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * x[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    expression = gp.LinExpr()
    for name, coefficient in constraint["terms"].items():
        expression += coefficient * x[name]
    if constraint["sense"] == "<=":
        model.addConstr(expression <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(expression >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(expression == constraint["rhs"], name=constraint["name"])

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
    values = {name: x[name].X for name in x}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    violations = []
    for constraint in ir["constraints"]:
        lhs = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        rhs = constraint["rhs"]
        if constraint["sense"] == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif constraint["sense"] == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for variable in ir["variables"]:
        value = values[variable["name"]]
        violations.append(max(0.0, variable["lb"] - value, value - variable["ub"]))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max_constraint_violation),
        "integrality_violation": float(integrality_violation)
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