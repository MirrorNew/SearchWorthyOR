import gurobipy as gp
import json
import math

model = gp.Model("SWOR011")

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]

model.setObjective(
    1016 * x[0] + 955 * x[1] + 894 * x[2] + 852 * x[3] + 791 * x[4] + 749 * x[5],
    gp.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[1] + x[2] + x[3] + x[4] + x[5] == 3, name="complete_exactly_3")
model.addConstr(x[0] + x[3] <= 1, name="subject_1_at_most_one")
model.addConstr(x[1] + x[4] <= 1, name="subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_at_most_one")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3],
        values[1] + values[4],
        values[2] + values[5],
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 1.0),
        max(0.0, lhs_values[2] - 1.0),
        max(0.0, lhs_values[3] - 1.0),
    ]
    max_constraint_violation = max(violations)
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
