import gurobipy as gp
import json
import math

model = gp.Model("SWOR088")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefit = [1003, 961, 900, 858, 797, 736, 694, 633]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("segment_1_exactly_one", "==", 1.0, {0: 1.0, 3: 1.0, 6: 1.0}),
    ("segment_2_exactly_one", "==", 1.0, {1: 1.0, 4: 1.0, 7: 1.0}),
    ("segment_3_exactly_one", "==", 1.0, {2: 1.0, 5: 1.0}),
    ("core_A_or_backup_D", ">=", 1.0, {0: 1.0, 3: 1.0}),
    ("policy_A_ineligible", "==", 0.0, {0: 1.0})
]

for name, sense, rhs, terms in constraint_specs:
    lhs = gp.quicksum(coef * x[index] for index, coef in terms.items())
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
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = [var.X for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    violations = []
    for name, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * raw_values[index] for index, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
    objective = model.ObjVal
else:
    projected_action = [0 for _ in x]
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