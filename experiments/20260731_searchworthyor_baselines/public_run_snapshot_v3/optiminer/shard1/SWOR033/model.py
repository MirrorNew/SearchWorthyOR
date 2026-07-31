import gurobipy as gp
import json
import math

model = gp.Model("SWOR033")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# OBJECTIVE
profits = [1013, 952, 910, 849, 788, 746]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

# C_BASE_MAX_UNITS
model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_units")

# C_BASE_GRID_CAPACITY
capacity = [1, 2, 3, 4, 1, 2]
model.addConstr(gp.quicksum(capacity[i] * x[i] for i in range(6)) <= 6, name="grid_resource_capacity")

# C_BASE_CLEAN_CAPABILITY
model.addConstr(x[0] + x[3] >= 1, name="minimum_clean_capability")

# C_BASE_BACKUP_CAPABILITY
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")

# C_POLICY_A_EXCLUDES_B
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

# SOLVE_AND_REPORT
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
    values = [float(v.X) for v in x]
    projected_action = [1 if value >= 0.5 else 0 for value in values]
    checks = [
        (sum(values), "<=", 3.0),
        (sum(capacity[i] * values[i] for i in range(6)), "<=", 6.0),
        (values[0] + values[3], ">=", 1.0),
        (values[1] + values[4], ">=", 1.0),
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
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
