import gurobipy as gp
import json
import math

model = gp.Model("SWOR029_patched")
model.Params.OutputFlag = 0

variable_names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {
    name: model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=name)
    for name in variable_names
}
model.update()

objective_terms = {
    "x_0": 1015,
    "x_1": 954,
    "x_2": 912,
    "x_3": 851,
    "x_4": 790,
    "x_5": 748,
    "x_6": 687,
    "x_7": 645
}
model.setObjective(
    gp.quicksum(coefficient * x[name] for name, coefficient in objective_terms.items()),
    gp.GRB.MAXIMIZE
)

rows = [
    ("segment_1_exactly_one", "==", 1.0, {"x_0": 1.0, "x_3": 1.0, "x_6": 1.0}),
    ("segment_2_exactly_one", "==", 1.0, {"x_1": 1.0, "x_4": 1.0, "x_7": 1.0}),
    ("segment_3_exactly_one", "==", 1.0, {"x_2": 1.0, "x_5": 1.0}),
    ("core_abc_at_least_two", ">=", 2.0, {"x_0": 1.0, "x_1": 1.0, "x_2": 1.0}),
    ("safeguard_GH_at_least_one", ">=", 1.0, {"x_6": 1.0, "x_7": 1.0})
]

for row_name, row_sense, rhs, terms in rows:
    expression = gp.quicksum(coefficient * x[name] for name, coefficient in terms.items())
    if row_sense == "==":
        model.addConstr(expression == rhs, name=row_name)
    elif row_sense == ">=":
        model.addConstr(expression >= rhs, name=row_name)
    else:
        model.addConstr(expression <= rhs, name=row_name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in variable_names}
    projected_action = [int(values[name] >= 0.5) for name in variable_names]
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None

    violations = []
    for row_name, row_sense, rhs, terms in rows:
        lhs = sum(coefficient * values[name] for name, coefficient in terms.items())
        if row_sense == "==":
            violation = abs(lhs - rhs)
        elif row_sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = max(0.0, lhs - rhs)
        violations.append(violation)

    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(
        abs(values[name] - round(values[name])) for name in variable_names
    )
else:
    objective = None
    projected_action = [0 for _ in variable_names]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))