import gurobipy
import json
import math

model = gurobipy.Model("SWOR093")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0.0, ub=1.0, name=f"x_{i}") for i in range(6)]
model.update()

returns = [1016, 955, 894, 852, 791, 749]
capital = [2, 3, 4, 1, 2, 3]
risk = [3, 5, 2, 4, 1, 3]

model.setObjective(gurobipy.quicksum(returns[i] * x[i] for i in range(6)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x[i] for i in range(6)) == 3, name="position_count")
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(6)) <= 12, name="capital_limit")
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(6)) <= 15, name="risk_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(x[i].X) for i in range(6)]
    projected_action = [int(values[i] >= 0.5) for i in range(6)]
    position_value = sum(values)
    capital_value = sum(capital[i] * values[i] for i in range(6))
    risk_value = sum(risk[i] * values[i] for i in range(6))
    core_value = values[0] + values[1] + values[2]
    violations = [
        abs(position_value - 3.0),
        max(0.0, capital_value - 12.0),
        max(0.0, risk_value - 15.0),
        max(0.0, 2.0 - core_value)
    ]
    violations.extend(max(0.0, -v, v - 1.0) for v in values)
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(v - round(v)) for v in values)
    objective = float(model.ObjVal)
else:
    objective = None
    projected_action = [0, 0, 0, 0, 0, 0]
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