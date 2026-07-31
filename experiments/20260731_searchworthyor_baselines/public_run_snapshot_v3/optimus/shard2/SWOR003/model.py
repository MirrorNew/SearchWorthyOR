import gurobipy as gp
import json

model = gp.Model("SWOR003_patched")
model.Params.OutputFlag = 0

contribution = [1001, 959, 898, 856, 795, 753, 692]
capacity = [1, 2, 3, 4, 1, 2, 3]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

model.setObjective(gp.quicksum(contribution[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 6, name="equipment_capacity")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup_required")
model.addConstr(x[0] == 0, name="mode_A_calorie_disclosure_availability")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        sum(capacity[i] * values[i] for i in range(7)),
        values[0] + values[3],
        values[0]
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 6.0),
        max(0.0, 1.0 - lhs_values[2]),
        abs(lhs_values[3])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))