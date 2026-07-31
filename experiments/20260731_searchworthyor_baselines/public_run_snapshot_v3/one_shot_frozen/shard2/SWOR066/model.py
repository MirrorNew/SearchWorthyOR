import gurobipy as gp
import json

model = gp.Model("SWOR066_patched")
model.Params.OutputFlag = 0

profits = [1011, 950, 908, 847, 805, 744, 683, 641]
capital = [1, 2, 3, 4, 1, 2, 3, 4]
risk = [1, 3, 5, 2, 4, 1, 3, 5]

x = []
for i in range(8):
    upper_bound = 0 if i == 0 else 1
    x.append(model.addVar(lb=0, ub=upper_bound, vtype=gp.GRB.BINARY, name=f"x_{i}"))

model.setObjective(gp.quicksum(profits[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(8)) == 3, name="holdings_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_limit")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)

    holdings_lhs = sum(values)
    capital_lhs = sum(capital[i] * values[i] for i in range(8))
    risk_lhs = sum(risk[i] * values[i] for i in range(8))
    violations = [
        abs(holdings_lhs - 3),
        max(0.0, capital_lhs - 12),
        max(0.0, risk_lhs - 15)
    ]
    for i, value in enumerate(values):
        upper_bound = 0 if i == 0 else 1
        violations.append(max(0.0, -value, value - upper_bound))

    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
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