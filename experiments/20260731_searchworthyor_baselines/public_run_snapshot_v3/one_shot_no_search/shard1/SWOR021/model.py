import gurobipy
import json
import math

model = gurobipy.Model("SWOR021")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
profits = [1018, 957, 896, 854, 793, 751, 690]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gurobipy.quicksum(profits[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)

model.addConstr(gurobipy.quicksum(x) <= 3, name="max_enabled_units")
model.addConstr(2*x[0] + 3*x[1] + 4*x[2] + x[3] + 2*x[4] + 3*x[5] + 4*x[6] <= 9, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_candidates")

model.optimize()

status = int(model.Status)
if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "<=", 3.0),
        (2*values[0] + 3*values[1] + 4*values[2] + values[3] + 2*values[4] + 3*values[5] + 4*values[6], "<=", 9.0),
        (values[0] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
        (values[0] + values[1] + values[2], ">=", 2.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
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