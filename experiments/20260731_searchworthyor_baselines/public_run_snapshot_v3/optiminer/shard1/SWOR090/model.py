import gurobipy as gp
import json
import math

model = gp.Model("SWOR090")
model.Params.OutputFlag = 0

# [variables]
x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

returns = [1005, 963, 902, 841, 799, 738, 696, 635]
capital = [2, 3, 4, 1, 2, 3, 4, 1]
risk = [4, 1, 3, 5, 2, 4, 1, 3]

# [objective]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

# [base_constraints]
model.addConstr(gp.quicksum(x) == 3, name="hold_exactly_3")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_cap")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_cap")
model.addConstr(x[0] + x[3] >= 1, name="core_A_or_D")

# [policy_constraint_DOC-7AAA725DBD86F11F]
model.addConstr(x[0] + x[1] <= 1, name="policy_A_B_mutex")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))
result = {
    "status": status,
    "objective": None,
    "projected_action": [0] * 8,
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [v.X for v in x]
    projected = [int(round(value)) for value in values]
    cardinality = sum(values)
    capital_used = sum(capital[i] * values[i] for i in range(8))
    risk_used = sum(risk[i] * values[i] for i in range(8))
    violations = [
        abs(cardinality - 3),
        max(0.0, capital_used - 12),
        max(0.0, risk_used - 15),
        max(0.0, 1 - values[0] - values[3]),
        max(0.0, values[0] + values[1] - 1)
    ]
    result = {
        "status": status,
        "objective": float(model.ObjVal),
        "projected_action": projected,
        "max_constraint_violation": float(max(violations)),
        "integrality_violation": float(max(abs(value - round(value)) for value in values))
    }

print(json.dumps(result, ensure_ascii=False))
