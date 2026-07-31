import gurobipy as gp
import json
import math

model = gp.Model("SWOR049")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

utility = [1003, 961, 900, 858, 797, 736]
capital = [1, 2, 3, 4, 1, 2]
risk = [5, 2, 4, 1, 3, 5]

model.setObjective(gp.quicksum(utility[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_limit")
model.addConstr(x[1] + x[4] + x[5] == 1, name="core_backup_emergency_exactly_one")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [x[i].X for i in range(6)]
    projected_action = [int(round(v)) for v in values]
    position_value = sum(values)
    capital_value = sum(capital[i] * values[i] for i in range(6))
    risk_value = sum(risk[i] * values[i] for i in range(6))
    relation_value = values[1] + values[4] + values[5]
    violations = [
        abs(position_value - 3),
        max(0.0, capital_value - 12),
        max(0.0, risk_value - 15),
        abs(relation_value - 1)
    ]
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
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