import gurobipy as gp
import json
import math

model = gp.Model("SWOR063_patched")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]

utilities = [1009, 948, 906, 845, 803, 742]
capital = [4, 1, 2, 3, 4, 1]
risk = [2, 4, 1, 3, 5, 2]

model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(6)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_limit")
model.addConstr(x[4] + x[5] <= 1, name="terminal_backup_exclusion")
c_eligibility_A = model.addConstr(x[0] == 0, name="eligibility_A")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT",
    gp.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [var.X for var in x]
    projected_action = [int(value >= 0.5) for value in values]
    objective = float(model.ObjVal)
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(6)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(6)) - 15.0),
        max(0.0, values[4] + values[5] - 1.0),
        abs(values[0])
    ]
    for value in values:
        violations.append(max(0.0, -value, value - 1.0))
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in values))
else:
    projected_action = [0, 0, 0, 0, 0, 0]
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
print(json.dumps(result, ensure_ascii=False, allow_nan=False))