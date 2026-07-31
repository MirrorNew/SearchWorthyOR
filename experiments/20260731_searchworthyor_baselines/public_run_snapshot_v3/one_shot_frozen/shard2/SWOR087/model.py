import gurobipy as gp
import json
import math

model = gp.Model("SWOR087_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
profits = [1007, 965, 904, 843, 801, 740, 698]
capacity = [4, 1, 2, 3, 4, 1, 2]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 7, name="equipment_capacity")
model.addConstr(x[0] + x[1] <= 1, name="policy_mutual_exclusion_A_B")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
values = [float(v.X) for v in x] if model.SolCount > 0 else [0.0] * 7
projected_action = [int(round(v)) for v in values]
objective = float(model.ObjVal) if model.SolCount > 0 else None

constraint_violations = [
    max(0.0, sum(values) - 3.0),
    max(0.0, sum(capacity[i] * values[i] for i in range(7)) - 7.0),
    max(0.0, values[0] + values[1] - 1.0)
]
bound_violations = [max(0.0, -v, v - 1.0) for v in values]
max_constraint_violation = max(constraint_violations + bound_violations)
integrality_violation = max(abs(v - round(v)) for v in values)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))