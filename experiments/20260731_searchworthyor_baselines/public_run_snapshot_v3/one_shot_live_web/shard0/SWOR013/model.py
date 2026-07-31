import gurobipy
import json
import math

GRB = gurobipy.GRB
model = gurobipy.Model("SWOR013_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

objective_coefficients = [1000, 958, 897, 855, 794, 752, 691, 630]
model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(8)),
    GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) == 3, name="complete_exactly_3")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="resource_subject_1_at_most_1")
model.addConstr(x[1] + x[4] + x[7] <= 1, name="resource_subject_2_at_most_1")
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_at_most_1")
model.addConstr(x[0] + x[3] >= 1, name="candidate_A_or_backup_D")
model.addConstr(x[0] - x[6] - x[7] <= 0, name="federal_30min_break_if_match_A")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    objective = float(model.ObjVal)

    checks = [
        (sum(values), "==", 3.0),
        (values[0] + values[3] + values[6], "<=", 1.0),
        (values[1] + values[4] + values[7], "<=", 1.0),
        (values[2] + values[5], "<=", 1.0),
        (values[0] + values[3], ">=", 1.0),
        (values[0] - values[6] - values[7], "<=", 0.0),
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
    projected_action = [0] * 8
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