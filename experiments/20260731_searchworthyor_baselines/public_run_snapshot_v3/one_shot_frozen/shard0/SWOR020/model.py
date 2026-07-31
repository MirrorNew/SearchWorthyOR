import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR020",
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
        {"name": "max_energy_units", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "grid_resource_capacity", "sense": "<=", "rhs": 7, "terms": {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1, "x_6": 2, "x_7": 3}},
        {"name": "minimum_clean_capability", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "minimum_backup_capability", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "policy_incompat_A_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
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

objective = ir["objective"]["constant"] + gp.quicksum(
    coefficient * x[name]
    for name, coefficient in ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gp.quicksum(
        coefficient * x[name]
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
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}

if model.SolCount > 0:
    values = {name: x[name].X for name in x}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(
            coefficient * values[name]
            for name, coefficient in constraint["terms"].items()
        )
        if constraint["sense"] == "<=":
            violations.append(max(0.0, lhs_value - constraint["rhs"]))
        elif constraint["sense"] == ">=":
            violations.append(max(0.0, constraint["rhs"] - lhs_value))
        else:
            violations.append(abs(lhs_value - constraint["rhs"]))
    integrality_violation = max(
        abs(value - round(value)) for value in values.values()
    )
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations) if violations else 0.0,
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": None,
        "projected_action": [0 for _ in ir["action_projection"]],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))