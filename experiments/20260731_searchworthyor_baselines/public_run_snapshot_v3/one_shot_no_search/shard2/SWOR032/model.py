import gurobipy as gp
import json
import math

model = gp.Model("SWOR032")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

profits = [1014, 953, 911, 850, 789, 747, 686, 644]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_segment_supply")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="back_segment_supply")

model.optimize()

status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[1] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[2] + values[4] + values[7]))
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
