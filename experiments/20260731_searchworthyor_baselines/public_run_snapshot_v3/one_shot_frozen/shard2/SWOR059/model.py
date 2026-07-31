import gurobipy as gp
import json
import math

model = gp.Model("SWOR059_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

objective_coefficients = [1000, 958, 897, 855, 794, 752]
model.setObjective(
    gp.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gp.GRB.MAXIMIZE,
)

model.addConstr(x[0] + x[3] == 1, name="segment_1_exactly_one")
model.addConstr(x[1] + x[4] == 1, name="segment_2_exactly_one")
model.addConstr(x[2] + x[5] == 1, name="segment_3_exactly_one")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

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
    raw_values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    objective_raw = float(model.ObjVal)
    objective = objective_raw if math.isfinite(objective_raw) else None

    checks = [
        (raw_values[0] + raw_values[3], "==", 1.0),
        (raw_values[1] + raw_values[4], "==", 1.0),
        (raw_values[2] + raw_values[5], "==", 1.0),
        (raw_values[0] + raw_values[1], "<=", 1.0),
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    objective = None
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
