import gurobipy as gp
import json
import math

model = gp.Model("SWOR050")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1007,
    "x_1": 965,
    "x_2": 904,
    "x_3": 843,
    "x_4": 801,
    "x_5": 740
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraint_data = [
    ("max_enabled_units", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1}),
    ("grid_resource_capacity", "<=", 9, {"x_0": 2, "x_1": 3, "x_2": 4, "x_3": 1, "x_4": 2, "x_5": 3}),
    ("minimum_clean_capability", ">=", 1, {"x_0": 1, "x_3": 1}),
    ("minimum_backup_capability", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("core_or_alternative", ">=", 1, {"x_0": 1, "x_3": 1})
]

for cname, sense, rhs, terms in constraint_data:
    lhs = gp.quicksum(coef * x[name] for name, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=cname)
    else:
        model.addConstr(lhs == rhs, name=cname)

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
    raw_values = {name: float(x[name].X) for name in names}
    projected_action = [int(round(raw_values[name])) for name in names]
    objective = float(model.ObjVal)

    violations = []
    for cname, sense, rhs, terms in constraint_data:
        lhs_value = sum(coef * raw_values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))

    for name in names:
        violations.append(max(0.0, -raw_values[name], raw_values[name] - 1.0))

    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(v), abs(v - 1.0)) for v in raw_values.values())
else:
    projected_action = [0 for _ in names]
    objective = None
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