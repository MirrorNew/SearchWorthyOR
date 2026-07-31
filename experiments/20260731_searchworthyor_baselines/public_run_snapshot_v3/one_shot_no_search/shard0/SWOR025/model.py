import gurobipy
import json
import math

model = gurobipy.Model("SWOR025")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(
    1006 * x[0]
    + 964 * x[1]
    + 903 * x[2]
    + 842 * x[3]
    + 800 * x[4]
    + 739 * x[5]
    + 697 * x[6],
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) == 3, name="enable_exactly_three")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[5] + x[6] <= 1, name="backup_F_G_incompatibility")

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
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4])),
        max(0.0, 1.0 - (values[2] + values[5])),
        max(0.0, values[5] + values[6] - 1.0),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))