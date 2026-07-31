import gurobipy as gp
import json
import math

model = gp.Model("SWOR009")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
returns = [1018, 957, 896, 854, 793, 751, 690, 629]
capital = [3, 4, 1, 2, 3, 4, 1, 2]
risk = [2, 4, 1, 3, 5, 2, 4, 1]

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="position_count_exactly_3")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_usage_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_points_limit")
model.addConstr(x[6] + x[7] <= 1, name="packages_G_H_mutually_exclusive")

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
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    lhs_position = sum(values)
    lhs_capital = sum(capital[i] * values[i] for i in range(8))
    lhs_risk = sum(risk[i] * values[i] for i in range(8))
    lhs_mutual = values[6] + values[7]
    violations = [
        abs(lhs_position - 3),
        max(0.0, lhs_capital - 12),
        max(0.0, lhs_risk - 15),
        max(0.0, lhs_mutual - 1)
    ]
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max(violations + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = []
    max_constraint_violation = None
    integrality_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
