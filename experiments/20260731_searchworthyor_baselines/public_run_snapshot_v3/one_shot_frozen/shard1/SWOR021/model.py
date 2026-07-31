import gurobipy as gp
import json
import math

model = gp.Model("SWOR021")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

profits = [1018, 957, 896, 854, 793, 751, 690]
capacities = [2, 3, 4, 1, 2, 3, 4]
model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="max_enabled_units")
model.addConstr(gp.quicksum(capacities[i] * x[i] for i in range(7)) <= 9, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="minimum_core_candidates")
model.addConstr(x[0] == 0, name="eligibility_A")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = model.ObjVal
    checks = [
        (sum(values), "<=", 3),
        (sum(capacities[i] * values[i] for i in range(7)), "<=", 9),
        (values[0] + values[3] + values[6], ">=", 1),
        (values[1] + values[4], ">=", 1),
        (values[0] + values[1] + values[2], ">=", 2),
        (values[0], "==", 0)
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
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
