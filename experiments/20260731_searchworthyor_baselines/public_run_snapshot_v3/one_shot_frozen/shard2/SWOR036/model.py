import gurobipy as gp
import json
import math

model = gp.Model("SWOR036")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

values = [1009, 948, 906, 845, 803, 742]
capacity = [1, 2, 3, 4, 1, 2]

model.setObjective(gp.quicksum(values[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(6)) <= 6, name="equipment_capacity")
model.addConstr(x[1] + x[4] + x[5] == 1, name="frozen_exactly_one_B_E_F")
model.addConstr(x[0] == 0, name="policy_mode_A_ineligible")

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
    vals = [var.X for var in x]
    projected_action = [int(v >= 0.5) for v in vals]
    violations = [
        max(0.0, sum(vals) - 3.0),
        max(0.0, sum(capacity[i] * vals[i] for i in range(6)) - 6.0),
        abs(vals[1] + vals[4] + vals[5] - 1.0),
        abs(vals[0])
    ]
    for v in vals:
        violations.append(max(0.0, -v, v - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in vals)
    objective = model.ObjVal
else:
    projected_action = None
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
