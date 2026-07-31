import gurobipy as gp
import json
import math

ir = {
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
        "terms": {"x_0": 1013, "x_1": 952, "x_2": 910, "x_3": 849, "x_4": 788, "x_5": 746, "x_6": 685, "x_7": 643}
    },
    "constraints": [
        {"name": "facility_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "service_area_1_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1, "x_4": 1, "x_6": 1}},
        {"name": "service_area_2_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_3": 1, "x_5": 1, "x_7": 1}},
        {"name": "terminal_backup_mutual_exclusion", "sense": "<=", "rhs": 1, "terms": {"x_6": 1, "x_7": 1}},
        {"name": "applicable_safeguard_minimum", "sense": ">=", "rhs": 1, "terms": {"x_6": 1, "x_7": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model("SWOR028")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0
x = {}
for spec in ir["variables"]:
    x[spec["name"]] = model.addVar(lb=spec["lb"], ub=spec["ub"], vtype=gp.GRB.BINARY, name=spec["name"])
model.update()

objective = ir["objective"]["constant"] + gp.quicksum(coef * x[name] for name, coef in ir["objective"]["terms"].items())
model.setObjective(objective, gp.GRB.MAXIMIZE)

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
    raw_values = {name: x[name].X for name in x}
    projected_action = [int(raw_values[name] >= 0.5) for name in ir["action_projection"]]
    max_constraint_violation = 0.0
    for constraint in ir["constraints"]:
        lhs_value = sum(coef * raw_values[name] for name, coef in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - constraint["rhs"])
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in raw_values.values())
    objective_value = model.ObjVal
else:
    projected_action = [0 for _ in ir["action_projection"]]
    max_constraint_violation = None
    integrality_violation = None
    objective_value = None

print(json.dumps({
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))