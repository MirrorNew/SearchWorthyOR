import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR026",
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
        "terms": {"x_0": 1002, "x_1": 960, "x_2": 899, "x_3": 857, "x_4": 796, "x_5": 735, "x_6": 693}
    },
    "constraints": [
        {"name": "c_max_modules", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "c_zone1_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "c_zone2_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "c_zone3_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "c_A_requires_B_or_E", "sense": "<=", "rhs": 0, "terms": {"x_0": 1, "x_1": -1, "x_4": -1}},
        {"name": "c_exactly_one_B_E_G", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_6": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"], ub=spec["ub"], vtype=gp.GRB.BINARY, name=spec["name"]
    )

objective = gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in ir["objective"]["terms"].items()
) + ir["objective"]["constant"]
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
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: variable.X for name, variable in variables.items()}
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(
            coefficient * values[name]
            for name, coefficient in constraint["terms"].items()
        )
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(
        abs(value - round(value)) for value in values.values()
    ) if values else 0.0
    objective_value = float(model.ObjVal)
    if not math.isfinite(objective_value):
        objective_value = None
    projected_action = [
        int(round(values[name])) for name in ir["action_projection"]
    ]
else:
    objective_value = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))