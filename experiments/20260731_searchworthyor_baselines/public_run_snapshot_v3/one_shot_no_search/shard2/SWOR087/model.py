import gurobipy as gp
import json
import math

model = gp.Model("SWOR087")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name="x_%d" % i) for i in range(7)]

objective_coefficients = [1007, 965, 904, 843, 801, 740, 698]
capacity_coefficients = [4, 1, 2, 3, 4, 1, 2]

model.setObjective(gp.quicksum(objective_coefficients[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)
model.addConstr(gp.quicksum(x[i] for i in range(7)) <= 3, name="max_enabled_modes")
model.addConstr(gp.quicksum(capacity_coefficients[i] * x[i] for i in range(7)) <= 7, name="total_device_capacity")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, "STATUS_%d" % model.Status)

if model.SolCount > 0:
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    enabled_lhs = sum(values)
    capacity_lhs = sum(capacity_coefficients[i] * values[i] for i in range(7))
    bound_violations = [max(0.0, -value, value - 1.0) for value in values]
    max_constraint_violation = max([0.0, enabled_lhs - 3.0, capacity_lhs - 7.0] + bound_violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
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
