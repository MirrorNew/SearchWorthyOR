import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR017",
    "sense": "max",
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1},
        {"name": "x_7", "vartype": "B", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841, "x_4": 799, "x_5": 738, "x_6": 696, "x_7": 635}
    },
    "constraints": [
        {"name": "maximum_enabled_modes", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "equipment_capacity_limit", "sense": "<=", "rhs": 8, "terms": {"x_0": 3, "x_1": 4, "x_2": 1, "x_3": 2, "x_4": 3, "x_5": 4, "x_6": 1, "x_7": 2}},
        {"name": "terminal_backup_conflict", "sense": "<=", "rhs": 1, "terms": {"x_6": 1, "x_7": 1}},
        {"name": "external_A_trigger_forbids_B", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = gp.LinExpr()
objective.addConstant(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for spec in ir["constraints"]:
    lhs = gp.LinExpr()
    for name, coefficient in spec["terms"].items():
        lhs += coefficient * variables[name]
    if spec["sense"] == "<=":
        model.addConstr(lhs <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(lhs >= spec["rhs"], name=spec["name"])
    else:
        model.addConstr(lhs == spec["rhs"], name=spec["name"])

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: variables[name].X for name in variables}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    objective_value = float(model.ObjVal)
    max_constraint_violation = 0.0
    for spec in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs_value - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - spec["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    for spec in ir["variables"]:
        value = values[spec["name"]]
        max_constraint_violation = max(max_constraint_violation, max(0.0, spec["lb"] - value, value - spec["ub"]))
    integrality_violation = max(abs(value - round(value)) for value in values.values())
else:
    objective_value = None
    projected_action = None
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