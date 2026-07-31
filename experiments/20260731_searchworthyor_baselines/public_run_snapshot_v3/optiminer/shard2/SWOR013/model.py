import gurobipy as gp
import json
import math

model = gp.Model("SWOR013_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
utilities = [1000, 958, 897, 855, 794, 752, 691, 630]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_specs = [
    ("select_exactly_3", "==", 3, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
    ("resource_subject_1", "<=", 1, {0: 1, 3: 1, 6: 1}),
    ("resource_subject_2", "<=", 1, {1: 1, 4: 1, 7: 1}),
    ("resource_subject_3", "<=", 1, {2: 1, 5: 1}),
    ("core_A_or_backup_D", ">=", 1, {0: 1, 3: 1}),
    ("hos_break_required_for_A", "<=", 0, {0: 1, 6: -1, 7: -1}),
    ("unique_break_slot_B_vs_G", "<=", 1, {1: 1, 6: 1}),
    ("unique_break_slot_B_vs_H", "<=", 1, {1: 1, 7: 1})
]

for name, sense, rhs, terms in constraint_specs:
    expr = gp.quicksum(coef * x[index] for index, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=name)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=name)
    else:
        model.addConstr(expr == rhs, name=name)

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
has_solution = model.SolCount > 0

if has_solution:
    raw_values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
    max_constraint_violation = 0.0
    for name, sense, rhs, terms in constraint_specs:
        lhs = sum(coef * raw_values[index] for index, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    objective = float(model.ObjVal)
else:
    projected_action = []
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))