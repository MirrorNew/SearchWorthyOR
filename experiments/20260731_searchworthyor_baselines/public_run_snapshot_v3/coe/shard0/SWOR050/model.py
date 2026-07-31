import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR050_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = model.addVars(6, vtype=GRB.BINARY, lb=0, ub=1, name="x")
profit = [1007, 965, 904, 843, 801, 740]
capacity = [2, 3, 4, 1, 2, 3]

model.setObjective(gp.quicksum(profit[i] * x[i] for i in range(6)), GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(6)) <= 3, name="B1_max_units")
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(6)) <= 9, name="B2_grid_capacity")
model.addConstr(x[0] + x[3] >= 1, name="B3_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="B4_backup_capability")
model.addConstr(x[0] + x[3] >= 1, name="B5_core_or_backup")
model.addConstr(x[0] == 0, name="P1_A_ineligible")

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

if model.Status == GRB.OPTIMAL:
    values = [x[i].X for i in range(6)]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    rows = [
        ("<=", 3.0, [1, 1, 1, 1, 1, 1]),
        ("<=", 9.0, [2, 3, 4, 1, 2, 3]),
        (">=", 1.0, [1, 0, 0, 1, 0, 0]),
        (">=", 1.0, [0, 1, 0, 0, 1, 0]),
        (">=", 1.0, [1, 0, 0, 1, 0, 0]),
        ("==", 0.0, [1, 0, 0, 0, 0, 0])
    ]
    violations = []
    for sense, rhs, coefficients in rows:
        lhs = sum(coefficients[i] * values[i] for i in range(6))
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(math.fabs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))

    max_constraint_violation = max(violations)
    integrality_violation = max(math.fabs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
