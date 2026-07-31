import gurobipy as gp
import json
import math

model = gp.Model("SWOR056")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
profits = [1002, 960, 899, 857, 796, 735, 693, 632]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.update()

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_segment_coverage")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_segment_coverage")
model.addConstr(x[6] + x[7] <= 1, name="terminal_backups_mutex")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    activities = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4] + values[7],
        values[6] + values[7]
    ]
    violations = [
        abs(activities[0] - 3.0),
        max(0.0, 1.0 - activities[1]),
        max(0.0, 1.0 - activities[2]),
        max(0.0, activities[3] - 1.0)
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))