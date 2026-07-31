import gurobipy as gp
import json
import math

model = gp.Model("SWOR041_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]
utilities = [1000, 958, 897, 855, 794, 752, 691]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="enable_exactly_three")
model.addConstr(x[0] + x[1] >= 1, name="emergency_coverage")
model.addConstr(x[1] + x[2] >= 1, name="continuity_coverage")
model.addConstr(x[0] + x[2] >= 1, name="specialty_coverage")
model.addConstr(x[5] + x[6] <= 1, name="backup_mutual_exclusion")
model.addConstr(x[0] == 0, name="policy_A_ineligible")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

constraint_data = [
    ("==", 3.0, {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0}),
    (">=", 1.0, {0: 1.0, 1: 1.0}),
    (">=", 1.0, {1: 1.0, 2: 1.0}),
    (">=", 1.0, {0: 1.0, 2: 1.0}),
    ("<=", 1.0, {5: 1.0, 6: 1.0}),
    ("==", 0.0, {0: 1.0})
]

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    violations = []
    for sense, rhs, terms in constraint_data:
        lhs = sum(coef * raw[index] for index, coef in terms.items())
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
    objective = None
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
