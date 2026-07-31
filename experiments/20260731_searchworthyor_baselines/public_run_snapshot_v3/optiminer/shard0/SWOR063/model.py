import gurobipy as gp
from gurobipy import GRB
import json
import math

model = gp.Model("SWOR063_patched")
model.Params.OutputFlag = 0

# [VARIABLES_AND_PROJECTION]
x = [model.addVar(vtype=GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]

# [OBJECTIVE]
returns = [1009, 948, 906, 845, 803, 742]
model.setObjective(gp.quicksum(returns[i] * x[i] for i in range(6)), GRB.MAXIMIZE)

# [BASE_CONSTRAINTS]
capital = [4, 1, 2, 3, 4, 1]
risk = [2, 4, 1, 3, 5, 2]
model.addConstr(gp.quicksum(x) == 3, name="position_count")
model.addConstr(gp.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_limit")
model.addConstr(gp.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_limit")
model.addConstr(x[4] + x[5] <= 1, name="terminal_backup_exclusion")

# [POLICY_DOC_262EEDFFEB78EF62]
model.addConstr(x[0] == 0, name="policy_A_ineligible")

model.optimize()

status_names = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(v)) for v in values]
    objective = float(model.ObjVal)
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(6)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(6)) - 15.0),
        max(0.0, values[4] + values[5] - 1.0),
        abs(values[0])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
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
print(json.dumps(result, ensure_ascii=False))
