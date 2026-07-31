import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR027_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
profits = [1008, 947, 905, 844, 802, 741, 699, 638]
x = {name: model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=name) for name in names}

model.setObjective(gp.quicksum(profits[i] * x[names[i]] for i in range(8)), GRB.MAXIMIZE)

constraint_data = [
    ("select_exactly_three", "==", 3, {name: 1 for name in names}),
    ("front_segment_availability", ">=", 1, {"x_0": 1, "x_1": 1, "x_3": 1, "x_6": 1}),
    ("back_segment_frozen_requirement", ">=", 1, {"x_1": 1, "x_2": 1, "x_4": 1, "x_7": 1}),
    ("core_or_backup_requirement", ">=", 1, {"x_0": 1, "x_3": 1}),
    ("evidence_ineligibility_A", "==", 0, {"x_0": 1})
]

for cname, sense, rhs, terms in constraint_data:
    expr = gp.quicksum(coef * x[var] for var, coef in terms.items())
    if sense == "<=":
        model.addConstr(expr <= rhs, name=cname)
    elif sense == ">=":
        model.addConstr(expr >= rhs, name=cname)
    else:
        model.addConstr(expr == rhs, name=cname)

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = {name: float(x[name].X) for name in names}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in names]
    max_constraint_violation = 0.0
    for cname, sense, rhs, terms in constraint_data:
        lhs = sum(coef * values[var] for var, coef in terms.items())
        if sense == "<=":
            violation = max(0.0, lhs - rhs)
        elif sense == ">=":
            violation = max(0.0, rhs - lhs)
        else:
            violation = abs(lhs - rhs)
        max_constraint_violation = max(max_constraint_violation, violation)
    integrality_violation = max(abs(values[name] - round(values[name])) for name in names)
    objective = float(model.ObjVal)
else:
    projected_action = None
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