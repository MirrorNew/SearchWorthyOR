import gurobipy as gp
import json
import math

model = gp.Model("SWOR024")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

profits = [1013, 952, 910, 849, 788, 746, 685]
capacity = [3, 4, 1, 2, 3, 4, 1]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="max_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 8, name="capacity_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")
model.addConstr(x[5] + x[6] >= 1, name="safeguard_minimum")

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
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    lhs_values = [
        sum(values),
        sum(capacity[i] * values[i] for i in range(7)),
        values[0] + values[1] + values[2],
        values[5] + values[6]
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 8.0),
        max(0.0, 2.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(math.fabs(value - round(value)) for value in values)
else:
    projected_action = []
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
