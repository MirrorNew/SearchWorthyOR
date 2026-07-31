import gurobipy as gp
import json
import math

model = gp.Model("SWOR018_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names}

objective_terms = {
    "x_0": 1005, "x_1": 963, "x_2": 902, "x_3": 841,
    "x_4": 799, "x_5": 738, "x_6": 696
}
model.setObjective(gp.quicksum(coef * x[name] for name, coef in objective_terms.items()), gp.GRB.MAXIMIZE)

constraints = [
    ("c_max_units", "<=", 3, {"x_0": 1, "x_1": 1, "x_2": 1, "x_3": 1, "x_4": 1, "x_5": 1, "x_6": 1}),
    ("c_grid_capacity", "<=", 6, {"x_0": 1, "x_1": 2, "x_2": 3, "x_3": 4, "x_4": 1, "x_5": 2, "x_6": 3}),
    ("c_clean_capability", ">=", 1, {"x_0": 1, "x_3": 1, "x_6": 1}),
    ("c_backup_capability", ">=", 1, {"x_1": 1, "x_4": 1}),
    ("c_exactly_one_core_backup_emergency", "==", 1, {"x_1": 1, "x_4": 1, "x_6": 1}),
    ("c_policy_safeguard_option", ">=", 1, {"x_5": 1, "x_6": 1})
]

for cname, sense, rhs, terms in constraints:
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
    values = {name: x[name].X for name in names}
    projected_action = [int(round(values[name])) for name in names]
    violations = []
    for cname, sense, rhs, terms in constraints:
        lhs_value = sum(coef * values[name] for name, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    objective = model.ObjVal
else:
    projected_action = [0 for _ in names]
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
