import gurobipy
import json
import math

model = gurobipy.Model("SWOR032")
model.Params.OutputFlag = 0

revenues = [1014, 953, 911, 850, 789, 747, 686, 644]
x = [model.addVar(vtype=gurobipy.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

model.setObjective(gurobipy.quicksum(revenues[i] * x[i] for i in range(8)), gurobipy.GRB.MAXIMIZE)
model.addConstr(gurobipy.quicksum(x) == 3, name="c_exactly_three")
model.addConstr(x[0] + x[1] + x[3] + x[6] >= 1, name="c_front_segment")
model.addConstr(x[1] + x[2] + x[4] + x[7] >= 1, name="c_back_segment")
model.addConstr(x[6] + x[7] >= 1, name="c_external_guard_option")

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
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[1] + values[3] + values[6],
        values[1] + values[2] + values[4] + values[7],
        values[6] + values[7]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, 1.0 - lhs_values[1]),
        max(0.0, 1.0 - lhs_values[2]),
        max(0.0, 1.0 - lhs_values[3])
    ]
    objective = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
else:
    objective = None
    projected_action = []
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