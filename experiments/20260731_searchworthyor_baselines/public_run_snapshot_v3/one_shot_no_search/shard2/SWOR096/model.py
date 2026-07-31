import gurobipy as gp
import json
import math

model = gp.Model("SWOR096")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1016,
    "x_1": 955,
    "x_2": 894,
    "x_3": 852,
    "x_4": 791,
    "x_5": 749,
    "x_6": 688,
    "x_7": 646
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_data = [
    ("enable_exactly_3_shifts", "==", 3, {name: 1 for name in names}),
    ("period_1_coverage", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("period_2_coverage", ">=", 1, {"x_1": 1, "x_4": 1, "x_7": 1}),
    ("period_3_coverage", ">=", 1, {"x_2": 1, "x_5": 1}),
    ("backup_G_H_mutual_exclusion", "<=", 1, {"x_6": 1, "x_7": 1})
]

for cname, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "==":
        model.addConstr(lhs == rhs, name=cname)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=cname)
    else:
        model.addConstr(lhs <= rhs, name=cname)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: x[name].X for name in names}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in names]
    violations = []
    for cname, sense, rhs, terms in constraint_data:
        lhs = sum(coef * values[name] for name, coef in terms.items())
        if sense == "==":
            violation = abs(lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = max(0.0, lhs - rhs)
        violations.append(violation)
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
