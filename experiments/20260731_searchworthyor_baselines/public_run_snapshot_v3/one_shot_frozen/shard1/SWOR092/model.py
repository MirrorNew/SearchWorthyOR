import gurobipy
import json
import math

ir = {
    "model_id": "SWOR092_patched",
    "sense": "max",
    "variables": [
        {"name": "x_0", "semantic_name": "班次A", "lb": 0, "ub": 1},
        {"name": "x_1", "semantic_name": "班次B", "lb": 0, "ub": 1},
        {"name": "x_2", "semantic_name": "班次C", "lb": 0, "ub": 1},
        {"name": "x_3", "semantic_name": "班次D", "lb": 0, "ub": 1},
        {"name": "x_4", "semantic_name": "班次E", "lb": 0, "ub": 1},
        {"name": "x_5", "semantic_name": "班次F", "lb": 0, "ub": 1},
        {"name": "x_6", "semantic_name": "班次G", "lb": 0, "ub": 1}
    ],
    "objective": {
        "constant": 0,
        "terms": {"x_0": 1000, "x_1": 958, "x_2": 897, "x_3": 855, "x_4": 794, "x_5": 752, "x_6": 691}
    },
    "constraints": [
        {"name": "select_exactly_3", "sense": "==", "rhs": 3, "terms": {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}},
        {"name": "cover_period_1", "sense": ">=", "rhs": 1, "terms": {"x_0": 1, "x_3": 1, "x_6": 1}},
        {"name": "cover_period_2", "sense": ">=", "rhs": 1, "terms": {"x_1": 1, "x_4": 1}},
        {"name": "cover_period_3", "sense": ">=", "rhs": 1, "terms": {"x_2": 1, "x_5": 1}},
        {"name": "core_choice_exactly_1", "sense": "==", "rhs": 1, "terms": {"x_1": 1, "x_4": 1, "x_6": 1}},
        {"name": "rest_break_10min_per_4h", "sense": ">=", "rhs": 1, "terms": {"x_5": 1, "x_6": 1}}
    ],
    "action_projection": ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
}

model = gurobipy.Model(ir["model_id"])
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = {}
for variable in ir["variables"]:
    x[variable["name"]] = model.addVar(
        lb=variable["lb"],
        ub=variable["ub"],
        vtype=gurobipy.GRB.BINARY,
        name=variable["name"]
    )

objective = gurobipy.LinExpr()
objective += ir["objective"]["constant"]
for name, coefficient in ir["objective"]["terms"].items():
    objective += coefficient * x[name]
model.setObjective(objective, gurobipy.GRB.MAXIMIZE)

for constraint in ir["constraints"]:
    lhs = gurobipy.LinExpr()
    for name, coefficient in constraint["terms"].items():
        lhs += coefficient * x[name]
    if constraint["sense"] == "<=":
        model.addConstr(lhs <= constraint["rhs"], name=constraint["name"])
    elif constraint["sense"] == ">=":
        model.addConstr(lhs >= constraint["rhs"], name=constraint["name"])
    else:
        model.addConstr(lhs == constraint["rhs"], name=constraint["name"])

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))
projected_action = [0 for _ in ir["action_projection"]]
objective_value = None
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = {name: x[name].X for name in x}
    projected_action = [int(round(values[name])) for name in ir["action_projection"]]
    objective_value = float(model.ObjVal)
    violations = []
    for constraint in ir["constraints"]:
        activity = sum(coefficient * values[name] for name, coefficient in constraint["terms"].items())
        if constraint["sense"] == "<=":
            violation = max(0.0, activity - constraint["rhs"])
        elif constraint["sense"] == ">=":
            violation = max(0.0, constraint["rhs"] - activity)
        else:
            violation = abs(activity - constraint["rhs"])
        violations.append(violation)
    max_constraint_violation = float(max(violations, default=0.0))
    integrality_violation = float(max((abs(value - round(value)) for value in values.values()), default=0.0))
    if not math.isfinite(objective_value):
        objective_value = None

result = {
    "status": status,
    "objective": objective_value,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
