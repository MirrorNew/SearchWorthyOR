import gurobipy as gp
import json
import math

patched_ir = {
    "model_id": "SWOR038_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "lb": 0, "ub": 1},
        {"name": "x_1", "lb": 0, "ub": 1},
        {"name": "x_2", "lb": 0, "ub": 1},
        {"name": "x_3", "lb": 0, "ub": 1},
        {"name": "x_4", "lb": 0, "ub": 1},
        {"name": "x_5", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1011, "x_1": 950, "x_2": 908, "x_3": 847, "x_4": 805, "x_5": 744}
    },
    "constraints": [
        {"name": "max_modules", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "zone_1_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1}},
        {"name": "zone_2_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "zone_3_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "access_backhaul_link", "sense": "<=", "rhs": 0, "terms": {"x_0": 1, "x_1": -1, "x_4": -1}},
        {"name": "exclusive_core_backup_emergency", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_5": 1}},
        {"name": "ca_meal_period_module_A", "sense": "==", "rhs": 0, "terms": {"x_0": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        vtype=gp.GRB.BINARY,
        lb=spec["lb"],
        ub=spec["ub"],
        name=spec["name"]
    )
model.update()

objective = patched_ir["objective"]["constant"] + gp.quicksum(
    coefficient * variables[name]
    for name, coefficient in patched_ir["objective"]["terms"].items()
)
model.setObjective(objective, gp.GRB.MAXIMIZE)

for constraint in patched_ir["constraints"]:
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
status = status_names.get(model.Status, str(model.Status))
if model.SolCount > 0:
    raw_values = {name: variables[name].X for name in variables}
    projected_action = [int(round(raw_values[name])) for name in patched_ir["action_projection"]]
    objective_value = float(model.ObjVal)
else:
    raw_values = {name: 0.0 for name in variables}
    projected_action = [0 for _ in patched_ir["action_projection"]]
    objective_value = None

violations = []
for constraint in patched_ir["constraints"]:
    lhs_value = sum(
        coefficient * raw_values[name]
        for name, coefficient in constraint["terms"].items()
    )
    if constraint["sense"] == "<=":
        violations.append(max(0.0, lhs_value - constraint["rhs"]))
    elif constraint["sense"] == ">=":
        violations.append(max(0.0, constraint["rhs"] - lhs_value))
    else:
        violations.append(abs(lhs_value - constraint["rhs"]))

max_constraint_violation = max(violations) if violations else 0.0
integrality_violation = max(
    (abs(value - round(value)) for value in raw_values.values()),
    default=0.0
)
result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": float(max_constraint_violation),
    "integrality_violation": float(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
