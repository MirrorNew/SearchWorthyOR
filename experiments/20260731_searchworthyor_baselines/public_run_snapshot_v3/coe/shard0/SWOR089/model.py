import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR089_patched")
model.Params.OutputFlag = 0

profit = [1004, 962, 901, 859, 798, 737, 695]
x = model.addVars(7, vtype=GRB.BINARY, lb=0, ub=1, name="x")

model.setObjective(
    gp.quicksum(profit[i] * x[i] for i in range(7)),
    GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="frozen_exactly_3")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_stage_coverage")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_stage_coverage")
model.addConstr(x[5] + x[6] >= 1, name="policy_guarantee_option")

model.optimize()
status = "OPTIMAL" if model.Status == GRB.OPTIMAL else "STATUS_%d" % model.Status

if model.Status == GRB.OPTIMAL:
    raw = [x[i].X for i in range(7)]
    projected = [int(round(value)) for value in raw]
    lhs = [
        sum(raw),
        raw[0] + raw[1] + raw[3] + raw[6],
        raw[1] + raw[2] + raw[4],
        raw[5] + raw[6],
    ]
    violations = [
        abs(lhs[0] - 3.0),
        max(0.0, 1.0 - lhs[1]),
        max(0.0, 1.0 - lhs[2]),
        max(0.0, 1.0 - lhs[3]),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    objective = None
    projected = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}, ensure_ascii=False))
