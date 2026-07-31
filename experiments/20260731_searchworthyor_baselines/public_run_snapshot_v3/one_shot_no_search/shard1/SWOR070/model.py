import gurobipy as gp
import json
import math

model = gp.Model("SWOR070")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1001 * x[0] + 959 * x[1] + 898 * x[2] +
    856 * x[3] + 795 * x[4] + 753 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_units")
model.addConstr(3*x[0] + 4*x[1] + x[2] + 2*x[3] + 3*x[4] + 4*x[5] <= 8, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[4] + x[5] <= 1, name="terminal_backup_mutex")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(sum(values) - 3.0, 0.0),
        max(3*values[0] + 4*values[1] + values[2] + 2*values[3] + 3*values[4] + 4*values[5] - 8.0, 0.0),
        max(1.0 - values[0] - values[3], 0.0),
        max(1.0 - values[1] - values[4], 0.0),
        max(values[4] + values[5] - 1.0, 0.0)
    ]
    for value in values:
        violations.append(max(-value, value - 1.0, 0.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in values)
    objective = model.ObjVal
else:
    objective = None
    projected_action = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))