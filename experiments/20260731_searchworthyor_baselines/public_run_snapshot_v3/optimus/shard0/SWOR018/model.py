import gurobipy as gp
import json
import math

model = gp.Model("SWOR018_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
benefit = [1005, 963, 902, 841, 799, 738, 696]
model.setObjective(gp.quicksum(benefit[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="maximum_enabled_items")
model.addConstr(x[0] + 2*x[1] + 3*x[2] + 4*x[3] + x[4] + 2*x[5] + 3*x[6] <= 6, name="grid_resource_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="minimum_clean_capability")
model.addConstr(x[1] + x[4] >= 1, name="minimum_backup_capability")
model.addConstr(x[1] + x[4] + x[6] == 1, name="exclusive_B_E_G")
model.addConstr(x[5] + x[6] >= 1, name="policy_safeguard_min_1")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))
objective = None
projected_action = [0] * 7
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    constraint_specs = [
        ([1, 1, 1, 1, 1, 1, 1], "<=", 3),
        ([1, 2, 3, 4, 1, 2, 3], "<=", 6),
        ([1, 0, 0, 1, 0, 0, 1], ">=", 1),
        ([0, 1, 0, 0, 1, 0, 0], ">=", 1),
        ([0, 1, 0, 0, 1, 0, 1], "==", 1),
        ([0, 0, 0, 0, 0, 1, 1], ">=", 1)
    ]
    violations = []
    for coefficients, relation, rhs in constraint_specs:
        activity = sum(coefficients[i] * values[i] for i in range(7))
        if relation == "<=":
            violations.append(max(0.0, activity - rhs))
        elif relation == ">=":
            violations.append(max(0.0, rhs - activity))
        else:
            violations.append(abs(activity - rhs))
    violations.extend(max(0.0, -value, value - 1.0) for value in values)
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in values))

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))