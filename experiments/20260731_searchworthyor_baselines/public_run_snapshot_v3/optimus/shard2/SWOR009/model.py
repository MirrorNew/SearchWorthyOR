import gurobipy as gp
import json
import math

model = gp.Model("SWOR009_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

returns = [1018, 957, 896, 854, 793, 751, 690, 629]
capital = [3, 4, 1, 2, 3, 4, 1, 2]
risk = [2, 4, 1, 3, 5, 2, 4, 1]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_capacity")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_capacity")
model.addConstr(x[6] + x[7] <= 1, name="base_exclusion_G_H")
model.addConstr(x[0] + x[1] <= 1, name="policy_exclusion_A_B")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    integrality_violation = max(abs(v - round(v)) for v in values)

    checks = [
        (sum(values), "==", 3.0),
        (sum(capital[i] * values[i] for i in range(8)), "<=", 12.0),
        (sum(risk[i] * values[i] for i in range(8)), "<=", 15.0),
        (values[6] + values[7], "<=", 1.0),
        (values[0] + values[1], "<=", 1.0)
    ]
    violations = []
    for lhs, sense, rhs in checks:
        if sense == "==":
            violations.append(abs(lhs - rhs))
        else:
            violations.append(max(0.0, lhs - rhs))
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    objective = float(model.ObjVal)
else:
    projected_action = None
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))