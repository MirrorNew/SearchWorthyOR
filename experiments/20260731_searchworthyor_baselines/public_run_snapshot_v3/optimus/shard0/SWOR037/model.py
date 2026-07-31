import gurobipy
import json
import math

model = gurobipy.Model("SWOR037")
model.Params.OutputFlag = 0

variable_names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {
    name: model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name)
    for name in variable_names
}
model.update()

objective_terms = {
    "x_0": 1013,
    "x_1": 952,
    "x_2": 910,
    "x_3": 849,
    "x_4": 788,
    "x_5": 746,
    "x_6": 685,
    "x_7": 643
}
model.setObjective(
    gurobipy.quicksum(coef * x[name] for name, coef in objective_terms.items()),
    gurobipy.GRB.MAXIMIZE
)

constraint_data = [
    ("maximum_enabled_modules", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1, "x_7": 1}),
    ("zone_1_coverage", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("zone_2_coverage", ">=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("zone_3_coverage", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("main_access_backhaul", "<=", 0, {"x_0": 1, "x_1": -1, "x_4": -1}),
    ("first_core_candidate", ">=", 1, {"x_0": 1, "x_3": 1})
]

for constraint_name, sense, rhs, terms in constraint_data:
    lhs = gurobipy.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=constraint_name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=constraint_name)
    else:
        model.addConstr(lhs == rhs, name=constraint_name)

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
action_projection = variable_names

if model.SolCount > 0:
    values = {name: x[name].X for name in variable_names}
    projected_action = [int(round(values[name])) for name in action_projection]
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None

    violations = []
    for name in variable_names:
        violations.append(max(0.0, -values[name], values[name] - 1.0))
    for constraint_name, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))

    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(
        abs(values[name] - round(values[name])) for name in variable_names
    )
else:
    objective = None
    projected_action = [0 for _ in action_projection]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))