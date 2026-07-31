import gurobipy as gp
import json
import math

model = gp.Model("SWOR053_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
benefits = [1006, 964, 903, 842, 800, 739, 697, 636]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.update()
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

constraint_data = [
    ("c_max_modules", "<=", 3, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1}),
    ("c_zone_1", ">=", 1, {0: 1, 3: 1, 6: 1}),
    ("c_zone_2", ">=", 1, {1: 1, 4: 1, 7: 1}),
    ("c_zone_3", ">=", 1, {2: 1, 5: 1}),
    ("c_access_backhaul", "<=", 0, {0: 1, 1: -1, 4: -1}),
    ("c_core_min_two", ">=", 2, {0: 1, 1: 1, 2: 1}),
    ("c_policy_safeguard", ">=", 1, {6: 1, 7: 1})
]

for cname, sense, rhs, terms in constraint_data:
    expr = gp.quicksum(coef * x[i] for i, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=cname)
    else:
        model.addConstr(expr == rhs, name=cname)

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
    raw = [float(var.X) for var in x]
    projected_action = [1 if value >= 0.5 else 0 for value in raw]
    max_constraint_violation = 0.0
    for cname, sense, rhs, terms in constraint_data:
        lhs = sum(coef * raw[i] for i, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
else:
    projected_action = []
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))