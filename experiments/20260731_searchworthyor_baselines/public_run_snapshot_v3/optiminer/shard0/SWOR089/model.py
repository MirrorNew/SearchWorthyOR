import gurobipy as gp
import json
import math

model = gp.Model("SWOR089_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_%d" % i) for i in range(7)]

profits = [1004, 962, 901, 859, 798, 737, 695]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="frozen_selection_count")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="early_arrival_coverage")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="late_arrival_coverage")
model.addConstr(x[5] + x[6] >= 1, name="guaranteed_option_coverage")

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
    raw_values = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw_values]
    objective = model.ObjVal
    integrality_violation = max(abs(value - round(value)) for value in raw_values)

    violations = [
        abs(sum(raw_values) - 3.0),
        max(0.0, 1.0 - (raw_values[0] + raw_values[1] + raw_values[3] + raw_values[6])),
        max(0.0, 1.0 - (raw_values[1] + raw_values[2] + raw_values[4])),
        max(0.0, 1.0 - (raw_values[5] + raw_values[6]))
    ]
    max_constraint_violation = max(violations)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    objective = None
    integrality_violation = None
    max_constraint_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
