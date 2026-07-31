import gurobipy as gp
import json
import math

model = gp.Model("SWOR047_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

benefit = [1011, 950, 908, 847, 805, 744, 683, 641]
capacity = [2, 3, 4, 1, 2, 3, 4, 1]

model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 9, name="equipment_capacity")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutual_exclusion")

model.optimize()

status_map = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_map.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    lhs_count = sum(raw)
    lhs_capacity = sum(capacity[i] * raw[i] for i in range(8))
    violations = [
        max(0.0, lhs_count - 3.0),
        max(0.0, lhs_capacity - 9.0),
        max(0.0, 1.0 - raw[0] - raw[3]),
        max(0.0, raw[0] + raw[1] - 1.0)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = model.ObjVal if math.isfinite(model.ObjVal) else None
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
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