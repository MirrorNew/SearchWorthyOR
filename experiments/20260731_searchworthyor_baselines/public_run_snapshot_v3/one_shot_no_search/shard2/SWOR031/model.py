import gurobipy as gp
import json
import math

model = gp.Model("SWOR031")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

benefit = [1015, 954, 912, 851, 790, 748, 687]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="c_max_modules")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="c_zone_1")
model.addConstr(x[1] + x[4] >= 1, name="c_zone_2")
model.addConstr(x[2] + x[5] >= 1, name="c_zone_3")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="c_access_backhaul")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="c_core_min_two")

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

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    raw_objective = float(model.ObjVal)
    objective = raw_objective if math.isfinite(raw_objective) else None
else:
    values = [0.0] * 7
    projected_action = [0] * 7
    objective = None

rows = [
    ("<=", 3.0, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}),
    (">=", 1.0, {0: 1, 3: 1, 6: 1}),
    (">=", 1.0, {1: 1, 4: 1}),
    (">=", 1.0, {2: 1, 5: 1}),
    ("<=", 0.0, {0: 1, 1: -1, 4: -1}),
    (">=", 2.0, {0: 1, 1: 1, 2: 1})
]

violations = []
for sense, rhs, terms in rows:
    lhs = sum(coef * values[index] for index, coef in terms.items())
    if sense == "<=":
        violations.append(max(0.0, lhs - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(abs(lhs - rhs))

max_constraint_violation = max(violations) if violations else 0.0
integrality_violation = max(abs(value - round(value)) for value in values)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))