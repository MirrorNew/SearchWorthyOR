import gurobipy as gp
import json
import math

model = gp.Model("SWOR032_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

profits = [1014, 953, 911, 850, 789, 747, 686, 644]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="frozen_select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_segment_at_least_one")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_segment_at_least_one")
model.addConstr(x[6] + x[7] >= 1, name="policy保障选项_at_least_one")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4] + values[7],
        values[6] + values[7]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3])
    ]
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
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))