import gurobipy as gp
import json
import math

model = gp.Model("SWOR065_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

returns = [1001, 959, 898, 856, 795, 753, 692]
capital = [4, 1, 2, 3, 4, 1, 2]
risk = [1, 3, 5, 2, 4, 1, 3]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_limit")
model.addConstr(x[0] <= 0, name="regulatory_eligibility_A")

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
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(v)) for v in values]
    count_violation = abs(sum(values) - 3)
    capital_violation = max(0.0, sum(capital[i] * values[i] for i in range(7)) - 12)
    risk_violation = max(0.0, sum(risk[i] * values[i] for i in range(7)) - 15)
    eligibility_violation = max(0.0, values[0])
    max_constraint_violation = max(count_violation, capital_violation, risk_violation, eligibility_violation)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
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
