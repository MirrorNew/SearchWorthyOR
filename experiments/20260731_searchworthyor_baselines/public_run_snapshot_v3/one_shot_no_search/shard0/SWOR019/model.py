import gurobipy as gp
import json
import math

model = gp.Model("SWOR019")
model.Params.OutputFlag = 0

# REGION variables
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.update()

# REGION objective
profits = [1011, 950, 908, 847, 805, 744, 683]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# REGION max_enabled_units
model.addConstr(gp.quicksum(x[i] for i in range(7)) <= 3, name="max_enabled_units")

# REGION grid_resource_limit
resources = [4, 1, 2, 3, 4, 1, 2]
model.addConstr(gp.quicksum(resources[i] * x[i] for i in range(7)) <= 7, name="grid_resource_limit")

# REGION minimum_clean_capability
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")

# REGION minimum_backup_capability
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")

# REGION terminal_candidates_mutex
model.addConstr(x[5] + x[6] <= 1, name="terminal_candidates_mutex")

# REGION solve_and_project
model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD"
}
status = status_names.get(model.Status, str(model.Status))

if model.Status == gp.GRB.OPTIMAL:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, sum(resources[i] * values[i] for i in range(7)) - 7.0),
        max(0.0, 1.0 - (values[0] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[4])),
        max(0.0, values[5] + values[6] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))