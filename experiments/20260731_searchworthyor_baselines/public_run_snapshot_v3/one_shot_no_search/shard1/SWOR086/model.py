import gurobipy
import json
import math

model = gurobipy.Model("SWOR086")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name) for name in names}
model.update()

objective_coefficients = {
    "x_0": 1002,
    "x_1": 960,
    "x_2": 899,
    "x_3": 857,
    "x_4": 796,
    "x_5": 735,
    "x_6": 693
}
model.setObjective(
    gurobipy.quicksum(objective_coefficients[name] * x[name] for name in names),
    gurobipy.GRB.MAXIMIZE
)

constraint_specs = [
    ("exactly_three_assignments", "==", 3, {name: 1 for name in names}),
    ("resource_subject_1_at_most_one", "<=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("resource_subject_2_at_most_one", "<=", 1, {"x_1": 1, "x_4": 1}),
    ("resource_subject_3_at_most_one", "<=", 1, {"x_2": 1, "x_5": 1}),
    ("at_least_two_core_matches", ">=", 2, {"x_0": 1, "x_1": 1, "x_2": 1})
]

for constraint_name, sense, rhs, terms in constraint_specs:
    expression = gurobipy.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if sense == "==":
        model.addConstr(expression == rhs, name=constraint_name)
    elif sense == "<=":
        model.addConstr(expression <= rhs, name=constraint_name)
    else:
        model.addConstr(expression >= rhs, name=constraint_name)

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = {name: x[name].X for name in names}
    projected_action = [int(raw_values[name] >= 0.5) for name in names]
    integrality_violation = max(abs(value - round(value)) for value in raw_values.values())
    violations = []
    for constraint_name, sense, rhs, terms in constraint_specs:
        lhs = sum(coefficient * raw_values[name] for name, coefficient in terms.items())
        if sense == "==":
            violation = abs(lhs - rhs)
        elif sense == "<=":
            violation = max(0.0, lhs - rhs)
        else:
            violation = max(0.0, rhs - lhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    projected_action = []
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
