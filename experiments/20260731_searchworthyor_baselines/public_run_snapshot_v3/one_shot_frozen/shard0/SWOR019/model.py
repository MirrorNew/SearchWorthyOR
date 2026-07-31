import gurobipy as gp
import json
import math

model = gp.Model("SWOR019_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

objective_coefficients = [1011, 950, 908, 847, 805, 744, 683]
model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) <= 3, name="c_max_units")
model.addConstr(4*x[0] + x[1] + 2*x[2] + 3*x[3] + 4*x[4] + x[5] + 2*x[6] <= 7, name="c_grid_capacity")
model.addConstr(x[0] + x[3] + x[6] >= 1, name="c_clean_min")
model.addConstr(x[1] + x[4] >= 1, name="c_backup_min")
model.addConstr(x[5] + x[6] <= 1, name="c_terminal_exclusion")
# POLICY DOC-26D924FE3EB32A96: 至少启用一个保障选项F或G。
model.addConstr(x[5] + x[6] >= 1, name="c_policy_guarantee_min")

model.optimize()

status = "OPTIMAL" if model.Status == gp.GRB.OPTIMAL else str(model.Status)
if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = model.ObjVal
else:
    values = [0.0] * 7
    projected_action = [0] * 7
    objective = None

checks = [
    (sum(values), "<=", 3),
    (4*values[0] + values[1] + 2*values[2] + 3*values[3] + 4*values[4] + values[5] + 2*values[6], "<=", 7),
    (values[0] + values[3] + values[6], ">=", 1),
    (values[1] + values[4], ">=", 1),
    (values[5] + values[6], "<=", 1),
    (values[5] + values[6], ">=", 1)
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

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
