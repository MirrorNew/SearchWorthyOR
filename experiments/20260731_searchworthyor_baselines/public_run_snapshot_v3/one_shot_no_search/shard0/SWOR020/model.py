import gurobipy as gp
import json
import math

model = gp.Model("SWOR020")
model.Params.OutputFlag = 0

x = {
    i: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(8)
}

profits = [1003, 961, 900, 858, 797, 736, 694, 633]
capacities = [4, 1, 2, 3, 4, 1, 2, 3]

model.setObjective(
    gp.quicksum(profits[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(
    gp.quicksum(x[i] for i in range(8)) <= 3,
    name="max_enabled_units",
)
model.addConstr(
    gp.quicksum(capacities[i] * x[i] for i in range(8)) <= 7,
    name="grid_resource_capacity",
)
model.addConstr(
    x[0] + x[3] + x[6] >= 1,
    name="minimum_clean_capability",
)
model.addConstr(
    x[1] + x[4] + x[7] >= 1,
    name="minimum_backup_capability",
)

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacities[i] * values[i] for i in range(8)) - 7.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4] + values[7])),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(
        abs(value - round(value)) for value in values
    )
    objective = model.ObjVal
else:
    projected_action = [0 for _ in range(8)]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
