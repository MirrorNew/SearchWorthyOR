import gurobipy as gp
import json
import math

model = gp.Model("SWOR017")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(8)
]

profits = [1005, 963, 902, 841, 799, 738, 696, 635]
capacity = [3, 4, 1, 2, 3, 4, 1, 2]

model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)
model.addConstr(gp.quicksum(x) <= 3, name="max_active_modes")
model.addConstr(
    gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 8,
    name="equipment_capacity",
)
model.addConstr(x[6] + x[7] <= 1, name="backup_mutual_exclusion")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, math.fsum(values) - 3.0),
        max(0.0, math.fsum(capacity[i] * values[i] for i in range(8)) - 8.0),
        max(0.0, values[6] + values[7] - 1.0),
    ]
    violations.extend(max(0.0, -value, value - 1.0) for value in values)
    max_constraint_violation = float(max(violations))
    integrality_violation = float(
        max(abs(value - round(value)) for value in values)
    )
    objective = float(model.ObjVal)
else:
    projected_action = [0] * 8
    objective = None
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