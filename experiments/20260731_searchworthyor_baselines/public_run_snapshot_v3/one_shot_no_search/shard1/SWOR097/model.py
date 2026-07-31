import gurobipy as gp
import json
import math

model = gp.Model("SWOR097")
model.Params.OutputFlag = 0

x = [model.addVar(vtype=gp.GRB.BINARY, lb=0, ub=1, name=f"x_{i}") for i in range(8)]

utilities = [1012, 951, 909, 848, 806, 745, 684, 642]
model.setObjective(gp.quicksum(utilities[i] * x[i] for i in range(8)), gp.GRB.MAXIMIZE)

model.addConstr(gp.quicksum(x) == 3, name="exactly_three_assignments")
model.addConstr(x[0] + x[3] + x[6] <= 1, name="resource_subject_1_at_most_one")
model.addConstr(x[1] + x[4] + x[7] <= 1, name="resource_subject_2_at_most_one")
model.addConstr(x[2] + x[5] <= 1, name="resource_subject_3_at_most_one")
model.addConstr(x[0] + x[1] + x[2] >= 2, name="at_least_two_core_matches")

model.optimize()

status_names = {
    gp.GRB.OPTIMAL: "OPTIMAL",
    gp.GRB.INFEASIBLE: "INFEASIBLE",
    gp.GRB.UNBOUNDED: "UNBOUNDED",
    gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    gp.GRB.TIME_LIMIT: "TIME_LIMIT"
}
status = status_names.get(model.Status, str(model.Status))

if model.SolCount > 0:
    values = [float(v.X) for v in x]
    projected_action = [int(round(value)) for value in values]
    lhs_values = [
        sum(values),
        values[0] + values[3] + values[6],
        values[1] + values[4] + values[7],
        values[2] + values[5],
        values[0] + values[1] + values[2]
    ]
    violations = [
        abs(lhs_values[0] - 3.0),
        max(0.0, lhs_values[1] - 1.0),
        max(0.0, lhs_values[2] - 1.0),
        max(0.0, lhs_values[3] - 1.0),
        max(0.0, 2.0 - lhs_values[4])
    ]
    max_constraint_violation = max(violations)
    integrality_violation = max(abs(value - round(value)) for value in values)
    objective = float(model.ObjVal) if math.isfinite(model.ObjVal) else None
else:
    projected_action = [0] * 8
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
print(json.dumps(result, ensure_ascii=False))
