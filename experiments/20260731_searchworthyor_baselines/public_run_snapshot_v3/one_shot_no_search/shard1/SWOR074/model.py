import gurobipy as gp
import json
import math

model = gp.Model("SWOR074")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1014 * x[0] + 953 * x[1] + 911 * x[2] +
    850 * x[3] + 789 * x[4] + 747 * x[5],
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) <= 3, name="unit_count_limit")
model.addConstr(4*x[0] + x[1] + 2*x[2] + 3*x[3] + 4*x[4] + x[5] <= 7, name="grid_resource_limit")
model.addConstr(x[0] + x[3] >= 1, name="clean_capability_requirement")
model.addConstr(x[1] + x[4] >= 1, name="backup_capability_requirement")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_one")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        max(0.0, sum(values) - 3.0),
        max(0.0, 4*values[0] + values[1] + 2*values[2] + 3*values[3] + 4*values[4] + values[5] - 7.0),
        max(0.0, 1.0 - values[0] - values[3]),
        max(0.0, 1.0 - values[1] - values[4]),
        abs(values[1] + values[4] + values[5] - 1.0)
    ]
    integrality_violation = max(min(abs(value), abs(value - 1.0)) for value in values)
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
