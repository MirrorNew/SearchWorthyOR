import gurobipy
import json

model = gurobipy.Model("SWOR001")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}")
    for i in range(6)
]

profits = [1015, 954, 912, 851, 790, 748]
capacities = [4, 1, 2, 3, 4, 1]

model.setObjective(
    gurobipy.quicksum(profits[i] * x[i] for i in range(6)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(
    gurobipy.quicksum(x[i] for i in range(6)) <= 3,
    name="max_enabled_modes",
)
model.addConstr(
    gurobipy.quicksum(capacities[i] * x[i] for i in range(6)) <= 7,
    name="equipment_capacity",
)
model.addConstr(
    x[4] + x[5] <= 1,
    name="backup_modes_mutual_exclusion",
)

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
    values = [x[i].X for i in range(6)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacities[i] * values[i] for i in range(6)) - 7.0),
        max(0.0, values[4] + values[5] - 1.0),
    ]
    max_constraint_violation = max(violations)
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
