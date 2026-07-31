import gurobipy as gp
import json
import math

ir = {
    "sense": "max",
    "single_objective": True,
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
        "terms": {"x_0": 1011, "x_1": 950, "x_2": 908, "x_3": 847, "x_4": 805, "x_5": 744}
    },
    "constraints": [
        {"name": "facility_count", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}},
        {"name": "service_area_1_coverage", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_2": 1, "x_4": 1}},
        {"name": "service_area_2_coverage", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_3": 1, "x_5": 1}},
        {"name": "core_candidates_minimum", "sense": ">=", "rhs": 2, "terms": {"x_0": 1, "x_1": 1, "x_2": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
}

model = gp.Model("SWOR040")
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
    if constraint["sense"] == "==":
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
objective_value = None
projected_action = []
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = {name: x[name].X for name in x}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    objective_value = model.ObjVal
    violations = []
    for constraint in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "==":
            violation = abs(lhs_value - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - lhs_value)
        else:
            violation = max(0.0, lhs_value - constraint["rhs"])
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values.values())

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
