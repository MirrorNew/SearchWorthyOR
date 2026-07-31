import gurobipy as gp
import json
import math

model = gp.Model("SWOR024")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# Objective
benefits = [1013, 952, 910, 849, 788, 746, 685]
model.setObjective(gp.quicksum(benefits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# Base constraints
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modes")
capacity = [3, 4, 1, 2, 3, 4, 1]
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(7)) <= 8, name="equipment_capacity")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_modes_minimum")

# Policy constraint: DOC-589C6184F362B090
model.addConstr(x[5] + x[6] >= 1, name="policy_safeguard_minimum")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
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
    bound_violations = [max(0.0, -v, v - 1.0) for v in values]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
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