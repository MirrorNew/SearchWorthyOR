import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR065")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

returns = [1001, 959, 898, 856, 795, 753, 692]
capital = [4, 1, 2, 3, 4, 1, 2]
risk = [1, 3, 5, 2, 4, 1, 3]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(7)) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_occupancy_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_points_limit")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED",
    GRB.SUBOPTIMAL: "SUBOPTIMAL"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in raw]
    position_lhs = sum(raw)
    capital_lhs = sum(capital[i] * raw[i] for i in range(7))
    risk_lhs = sum(risk[i] * raw[i] for i in range(7))
    bound_violation = max([max(0.0, -value, value - 1.0) for value in raw])
    max_constraint_violation = max(
        abs(position_lhs - 3.0),
        max(0.0, capital_lhs - 12.0),
        max(0.0, risk_lhs - 15.0),
        bound_violation
    )
    integrality_violation = max(abs(value - round(value)) for value in raw)
    objective = float(model.ObjVal)
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
print(json.dumps(result, ensure_ascii=False))
