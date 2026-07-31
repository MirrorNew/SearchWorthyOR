import gurobipy as gp
import json
import math

model = gp.Model("SWOR061")
model.Params.OutputFlag = 0

profits = [1017, 956, 895, 853, 792, 750, 689, 647]
capacity_use = [1, 2, 3, 4, 1, 2, 3, 4]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(8)) <= 3, name="max_enabled_modes")
model.addConstr(gp.quicksum(capacity_use[i] * x[i] for i in range(8)) <= 6, name="equipment_capacity")
model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    mode_count = sum(values)
    capacity_total = sum(capacity_use[i] * values[i] for i in range(8))
    max_constraint_violation = max(0.0, mode_count - 3.0, capacity_total - 6.0)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
