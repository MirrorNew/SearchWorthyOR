import gurobipy as gp
import json
import math

model = gp.Model("SWOR063")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

returns = [1009, 948, 906, 845, 803, 742]
capital = [4, 1, 2, 3, 4, 1]
risk = [2, 4, 1, 3, 5, 2]

model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="position_count_exactly_3")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_occupancy_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_points_limit")
model.addConstr(x[4] + x[5] <= 1, name="packages_E_F_mutually_exclusive")

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
    raw = [v.X for v in x]
    projected_action = [int(round(value)) for value in raw]
    lhs_position = sum(raw)
    lhs_capital = sum(capital[i] * raw[i] for i in range(6))
    lhs_risk = sum(risk[i] * raw[i] for i in range(6))
    lhs_exclusion = raw[4] + raw[5]
    violations = [
        abs(lhs_position - 3),
        max(0.0, lhs_capital - 12),
        max(0.0, lhs_risk - 15),
        max(0.0, lhs_exclusion - 1)
    ]
    for value in raw:
        violations.append(max(0.0, -value))
        violations.append(max(0.0, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw)
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
