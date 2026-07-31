import gurobipy
import json
import math

model = gurobipy.Model("SWOR047_patched")
model.Params.OutputFlag = 0

contribution = [1011, 950, 908, 847, 805, 744, 683, 641]
capacity = [2, 3, 4, 1, 2, 3, 4, 1]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(8)]

model.setObjective(
    gurobipy.quicksum(contribution[i] * x[i] for i in range(8)),
    gurobipy.GRB.MAXIMIZE,
)
model.addConstr(gurobipy.quicksum(x) <= 3, name="max_enabled_modes")
model.addConstr(
    gurobipy.quicksum(capacity[i] * x[i] for i in range(8)) <= 9,
    name="equipment_capacity",
)
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")
model.addConstr(x[0] + x[1] <= 1, name="external_mutex_A_B")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity[i] * values[i] for i in range(8)) - 9.0),
        max(0.0, 1.0 - values[0] - values[3]),
        max(0.0, values[0] + values[1] - 1.0),
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in values)),
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None,
    }

print(json.dumps(result, ensure_ascii=False))