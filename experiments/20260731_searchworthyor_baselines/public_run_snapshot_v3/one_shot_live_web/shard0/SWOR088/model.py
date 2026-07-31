import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR088_patched",
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
        "terms": {"x_0": 1003, "x_1": 961, "x_2": 900, "x_3": 858, "x_4": 797, "x_5": 736, "x_6": 694, "x_7": 633}
    },
    "constraints": [
        {"name": "segment_1_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "segment_2_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "segment_3_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "business_A_or_D", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
        {"name": "hos_11_hour_A_forbidden", "sense": "==", "rhs": 0, "terms": {"x_0": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
x = {}
for spec in ir["variables"]:
    x[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = ir["objective"]["constant"] + gp.quicksum(
    coefficient * x[name] for name, coefficient in ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in constraint["terms"].items())
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
    values = {name: float(var.X) for name, var in x.items()}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        rhs = float(constraint["rhs"])
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - rhs)
        elif constraint["sense"] == ">=":
            violation = max(0.0, rhs - lhs_value)
        else:
            violation = math.fabs(lhs_value - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(math.fabs(value - round(value)) for value in values.values())
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max_constraint_violation,
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