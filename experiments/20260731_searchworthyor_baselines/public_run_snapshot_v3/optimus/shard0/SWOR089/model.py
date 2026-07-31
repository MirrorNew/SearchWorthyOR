import gurobipy as gp
import json
import math

model = gp.Model("SWOR089_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(7)]
values = [1004, 962, 901, 859, 798, 737, 695]

model.setObjective(gp.quicksum(values[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="required_selection_count")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="early_plan_minimum")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="late_plan_minimum")
model.addConstr(x[5] + x[6] >= 1, name="assurance_option_minimum")

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
    raw_action = [float(x[i].X) for i in range(7)]
    projected_action = [int(round(v)) for v in raw_action]
    objective = float(model.ObjVal)
    integrality_violation = max(abs(v - round(v)) for v in raw_action)
    violations = [
        abs(sum(raw_action) - 3.0),
        max(0.0, 1.0 - (raw_action[0] + raw_action[1] + raw_action[3] + raw_action[6])),
        max(0.0, 1.0 - (raw_action[1] + raw_action[2] + raw_action[4])),
        max(0.0, 1.0 - (raw_action[5] + raw_action[6]))
    ]
    for value in raw_action:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))