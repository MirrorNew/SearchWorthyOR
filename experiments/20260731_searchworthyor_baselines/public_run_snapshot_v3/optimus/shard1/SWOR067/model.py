import gurobipy as gp
import json
import math

model = gp.Model("SWOR067_patched")
model.Params.OutputFlag = 0

utility = [1002, 960, 899, 857, 796, 735]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.setObjective(gp.quicksum(utility[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)

rows = [
    ("required_blocks", "==", 3.0, [1, 1, 1, 1, 1, 1]),
    ("emergency_coverage", ">=", 1.0, [1, 1, 0, 0, 0, 0]),
    ("continuity_coverage", ">=", 1.0, [0, 1, 1, 0, 0, 0]),
    ("specialty_coverage", ">=", 1.0, [1, 0, 1, 0, 0, 0]),
    ("compliance_A_excludes_B", "<=", 1.0, [1, 1, 0, 0, 0, 0])
]

for name, sense, rhs, coefficients in rows:
    expression = gp.quicksum(coefficients[i] * x[i] for i in range(6))
    if sense == "==":
        model.addConstr(expression == rhs, name=name)
    elif sense == ">=":
        model.addConstr(expression >= rhs, name=name)
    else:
        model.addConstr(expression <= rhs, name=name)

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

if model.SolCount > 0:
    values = [float(variable.X) for variable in x]
    projected_action = [int(round(value)) for value in values]
    violations = []
    for name, sense, rhs, coefficients in rows:
        lhs = sum(coefficients[i] * values[i] for i in range(6))
        if sense == "==":
            violations.append(abs(lhs - rhs))
        elif sense == ">=":
            violations.append(max(0.0, rhs - lhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    max_constraint_violation = max(violations) if violations else 0.0
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal)
    if not math.isfinite(objective):
        objective = None
else:
    objective = None
    projected_action = []
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