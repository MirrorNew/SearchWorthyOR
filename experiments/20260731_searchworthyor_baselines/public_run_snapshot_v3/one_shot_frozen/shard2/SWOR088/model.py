import gurobipy as gp
import json

model = gp.Model("SWOR088")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
revenues = [1003, 961, 900, 858, 797, 736, 694, 633]
model.setObjective(gp.quicksum(revenues[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(x[0] + x[3] + x[6] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] + x[7] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
model.addConstr(x[0] == 0, name="policy_11_hour_limit_A")

model.optimize()

if model.Status == gp.GRB.OPTIMAL:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    violations = [
        abs(values[0] + values[3] + values[6] - 1),
        abs(values[1] + values[4] + values[7] - 1),
        abs(values[2] + values[5] - 1),
        max(0.0, 1 - values[0] - values[3]),
        abs(values[0])
    ]
    result = {
        "status": "OPTIMAL",
        "objective": float(model.ObjVal),
        "projected_action": projected_action,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in values))
    }
else:
    result = {
        "status": str(model.Status),
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))
