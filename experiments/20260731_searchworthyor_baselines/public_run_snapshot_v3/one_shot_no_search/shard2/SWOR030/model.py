import gurobipy
import json
import math

model = gurobipy.Model("SWOR030")
model.Params.OutputFlag = 0

x = [
    model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}")
    for i in range(6)
]

objective_coefficients = [1003, 961, 900, 858, 797, 736]
capacity_coefficients = [2, 3, 4, 1, 2, 3]

model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gurobipy.GRB.MAXIMIZE,
)
model.addConstr(gurobipy.quicksum(x[i] for i in range(6)) <= 3, name="max_enabled_modes")
model.addConstr(
    gurobipy.quicksum(capacity_coefficients[i] * x[i] for i in range(6)) <= 9,
    name="equipment_capacity",
)
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [variable.X for variable in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(capacity_coefficients[i] * values[i] for i in range(6)) - 9.0),
        max(0.0, 2.0 - sum(values[i] for i in range(3))),
    ]
    for value in values:
        violations.append(max(0.0, -value))
        violations.append(max(0.0, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    if not math.isfinite(objective):
        objective = None
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
