import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR085_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "lb": 0, "ub": 1},
        {"name": "x_1", "lb": 0, "ub": 1},
        {"name": "x_2", "lb": 0, "ub": 1},
        {"name": "x_3", "lb": 0, "ub": 1},
        {"name": "x_4", "lb": 0, "ub": 1},
        {"name": "x_5", "lb": 0, "ub": 1},
        {"name": "x_6", "lb": 0, "ub": 1},
        {"name": "x_7", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1018, "x_1": 957, "x_2": 896, "x_3": 854, "x_4": 793, "x_5": 751, "x_6": 690, "x_7": 629}
    },
    "constraints": [
        {"name": "max_three_modes", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "equipment_capacity", "sense": "<=", "rhs": 7, "terms": {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1, "x_6": 2, "x_7": 3}},
        {"name": "frozen_exactly_one_B_E_H", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "gluten_free_A_B_conflict", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in ir["variables"]:
    variables[spec["name"]] = model.addVar(
        vtype=gp.GRB.BINARY,
        lb=spec["lb"],
        ub=spec["ub"],
        name=spec["name"]
    )
model.update()

objective = ir["objective"]["constant"] + gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gp.quicksum(
        coefficient * variables[name]
        for name, coefficient in constraint["terms"].items()
    )
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
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = {name: variables[name].X for name in ir["action_projection"]}
    projected_action = [1 if raw[name] >= 0.5 else 0 for name in ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in ir["constraints"]:
        lhs_value = sum(coefficient * raw[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in raw.values())
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
        "projected_action": [0 for _ in ir["action_projection"]],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))