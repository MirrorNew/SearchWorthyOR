import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR015")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

benefits = [1012, 951, 909, 848, 806, 745]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(6)), GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_supply_min_1")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_supply_min_1")
model.addConstr(x[4] + x[5] <= 1, name="reserve_exclusion")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(var.X) for var in x]
    projected_action = [int(value >= 0.5) for value in raw]
    violations = [
        abs(sum(raw) - 3.0),
        max(0.0, 1.0 - (raw[0] + raw[1] + raw[3])),
        max(0.0, 1.0 - (raw[1] + raw[2] + raw[4])),
        max(0.0, raw[4] + raw[5] - 1.0)
    ]
    for value in raw:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))