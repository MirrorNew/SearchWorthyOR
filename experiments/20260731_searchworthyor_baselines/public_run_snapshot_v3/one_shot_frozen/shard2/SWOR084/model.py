import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR084")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

values = [1009, 948, 906, 845, 803, 742, 700, 639]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(8)), GRB.MAXIMIZE)

model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] + x[7] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="policy_no_A_B")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    objective = float(model.ObjVal)

    lhs_values = [
        raw[0] + raw[3] + raw[6],
        raw[1] + raw[4] + raw[7],
        raw[2] + raw[5],
        raw[0] + raw[1]
    ]
    violations = [
        abs(lhs_values[0] - 1.0),
        abs(lhs_values[1] - 1.0),
        abs(lhs_values[2] - 1.0),
        max(0.0, lhs_values[3] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
else:
    objective = None
    projected_action = [0] * 8
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
