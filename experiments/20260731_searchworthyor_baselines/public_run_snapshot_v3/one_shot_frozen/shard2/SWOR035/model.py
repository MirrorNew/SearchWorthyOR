import gurobipy as gp
import json
import math

model = gp.Model("SWOR035_patched")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6"]
profits = [1017, 956, 895, 853, 792, 750, 689]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_3")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="front_arrival_min")
model.addConstr(x[1] + x[2] + x[4] >= 1, name="back_arrival_min")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_backup_D")
model.addConstr(x[0] - x[5] - x[6] <= 0, name="nutrition_support_for_A")
model.addConstr(x[1] == 0, name="exclude_final_unlabeled_B")

model.optimize()

status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
objective = None
projected_action = []
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = [var.X for var in x]
    objective = float(model.ObjVal)
    projected_action = [int(round(value)) for value in values]
    integrality_violation = max(abs(value - round(value)) for value in values)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[1] + values[3] + values[6], ">=", 1.0),
        (values[1] + values[2] + values[4], ">=", 1.0),
        (values[0] + values[3], ">=", 1.0),
        (values[0] - values[5] - values[6], "<=", 0.0),
        (values[1], "==", 0.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations)

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))