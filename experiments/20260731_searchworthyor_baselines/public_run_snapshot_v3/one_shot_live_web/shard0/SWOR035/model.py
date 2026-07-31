import gurobipy as gp
import json
import math

model = gp.Model("SWOR035")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

benefit = [1017, 956, 895, 853, 792, 750, 689]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_segment_arrival")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_segment_arrival")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
model.addConstr(x[1] == 0, name="final_unlabeled_B_forbidden")
model.addConstr(x[0] - x[5] - x[6] <= 0, name="A_requires_matching_label_service")

model.optimize()

result = {
    "status": int(model.Status),
    "objective": None,
    "projected_action": [],
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected = [int(v >= 0.5) for v in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, 1.0 - (values[0] + values[1] + values[3] + values[6])),
        max(0.0, 1.0 - (values[1] + values[2] + values[4])),
        max(0.0, 1.0 - (values[0] + values[3])),
        abs(values[1]),
        max(0.0, values[0] - values[5] - values[6])
    ]
    objective = float(model.ObjVal)
    result["objective"] = objective if math.isfinite(objective) else None
    result["projected_action"] = projected
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(min(abs(v), abs(1.0 - v)) for v in values)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))