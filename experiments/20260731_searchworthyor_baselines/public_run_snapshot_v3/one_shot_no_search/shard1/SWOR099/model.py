import gurobipy as gp
import json
import math

model = gp.Model("SWOR099")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

objective_coefficients = [1015, 954, 912, 851, 790, 748, 687, 645]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(8)),
    gp.GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three_blocks")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="early_plan_availability")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="late_plan_availability")
model.addConstr(x[1] + x[4] + x[7] == 1, name="core_backup_emergency_exclusivity")

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
    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4] + values[7],
        values[1] + values[4] + values[7]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        abs(lhs_values[3] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = [0] * 8
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
