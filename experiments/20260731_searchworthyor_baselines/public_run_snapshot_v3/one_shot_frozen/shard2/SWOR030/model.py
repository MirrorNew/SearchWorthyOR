import gurobipy as gp
import json
import math

model = gp.Model("SWOR030_patched")
model.Params.OutputFlag = 0

semantic_names = ["模式A", "模式B", "模式C", "模式D", "模式E", "模式F"]
objective_coefficients = [1003, 961, 900, 858, 797, 736]
capacity_coefficients = [2, 3, 4, 1, 2, 3]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(6)]

model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x[i] for i in range(6)) <= 3, name="max_enabled_modes")
model.addConstr(
    gp.quicksum(capacity_coefficients[i] * x[i] for i in range(6)) <= 9,
    name="equipment_capacity",
)
model.addConstr(x[0] + x[1] + x[2] >= 2, name="min_core_modes")
model.addConstr(x[0] + x[1] <= 1, name="policy_ab_mutex")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [x[i].X for i in range(6)]
    projected_action = [int(round(value)) for value in raw]
    lhs_values = [
        sum(raw),
        sum(capacity_coefficients[i] * raw[i] for i in range(6)),
        raw[0] + raw[1] + raw[2],
        raw[0] + raw[1],
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 9.0),
        max(0.0, 2.0 - lhs_values[2]),
        max(0.0, lhs_values[3] - 1.0),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))