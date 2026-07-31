import gurobipy as gp
import json
import math

model = gp.Model("SWOR005")
model.Params.OutputFlag = 0

# VARIABLES
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# OBJECTIVE
profits = [1003, 961, 900, 858, 797, 736, 694]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# CONSTRAINT_FACILITY_COUNT
model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="facility_count")

# CONSTRAINT_SERVICE_AREA_1
model.addConstr(x[0] + x[2] + x[4] + x[6] >= 1, name="service_area_1_coverage")

# CONSTRAINT_SERVICE_AREA_2
model.addConstr(x[1] + x[3] + x[5] >= 1, name="service_area_2_coverage")

# CONSTRAINT_BACKUP_MUTEX
model.addConstr(x[5] + x[6] <= 1, name="terminal_backup_mutex")

# OPTIMIZE_AND_OUTPUT
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD"
}
status = status_names.get(model.Status, str(model.Status))

if model.Status == gp.GRB.OPTIMAL:
    raw_values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in raw_values]
    lhs_values = [
        sum(raw_values),
        raw_values[0] + raw_values[2] + raw_values[4] + raw_values[6],
        raw_values[1] + raw_values[3] + raw_values[5],
        raw_values[5] + raw_values[6]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, lhs_values[3] - 1)
    ]
    bound_violations = [max(0.0, -value, value - 1) for value in raw_values]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = math.inf
    integrality_violation = math.inf
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False, allow_nan=True))