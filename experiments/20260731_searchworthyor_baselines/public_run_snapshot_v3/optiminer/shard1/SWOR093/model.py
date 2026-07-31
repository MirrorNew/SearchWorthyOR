import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR093_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(
    1016 * x[0] + 955 * x[1] + 894 * x[2] +
    852 * x[3] + 791 * x[4] + 749 * x[5],
    GRB.MAXIMIZE
)

model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(2*x[0] + 3*x[1] + 4*x[2] + x[3] + 2*x[4] + 3*x[5] <= 12, name="capital_limit")
model.addConstr(3*x[0] + 5*x[1] + 2*x[2] + 4*x[3] + x[4] + 3*x[5] <= 15, name="risk_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")
model.addConstr(x[0] + x[1] <= 1, name="policy_ab_mutex")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(v >= 0.5) for v in values]

    lhs_values = [
        sum(values),
        2*values[0] + 3*values[1] + 4*values[2] + values[3] + 2*values[4] + 3*values[5],
        3*values[0] + 5*values[1] + 2*values[2] + 4*values[3] + values[4] + 3*values[5],
        values[0] + values[1] + values[2],
        values[0] + values[1]
    ]
    constraint_violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 12),
        max(0.0, lhs_values[2] - 15),
        max(0.0, 2 - lhs_values[3]),
        max(0.0, lhs_values[4] - 1)
    ]
    bound_violations = [max(0.0, -v, v - 1.0) for v in values]
    max_constraint_violation = max(constraint_violations + bound_violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = None
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
