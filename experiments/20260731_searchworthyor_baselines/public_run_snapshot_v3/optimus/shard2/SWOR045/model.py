import gurobipy as gp
import json

benefits = [1009, 948, 906, 845, 803, 742, 700]
constraint_rows = [
    ("select_exactly_three", {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3),
    ("cover_service_area_1", {0: 1, 2: 1, 4: 1, 6: 1}, ">=", 1),
    ("cover_service_area_2", {1: 1, 3: 1, 5: 1}, ">=", 1),
    ("core_A_or_alternative_D", {0: 1, 3: 1}, ">=", 1),
    ("compliance_A_excludes_B", {0: 1, 1: 1}, "<=", 1),
]

model = gp.Model("SWOR045")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

for name, terms, sense, rhs in constraint_rows:
    lhs = gp.quicksum(coef * x[i] for i, coef in terms.items())
    if sense == "<=":
        model.addConstr(lhs <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(lhs >= rhs, name=name)
    else:
        model.addConstr(lhs == rhs, name=name)

model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for name, terms, sense, rhs in constraint_rows:
        lhs_value = sum(coef * values[i] for i, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs_value - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs_value))
        else:
            violations.append(abs(lhs_value - rhs))
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations) if violations else 0.0,
        "integrality_violation": max(abs(value - round(value)) for value in values),
    }
else:
    result = {
        "status": status_names.get(model.Status, str(model.Status)),
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False, sort_keys=True))