import gurobipy as gp
import json
import math

model = gp.Model("SWOR029")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.setObjective(
    1015 * x[0] + 954 * x[1] + 912 * x[2] + 851 * x[3]
    + 790 * x[4] + 748 * x[5] + 687 * x[6] + 645 * x[7],
    gp.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] + x[7] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_core_packages")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    constraint_violations = [
        abs(values[0] + values[3] + values[6] - 1.0),
        abs(values[1] + values[4] + values[7] - 1.0),
        abs(values[2] + values[5] - 1.0),
        max(0.0, 2.0 - values[0] - values[1] - values[2]),
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
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
