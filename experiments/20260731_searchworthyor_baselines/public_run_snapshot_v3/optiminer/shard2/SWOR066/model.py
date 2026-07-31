import gurobipy
import json
import math

model = gurobipy.Model("SWOR066_patched")
model.Params.OutputFlag = 0

returns = [1011, 950, 908, 847, 805, 744, 683, 641]
capital = [1, 2, 3, 4, 1, 2, 3, 4]
risk = [1, 3, 5, 2, 4, 1, 3, 5]

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name="x_" + str(i)) for i in range(8)]
model.setObjective(gurobipy.quicksum(returns[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) == 3, name="exactly_three_positions")
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_limit")
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_limit")
model.addConstr(x[0] == 0, name="policy_A_ineligible")

model.optimize()

if model.Status == gurobipy.GRB.OPTIMAL:
    values = [v.X for v in x]
    projected_action = [int(round(value)) for value in values]
    position_lhs = sum(values)
    capital_lhs = sum(capital[i] * values[i] for i in range(8))
    risk_lhs = sum(risk[i] * values[i] for i in range(8))
    policy_lhs = values[0]
    violations = [abs(position_lhs - 3), max(0.0, capital_lhs - 12), max(0.0, risk_lhs - 15), abs(policy_lhs)]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    result = {"status":"OPTIMAL","objective":model.ObjVal,"projected_action":projected_action,"max_constraint_violation":max_constraint_violation,"integrality_violation":integrality_violation}
else:
    status_names = {gurobipy.GRB.INFEASIBLE:"INFEASIBLE",gurobipy.GRB.UNBOUNDED:"UNBOUNDED",gurobipy.GRB.INF_OR_UNBD:"INF_OR_UNBD"}
    result = {"status":status_names.get(model.Status, str(model.Status)),"objective":None,"projected_action":[],"max_constraint_violation":None,"integrality_violation":None}

print(json.dumps(result, ensure_ascii=False))