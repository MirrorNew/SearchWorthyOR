import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR053")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

objective_coefficients = [1006, 964, 903, 842, 800, 739, 697, 636]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(8)), GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_modules")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="communication_zone_1_coverage")
model.addConstr(x[1] + x[4] + x[7] >= 1, name="communication_zone_2_coverage")
model.addConstr(x[2] + x[5] >= 1, name="communication_zone_3_coverage")
model.addConstr(x[0] - x[1] - x[4] <= 0, name="module_A_requires_B_or_E")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_of_A_B_C")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (sum(values), "<=", 3),
        (values[0] + values[3] + values[6], ">=", 1),
        (values[1] + values[4] + values[7], ">=", 1),
        (values[2] + values[5], ">=", 1),
        (values[0] - values[1] - values[4], "<=", 0),
        (values[0] + values[1] + values[2], ">=", 2)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))

    result = {
        "status": status,
        "objective": model.ObjVal,
        "projected_action": projected_action,
        "max_constraint_violation": max(violations),
        "integrality_violation": integrality_violation
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