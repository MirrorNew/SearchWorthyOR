import gurobipy
import json
import math

model = gurobipy.Model("SWOR009")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]
model.update()

returns = [1018, 957, 896, 854, 793, 751, 690, 629]
capital = [3, 4, 1, 2, 3, 4, 1, 2]
risk = [2, 4, 1, 3, 5, 2, 4, 1]

model.setObjective(gurobipy.quicksum(returns[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) == 3, name="position_count")
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(8)) <= 12, name="capital_limit")
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(8)) <= 15, name="risk_limit")
model.addConstr(x[6] + x[7] <= 1, name="backup_mutual_exclusion")
model.addConstr(x[0] + x[1] <= 1, name="policy_A_excludes_B")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED"
}
status = status_names.get(model.Status, str(model.Status))

result = {
    "status": status,
    "objective": None,
    "projected_action": None,
    "max_constraint_violation": None,
    "integrality_violation": None
}

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(8)]
    projected = [int(round(value)) for value in values]
    violations = [
        abs(sum(values) - 3.0),
        max(0.0, sum(capital[i] * values[i] for i in range(8)) - 12.0),
        max(0.0, sum(risk[i] * values[i] for i in range(8)) - 15.0),
        max(0.0, values[6] + values[7] - 1.0),
        max(0.0, values[0] + values[1] - 1.0),
        max(max(0.0, -value, value - 1.0) for value in values)
    ]
    objective = float(model.ObjVal)
    result["objective"] = objective if math.isfinite(objective) else None
    result["projected_action"] = projected
    result["max_constraint_violation"] = max(violations)
    result["integrality_violation"] = max(abs(value - round(value)) for value in values)

print(json.dumps(result, ensure_ascii=False, allow_nan=False))
