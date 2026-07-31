import gurobipy as gp
import json
import math

model = gp.Model("SWOR015")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
benefits = [1012, 951, 909, 848, 806, 745]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

constraint_data = [
    ("select_exactly_three", {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1}, "==", 3),
    ("front_segment_coverage", {0: 1, 1: 1, 3: 1}, ">=", 1),
    ("rear_segment_coverage", {1: 1, 2: 1, 4: 1}, ">=", 1),
    ("reserve_E_F_mutex", {4: 1, 5: 1}, "<=", 1),
    ("policy_A_trigger_excludes_B", {0: 1, 1: 1}, "<=", 1)
]

for name, terms, sense, rhs in constraint_data:
    expression = gp.quicksum(coef * x[index] for index, coef in terms.items())
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
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    violations = []
    for _, terms, sense, rhs in constraint_data:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
