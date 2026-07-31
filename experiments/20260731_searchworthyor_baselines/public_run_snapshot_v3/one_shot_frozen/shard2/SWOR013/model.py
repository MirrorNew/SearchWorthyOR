import gurobipy as gp
import json
import math

model = gp.Model("SWOR013_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

profits = [1000, 958, 897, 855, 794, 752, 691, 630]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_data = [
    ("assign_exactly_3", {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}, "==", 3.0),
    ("subject_1_at_most_1", {0: 1, 3: 1, 6: 1}, "<=", 1.0),
    ("subject_2_at_most_1", {1: 1, 4: 1, 7: 1}, "<=", 1.0),
    ("subject_3_at_most_1", {2: 1, 5: 1}, "<=", 1.0),
    ("core_A_or_D", {0: 1, 3: 1}, ">=", 1.0),
    ("hos_8h_break_required", {0: 1, 6: -1, 7: -1}, "<=", 0.0)
]

for name, terms, sense, rhs in constraint_data:
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
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
values = [float(variable.X) for variable in x]
projected_action = [int(round(value)) for value in values]
max_constraint_violation = 0.0
for name, terms, sense, rhs in constraint_data:
    lhs = sum(coefficient * values[index] for index, coefficient in terms.items())
    if sense == "<=":
        violation = max(0.0, lhs - rhs)
    elif sense == ">=":
        violation = max(0.0, rhs - lhs)
    else:
        violation = abs(lhs - rhs)
    max_constraint_violation = max(max_constraint_violation, violation)
for value in values:
    max_constraint_violation = max(max_constraint_violation, max(0.0, -value, value - 1.0))
integrality_violation = max(abs(value - round(value)) for value in values)
objective = float(model.ObjVal)
if not math.isfinite(objective):
    objective = None
result = {
    "status": status_names.get(model.Status, str(model.Status)),
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))