import gurobipy as gp
import json
import math

model = gp.Model("SWOR012")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1015,
    "x_1": 954,
    "x_2": 912,
    "x_3": 851,
    "x_4": 790,
    "x_5": 748
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

rows = [
    ("exactly_three_service_blocks", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("emergency_coverage", ">=", 1, {"x_0": 1, "x_1": 1}),
    ("continuity_coverage", ">=", 1, {"x_1": 1, "x_2": 1}),
    ("specialty_coverage", ">=", 1, {"x_0": 1, "x_2": 1}),
    ("core_or_backup", ">=", 1, {"x_0": 1, "x_3": 1})
]

for row_name, sense, rhs, terms in rows:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=row_name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=row_name)
    else:
        model.addConstr(lhs <= rhs, name=row_name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = {name: x[name].X for name in names}
    projected_action = [int(raw_values[name] >= 0.5) for name in names]
    violations = []
    for _, sense, rhs, terms in rows:
        lhs_value = sum(coef * raw_values[name] for name, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(max(0.0, lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in raw_values.values())
    objective = model.ObjVal
else:
    projected_action = [0 for _ in names]
    objective = None
    max_constraint_violation = 3.0
    integrality_violation = 0.0

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))