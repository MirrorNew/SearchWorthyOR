import gurobipy as gp
import json
import math

model = gp.Model("SWOR052_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
utilities = [1006, 964, 903, 842, 800, 739, 697, 636]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="assignment_count_exact")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="subject_1_at_most_one")
model.addConstr(x[1] + x[4] + x[7] <= 1, name="subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_at_most_one")
model.addConstr(x[6] + x[7] >= 1, name="policy_guarantee_min_one")

model.optimize()

status_names = {
    gp.GRB.LOADED: "LOADED",
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.CUTOFF: "CUTOFF",
    gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    gp.GRB.NODE_LIMIT: "NODE_LIMIT",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED",
    gp.GRB.NUMERIC: "NUMERIC",
    gp.GRB.SUBOPTIMAL: "SUBOPTIMAL"
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
        (values[6] + values[7], ">=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    violations.extend(max(0.0, -value, value - 1.0) for value in values)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    if not math.isfinite(objective):
        objective = None
else:
    objective = None
    projected_action = [0 for _ in range(8)]
    max_constraint_violation = None
    integrality_violation = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))