import gurobipy as gp
import json
import math

model = gp.Model("SWOR047")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
profits = [1011, 950, 908, 847, 805, 744, 683, 641]
capacity = [2, 3, 4, 1, 2, 3, 4, 1]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="mode_count_limit")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 9, name="equipment_capacity_limit")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup_requirement")

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
    action = [int(round(v.X)) for v in x]
    objective = float(model.ObjVal)
    activities = [
        sum(action),
        sum(capacity[i] * action[i] for i in range(8)),
        action[0] + action[3]
    ]
    violations = [
        max(0.0, activities[0] - 3.0),
        max(0.0, activities[1] - 9.0),
        max(0.0, 1.0 - activities[2])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v.X - round(v.X)) for v in x)
else:
    action = [0 for _ in names]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
