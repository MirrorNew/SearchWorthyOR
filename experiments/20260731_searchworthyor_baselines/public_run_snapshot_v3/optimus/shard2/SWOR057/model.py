import gurobipy as gp
import json
import math

model = gp.Model("SWOR057_patched")
model.Params.OutputFlag = 0

variable_names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in variable_names}

objective_terms = {
    "x_0": 1008,
    "x_1": 947,
    "x_2": 905,
    "x_3": 844,
    "x_4": 802,
    "x_5": 741
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_data = [
    ("exact_shift_count", "==", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("period_1_coverage", ">=", 1, {"x_0": 1, "x_3": 1}),
    ("period_2_coverage", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("period_3_coverage", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("policy_min_guarantee", ">=", 1, {"x_4": 1, "x_5": 1})
]

for name, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[var_name] for var_name, coef in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs <= rhs, name=name)

model.optimize()

status_labels = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_labels.get(model.Status, "STATUS_" + str(model.Status))

if model.SolCount > 0:
    raw_values = {name: float(x[name].X) for name in variable_names}
    projected_action = [int(raw_values[name] >= 0.5) for name in variable_names]
    objective = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
    violations = []
    for _, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * raw_values[var_name] for var_name, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(max(0.0, lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in raw_values.values())
else:
    objective = None
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "status_code": int(model.Status),
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
