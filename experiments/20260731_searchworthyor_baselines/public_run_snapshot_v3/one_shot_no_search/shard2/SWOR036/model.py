import gurobipy as gp
import json

model = gp.Model("SWOR036")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1009 * x[0] + 948 * x[1] + 906 * x[2]
    + 845 * x[3] + 803 * x[4] + 742 * x[5],
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) <= 3, name="max_active_modes")
model.addConstr(
    x[0] + 2 * x[1] + 3 * x[2] + 4 * x[3] + x[4] + 2 * x[5] <= 6,
    name="equipment_capacity",
)
model.addConstr(x[1] + x[4] + x[5] == 1, name="frozen_core_choice")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    active_lhs = sum(raw)
    capacity_lhs = raw[0] + 2 * raw[1] + 3 * raw[2] + 4 * raw[3] + raw[4] + 2 * raw[5]
    frozen_lhs = raw[1] + raw[4] + raw[5]
    max_constraint_violation = max(
        max(active_lhs - 3.0, 0.0),
        max(capacity_lhs - 6.0, 0.0),
        abs(frozen_lhs - 1.0),
    )
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
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
