import gurobipy as gp
import json
import math

model = gp.Model("SWOR070_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1001, 959, 898, 856, 795, 753]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_units")
model.addConstr(3*x[0] + 4*x[1] + x[2] + 2*x[3] + 3*x[4] + 4*x[5] <= 8, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] >= 1, name="clean_capability_min")
model.addConstr(x[1] + x[4] >= 1, name="reserve_capability_min")
model.addConstr(x[4] + x[5] <= 1, name="terminal_reserve_mutex")
model.addConstr(x[4] + x[5] >= 1, name="policy_guarantee_min")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    rows = [
        ([1, 1, 1, 1, 1, 1], "<=", 3),
        ([3, 4, 1, 2, 3, 4], "<=", 8),
        ([1, 0, 0, 1, 0, 0], ">=", 1),
        ([0, 1, 0, 0, 1, 0], ">=", 1),
        ([0, 0, 0, 0, 1, 1], "<=", 1),
        ([0, 0, 0, 0, 1, 1], ">=", 1),
    ]
    violations = []
    for coefficients, row_sense, rhs in rows:
        lhs = sum(coefficients[i] * values[i] for i in range(6))
        if row_sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        elif row_sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(abs(lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(min(abs(value), abs(1.0 - value)) for value in values)
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
