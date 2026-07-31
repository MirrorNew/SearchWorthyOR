import gurobipy
import json
import math

model = gurobipy.Model("SWOR085_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
values = [1018, 957, 896, 854, 793, 751, 690, 629]
capacity = [4, 1, 2, 3, 4, 1, 2, 3]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gurobipy.quicksum(values[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) <= 3, name="max_enabled_modes")
model.addConstr(gurobipy.quicksum(capacity[i] * x[i] for i in range(8)) <= 7, name="equipment_capacity")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exactly_one_of_B_E_H")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, "STATUS_" + str(model.Status))
projected_action = [0] * 8
objective = None
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    raw = [var.X for var in x]
    projected_action = [int(round(value)) for value in raw]
    objective = model.ObjVal
    row_violations = [
        max(0.0, sum(raw) - 3.0),
        max(0.0, sum(capacity[i] * raw[i] for i in range(8)) - 7.0),
        abs(raw[1] + raw[4] + raw[7] - 1.0)
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in raw]
    max_constraint_violation = max(row_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))