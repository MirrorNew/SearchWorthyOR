import gurobipy
import json
import math

model = gurobipy.Model("SWOR018_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
model.setObjective(
    1005 * x[0] + 963 * x[1] + 902 * x[2] + 841 * x[3]
    + 799 * x[4] + 738 * x[5] + 696 * x[6],
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(sum(x) <= 3, name="max_enabled_units")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] + 3*x[6] <= 6, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exactly_one_core_backup_emergency")
model.addConstr(x[5] + x[6] >= 1, name="policy_minimum_safeguard_option")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = model.ObjVal

    checks = [
        (sum(values), "<=", 3),
        (values[0] + 2*values[1] + 3*values[2] + 4*values[3] + values[4] + 2*values[5] + 3*values[6], "<=", 6),
        (values[0] + values[3] + values[6], ">=", 1),
        (values[1] + values[4], ">=", 1),
        (values[1] + values[4] + values[6], "==", 1),
        (values[5] + values[6], ">=", 1),
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

    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0, 0]
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
