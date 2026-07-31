import gurobipy as gp
from gurobipy import GRB
import json
import math

m = gp.Model("SWOR065")
m.Params.OutputFlag = 0

x = [m.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

returns = [1001, 959, 898, 856, 795, 753, 692]
capital = [4, 1, 2, 3, 4, 1, 2]
risk = [1, 3, 5, 2, 4, 1, 3]

m.setObjective(gp.quicksum(returns[i] * x[i] for i in range(7)), GRB.MAXIMIZE)
m.addConstr(gp.quicksum(x) == 3, name="position_count")
m.addConstr(gp.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_limit")
m.addConstr(gp.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_limit")
m.addConstr(x[0] == 0, name="policy_A_ineligible")

m.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(m.Status, str(m.Status))

if m.SolCount > 0:
    values = [float(v.X) for v in x]
    projected = [int(v >= 0.5) for v in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(7)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(7)) - 15.0),
        abs(values[0]),
        max(max(0.0, -v, v - 1.0) for v in values)
    ]
    integrality_violation = max(abs(v - round(v)) for v in values)
    result = {
        "status": status,
        "objective": float(m.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(integrality_violation)
    }
else:
    result = {
        "status": status,
        "objective": None,
        "projected_action": [],
        "max_constraint_violation": None,
        "integrality_violation": None
    }

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
