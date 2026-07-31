import gurobipy as gp
import json
import math

returns = [1011, 950, 908, 847, 805, 744, 683, 641]
capital = [1, 2, 3, 4, 1, 2, 3, 4]
risk = [1, 3, 5, 2, 4, 1, 3, 5]

model = gp.Model("SWOR066_patched")
model.Params.OutputFlag = 0
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(8)]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="exactly_three_positions")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_capacity")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_point_limit")
# POLICY_PATCH_DOC_AA5B77E57E811C19
model.addConstr(x[0] <= 0, name="policy_strategy_A_ineligible")
model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
values = [x[i].X for i in range(8)]
# SOLUTION_PROJECTION
projected_action = [int(round(value)) for value in values]
position_lhs = sum(values)
capital_lhs = sum(capital[i] * values[i] for i in range(8))
risk_lhs = sum(risk[i] * values[i] for i in range(8))
constraint_violations = [
    abs(position_lhs - 3),
    max(0.0, capital_lhs - 12),
    max(0.0, risk_lhs - 15),
    max(0.0, values[0])
]
for value in values:
    constraint_violations.append(max(0.0, -value))
    constraint_violations.append(max(0.0, value - 1.0))
integrality_violation = max(abs(value - round(value)) for value in values)
result = {
    "status": status,
    "objective": float(model.ObjVal),
    "projected_action": projected_action,
    "max_constraint_violation": float(max(constraint_violations)),
    "integrality_violation": float(integrality_violation)
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
