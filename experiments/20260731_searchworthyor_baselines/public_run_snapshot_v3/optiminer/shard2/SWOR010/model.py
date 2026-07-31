import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR010_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

profits = [1000, 958, 897, 855, 794, 752]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(6)), GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_supply_min_1")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_supply_min_1")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_candidates_min_2")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

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
    values = [v.X for v in x]
    projected_action = [int(v >= 0.5) for v in values]
    violations = [
        abs(sum(values) - 3),
        max(0.0, 1 - (values[0] + values[1] + values[3])),
        max(0.0, 1 - (values[1] + values[2] + values[4])),
        max(0.0, 2 - (values[0] + values[1] + values[2])),
        max(0.0, values[0] + values[1] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal
else:
    projected_action = []
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