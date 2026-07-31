import gurobipy as gp
import json
import math

model = gp.Model("SWOR044")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(7)]

utilities = [1008, 947, 905, 844, 802, 741, 699]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(7)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_assignments")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="subject_1_at_most_one")
model.addConstr(x[1] + x[4] <= 1, name="subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="subject_3_at_most_one")
model.addConstr(x[1] + x[4] + x[6] == 1, name="core_backup_emergency_exactly_one")

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
    values = [x[i].X for i in range(7)]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3] + values[6],
        values[1] + values[4],
        values[2] + values[5],
        values[1] + values[4] + values[6]
    ]
    violations = [
        abs(lhs_values[0] - 3),
        max(0.0, lhs_values[1] - 1),
        max(0.0, lhs_values[2] - 1),
        max(0.0, lhs_values[3] - 1),
        abs(lhs_values[4] - 1)
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = model.ObjVal
else:
    projected_action = [0, 0, 0, 0, 0, 0, 0]
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
