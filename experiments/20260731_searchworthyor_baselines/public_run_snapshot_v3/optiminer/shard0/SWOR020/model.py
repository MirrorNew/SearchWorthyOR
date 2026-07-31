import gurobipy as gp
import json
import math

model = gp.Model("SWOR020_patched")
model.Params.OutputFlag = 0

profits = [1003, 961, 900, 858, 797, 736, 694, 633]
capacities = [4, 1, 2, 3, 4, 1, 2, 3]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("max_enabled_units", "<=", 3, {i: 1 for i in range(8)}),
    ("grid_resource_capacity", "<=", 7, {i: capacities[i] for i in range(8)}),
    ("minimum_clean_capability", ">=", 1, {0: 1, 3: 1, 6: 1}),
    ("minimum_backup_capability", ">=", 1, {1: 1, 4: 1, 7: 1}),
    ("policy_mutual_exclusion_A_B", "<=", 1, {0: 1, 1: 1})
]

for name, sense, rhs, terms in constraint_specs:
    expression = gp.quicksum(coef * x[i] for i, coef in terms.items())
    if sense == "<=":
        model.addConstr(expression <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    else:
        model.addConstr(expression == rhs, name=name)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": None,
    "projected_action": [0 for _ in x],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for _, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * values[i] for i, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    result["objective"] = float(model.ObjVal)
    result["projected_action"] = projected_action
    result["max_constraint_violation"] = float(max(violations))
    result["integrality_violation"] = float(max(abs(value - round(value)) for value in values))

print(json.dumps(result, ensure_ascii=False))
