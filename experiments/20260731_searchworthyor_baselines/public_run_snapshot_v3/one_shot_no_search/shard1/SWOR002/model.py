import gurobipy as gp
import json
import math

ir = {
    "model_id": "SWOR002",
    "sense": "max",
    "variables": [
        {"name": "x_0", "semantic_name": "服务模块A"},
        {"name": "x_1", "semantic_name": "服务模块B"},
        {"name": "x_2", "semantic_name": "服务模块C"},
        {"name": "x_3", "semantic_name": "服务模块D"},
        {"name": "x_4", "semantic_name": "服务模块E"},
        {"name": "x_5", "semantic_name": "服务模块F"},
        {"name": "x_6", "semantic_name": "服务模块G"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1008, "x_1": 947, "x_2": 905, "x_3": 844, "x_4": 802, "x_5": 741, "x_6": 699}
    },
    "constraints": [
        {"name": "max_three_modules", "sense": "<=", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "zone_1_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "zone_2_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "zone_3_connectivity", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "module_A_requires_B_or_E", "sense": ">=", "rhs": 0, "terms": {"x_0": -1, "x_1": 1, "x_4": 1}},
        {"name": "modules_F_G_mutual_exclusion", "sense": "<=", "rhs": 1, "terms": {"x_5": 1, "x_6": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gp.Model(ir["model_id"])
model.Params.OutputFlag = 0
x = {}
for spec in ir["variables"]:
    x[spec["name"]] = model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=spec["name"])

objective = gp.LinExpr(ir["objective"]["constant"])
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * x[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for spec in ir["constraints"]:
    lhs = gp.quicksum(coefficient * x[name] for name, coefficient in spec["terms"].items())
    if spec["sense"] == "<=":
        model.addConstr(lhs <= spec["rhs"], name=spec["name"])
    elif spec["sense"] == ">=":
        model.addConstr(lhs >= spec["rhs"], name=spec["name"])
    else:
        model.addConstr(lhs == spec["rhs"], name=spec["name"])

model.optimize()

has_solution = model.SolCount > 0
result = {
    "status": int(model.Status),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if has_solution:
    values = {name: x[name].X for name in x}
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = [int(round(values[name])) for name in ir["action_projection"]]
    violations = []
    for spec in ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in spec["terms"].items())
        if spec["sense"] == "<=":
            violation = max(0.0, lhs_value - spec["rhs"])
        elif spec["sense"] == ">=":
            violation = max(0.0, spec["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - spec["rhs"])
        violations.append(violation)
    result["max_constraint_violation"] = float(max(violations) if violations else 0.0)
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in values.values()))

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
