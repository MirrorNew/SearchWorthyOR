import gurobipy as gp
import json
import math

model = gp.Model("SWOR071_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

utilities = [1006, 964, 903, 842, 800, 739, 697]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="select_exactly_three")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_of_care")
model.addConstr(x[0] + x[2] >= 1, name="specialty_service")
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")
model.addConstr(x[0] + x[1] <= 1, name="external_A_branch_excludes_B")

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
    raw = [v.X for v in x]
    action = [int(value >= 0.5) for value in raw]
    objective = model.ObjVal
    if math.isclose(objective, round(objective), abs_tol=1e-7):
        objective = int(round(objective))

    checks = [
        (sum(action), "==", 3),
        (action[0] + action[1], ">=", 1),
        (action[1] + action[2], ">=", 1),
        (action[0] + action[2], ">=", 1),
        (action[0] + action[3], ">=", 1),
        (action[0] + action[1], "<=", 1)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0, rhs - lhs))
        else:
            violations.append(max(0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
else:
    objective = None
    action = [0, 0, 0, 0, 0, 0, 0]
    max_constraint_violation = None
    integrality_violation = None

print(json.dumps({
    "status": status,
    "objective": objective,
    "projected_action": action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}, ensure_ascii=False))
