import gurobipy as gp
import json
import math

model = gp.Model("SWOR022_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

benefit = [1006, 964, 903, 842, 800, 739]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="required_selection_count")
model.addConstr(x[0] + x[1] + x[3] >= 1, name="front_group_minimum")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_group_minimum")
model.addConstr(x[1] + x[4] + x[5] == 1, name="exclusive_B_E_F")
# code_region: policy_A_ineligible
model.addConstr(x[0] == 0, name="policy_A_ineligible")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [x[i].X for i in range(6)]
    projected_action = [int(v >= 0.5) for v in raw]
    violations = [
        abs(sum(raw) - 3),
        max(0.0, 1.0 - (raw[0] + raw[1] + raw[3])),
        max(0.0, 1.0 - (raw[1] + raw[2] + raw[4])),
        abs(raw[1] + raw[4] + raw[5] - 1.0),
        abs(raw[0])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(min(abs(v), abs(1.0 - v)) for v in raw)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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
