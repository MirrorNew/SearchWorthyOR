import gurobipy as gp
import json
import math

model = gp.Model("SWOR054")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(
    1014 * x[0] + 953 * x[1] + 911 * x[2] + 850 * x[3]
    + 789 * x[4] + 747 * x[5] + 686 * x[6],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) == 3, name="complete_exactly_3")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="resource_subject_1_at_most_1")
model.addConstr(x[1] + x[4] <= 1, name="resource_subject_2_at_most_1")
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_at_most_1")
model.addConstr(x[5] + x[6] <= 1, name="terminal_reserves_not_both")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, values[0] + values[3] + values[6] - 1),
        max(0.0, values[1] + values[4] - 1),
        max(0.0, values[2] + values[5] - 1),
        max(0.0, values[5] + values[6] - 1),
    ]
    objective = model.ObjVal
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = []
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
