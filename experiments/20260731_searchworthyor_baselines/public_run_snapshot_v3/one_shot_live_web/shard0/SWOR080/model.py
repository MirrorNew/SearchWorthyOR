import gurobipy as gp
import json
import math

patched_ir = {
    "model_id": "SWOR080",
    "world": "live_web",
    "sense": "max",
    "single_objective": True,
    "variables": [
        {"name": "x_0", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包A"},
        {"name": "x_1", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包B"},
        {"name": "x_2", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包C"},
        {"name": "x_3", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包D"},
        {"name": "x_4", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包E"},
        {"name": "x_5", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包F"},
        {"name": "x_6", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包G"},
        {"name": "x_7", "vartype": "B", "lb": 0, "ub": 1, "semantic_name": "策略包H"}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1012, "x_1": 951, "x_2": 909, "x_3": 848, "x_4": 806, "x_5": 745, "x_6": 684, "x_7": 642}
    },
    "constraints": [
        {"name": "hold_exactly_3_positions", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}},
        {"name": "capital_occupancy_limit", "sense": "<=", "rhs": 12, "terms": {"x_0": 4, "x_1": 1, "x_2": 2, "x_3": 3, "x_4": 4, "x_5": 1, "x_6": 2, "x_7": 3}},
        {"name": "portfolio_risk_limit", "sense": "<=", "rhs": 15, "terms": {"x_0": 5, "x_1": 2, "x_2": 4, "x_3": 1, "x_4": 3, "x_5": 5, "x_6": 2, "x_7": 4}},
        {"name": "B_E_H_exactly_one", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_7": 1}},
        {"name": "federal_no_double_30D_45W_same_vehicle", "sense": "<=", "rhs": 1, "terms": {"x_0": 1, "x_1": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
}

model = gp.Model(patched_ir["model_id"])
model.Params.OutputFlag = 0
variables = {}
for spec in patched_ir["variables"]:
    variables[spec["name"]] = model.addVar(
        lb=spec["lb"],
        ub=spec["ub"],
        vtype=gp.GRB.BINARY,
        name=spec["name"]
    )
model.update()

objective = gp.LinExpr(patched_ir["objective"]["constant"])
for name, coefficient in patched_ir["objective"]["terms"].items():
    objective += coefficient * variables[name]
model.setObjective(objective, gp.GRB.MAXIMIZE)

for row in patched_ir["constraints"]:
    lhs = gp.LinExpr()
    for name, coefficient in row["terms"].items():
        lhs += coefficient * variables[name]
    if row["sense"] == "<=":
        model.addConstr(lhs <= row["rhs"], name=row["name"])
    elif row["sense"] == ">=":
        model.addConstr(lhs >= row["rhs"], name=row["name"])
    else:
        model.addConstr(lhs == row["rhs"], name=row["name"])

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [0 for _ in patched_ir["action_projection"]],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = {name: variables[name].X for name in variables}
    projected_action = [int(round(values[name])) for name in patched_ir["action_projection"]]
    max_violation = 0.0
    for row in patched_ir["constraints"]:
        lhs_value = sum(coefficient * values[name] for name, coefficient in row["terms"].items())
        if row["sense"] == "<=":
            violation = max(0.0, lhs_value - row["rhs"])
        elif row["sense"] == ">=":
            violation = max(0.0, row["rhs"] - lhs_value)
        else:
            violation = abs(lhs_value - row["rhs"])
        max_violation = max(max_violation, violation)
    for spec in patched_ir["variables"]:
        value = values[spec["name"]]
        max_violation = max(max_violation, max(0.0, spec["lb"] - value, value - spec["ub"]))
    integrality_violation = max(abs(value - round(value)) for value in values.values())
    objective_value = float(model.ObjVal)
    result["objective"] = objective_value if math.isfinite(objective_value) else None
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = float(max_violation)
    result["integrality_violation"] = float(integrality_violation)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))