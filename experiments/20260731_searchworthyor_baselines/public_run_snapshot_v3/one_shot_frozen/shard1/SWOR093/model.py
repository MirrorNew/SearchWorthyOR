import gurobipy as gp
import json
import math

model = gp.Model("SWOR093_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

returns = [1016, 955, 894, 852, 791, 749]
capital = [2, 3, 4, 1, 2, 3]
risk = [3, 5, 2, 4, 1, 3]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_cap")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_cap")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_min")
model.addConstr(x[0] + x[1] <= 1, name="evidence_ab_mutual_exclusion")

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
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    integrality_violation = max(abs(value - round(value)) for value in raw)

    position_lhs = sum(raw)
    capital_lhs = sum(capital[i] * raw[i] for i in range(6))
    risk_lhs = sum(risk[i] * raw[i] for i in range(6))
    core_lhs = raw[0] + raw[1] + raw[2]
    exclusion_lhs = raw[0] + raw[1]
    violations = [
        abs(position_lhs - 3),
        max(0.0, capital_lhs - 12),
        max(0.0, risk_lhs - 15),
        max(0.0, 2 - core_lhs),
        max(0.0, exclusion_lhs - 1)
    ]
    for value in raw:
        violations.append(max(0.0, -value, value - 1))
    max_constraint_violation = max(violations)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0]
    integrality_violation = None
    max_constraint_violation = None
    objective = None

result = {
    "status": status,
    "objective": objective,
    "projected_action": projected_action,
    "max_constraint_violation": max_constraint_violation,
    "integrality_violation": integrality_violation
}
print(json.dumps(result, ensure_ascii=False))