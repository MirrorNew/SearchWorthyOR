import gurobipy
import json
import math

model = gurobipy.Model("SWOR079")
model.Params.OutputFlag = 0
model.Params.MIPGap = 0.0

x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(6)]
model.update()

objective_coefficients = [1010, 949, 907, 846, 804, 743]
model.setObjective(
    gurobipy.quicksum(objective_coefficients[i] * x[i] for i in range(6)),
    gurobipy.GRB.MAXIMIZE,
)

model.addConstr(gurobipy.quicksum(x) <= 3, name="max_three_modules")
model.addConstr(x[0] + x[3] >= 1, name="zone_1_connectivity")
model.addConstr(x[1] + x[4] >= 1, name="zone_2_connectivity")
model.addConstr(x[2] + x[5] >= 1, name="zone_3_connectivity")
model.addConstr(-x[0] + x[1] + x[4] >= 0, name="module_a_requires_b_or_e")

model.optimize()

status_names = {
    gurobipy.GRB.OPTIMAL: "OPTIMAL",
    gurobipy.GRB.INFEASIBLE: "INFEASIBLE",
    gurobipy.GRB.UNBOUNDED: "UNBOUNDED",
    gurobipy.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gurobipy.GRB.TIME_LIMIT: "TIME_LIMIT",
    gurobipy.GRB.INTERRUPTED: "INTERRUPTED",
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    raw_values = [var.X for var in x]
    projected_action = [int(round(value)) for value in raw_values]
    objective = model.ObjVal

    lhs_values = [
        sum(raw_values),
        raw_values[0] + raw_values[3],
        raw_values[1] + raw_values[4],
        raw_values[2] + raw_values[5],
        -raw_values[0] + raw_values[1] + raw_values[4],
    ]
    violations = [
        max(0.0, lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3]),
        max(0.0, 0.0 - lhs_values[4]),
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in raw_values)
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
    "integrality_violation": integrality_violation,
}
print(json.dumps(result, ensure_ascii=False, allow_nan=False))