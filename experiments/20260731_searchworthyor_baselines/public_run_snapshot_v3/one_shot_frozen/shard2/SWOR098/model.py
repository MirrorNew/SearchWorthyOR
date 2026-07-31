import gurobipy as gp
import json

model = gp.Model("SWOR098_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

objective_coefficients = [1009, 948, 906, 845, 803, 742, 700, 639]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)

constraint_specs = [
    ("max_enabled_units", "<=", 3, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
    ("grid_resource_capacity", "<=", 8, {0: 3, 1: 4, 2: 1, 3: 2, 4: 3, 5: 4, 6: 1, 7: 2}),
    ("minimum_clean_capability", ">=", 1, {0: 1, 3: 1, 6: 1}),
    ("minimum_backup_capability", ">=", 1, {1: 1, 4: 1, 7: 1}),
    ("minimum_core_candidates", ">=", 2, {0: 1, 1: 1, 2: 1}),
    ("regulatory_A_B_mutual_exclusion", "<=", 1, {0: 1, 1: 1}),
]

for name, sense, rhs, terms in constraint_specs:
    expression = gp.quicksum(coefficient * x[index] for index, coefficient in terms.items())
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
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in raw_values]
    violations = []
    for name, sense, rhs, terms in constraint_specs:
        lhs = sum(coefficient * raw_values[index] for index, coefficient in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in raw_values),
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))
