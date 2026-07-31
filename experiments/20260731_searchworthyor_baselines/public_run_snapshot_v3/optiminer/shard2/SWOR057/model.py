import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR057_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1008, 947, 905, 844, 802, 741]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)), GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3_shifts")
model.addConstr(x[0] + x[3] >= 1, name="cover_period_1")
model.addConstr(x[1] + x[4] >= 1, name="cover_period_2")
model.addConstr(x[2] + x[5] >= 1, name="cover_period_3")
model.addConstr(x[4] + x[5] >= 1, name="require_protection_shift")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3],
        values[1] + values[4],
        values[2] + values[5],
        values[4] + values[5]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, 1 - lhs_values[1]),
        max(0.0, 1 - lhs_values[2]),
        max(0.0, 1 - lhs_values[3]),
        max(0.0, 1 - lhs_values[4])
    ]
    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": max(abs(value - round(value)) for value in values)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False))