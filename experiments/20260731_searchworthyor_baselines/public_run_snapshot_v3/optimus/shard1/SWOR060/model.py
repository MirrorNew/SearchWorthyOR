import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR060_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "lb": 0, "ub": 1},
        {"name": "x_1", "lb": 0, "ub": 1},
        {"name": "x_2", "lb": 0, "ub": 1},
        {"name": "x_3", "lb": 0, "ub": 1},
        {"name": "x_4", "lb": 0, "ub": 1},
        {"name": "x_5", "lb": 0, "ub": 1},
        {"name": "x_6", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1011, "x_1": 950, "x_2": 908, "x_3": 847, "x_4": 805, "x_5": 744, "x_6": 683}
    },
    "constraints": [
        {"name": "segment_1_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "segment_2_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "segment_3_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "core_B_E_G_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_6": 1}},
        {"name": "policy_min_guarantee", "sense": ">=", "rhs": 1, "terms": {"x_5": 1, "x_6": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for specification in ir["variables"]:
    variables[specification["name"]] = model.addVar(
        lb=specification["lb"],
        ub=specification["ub"],
        vtype=gp.GRB.BINARY,
        name=specification["name"]
    )
model.update()

objective = gp.LinExpr(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    expression = gp.LinExpr()
    for name, coefficient in constraint["terms"].items():
        expression += coefficient * variables[name]
    if constraint["sense"] == "==":
        model.addConstr(expression == constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(expression >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(expression <= constraint["rhs"], name=constraint["name"])

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
    values = {name: variables[name].X for name in variables}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in ir["constraints"]:
        lhs = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "==":
            violation = abs(lhs - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs)
        else:
            violation = max(0.0, lhs - constraint["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max_constraint_violation,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0 for name in ir["action_projection"]],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))