import gurobipy
import json
import math

profits = [1013, 952, 910, 849, 788, 746, 685]
capacity_usage = [3, 4, 1, 2, 3, 4, 1]

model = gurobipy.Model("SWOR024_patched")
model.Params.OutputFlag = 0
x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(7)
]

model.setObjective(
    gurobipy.quicksum(profits[i] * x[i] for i in range(7)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) <= 3, name="max_enabled_modes")
model.addConstr(
    gurobipy.quicksum(capacity_usage[i] * x[i] for i in range(7)) <= 8,
    name="capacity_limit",
)
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_modes")
model.addConstr(x[5] + x[6] >= 1, name="policy_minimum_guarantee")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        sum(capacity_usage[i] * values[i] for i in range(7)),
        values[0] + values[1] + values[2],
        values[5] + values[6],
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 8.0),
        max(0.0, 2.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(
        abs(value - round(value)) for value in values
    )
    objective = float(model.ObjVal)
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
