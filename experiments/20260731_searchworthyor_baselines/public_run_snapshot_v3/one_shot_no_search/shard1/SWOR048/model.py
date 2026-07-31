import gurobipy as gp
import json
import math

# [CODE:variables]
model = gp.Model("SWOR048")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

# [CODE:objective]
returns = [1014, 953, 911, 850, 789, 747, 686]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

# [CODE:position_count]
model.addConstr(gp.quicksum(x) == 3, name="position_count")

# [CODE:capital_limit]
capital = [1, 2, 3, 4, 1, 2, 3]
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_limit")

# [CODE:risk_limit]
risk = [4, 1, 3, 5, 2, 4, 1]
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_limit")

# [CODE:core_or_backup]
model.addConstr(x[0] + x[3] >= 1, name="core_or_backup")

# [CODE:solve_and_report]
model.optimize()
status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
action = [0] * 7
objective = None
max_constraint_violation = None
integrality_violation = None

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    lhs_position = sum(values)
    lhs_capital = sum(capital[i] * values[i] for i in range(7))
    lhs_risk = sum(risk[i] * values[i] for i in range(7))
    lhs_core = values[0] + values[3]
    violations = [
        abs(lhs_position - 3),
        max(0.0, lhs_capital - 12),
        max(0.0, lhs_risk - 15),
        max(0.0, 1 - lhs_core)
    ]
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(v - round(v)) for v in values))

result = {
    "status": status,
    "objective": objective,
    "projected_action": action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))
