import gurobipy as gp
import json
import math

utilities = [1002, 960, 899, 857, 796, 735, 693]

model = gp.Model("SWOR086_patched")
model.Params.OutputFlag = 0

# [REGION:variables]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(7)]

# [REGION:objective]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# [REGION:selection_count_eq]
model.addConstr(gp.quicksum(x) == 3, name="selection_count_eq")

# [REGION:subject1_at_most_one]
model.addConstr(x[0] + x[3] + x[6] <= 1, name="subject1_at_most_one")

# [REGION:subject2_at_most_one]
model.addConstr(x[1] + x[4] <= 1, name="subject2_at_most_one")

# [REGION:subject3_at_most_one]
model.addConstr(x[2] + x[5] <= 1, name="subject3_at_most_one")

# [REGION:core_min_two]
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_min_two")

# [REGION:safeguard_min_one]
model.addConstr(x[5] + x[6] >= 1, name="safeguard_min_one")

# [REGION:solve_and_report]
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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    specs = [
        ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}, "==", 3),
        ({0: 1, 3: 1, 6: 1}, "<=", 1),
        ({1: 1, 4: 1}, "<=", 1),
        ({2: 1, 5: 1}, "<=", 1),
        ({0: 1, 1: 1, 2: 1}, ">=", 2),
        ({5: 1, 6: 1}, ">=", 1)
    ]
    violations = []
    for terms, sense, rhs in specs:
        lhs = sum(coef * values[index] for index, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == "<=":
            violations.append(max(0.0, lhs - rhs))
        else:
            violations.append(max(0.0, rhs - lhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    if not math.isfinite(objective):
        objective = None
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
