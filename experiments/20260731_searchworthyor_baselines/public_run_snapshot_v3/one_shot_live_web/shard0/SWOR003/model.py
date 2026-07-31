import gurobipy as gp
import json
import math

model = gp.Model("SWOR003")
model.Params.OutputFlag = 0

order = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
profits = {
    "x_0": 1001,
    "x_1": 959,
    "x_2": 898,
    "x_3": 856,
    "x_4": 795,
    "x_5": 753,
    "x_6": 692,
}
capacity = {
    "x_0": 1,
    "x_1": 2,
    "x_2": 3,
    "x_3": 4,
    "x_4": 1,
    "x_5": 2,
    "x_6": 3,
}

x = {name: model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in order}
model.setObjective(gp.quicksum(profits[name] * x[name] for name in order), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[name] for name in order) <= 3, name="mode_count_limit")
model.addConstr(gp.quicksum(capacity[name] * x[name] for name in order) <= 6, name="equipment_capacity")
model.addConstr(x["x_0"] + x["x_3"] >= 1, name="core_or_backup")
model.addConstr(x["x_0"] == 0, name="reg_mode_A_calorie_disclosure")

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
    values = {name: float(x[name].X) for name in order}
    projected_action = [1 if values[name] >= 0.5 else 0 for name in order]
    objective = float(model.ObjVal)

    violations = []
    violations.append(max(0.0, sum(values[name] for name in order) - 3.0))
    violations.append(max(0.0, sum(capacity[name] * values[name] for name in order) - 6.0))
    violations.append(max(0.0, 1.0 - values["x_0"] - values["x_3"]))
    violations.append(abs(values["x_0"]))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(values[name] - round(values[name])) for name in order)
else:
    projected_action = [0 for name in order]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False))
