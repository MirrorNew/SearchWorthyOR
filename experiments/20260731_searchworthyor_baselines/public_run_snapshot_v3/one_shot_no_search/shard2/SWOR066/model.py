import gurobipy as gp
import json

model = gp.Model("SWOR066")
model.Params.OutputFlag = 0

names = ["x_0", "x_1", "x_2", "x_3", "x_4", "x_5", "x_6", "x_7"]
returns = [1011, 950, 908, 847, 805, 744, 683, 641]
capital = [1, 2, 3, 4, 1, 2, 3, 4]
risk = [1, 3, 5, 2, 4, 1, 3, 5]

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=name) for name in names]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="frozen_position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_capacity")
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
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    position_violation = abs(sum(values) - 3)
    capital_violation = max(0.0, sum(capital[i] * values[i] for i in range(8)) - 12)
    risk_violation = max(0.0, sum(risk[i] * values[i] for i in range(8)) - 15)
    max_constraint_violation = max(position_violation, capital_violation, risk_violation)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0, 0]
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
print(json.dumps(result, ensure_ascii=False))