import gurobipy
import json
import math

model = gurobipy.Model("SWOR046_patched")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

returns = [1007, 965, 904, 843, 801, 740, 698]
capital = [3, 4, 1, 2, 3, 4, 1]
risk = [3, 5, 2, 4, 1, 3, 5]

model.setObjective(gurobipy.quicksum(returns[i] * x[i] for i in range(7)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) == 3, name="position_count")
model.addConstr(gurobipy.quicksum(capital[i] * x[i] for i in range(7)) <= 12, name="capital_limit")
model.addConstr(gurobipy.quicksum(risk[i] * x[i] for i in range(7)) <= 15, name="risk_limit")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="core_minimum")
model.addConstr(x[0] + x[1] <= 1, name="compliance_A_excludes_B")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(var.X) for var in x]
    projected_action = [int(round(value)) for value in values]
    position_value = sum(values)
    capital_value = sum(capital[i] * values[i] for i in range(7))
    risk_value = sum(risk[i] * values[i] for i in range(7))
    core_value = values[0] + values[1] + values[2]
    compliance_value = values[0] + values[1]
    violations = [
        abs(position_value - 3),
        max(0.0, capital_value - 12),
        max(0.0, risk_value - 15),
        max(0.0, 2 - core_value),
        max(0.0, compliance_value - 1)
    ]
    max_constraint_violation = float(max(violations))
    integrality_violation = float(max(abs(value - round(value)) for value in values))
    objective = float(model.ObjVal)
else:
    projected_action = None
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