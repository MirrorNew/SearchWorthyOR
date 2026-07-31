import gurobipy as gp
import json
import math

benefits = [1003, 961, 900, 858, 797, 736, 694]
model = gp.Model("SWOR005_patched")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(7)
]

model.setObjective(
    gp.quicksum(benefits[i] * x[i] for i in range(7)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="cover_service_area_1")
model.addConstr(x[1] + x[3] + x[5] >= 1, name="cover_service_area_2")
model.addConstr(x[5] + x[6] <= 1, name="conflict_f_g")
model.addConstr(x[5] + x[6] >= 1, name="policy_safeguard_min")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, f"STATUS_{model.Status}")

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    lhs_values = [
        sum(values),
        values[0] + values[2] + values[4] + values[6],
        values[1] + values[3] + values[5],
        values[5] + values[6],
        values[5] + values[6],
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, lhs_values[3] - 1.0),
        max(0.0, 1.0 - lhs_values[4]),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
