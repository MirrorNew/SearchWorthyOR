import gurobipy as gp
import json
import math

model = gp.Model("SWOR085")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

objective_coeffs = [1018, 957, 896, 854, 793, 751, 690, 629]
model.setObjective(gp.quicksum(objective_coeffs[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x[i] for i in range(8)) <= 3, name="max_three_modes")
capacity_coeffs = [4, 1, 2, 3, 4, 1, 2, 3]
model.addConstr(gp.quicksum(capacity_coeffs[i] * x[i] for i in range(8)) <= 7, name="equipment_capacity")
model.addConstr(x[1] + x[4] + x[7] == 1, name="exactly_one_of_B_E_H")
model.addConstr(x[0] + x[1] <= 1, name="gluten_free_claim_formula_compatibility")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(8)]
    projected_action = [int(round(value)) for value in values]
    objective = model.ObjVal
else:
    values = [0.0] * 8
    projected_action = [0] * 8
    objective = None

constraint_data = [
    ("<=", 3.0, [1, 1, 1, 1, 1, 1, 1, 1]),
    ("<=", 7.0, [4, 1, 2, 3, 4, 1, 2, 3]),
    ("==", 1.0, [0, 1, 0, 0, 1, 0, 0, 1]),
    ("<=", 1.0, [1, 1, 0, 0, 0, 0, 0, 0])
]
violations = []
for sense, rhs, coeffs in constraint_data:
    lhs = sum(coeffs[i] * values[i] for i in range(8))
    if sense == "<=":
        violations.append(max(0.0, lhs - rhs))
    elif sense == ">=":
        violations.append(max(0.0, rhs - lhs))
    else:
        violations.append(abs(lhs - rhs))

integrality_violation = max(abs(value - round(value)) for value in values)
result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max(violations),
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
