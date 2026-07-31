import gurobipy as gp
import json

model = gp.Model("SWOR032_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
benefits = [1014, 953, 911, 850, 789, 747, 686, 644]

model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="exact_package_count")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="minimum_early_stage")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="minimum_late_stage")
model.addConstr(x[6] + x[7] >= 1, name="minimum_guarantee_option")

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
    constraint_violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[1] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[2] + values[4] + values[7])),
        max(0.0, 1.0 - (values[6] + values[7]))
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
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