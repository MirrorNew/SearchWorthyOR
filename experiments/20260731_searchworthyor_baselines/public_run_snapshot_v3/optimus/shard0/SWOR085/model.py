import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR085_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

contribution = [1018, 957, 896, 854, 793, 751, 690, 629]
capacity = [4, 1, 2, 3, 4, 1, 2, 3]

model.setObjective(gp.quicksum(contribution[i] * x[i] for i in range(8)), GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(8)) <= 3, name="maximum_enabled_modes")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(8)) <= 7, name="equipment_capacity_limit")
model.addConstr(x[1] + x[4] + x[7] == 1, name="frozen_group_B_E_H")
model.addConstr(x[0] + x[1] <= 1, name="regulatory_gluten_free_conflict_A_B")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "<=", 3.0),
        (sum(capacity[i] * values[i] for i in range(8)), "<=", 7.0),
        (values[1] + values[4] + values[7], "==", 1.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))

    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0 for _ in range(8)]
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
print(json.dumps(result, ensure_ascii=False))