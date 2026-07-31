import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR054_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

utilities = [1014, 953, 911, 850, 789, 747, 686]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="c_exactly_3")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="c_subject1_at_most_1")
model.addConstr(x[1] + x[4] <= 1, name="c_subject2_at_most_1")
model.addConstr(x[2] + x[5] <= 1, name="c_subject3_at_most_1")
model.addConstr(x[5] + x[6] <= 1, name="c_reserve_mutual_exclusion")
model.addConstr(x[5] + x[6] >= 1, name="c_policy_guarantee_at_least_1")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(value >= 0.5) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, values[0] + values[3] + values[6] - 1.0),
        max(0.0, values[1] + values[4] - 1.0),
        max(0.0, values[2] + values[5] - 1.0),
        max(0.0, values[5] + values[6] - 1.0),
        max(0.0, 1.0 - values[5] - values[6])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
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
