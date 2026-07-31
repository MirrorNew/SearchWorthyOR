import gurobipy as gp
import json
import math

model = gp.Model("SWOR088")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

values = [1003, 961, 900, 858, 797, 736, 694, 633]
model.setObjective(gp.quicksum(values[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(x[0] + x[3] + x[6] == 1, name="c_segment_1_exactly_one")
model.addConstr(x[1] + x[4] + x[7] == 1, name="c_segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="c_segment_3_exactly_one")
model.addConstr(x[0] + x[3] >= 1, name="c_A_or_D_at_least_one")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected_action = [int(round(v)) for v in raw]
    violations = [
        abs(raw[0] + raw[3] + raw[6] - 1),
        abs(raw[1] + raw[4] + raw[7] - 1),
        abs(raw[2] + raw[5] - 1),
        max(0.0, 1 - raw[0] - raw[3])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(v - round(v)) for v in raw)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [0, 0, 0, 0, 0, 0, 0, 0],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
