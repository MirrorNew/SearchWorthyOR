import gurobipy as gp
import json

ir = {
    "model_id": "SWOR056",
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
        "terms": {"x_0": 1002, "x_1": 960, "x_2": 899, "x_3": 857, "x_4": 796, "x_5": 735, "x_6": 693, "x_7": 632}
    },
    "constraints": [
        {"name": "frozen_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "front_availability", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1, "x_3": 1, "x_6": 1}},
        {"name": "back_availability", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_2": 1, "x_4": 1, "x_7": 1}},
        {"name": "terminal_backup_mutex", "sense": "<=", "rhs": 1, "terms": {"x_6": 1, "x_7": 1}},
        {"name": "policy_ab_mutex", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
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

objective = gp.LinExpr(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * x[name]
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
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in x}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        violations.append(violation)
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations) if violations else 0.0,
        "integrality_violation": max(abs(value - round(value)) for value in values.values())
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
